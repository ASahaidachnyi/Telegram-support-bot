import os
import asyncio
import logging

from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F, Router, types
from aiogram.filters import CommandStart
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter


# =================== ENV ===================

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_CHAT_ID_STR = os.getenv("ADMIN_CHAT_ID", "").strip()

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set. Add it to .env or set it as an environment variable.")

if not ADMIN_CHAT_ID_STR:
    raise RuntimeError("ADMIN_CHAT_ID is not set. Add it to .env or set it as an environment variable.")

ADMIN_CHAT_ID = int(ADMIN_CHAT_ID_STR)


# =================== LOGGING / ROUTER ===================

logging.basicConfig(level=logging.INFO)
router = Router()


# =================== IN-MEMORY STORAGE ===================

# (message_thread_id, admin_message_id) -> user_chat_id
forward_map: dict[tuple[int, int], int] = {}

# user_id -> message_thread_id
user_topics: dict[int, int] = {}

# user_id -> asyncio.Lock
topic_locks: dict[int, asyncio.Lock] = {}


# =================== SAFE SEND ===================

async def safe_send_message(bot: Bot, chat_id: int, text: str, **kwargs) -> types.Message:
    """
    Sends a message and automatically waits if Telegram rate-limits the bot.
    """
    while True:
        try:
            return await bot.send_message(chat_id, text, **kwargs)
        except TelegramRetryAfter as e:
            logging.warning("Telegram flood control. Waiting %s seconds.", e.retry_after)
            await asyncio.sleep(e.retry_after)


# =================== COMMANDS ===================

@router.message(F.text == "/chatid")
async def show_chat_id(message: types.Message):
    """
    Shows current chat ID. Useful for getting ADMIN_CHAT_ID.
    """
    await message.answer(f"Chat ID: {message.chat.id}")


@router.message(CommandStart(), F.chat.type == "private")
async def start_private(message: types.Message):
    """
    /start in private chat.
    """
    await message.answer(
        "Вітаю! Це бот підтримки.\n"
        "Просто напишіть своє питання у цьому чаті, і адміністратор відповість вам."
    )


@router.message(CommandStart(), F.chat.id == ADMIN_CHAT_ID)
async def start_admin_group(message: types.Message):
    """
    /start in admin group.
    """
    await message.answer(
        "Це адмінська група бота підтримки.\n"
        "Група повинна бути forum-group з увімкненими Topics.\n"
        "Для кожного користувача бот створює окремий topic.\n"
        "Щоб відповісти користувачу, натисніть Reply на повідомленні бота в topic."
    )


# =================== TOPICS ===================

async def get_or_create_user_topic(bot: Bot, user: types.User) -> int:
    """
    Returns the message_thread_id for the user's topic.
    Creates a new topic if it does not exist.

    Uses per-user lock to avoid creating duplicate topics when many
    updates from the same user are processed at the same time.
    """
    user_id = user.id

    lock = topic_locks.setdefault(user_id, asyncio.Lock())
    async with lock:
        if user_id in user_topics:
            return user_topics[user_id]

        name = user.username or f"User {user_id}"
        name = str(name)[:128]

        topic = await bot.create_forum_topic(
            chat_id=ADMIN_CHAT_ID,
            name=name,
        )

        thread_id = topic.message_thread_id
        user_topics[user_id] = thread_id

        logging.info("Created topic for user_id=%s, thread_id=%s", user_id, thread_id)
        return thread_id


# =================== USER -> ADMIN GROUP ===================

@router.message(F.chat.type == "private", F.text)
async def handle_user_message(message: types.Message):
    """
    Handles any text message from a user in private chat.

    Flow:
    1. Get or create a forum topic for this user.
    2. Send the user's message to that topic.
    3. Save mapping so admin replies can be routed back to the user.
    """
    username = message.from_user.username or message.from_user.id
    thread_id = await get_or_create_user_topic(message.bot, message.from_user)

    text_for_admins = (
        f"📩 Повідомлення від @{username} (id: {message.from_user.id}):\n\n"
        f"{message.text}"
    )

    try:
        sent = await safe_send_message(
            message.bot,
            ADMIN_CHAT_ID,
            text_for_admins,
            message_thread_id=thread_id,
        )

    except TelegramBadRequest as e:
        # If an admin deleted the topic manually, Telegram returns:
        # Bad Request: message thread not found
        if "message thread not found" in str(e).lower():
            logging.warning("Topic was deleted. Recreating topic for user_id=%s", message.from_user.id)

            user_topics.pop(message.from_user.id, None)
            thread_id = await get_or_create_user_topic(message.bot, message.from_user)

            sent = await safe_send_message(
                message.bot,
                ADMIN_CHAT_ID,
                text_for_admins,
                message_thread_id=thread_id,
            )
        else:
            raise

    forward_map[(thread_id, sent.message_id)] = message.chat.id

    await message.answer(
        "Ваше повідомлення передано адміністраторам. "
        "Як тільки хтось із них відповість, ви отримаєте відповідь тут."
    )


# =================== ADMIN GROUP -> USER ===================

@router.message(F.chat.id == ADMIN_CHAT_ID, F.reply_to_message, F.text)
async def handle_admin_reply(message: types.Message):
    """
    Handles admin replies in the support group.

    Admin must reply directly to the bot's message inside the user's topic.
    The bot uses (thread_id, replied_message_id) to find the target user.
    """
    reply_to = message.reply_to_message

    if not reply_to.from_user or not reply_to.from_user.is_bot:
        return

    thread_id = message.message_thread_id
    if thread_id is None:
        await message.answer("Цей чат не є forum topic або відповідь зроблена не в topic.")
        return

    key = (thread_id, reply_to.message_id)

    if key not in forward_map:
        await message.answer(
            "Не вдалося знайти користувача для цієї відповіді. "
            "Можливо, це старе повідомлення після рестарту бота."
        )
        return

    user_chat_id = forward_map[key]

    await safe_send_message(
        message.bot,
        user_chat_id,
        f"Відповідь від підтримки:\n\n{message.text}",
    )

    await message.answer("Відповідь надіслано користувачу.")


# =================== MAIN ===================

async def main():
    bot = Bot(BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)

    # If you do not want to process messages received while the bot was offline,
    # use this instead:
    # await dp.start_polling(bot, drop_pending_updates=True)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
