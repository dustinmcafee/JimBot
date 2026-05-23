import asyncio
import struct
from providers.base import STTProvider


class FasterWhisperProvider(STTProvider):
    """Local STT via faster-whisper. Runs on GPU (CUDA) if available.
    See wiki/Installation.md for CUDA PyTorch setup."""

    def __init__(self, cfg: dict):
        self._model_size = cfg.get("model", "large-v3")
        self._device = cfg.get("device", "cuda")
        self._model = None  # lazy init

    def _get_model(self):
        if self._model is None:
            from faster_whisper import WhisperModel
            compute = "float16" if self._device == "cuda" else "int8"
            self._model = WhisperModel(self._model_size, device=self._device, compute_type=compute)
        return self._model

    async def transcribe(self, pcm_bytes: bytes, sample_rate: int = 16000) -> str:
        return await asyncio.to_thread(self._run, pcm_bytes, sample_rate)

    def _run(self, pcm_bytes: bytes, sample_rate: int) -> str:
        import numpy as np
        model = self._get_model()
        # Convert raw 16-bit PCM to float32 numpy array
        samples = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        segments, _ = model.transcribe(samples, language="en", beam_size=5)
        return " ".join(seg.text.strip() for seg in segments).strip()
