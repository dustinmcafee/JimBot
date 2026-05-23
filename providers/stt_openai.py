import asyncio
import io
import wave
from openai import AsyncOpenAI
from providers.base import STTProvider


class OpenAISTTProvider(STTProvider):
    def __init__(self, cfg: dict):
        self._client = AsyncOpenAI(api_key=cfg["api_key"])

    async def transcribe(self, pcm_bytes: bytes, sample_rate: int = 16000) -> str:
        wav_bytes = _pcm_to_wav(pcm_bytes, sample_rate)
        response = await self._client.audio.transcriptions.create(
            model="whisper-1",
            file=("audio.wav", io.BytesIO(wav_bytes), "audio/wav"),
        )
        return response.text.strip()


def _pcm_to_wav(pcm: bytes, sample_rate: int) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)
    return buf.getvalue()
