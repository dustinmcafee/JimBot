import asyncio
import io
import tempfile
import os
from providers.base import TTSProvider


class CoquiXTTSProvider(TTSProvider):
    """Local TTS via Coqui TTS (XTTS-v2). Requires: pip install TTS.
    Downloads model on first run (~2GB). GPU recommended."""

    def __init__(self, cfg: dict):
        self._model_name = cfg.get("coqui_model", "tts_models/multilingual/multi-dataset/xtts_v2")
        self._tts = None  # lazy init — model load is slow

    def _get_tts(self):
        if self._tts is None:
            from TTS.api import TTS
            self._tts = TTS(self._model_name, gpu=True)
        return self._tts

    async def synthesize(self, text: str) -> bytes:
        return await asyncio.to_thread(self._run_tts, text)

    def _run_tts(self, text: str) -> bytes:
        tts = self._get_tts()
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            tts.tts_to_file(text=text, file_path=tmp_path)
            with open(tmp_path, "rb") as f:
                return f.read()
        finally:
            os.unlink(tmp_path)
