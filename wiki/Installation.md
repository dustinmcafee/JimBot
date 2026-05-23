# Installation

A complete, ordered walkthrough. If you only read one thing: **secrets go in a file named
`secrets.env`** (Step 8), and on a GPU machine **install CUDA PyTorch *before* the
requirements** (Step 4).

## System requirements

- Windows 10/11, macOS 12+, or Linux (Ubuntu 20.04+)
- **Python 3.11+** (developed and tested on 3.14)
- **ffmpeg** + **ffprobe**
- For local STT/TTS: an NVIDIA GPU with CUDA 11.8+ (RTX 3080‑class or better recommended)

---

## Step 1 — Install Python

Install Python 3.11 or newer from <https://python.org>. On Windows, tick
**"Add Python to PATH"** during setup.

```sh
python --version
```

---

## Step 2 — Install ffmpeg and ffprobe

Required for all audio encode/decode (both TTS playback and the test harness).

**Windows**
1. Download a static build (e.g. the gyan.dev builds linked from <https://ffmpeg.org/download.html>).
2. Extract it.
3. Either add its `bin/` folder to your system `PATH`, **or** drop `ffmpeg.exe` and
   `ffprobe.exe` into this project's `bin/` folder — `bot.py` automatically prepends
   `./bin` to `PATH` at startup.
4. Verify: `ffmpeg -version`

**macOS:** `brew install ffmpeg`
**Linux:** `sudo apt install ffmpeg`

> **Why isn't `bin/` in the repo?** ffmpeg.exe and ffprobe.exe are ~227 MB each — over
> GitHub's 100 MB per‑file limit — so `bin/` is git‑ignored. You provide these binaries
> locally via this step (and Step 6 for Piper).

---

## Step 3 — Create and activate a virtual environment

```sh
cd JimBot
python -m venv .venv

.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux
```

Always activate the venv before installing packages or running the bot.

> Avoid naming the venv `.env` — this project reserves the filename **`secrets.env`** for
> secrets, and a `.env/` venv next to it invites confusion. Use `.venv`.

---

## Step 4 — Install CUDA PyTorch (GPU users) — do this BEFORE Step 5

> Skip only if you'll run STT/TTS entirely in the cloud.

If you install the requirements first, pip may pull the CPU‑only torch build. Install the
CUDA build first so it "wins":

```sh
# Check what your driver supports:
nvidia-smi

# CUDA 12.1
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121
# (or CUDA 11.8)
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu118
```

Verify GPU is visible:
```python
import torch
print(torch.cuda.is_available())          # True
print(torch.cuda.get_device_name(0))
```

---

## Step 5 — Install project dependencies

```sh
pip install -r requirements.txt
```

This installs **py-cord from PR #3159** with the `[voice]` extra. That PR is required for
voice because:

- py-cord ≤ 2.6 uses the retired voice gateway v4 → every `/join` fails with close code **4006**
- py-cord 2.8.0 fixed the gateway but **can't receive audio** under Discord's DAVE encryption
- PR #3159 (heading into 2.9.0) implements DAVE decryption, so receiving works

The `[voice]` extra also pulls in **`davey`** (the DAVE/E2EE implementation) and **`PyNaCl`**.

> The git‑based install builds py-cord from source. It needs `git` on your `PATH`. Once a
> stable py-cord ≥ 2.9.0 ships the DAVE receive rework, you can replace the git line in
> `requirements.txt` with `py-cord[voice]>=2.9.0`.

---

## Step 6 — Install Piper (default TTS) and a voice model

Piper voices are an `.onnx` + `.onnx.json` file **pair**.

1. Browse voices: <https://github.com/rhasspy/piper/blob/master/VOICES.md>
2. Download a pair, e.g. `en_US-lessac-medium.onnx` **and** `en_US-lessac-medium.onnx.json`
3. Put both in `models/piper/` (create the folder if needed)
4. Point `config.yaml` at it:
   ```yaml
   tts:
     provider: piper
     piper_model_path: models/piper/en_US-lessac-medium.onnx
   ```

Get the Piper binary:

- **Windows:** download the Piper release from <https://github.com/rhasspy/piper/releases>,
  and place `piper.exe` (plus its bundled `espeak-ng.dll`, `onnxruntime.dll`, and
  `espeak-ng-data/`) into this project's `bin/` folder. `providers/tts_piper.py` runs
  `bin/piper.exe` directly.
- **Linux/macOS:** `pip install piper-tts`

> `models/` is git‑ignored (voice models are large), so you provide the model locally too.

---

## Step 7 (optional) — Coqui XTTS for a more expressive voice

Larger, slower to start, but much more natural than Piper.

```sh
pip install TTS
```
```yaml
tts:
  provider: coqui_xtts
  coqui_model: tts_models/multilingual/multi-dataset/xtts_v2
```
The model (~2 GB) downloads automatically on first synthesis (~30 s warm‑up).

---

## Step 8 — Configure secrets (`secrets.env`)

```sh
copy .env.example secrets.env    # Windows
# cp .env.example secrets.env    # macOS/Linux
```

Edit **`secrets.env`** and set at least your Discord token:
```
DISCORD_TOKEN=your_discord_bot_token
# plus any provider keys you actually use, e.g.:
# ANTHROPIC_API_KEY=...
```

The shipped `config.yaml` targets a local LM Studio server and needs **no** API key. You
only need provider keys if you switch to a cloud provider. See
[Discord-Setup.md](Discord-Setup.md) for getting the token, and
[Configuration.md](Configuration.md) for which key each provider needs.

> `secrets.env` is git‑ignored. Never commit it. If a token leaks, reset it in the Discord
> Developer Portal immediately.

---

## Step 9 — Run

```sh
python bot.py
```

Expected startup (values mirror your `config.yaml`):
```
JimBot online as JimBoi#7850 (ID: ...)
  LLM : openai_compat / qwen2.5-7b-instruct
  STT : faster_whisper
  TTS : piper
```

---

## Step 10 (optional) — Verify the audio pipeline offline

Before wrestling with a live voice channel, confirm the AI stack works end to end:

```sh
.venv\Scripts\python.exe test_pipeline.py
```

It synthesizes speech, runs it through VAD → STT → LLM, and prints each stage. All stages
passing means the only remaining variable for live voice is Discord/network.
