# Architecture

## Overview

JimBot has two independent interaction paths that share one bot process and one AI personality module.

```
Discord API
    │
    ├── Text path ──────────────────────────────────────────────────────────┐
    │   /roast command or @mention                                          │
    │       └── personality.generate_roast()                               │
    │               └── LLMProvider.generate()                             │
    │                       └── text reply to channel                      │
    │                                                                       │
    └── Voice path ──────────────────────────────────────────────────────── │
        /join → Pycord VoiceClient                                          │
            └── VoicePipeline (asyncio task)                               │
                    │                                                       │
                    ├── UserAudioSink (voice/sink.py)                      │
                    │     per-user 48kHz stereo PCM buffers, keyed by id    │
                    │     (write(data, user) — py-cord 2.8+ event API)      │
                    │                                                       │
                    ├── utterance detection (voice/pipeline.py)            │
                    │     buffer stops growing for SILENCE_TIMEOUT → done   │
                    │                                                       │
                    ├── SileroVAD (voice/vad.py)                           │
                    │     filter noise/silence in 512-sample windows        │
                    │     downsample 48kHz stereo → 16kHz mono for STT      │
                    │                                                       │
                    ├── STTProvider.transcribe()                           │
                    │     faster-whisper / Deepgram / OpenAI Whisper       │
                    │                                                       │
                    ├── personality.generate_roast()  ◄────────────────────┘
                    │     LLMProvider.generate() with rolling context
                    │
                    ├── TTSProvider.synthesize()
                    │     Piper / Coqui XTTS / ElevenLabs / OpenAI
                    │
                    └── discord.FFmpegPCMAudio → VoiceClient.play()
```

---

## Provider abstraction

```
providers/base.py
    LLMProvider (ABC)   .generate(messages, system) -> str
    STTProvider (ABC)   .transcribe(pcm_bytes, sample_rate) -> str
    TTSProvider (ABC)   .synthesize(text) -> bytes

factory.py
    build_llm(cfg) -> LLMProvider
    build_stt(cfg) -> STTProvider
    build_tts(cfg) -> TTSProvider
```

Concrete providers are imported lazily (only the configured one is imported at startup).
The bot core only ever holds references to the base classes.

---

## File map

```
bot.py                  Pycord client, cog loading, logging, startup,
                          clean-shutdown watcher (polls for shutdown.flag)
config_loader.py        Load + validate config.yaml and secrets.env
factory.py              Instantiate providers from config
personality.py          System prompts, generate_roast(), rolling history
test_pipeline.py        Offline VAD→STT→LLM test harness (no Discord)

providers/
  base.py               ABCs (LLMProvider, STTProvider, TTSProvider)
  llm_claude.py         Anthropic Claude
  llm_openai_compat.py  OpenAI / OpenRouter / Groq / Ollama
  stt_faster_whisper.py Local Whisper (CUDA)
  stt_deepgram.py       Deepgram cloud STT
  stt_openai.py         OpenAI Whisper API
  tts_piper.py          Local Piper TTS
  tts_coqui_xtts.py     Local Coqui XTTS-v2
  tts_elevenlabs.py     ElevenLabs cloud TTS
  tts_openai.py         OpenAI TTS

voice/
  sink.py               UserAudioSink — per-user PCM buffer (Pycord Sink)
  vad.py                SileroVAD — speech detection + downsample
  pipeline.py           VoicePipeline — async orchestration loop

commands/
  text.py               TextCog — /roast, /ping, @mention handler
  voice.py              VoiceCog — /join, /leave, /mute, /savage, /optout
```

---

## Concurrency model

- Everything runs in a single asyncio event loop.
- The voice pipeline is a long-lived `asyncio.Task` per guild.
- STT and TTS calls are wrapped in `asyncio.to_thread()` so they don't block the loop.
- Per-user utterance processing is also a `asyncio.Task`; parallel utterances from
  different users are processed concurrently.
- A shared `_last_roast_time` timestamp enforces the cooldown across users.

---

## Voice transport & DAVE (why the py-cord version is pinned)

Discord's voice stack changed in ways that dictate the library version:

- **Gateway version.** The voice WebSocket negotiates a protocol version in its URL
  (`wss://<endpoint>/?v=N`). Discord retired v4; py-cord ≤ 2.6 still requested it, so the
  voice server closes the connection with **4006 ("session no longer valid")** on every
  `/join`. py-cord 2.7+ uses **v8**.
- **DAVE (E2EE).** Since March 2026, Discord encrypts voice end‑to‑end. Sending audio works
  on 2.8.0, but **receiving** requires decrypting DAVE frames *before* Opus decode — only
  implemented in **PR #3159** (heading to 2.9.0). The `davey` dependency is the DAVE
  implementation; it's installed via the `py-cord[voice]` extra.

This is why `requirements.txt` installs py-cord from PR #3159. The receive path lands in
`UserAudioSink.write(data, user)`, where `data` is a `VoiceData` (`.pcm`, `.source`) and
`user` is a `User`/`Member` (or `None` before the SSRC→user mapping resolves) — the sink
normalizes that to an int user id.

## Utterance detection

Discord only sends voice packets while a user is actually speaking (Opus DTX), so the
pipeline treats a per‑user PCM buffer that **stops growing** for `SILENCE_TIMEOUT` (1.2 s)
as a finished utterance. It then drains the buffer, runs Silero VAD (in 512‑sample windows,
as the model requires) to reject pure silence/noise, downsamples 48 kHz stereo → 16 kHz
mono, and hands it to STT. A shared cooldown prevents the bot from talking over itself.

## Latency budget (RTX 3080, local STT/TTS)

| Stage | Typical time |
|-------|-------------|
| VAD silence detection | ~1.2s (configurable) |
| faster-whisper transcription | 0.2–0.8s |
| Claude Haiku API call | 0.3–0.8s |
| Piper TTS synthesis | 0.1–0.3s |
| **Total end-to-end** | **~2–3 seconds** |

Cloud TTS (ElevenLabs) adds ~0.5–1.5s. Cloud STT (Deepgram) is similar to local.
