from openai import AsyncOpenAI
from providers.base import TTSProvider


class OpenAITTSProvider(TTSProvider):
    def __init__(self, cfg: dict):
        self._client = AsyncOpenAI(api_key=cfg["api_key"])
        self._voice = cfg.get("openai_tts_voice", "onyx")
        self._model = cfg.get("openai_tts_model", "tts-1")

    async def synthesize(self, text: str) -> bytes:
        response = await self._client.audio.speech.create(
            model=self._model,
            voice=self._voice,
            input=text,
            response_format="wav",
        )
        return response.content
