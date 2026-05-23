import asyncio
from deepgram import DeepgramClient, PrerecordedOptions
from providers.base import STTProvider


class DeepgramProvider(STTProvider):
    def __init__(self, cfg: dict):
        self._client = DeepgramClient(cfg["api_key"])

    async def transcribe(self, pcm_bytes: bytes, sample_rate: int = 16000) -> str:
        options = PrerecordedOptions(
            model="nova-2",
            language="en",
            smart_format=True,
        )
        payload = {"buffer": pcm_bytes, "mimetype": f"audio/raw;encoding=linear16;sample_rate={sample_rate};channels=1"}
        response = await asyncio.to_thread(
            self._client.listen.prerecorded.v("1").transcribe_file, payload, options
        )
        words = response.results.channels[0].alternatives[0].transcript
        return words.strip()
