# Providers

JimBot uses a provider abstraction so you can swap AI backends by changing `config.yaml`. No code changes needed.

## How it works

Three abstract base classes live in `providers/base.py`:

```python
class LLMProvider:
    async def generate(messages, system) -> str

class STTProvider:
    async def transcribe(pcm_bytes, sample_rate) -> str

class TTSProvider:
    async def synthesize(text) -> bytes
```

`factory.py` reads `config.yaml` and instantiates the selected provider at startup. The rest of the bot only ever calls the interface.

---

## LLM Providers

### `claude` (default)
- **File:** `providers/llm_claude.py`
- **Requires:** `ANTHROPIC_API_KEY` in `secrets.env`
- **Models:** `claude-haiku-4-5` (fast/cheap), `claude-sonnet-4-6`, `claude-opus-4-7` (smartest)

```yaml
llm:
  provider: claude
  model: claude-haiku-4-5
  api_key_env: ANTHROPIC_API_KEY
```

### `openai`
- **File:** `providers/llm_openai_compat.py`
- **Requires:** `OPENAI_API_KEY` in `secrets.env`
- **Models:** `gpt-4o-mini`, `gpt-4o`, etc.

### `openai_compat`
- **File:** `providers/llm_openai_compat.py`
- Works with any OpenAI-format endpoint: OpenRouter, Groq, Together AI, LM Studio, etc.
- Set `base_url` to point at your endpoint.

**OpenRouter example:**
```yaml
llm:
  provider: openai_compat
  model: google/gemini-flash-1.5
  base_url: https://openrouter.ai/api/v1
  api_key_env: OPENAI_COMPAT_API_KEY
```

**Groq example:**
```yaml
llm:
  provider: openai_compat
  model: llama-3.1-70b-versatile
  base_url: https://api.groq.com/openai/v1
  api_key_env: OPENAI_COMPAT_API_KEY
```

### `ollama`
- **File:** `providers/llm_openai_compat.py` (reuses OpenAI-compat adapter)
- Requires a running Ollama server (`ollama serve`)
- No API key needed

```yaml
llm:
  provider: ollama
  model: llama3.1:8b
```

---

## STT Providers

### `faster_whisper` (default)
- **File:** `providers/stt_faster_whisper.py`
- Local inference — no API key, runs on your GPU
- Lazy model load on first transcription
- `device: cuda` for GPU, `cpu` for CPU-only

### `deepgram`
- **File:** `providers/stt_deepgram.py`
- Cloud, very fast streaming-capable API
- **Requires:** `DEEPGRAM_API_KEY`

```yaml
stt:
  provider: deepgram
  api_key_env: DEEPGRAM_API_KEY
```

### `openai`
- **File:** `providers/stt_openai.py`
- OpenAI Whisper API (cloud)
- **Requires:** `OPENAI_API_KEY`

---

## TTS Providers

### `piper` (default)
- **File:** `providers/tts_piper.py`
- Local, very fast, minimal GPU use
- Requires Piper binary + `.onnx` voice model (see [Installation.md](Installation.md))
- Good for functional TTS; voice quality is robotic-but-clear

### `coqui_xtts`
- **File:** `providers/tts_coqui_xtts.py`
- Local, more expressive voice quality
- **Requires:** `pip install TTS` (~2GB download on first use)
- Lazy model load — first synthesis takes ~30s

### `elevenlabs`
- **File:** `providers/tts_elevenlabs.py`
- Cloud, highest quality expressive voices
- **Requires:** `ELEVENLABS_API_KEY`
- Find voice IDs in your ElevenLabs dashboard

```yaml
tts:
  provider: elevenlabs
  elevenlabs_voice_id: EXAVITQu4vr4xnSDxMaL
  elevenlabs_model: eleven_monolingual_v1
  api_key_env: ELEVENLABS_API_KEY
```

### `openai`
- **File:** `providers/tts_openai.py`
- Cloud, good quality, multiple voices
- **Requires:** `OPENAI_API_KEY`
- Voices: `alloy`, `echo`, `fable`, `onyx`, `nova`, `shimmer`

---

## Adding a New Provider

1. Create a file in `providers/` that imports and implements the relevant ABC from `providers/base.py`.
2. Add a branch to the appropriate `build_*` function in `factory.py`.
3. Add any new config fields to `config.yaml` and document them in [Configuration.md](Configuration.md).

Example skeleton for a new TTS provider:

```python
# providers/tts_myservice.py
from providers.base import TTSProvider

class MyServiceProvider(TTSProvider):
    def __init__(self, cfg: dict):
        self._api_key = cfg["api_key"]
        # ... init client

    async def synthesize(self, text: str) -> bytes:
        # ... call API, return WAV bytes
```

Then in `factory.py`:
```python
if provider == "myservice":
    from providers.tts_myservice import MyServiceProvider
    return MyServiceProvider(cfg["tts"])
```

And in `config.yaml`:
```yaml
tts:
  provider: myservice
  api_key_env: MYSERVICE_API_KEY
```
