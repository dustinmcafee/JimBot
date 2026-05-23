from abc import ABC, abstractmethod


class LLMProvider(ABC):
    @abstractmethod
    async def generate(self, messages: list[dict], system: str) -> str:
        """Generate a reply given a list of chat messages and a system prompt."""


class STTProvider(ABC):
    @abstractmethod
    async def transcribe(self, pcm_bytes: bytes, sample_rate: int = 16000) -> str:
        """Transcribe raw 16-bit mono PCM audio to text."""


class TTSProvider(ABC):
    @abstractmethod
    async def synthesize(self, text: str) -> bytes:
        """Synthesize text to raw audio bytes (WAV or Opus accepted by Discord)."""
