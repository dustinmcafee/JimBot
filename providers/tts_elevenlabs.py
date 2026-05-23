import asyncio
from elevenlabs.client import AsyncElevenLabs
from elevenlabs import VoiceSettings
from providers.base import TTSProvider


class ElevenLabsProvider(TTSProvider):
    def __init__(self, cfg: dict):
        self._client = AsyncElevenLabs(api_key=cfg["api_key"])
        self._voice_id = cfg.get("elevenlabs_voice_id") or "EXAVITQu4vr4xnSDxMaL"
        self._model = cfg.get("elevenlabs_model", "eleven_monolingual_v1")

    async def synthesize(self, text: str) -> bytes:
        audio_iter = await self._client.generate(
            text=text,
            voice=self._voice_id,
            model=self._model,
            voice_settings=VoiceSettings(stability=0.4, similarity_boost=0.75),
        )
        chunks = []
        async for chunk in audio_iter:
            chunks.append(chunk)
        return b"".join(chunks)
