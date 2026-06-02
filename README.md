# Telegram Support Bot

A simple Telegram support bot built with **Python** and **aiogram 3**.

Users message the bot privately. The bot creates a separate **forum topic** in an admin group for each user. Admins reply inside that topic, and the bot sends the reply back to the user.

---

## Features

- Private user → admin group message forwarding
- Separate Telegram forum topic per user
- Admin replies through Telegram `Reply`
- Automatic topic recreation if an admin deletes a user's topic
- Basic Telegram flood-control handling with retry
- Environment-based configuration via `.env`

---

## How it works

1. A user opens the bot and sends a private message.
2. The bot checks if this user already has a topic in the admin group.
3. If no topic exists, the bot creates one.
4. The user's message is posted into that topic.
5. An admin opens the user's topic and replies to the bot's message using Telegram `Reply`.
6. The bot sends the admin's reply back to the user in private chat.

Important: admins must reply to the **bot's message** in the correct topic. If they just write a normal message in the topic, the bot will not know which user should receive it.

---

## Requirements

- Python 3.10+
- Telegram bot token from [@BotFather](https://t.me/BotFather)
- Telegram admin group with:
  - Topics / Forum enabled
  - Bot added to the group
  - Bot promoted to admin
  - Bot allowed to manage topics

---

## Installation

### 1. Clone the repository

```bash
git clone <your_repo_url>
cd heartbeatsupport_bot
```

Or download the project folder manually.

---

### 2. Create a virtual environment

#### Windows PowerShell

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

If PowerShell blocks activation scripts, run once:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

Then activate again:

```powershell
.\venv\Scripts\Activate.ps1
```

#### Linux / macOS

```bash
python3 -m venv venv
source venv/bin/activate
```

---

### 3. Install requirements

```bash
pip install -r requirements.txt
```

---

## Configuration

Create a `.env` file in the project root.

You can copy `.env.example`:

```bash
cp .env.example .env
```

On Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Then edit `.env`:

```env
BOT_TOKEN=your_bot_token_here
ADMIN_CHAT_ID=-1001234567890
```

### How to get `BOT_TOKEN`

1. Open Telegram.
2. Go to [@BotFather](https://t.me/BotFather).
3. Create a bot with:

```text
/newbot
```

4. Copy the token into `.env`.

### How to get `ADMIN_CHAT_ID`

1. Add the bot to your admin group.
2. Enable Topics / Forum in the group settings.
3. Promote the bot to admin and allow it to manage topics.
4. Start the bot locally.
5. Send this command in the admin group:

```text
/chatid
```

6. Copy the returned ID into `.env`.

For supergroups, the ID usually starts with `-100`.

---

## Running the bot

From the project folder:

```bash
python main.py
```

Expected console output:

```text
INFO:aiogram.dispatcher:Start polling
```

---

## Usage

### User side

1. User opens the bot.
2. User sends `/start`.
3. User sends a message.
4. Bot confirms that the message was sent to admins.

### Admin side

1. A new topic appears in the admin group for the user.
2. User messages appear in that topic.
3. Admin replies by pressing Telegram `Reply` on the bot's message.
4. Bot sends the reply to the user.
5. Bot confirms in the topic that the reply was sent.

---

## Notes

### Topic deletion

If an admin deletes a user's topic and the same user messages the bot again, the bot will automatically create a new topic.

### Bot restart

This bot currently stores routing data in memory.

That means after a bot restart:

- Existing Telegram topics remain in the group.
- New user messages will still be routed.
- Replies to old messages that were sent before restart may not work because the in-memory `forward_map` is reset.

For production usage, replace the in-memory dictionaries with a database such as SQLite or PostgreSQL.

### Offline backlog

By default, when the bot starts, it processes pending updates that arrived while it was offline.

If you do **not** want that behavior, change this line in `main.py`:

```python
await dp.start_polling(bot)
```

to:

```python
await dp.start_polling(bot, drop_pending_updates=True)
```

---

## Security notes

- Do not hardcode your bot token in `main.py`.
- Do not commit `.env` to GitHub.
- If your token is exposed, revoke it in BotFather immediately.
- Only trusted people should be in the admin group.
- Admins should not open suspicious links/files sent by users.

---

## Project structure

```text
heartbeatsupport_bot/
├── main.py
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

## License

MIT
