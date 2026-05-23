# Discord Setup

## Step 1 — Create a Discord Application

1. Go to https://discord.com/developers/applications
2. Click **New Application**
3. Give it a name (e.g. "JimBot") and click **Create**

---

## Step 2 — Create the Bot User

1. In your application, click **Bot** in the left sidebar
2. Click **Add Bot** → **Yes, do it!**
3. Under **Token**, click **Reset Token**, then copy it
4. Paste this token into your **`secrets.env`** file as `DISCORD_TOKEN=...`
   (the file is named `secrets.env`, not `.env` — see [Configuration.md](Configuration.md))

> Never share or commit your bot token. If it leaks, reset it immediately in this panel.

---

## Step 3 — Enable Intents

Still on the **Bot** page, scroll to **Privileged Gateway Intents**:

- **Message Content Intent** — **required.** `bot.py` enables `message_content`, which is a
  privileged intent; the bot will fail to read messages/@mentions without this toggle on.
- **Server Members Intent** — *optional.* Enables reliable display‑name resolution for voice
  roasting. (The shipped bot falls back to "someone" if a member can't be resolved; enable
  this and set `intents.members = True` in `bot.py` for best results.)

The **voice state** intent the bot uses for `/join` is not privileged and needs no toggle.

Save changes.

---

## Step 4 — Set Bot Permissions

Go to **OAuth2 → URL Generator** in the sidebar.

**Scopes — check:**
- `bot`
- `applications.commands`

**Bot Permissions — check:**
- Read Messages / View Channels
- Send Messages
- Use Slash Commands
- Connect (voice)
- Speak (voice)
- Use Voice Activity

---

## Step 5 — Generate and Use the Invite URL

1. Copy the generated URL from the bottom of the OAuth2 → URL Generator page
2. Open it in your browser
3. Select your target server and click **Authorize**

---

## Step 6 — Set Up Your Server's Voice Permissions

In your Discord server:

1. Right-click the voice channel JimBot should join
2. Go to **Edit Channel → Permissions**
3. Add JimBot (or its role) with **Connect** and **Speak** permissions

---

## Verifying the Setup

Run the bot (`python bot.py`) and check the console for:
```
JimBot online as JimBot#XXXX (ID: ...)
```

Then type `/ping` in any text channel where JimBot has access. It should reply with its latency.
