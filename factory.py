from providers.base import LLMProvider, STTProvider, TTSProvider


def build_llm(cfg: dict) -> LLMProvider:
    provider = cfg["llm"]["provider"]

    if provider == "claude":
        from providers.llm_claude import ClaudeProvider
        return ClaudeProvider(cfg["llm"])

    if provider in ("openai", "openai_compat"):
        from providers.llm_openai_compat import OpenAICompatProvider
        return OpenAICompatProvider(cfg["llm"])

    if provider == "ollama":
        from providers.llm_openai_compat import OpenAICompatProvider
        ollama_cfg = dict(cfg["llm"])
        ollama_cfg.setdefault("base_url", "http://localhost:11434/v1")
        ollama_cfg["api_key"] = "ollama"
        return OpenAICompatProvider(ollama_cfg)

    raise ValueError(f"Unknown LLM provider: {provider!r}")


def build_stt(cfg: dict) -> STTProvider:
    provider = cfg["stt"]["provider"]

    if provider == "faster_whisper":
        from providers.stt_faster_whisper import FasterWhisperProvider
        return FasterWhisperProvider(cfg["stt"])

    if provider == "deepgram":
        from providers.stt_deepgram import DeepgramProvider
        return DeepgramProvider(cfg["stt"])

    if provider == "openai":
        from providers.stt_openai import OpenAISTTProvider
        return OpenAISTTProvider(cfg["stt"])

    raise ValueError(f"Unknown STT provider: {provider!r}")


def build_tts(cfg: dict) -> TTSProvider:
    provider = cfg["tts"]["provider"]

    if provider == "piper":
        from providers.tts_piper import PiperProvider
        return PiperProvider(cfg["tts"])

    if provider == "coqui_xtts":
        from providers.tts_coqui_xtts import CoquiXTTSProvider
        return CoquiXTTSProvider(cfg["tts"])

    if provider == "elevenlabs":
        from providers.tts_elevenlabs import ElevenLabsProvider
        return ElevenLabsProvider(cfg["tts"])

    if provider == "openai":
        from providers.tts_openai import OpenAITTSProvider
        return OpenAITTSProvider(cfg["tts"])

    raise ValueError(f"Unknown TTS provider: {provider!r}")
