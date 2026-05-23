# Running JimBot

## Running locally

Activate the virtual environment, then:

```sh
python bot.py
```

Logs print to stdout and are saved to `jimbot.log`.

---

## Stopping cleanly (important when in voice)

How you stop the bot matters. If you hard‑kill the process while it's in a voice channel,
Discord may keep the voice session alive server‑side for a while — and the **next `/join`
can fail with close code 4006** until that stale session expires.

JimBot includes a clean‑shutdown watcher for exactly this. `bot.py` polls for a file named
`shutdown.flag` every ~2 seconds; when it appears, the bot disconnects all voice clients
gracefully, deletes the flag, and exits. To stop it cleanly:

```sh
# Windows (PowerShell)
New-Item -ItemType File shutdown.flag

# macOS/Linux
touch shutdown.flag
```

You'll see in the log:
```
Shutdown flag detected — disconnecting voice clients cleanly...
Graceful shutdown complete — closing bot.
JimBot offline.
```

`Ctrl+C` in the foreground also triggers a graceful voice disconnect via the `finally`
block in `main()`. Prefer either of these over force‑killing the process.

> The bot clears any leftover `shutdown.flag` on startup, so a stale flag won't immediately
> shut down a fresh run.

---

## Running in the background on Windows

### Option A — no console window

```sh
start /B pythonw bot.py
```
Logs still go to `jimbot.log`. Stop it with the `shutdown.flag` method above.

### Option B — Task Scheduler

1. Task Scheduler → **Create Basic Task**
2. Trigger: **At log on** (or a schedule)
3. Action: **Start a program**
   - Program: `C:\path\to\JimBot\.venv\Scripts\python.exe`
   - Arguments: `bot.py`
   - Start in: `C:\path\to\JimBot`
4. General tab → **Run whether user is logged on or not**

---

## Running on a Linux VPS (24/7) with systemd

Create `/etc/systemd/system/jimbot.service`:

```ini
[Unit]
Description=JimBot Discord Bot
After=network.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/home/youruser/JimBot
ExecStart=/home/youruser/JimBot/.venv/bin/python bot.py
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

```sh
sudo systemctl daemon-reload
sudo systemctl enable --now jimbot
sudo systemctl status jimbot
journalctl -u jimbot -f
```

> A bare local LLM/Piper setup needs a GPU box; a CPU‑only VPS should use cloud providers
> (Claude/OpenAI + Deepgram + ElevenLabs) — see [Configuration.md](Configuration.md).

---

## Viewing logs

```sh
# Windows PowerShell
Get-Content jimbot.log -Wait -Tail 50

# Linux/macOS
tail -f jimbot.log
```

---

## Updating

```sh
git pull
pip install -r requirements.txt   # pick up dependency changes
python bot.py
```

If `requirements.txt` changed the py-cord pin (e.g. moving from the PR build to a stable
`py-cord[voice]>=2.9.0`), re‑running the install upgrades it in place.

---

## Configuration changes

There are no CLI flags — all settings live in `config.yaml` and `secrets.env`. Edit and
restart to apply. To run against an alternate config file, call
`load_config("config.dev.yaml")` from `config_loader.py`.
