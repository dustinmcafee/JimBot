<div align="center">

# JimBot

**An argumentative, mocking Discord bot powered by AI — in text *and* live voice.**

JimBot roasts people on demand in chat, and can sit in a voice channel listening to
the conversation and firing back spoken insults in real time.

[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![py-cord](https://img.shields.io/badge/py--cord-2.9%20%28PR%20%233159%29-5865F2)](https://github.com/Pycord-Development/pycord)
[![Voice](https://img.shields.io/badge/voice-DAVE%2FE2EE%20ready-brightgreen)](#voice-the-important-bit)

</div>

---

## What it does

- **Text roasting** — `/roast <target>` or just @mention JimBot and it mocks whatever you said.
- **Live voice roasting** — `/join` your voice channel and JimBot listens (speech‑to‑text), thinks (LLM), and talks back (text‑to‑speech) with a roast, all in a few seconds.
- **Rolling memory** — it remembers the last several exchanges per server, so it can call back to earlier dumb things you said.
- **Swappable AI backends** — pick your LLM, STT, and TTS providers in `config.yaml` with zero code changes. Run fully local (no cloud bills) or fully cloud (no GPU).
- **Tunable savagery** — three intensity levels, changeable live with `/savage`.
- **Consent‑first** — announces itself on join, and anyone can `/optout`.

---

## How it works

JimBot is one process with two independent paths that share a single personality module:

```
                         ┌──────────────────────────────────────┐
 Discord  ──/roast,@──▶  │ personality.generate_roast()         │
                         │   → LLMProvider.generate()           │ ──▶ text reply
                         └──────────────────────────────────────┘
                                          ▲
 Discord  ──/join──▶  VoicePipeline (one asyncio task per guild)
     │                    │
     │   incoming audio   ▼
     │   ┌───────────────────────────────────────────────────────────────┐
     │   │ UserAudioSink   per‑user 48kHz PCM buffer                      │
     │   │ SileroVAD       end‑of‑utterance detection + downsample→16kHz  │
     │   │ STTProvider     transcribe speech → text                       │
     │   │ generate_roast  LLM reply with rolling per‑guild context  ─────┘
     │   │ TTSProvider     synthesize reply → audio
     │   └─ FFmpegPCMAudio → VoiceClient.play()  → you get roasted out loud
```

See [wiki/Architecture.md](wiki/Architecture.md) for the full breakdown.

---

## Voice: the important bit

Discord enforced **DAVE (end‑to‑end voice encryption)** in March 2026, and retired the
old voice gateway. This has hard consequences for which library version works:

| py-cord version | `/join` | Hear JimBot (send) | JimBot hears you (receive) |
|---|---|---|---|
| `2.6.x` (gateway v4) | ❌ closes with **4006** | — | — |
| `2.8.0` (gateway v8) | ✅ | ✅ | ❌ broken by DAVE |
| **PR #3159** (→ 2.9.0) | ✅ | ✅ | ✅ DAVE decryption |

That's why `requirements.txt` installs py-cord from **PR #3159** with the `[voice]` extra
(which pulls in `davey`, the DAVE implementation, and `PyNaCl`). Once py-cord ships a stable
release ≥ 2.9.0 with the DAVE receive rework, you can switch to that. If `/join` ever fails
with close code **4006**, see [Troubleshooting](wiki/Troubleshooting.md#voice-connection-fails-with-4006).

---

## Requirements

- **Python 3.11+** (developed/tested on 3.14)
- **ffmpeg** (`ffmpeg` + `ffprobe`) available on `PATH` — used for all audio encode/decode
- A **Discord bot token** with the *Message Content* and *Server Members* privileged intents
- **An LLM** — a local server (LM Studio / Ollama), or a cloud key (Anthropic, OpenAI, OpenRouter, …)
- For local speech‑to‑text (default): an **NVIDIA GPU with CUDA** is strongly recommended (CPU works but is slow)

> The 472 MB of binaries in `bin/` (ffmpeg, piper, …) are **not** in the repo. See
> [Installation](wiki/Installation.md) for how to fetch them.

---

## Quick start

```sh
# 1. Clone
git clone https://github.com/dustinmcafee/JimBot.git
cd JimBot

# 2. Virtual environment  (name it .venv — note: secrets live in secrets.env, see step 5)
python -m venv .venv
.venv\Scripts\activate           # Windows
# source .venv/bin/activate      # macOS/Linux

# 3. (GPU users) install CUDA PyTorch FIRST, or pip grabs the CPU build
#    see wiki/Installation.md for the right index URL

# 4. Install dependencies (pulls py-cord PR #3159 + voice extras)
pip install -r requirements.txt

# 5. Create your secrets file  →  it MUST be named secrets.env
copy .env.example secrets.env    # Windows
# cp .env.example secrets.env    # macOS/Linux
#   then edit secrets.env and set DISCORD_TOKEN (+ any provider keys you use)

# 6. Review config.yaml (ships pointed at a local LM Studio server — change as you like)

# 7. Run
python bot.py
```

On a healthy start you'll see (values reflect your `config.yaml`):

```
JimBot online as JimBoi#7850 (ID: ...)
  LLM : openai_compat / qwen2.5-7b-instruct
  STT : faster_whisper
  TTS : piper
```

> **Secrets go in `secrets.env`, not `.env`.** `config_loader.py` loads `secrets.env`
> specifically, because `.env/` is a common virtualenv folder name. This trips people up —
> don't skip it.

---

## Configuration profiles

JimBot ships configured for a **fully local** setup (LM Studio + faster‑whisper + Piper).
Swap any layer independently. Full reference: [wiki/Configuration.md](wiki/Configuration.md).

**Local LLM via LM Studio (the shipped default — no API keys needed):**
```yaml
llm:
  provider: openai_compat
  model: qwen2.5-7b-instruct
  base_url: http://localhost:1234/v1
stt: { provider: faster_whisper, model: medium, device: cuda }
tts: { provider: piper, piper_model_path: models/piper/en_US-lessac-medium.onnx }
```

**Cloud LLM (Anthropic Claude) + local voice:**
```yaml
llm:
  provider: claude
  model: claude-haiku-4-5
  api_key_env: ANTHROPIC_API_KEY      # set this var in secrets.env
```

**Full cloud (no GPU required):**
```yaml
llm: { provider: claude, model: claude-haiku-4-5, api_key_env: ANTHROPIC_API_KEY }
stt: { provider: deepgram, api_key_env: DEEPGRAM_API_KEY }
tts: { provider: elevenlabs, elevenlabs_voice_id: <id>, api_key_env: ELEVENLABS_API_KEY }
```

---

## Command reference

| Command | What it does |
|---|---|
| `/ping` | Check the bot is alive and show latency |
| `/roast <target>` | Roast a message, person, or idea |
| `@JimBot <message>` | Mention the bot in chat to get roasted |
| `/join` | Join your current voice channel and start listening |
| `/leave` | Disconnect from voice (and clear that server's memory) |
| `/mute` | Toggle voice responses on/off (text still works) |
| `/savage <1\|2\|3>` | Set roast intensity: mild · sarcastic · brutal |
| `/optout` | Toggle yourself in/out of voice roasting |

---

## Project layout

```
bot.py              Client, cog loading, logging, clean‑shutdown watcher
config_loader.py    Loads + validates config.yaml and secrets.env
factory.py          Builds the configured LLM/STT/TTS providers
personality.py      System prompts, generate_roast(), per‑guild rolling history
test_pipeline.py    Offline end‑to‑end test of VAD→STT→LLM (no Discord needed)

commands/           text.py (/roast, /ping, @mention) · voice.py (/join, /leave, …)
providers/          base.py ABCs + one file per LLM/STT/TTS backend
voice/              sink.py (PCM capture) · vad.py (Silero) · pipeline.py (orchestration)
wiki/               Full documentation
```

---

## Testing without Discord

`test_pipeline.py` synthesizes speech with your configured TTS, converts it to the exact
48 kHz‑stereo format Discord delivers, then runs it through the real **VAD → STT → LLM**
chain — so you can validate the whole stack without joining a voice channel:

```sh
.venv\Scripts\python.exe test_pipeline.py
```

It prints each stage and exits non‑zero if any stage fails. Great for sanity‑checking after
dependency or config changes.

---

## Running 24/7

systemd unit, Windows Task Scheduler, and a **clean‑shutdown** procedure (so Discord doesn't
leave a stale voice session behind) are all documented in [wiki/Running.md](wiki/Running.md).

---

## Responsible use

- JimBot **announces itself** when it joins voice; anyone can `/optout` at any time.
- Intended for servers of **consenting friends** who are in on the joke.
- Recording or processing someone's voice **without consent may be illegal** where you live — know your local laws.
- The prompts forbid slurs and targeting protected characteristics; keep your edits in that spirit.
- Stay within [Discord's Terms of Service](https://discord.com/terms).

---

## Documentation

| Page | Contents |
|---|---|
| [Installation](wiki/Installation.md) | Python, ffmpeg, CUDA PyTorch, Piper, dependencies |
| [Discord Setup](wiki/Discord-Setup.md) | Create the app, token, intents, invite URL |
| [Configuration](wiki/Configuration.md) | Every `config.yaml` and `secrets.env` option |
| [Providers](wiki/Providers.md) | Each LLM/STT/TTS backend + how to add your own |
| [Running](wiki/Running.md) | Background/24‑7 hosting, clean shutdown, updating |
| [Personality](wiki/Personality.md) | Editing prompts and savage levels |
| [Architecture](wiki/Architecture.md) | Internals, concurrency model, latency budget |
| [Troubleshooting](wiki/Troubleshooting.md) | 4006, DAVE, CUDA, audio, and LLM issues |
