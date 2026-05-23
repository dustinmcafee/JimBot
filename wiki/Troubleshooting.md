# Troubleshooting

Jump to: [start‑up](#bot-wont-start) · [slash commands](#slash-commands-dont-appear) ·
[**4006 / voice connect**](#voice-connection-fails-with-4006) ·
[**can't hear me / DAVE**](#jimbot-joins-and-talks-but-cant-hear-me) ·
[GPU](#gpu--cuda-issues) · [no audio out](#no-audio-in-voice-channel) · [LLM](#llm-errors)

---

## Bot won't start

**`ValueError: DISCORD_TOKEN is not set`**
- The secrets file must be named **`secrets.env`** (not `.env`). Create it with
  `copy .env.example secrets.env` and put `DISCORD_TOKEN=...` inside.
- Make sure you activated the venv before running.

**`ModuleNotFoundError`**
- Activate the venv: `.venv\Scripts\activate` (Windows) / `source .venv/bin/activate`.
- `pip install -r requirements.txt`.

**`discord.errors.LoginFailure: Improper token`**
- The token is wrong or was reset. Discord Developer Portal → Bot → Reset Token → update
  `secrets.env`.

**`MissingVoiceDependenciesError: davey is required for voice support`**
- py-cord 2.8+ needs the voice extra. Reinstall with the extra:
  `pip install "py-cord[voice] @ git+https://github.com/Pycord-Development/pycord@refs/pull/3159/head"`
  (this is what `requirements.txt` pins).

---

## Slash commands don't appear

py-cord syncs commands on `on_ready`; **global** commands can take up to an hour to
propagate. For instant sync during development, scope them to your guild:

```python
@discord.slash_command(name="roast", guild_ids=[YOUR_GUILD_ID])
```

Also confirm the invite URL included the `applications.commands` scope.

---

## Voice connection fails with 4006

`Voice connection failed (code 4006)` / `WebSocket closed with 4006`.

**By far the most common cause is an outdated py-cord.** Discord retired the old voice
gateway (v4); py-cord ≤ 2.6 still requests it and gets rejected with 4006 on *every*
`/join`, deterministically. Fix: install the pinned build.

```sh
python -c "import discord; print(discord.__version__)"   # must be 2.7+ (we pin a 2.9 PR build)
pip install -r requirements.txt
```

**If you're already on 2.7+ and still see 4006,** it's a genuine stale server‑side voice
session — usually from hard‑killing the process while it was in voice. To avoid creating
these, always stop the bot cleanly (see [Running → Stopping cleanly](Running.md#stopping-cleanly-important-when-in-voice)).
To clear an existing one:

- Wait a few minutes for Discord to expire it, then `/join` again, **or**
- Use the built‑in `/fix4006` command, **or**
- As a last resort, kick the bot from the server and re‑invite it.

The `/join` handler also auto‑retries once on 4006 (sends a gateway leave, waits for
confirmation, reconnects), which clears most transient cases on its own.

---

## JimBot joins and talks, but can't hear me

I.e. `/join` works, you hear the greeting, but it never responds to speech.

**Most likely: voice *reception* isn't supported by your py-cord build.** Since Discord
enforced DAVE (E2EE) in March 2026, incoming audio is encrypted. Only py-cord **PR #3159**
(→ 2.9.0) decrypts it. Released versions log a warning like *"Voice reception is currently
broken due to Discord's DAVE protocol."* Reinstall from `requirements.txt`, which pins the
PR build, and confirm `davey` is installed (`pip show davey`).

Other causes once reception works:
- **VAD filtering you out** — speak a full sentence and pause ~1.5 s; very short/quiet clips
  are dropped (`MIN_AUDIO_SECONDS`, VAD threshold).
- **`respond_only_when_addressed: true`** — it only replies when it hears `bot_name_trigger`.
  Set it `false` or say "jimbot".
- **Cooldown** — lower `roast_cooldown_seconds` (e.g. `3`) if responses feel suppressed.
- **You opted out** — toggle with `/optout`.

> Tip: run `python test_pipeline.py` to confirm VAD→STT→LLM work independently of Discord.
> If that passes, the problem is in the Discord transport, not your AI stack.

---

## GPU / CUDA issues

**`torch.cuda.is_available()` is False**
- You have the CPU‑only torch build. Reinstall with the CUDA index URL **before** the
  requirements (see [Installation.md](Installation.md), Step 4 — CUDA PyTorch).

**faster‑whisper slow or crashing / out of VRAM**
- Use a smaller model: `model: medium` or `small` in `config.yaml`.
- Confirm `device: cuda`.
- Running Coqui XTTS + large‑v3 together can exceed ~10 GB — prefer Piper for TTS.

---

## No audio in voice channel

**Joins but doesn't speak**
- `ffmpeg -version` must work (on `PATH`, or `ffmpeg.exe`/`ffprobe.exe` in `bin/`).
- Check `jimbot.log` for TTS errors.
- Piper: `piper_model_path` must point at a real `.onnx` (with its `.onnx.json` beside it).

**Piper binary not found**
- Put `piper.exe` + `espeak-ng.dll` + `onnxruntime.dll` + `espeak-ng-data/` in `bin/`
  (Windows), or `pip install piper-tts` (Linux/macOS). Verify the model path resolves.

**ElevenLabs errors**
- `ELEVENLABS_API_KEY` set in `secrets.env`; `elevenlabs_voice_id` is a real ID.

**Disconnects immediately after joining**
- The bot needs **Connect** and **Speak** in that channel.
- `PyNaCl` must be present (installed via `py-cord[voice]`): `pip show pynacl`.

---

## VAD errors (only if you're editing `voice/vad.py`)

- **`EOFError: EOF when reading a line`** during model load — torch.hub is asking to trust
  the Silero repo and the bot is non‑interactive. The code passes `trust_repo=True`; keep it.
- **`Provided number of samples is N (Supported values: 256/512)`** — current Silero VAD
  only accepts fixed 512‑sample windows at 16 kHz. Feed audio in 512‑sample chunks (the
  shipped `_check` already does this).

---

## LLM errors

**Anthropic `401 Unauthorized`** — `ANTHROPIC_API_KEY` in `secrets.env` is wrong/missing.

**`openai_compat` errors** — `base_url` must include the full path (e.g.
`https://openrouter.ai/api/v1`, or `http://localhost:1234/v1` for LM Studio), and the model
name must match exactly what the server exposes.

**Ollama connection refused** — start it (`ollama serve`); default `base_url` is
`http://localhost:11434/v1`.

**LM Studio: empty replies / connection refused** — start the local server in LM Studio,
load the model, and ensure `model:` in `config.yaml` matches the served model name.

---

## Latency too high

- Smaller Whisper model (`small`/`medium`).
- Deepgram for STT (low‑latency cloud) and Piper for TTS (fast local).
- Lower `max_tokens` for shorter, faster replies.

---

## Checking logs

```sh
# Windows PowerShell
Get-Content jimbot.log -Wait -Tail 100
# Linux/macOS
tail -f jimbot.log
```

Bump verbosity in `bot.py`'s `setup_logging()`:
```python
logging.getLogger("discord.voice_client").setLevel(logging.DEBUG)
logging.getLogger("discord.gateway").setLevel(logging.DEBUG)
```
