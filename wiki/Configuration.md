# Configuration

JimBot reads two files at startup:

- **`config.yaml`** — provider selection, model names, behavior tuning (safe to commit)
- **`secrets.env`** — API keys and your bot token (**git‑ignored, never commit**)

> The secrets file is literally named **`secrets.env`** — not `.env`. `config_loader.py`
> calls `load_dotenv("secrets.env")`, because `.env/` is a common virtualenv directory name.
> Copy the template with `copy .env.example secrets.env` (Windows) / `cp .env.example secrets.env`.

---

## secrets.env

Only the variables for providers you actually use are required.

| Variable | Required when | Description |
|----------|---------------|-------------|
| `DISCORD_TOKEN` | **Always** | Your bot token from the Discord Developer Portal |
| `ANTHROPIC_API_KEY` | `llm.provider: claude` | Anthropic API key |
| `OPENAI_API_KEY` | OpenAI LLM/STT/TTS | OpenAI API key |
| `OPENAI_COMPAT_API_KEY` | hosted `openai_compat` | Key for OpenRouter / Groq / Together / etc. |
| `ELEVENLABS_API_KEY` | `tts.provider: elevenlabs` | ElevenLabs API key |
| `DEEPGRAM_API_KEY` | `stt.provider: deepgram` | Deepgram API key |

Local providers (LM Studio, Ollama, faster‑whisper, Piper, Coqui) need **no** key.

A field in `config.yaml` named `api_key_env` is a **pointer** to one of these variable
names — e.g. `api_key_env: ANTHROPIC_API_KEY` tells JimBot to read the `ANTHROPIC_API_KEY`
value from `secrets.env`. Set it to `null` for keyless local providers.

---

## config.yaml reference

### `llm`

```yaml
llm:
  provider: openai_compat        # claude | openai | openai_compat | ollama
  model: qwen2.5-7b-instruct     # model name as the provider expects it
  api_key_env: null              # which secrets.env var holds the key (null = none)
  base_url: http://localhost:1234/v1   # endpoint for openai_compat / ollama
  temperature: 1.0               # 0.0–2.0; higher = more unhinged
  max_tokens: 300                # max reply length (tokens)
```

| `provider` | Meaning |
|-----------|---------|
| `claude` | Anthropic Claude API (`ANTHROPIC_API_KEY`) |
| `openai` | OpenAI Chat API (`OPENAI_API_KEY`) |
| `openai_compat` | Any OpenAI‑format endpoint — LM Studio, OpenRouter, Groq, Together. Set `base_url`. |
| `ollama` | Local Ollama; `base_url` auto‑defaults to `http://localhost:11434/v1`, no key |

**LM Studio (shipped default):**
```yaml
llm:
  provider: openai_compat
  model: qwen2.5-7b-instruct     # must match the model name LM Studio's server shows
  base_url: http://localhost:1234/v1
  api_key_env: null
```

**OpenRouter:**
```yaml
llm:
  provider: openai_compat
  model: meta-llama/llama-3.1-8b-instruct
  base_url: https://openrouter.ai/api/v1
  api_key_env: OPENAI_COMPAT_API_KEY
```

**Local Ollama:**
```yaml
llm: { provider: ollama, model: llama3.1:8b }
```

---

### `stt`

```yaml
stt:
  provider: faster_whisper       # faster_whisper | deepgram | openai
  model: medium                  # tiny | base | small | medium | large-v3
  device: cuda                   # cuda | cpu   (faster_whisper only)
  api_key_env: null              # DEEPGRAM_API_KEY or OPENAI_API_KEY for cloud
```

faster‑whisper model size vs. cost (approximate, RTX 3080):

| Model | VRAM | Speed | Accuracy |
|-------|------|-------|----------|
| `tiny` | ~1 GB | very fast | low |
| `small` | ~2 GB | fast | ok |
| `medium` *(default)* | ~3 GB | good | good |
| `large-v3` | ~5 GB | moderate | best |

The model is downloaded and loaded lazily on the first transcription.

---

### `tts`

```yaml
tts:
  provider: piper                # piper | coqui_xtts | elevenlabs | openai

  # piper
  piper_model_path: models/piper/en_US-lessac-medium.onnx

  # coqui_xtts
  coqui_model: tts_models/multilingual/multi-dataset/xtts_v2

  # elevenlabs
  elevenlabs_voice_id: null      # voice ID from your ElevenLabs dashboard
  elevenlabs_model: eleven_monolingual_v1

  # openai
  openai_tts_voice: onyx         # alloy | echo | fable | onyx | nova | shimmer
  openai_tts_model: tts-1        # tts-1 | tts-1-hd

  api_key_env: null              # ELEVENLABS_API_KEY or OPENAI_API_KEY for cloud
```

---

### `behavior`

```yaml
behavior:
  savage_level: 2                     # 1=mild | 2=sarcastic (default) | 3=brutal
  roast_cooldown_seconds: 8           # min seconds between unprompted voice roasts
  respond_only_when_addressed: false  # true = only roast when the trigger word is heard
  bot_name_trigger: jimbot            # trigger word (case‑insensitive)
  announce_when_joining: true         # speak a short greeting on join
```

- `savage_level` is also changeable live with `/savage 1|2|3` (per voice session).
- `roast_cooldown_seconds` is a **shared** cooldown across all speakers in the channel.
- With `respond_only_when_addressed: true`, JimBot stays quiet unless the transcript
  contains `bot_name_trigger`.

---

### `discord`

```yaml
discord:
  command_prefix: "!"       # legacy text‑command prefix; slash commands are primary
```

---

## Complete profiles

**All‑local (no cloud bills, needs a CUDA GPU):**
```yaml
llm:  { provider: openai_compat, model: qwen2.5-7b-instruct, base_url: http://localhost:1234/v1, api_key_env: null }
stt:  { provider: faster_whisper, model: medium, device: cuda }
tts:  { provider: piper, piper_model_path: models/piper/en_US-lessac-medium.onnx }
```

**Cloud LLM + local voice:**
```yaml
llm:  { provider: claude, model: claude-haiku-4-5, api_key_env: ANTHROPIC_API_KEY }
stt:  { provider: faster_whisper, model: medium, device: cuda }
tts:  { provider: piper, piper_model_path: models/piper/en_US-lessac-medium.onnx }
```

**Full cloud (no GPU):**
```yaml
llm:  { provider: claude, model: claude-haiku-4-5, api_key_env: ANTHROPIC_API_KEY }
stt:  { provider: deepgram, api_key_env: DEEPGRAM_API_KEY }
tts:  { provider: elevenlabs, elevenlabs_voice_id: EXAVITQu4vr4xnSDxMaL, api_key_env: ELEVENLABS_API_KEY }
```

**Maximum chaos:**
```yaml
llm: { provider: claude, model: claude-opus-4-7, api_key_env: ANTHROPIC_API_KEY, temperature: 1.3 }
tts: { provider: elevenlabs, elevenlabs_voice_id: <id>, elevenlabs_model: eleven_multilingual_v2, api_key_env: ELEVENLABS_API_KEY }
behavior: { savage_level: 3, roast_cooldown_seconds: 5 }
```
