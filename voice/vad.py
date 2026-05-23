import asyncio
import numpy as np
import torch

# Discord sends 48kHz stereo 16-bit PCM; Silero VAD works best at 16kHz mono.
DISCORD_SAMPLE_RATE = 48_000
VAD_SAMPLE_RATE = 16_000
CHANNELS = 2
BYTES_PER_SAMPLE = 2  # 16-bit


class SileroVAD:
    """Thin async wrapper around Silero VAD. Call has_speech() to check a PCM
    chunk. Lazily loads the model on first use."""

    _model = None
    _utils = None

    @classmethod
    def _load(cls):
        if cls._model is None:
            cls._model, cls._utils = torch.hub.load(
                repo_or_dir="snakers4/silero-vad",
                model="silero_vad",
                force_reload=False,
                trust_repo=True,  # non-interactive: don't prompt to trust the repo
            )
            cls._model.eval()

    async def has_speech(self, pcm_bytes: bytes, threshold: float = 0.5) -> bool:
        return await asyncio.to_thread(self._check, pcm_bytes, threshold)

    def _check(self, pcm_bytes: bytes, threshold: float) -> bool:
        self._load()
        audio = _to_float_mono_16k(pcm_bytes)
        window = 512  # Silero VAD requires exactly 512 samples per call at 16kHz
        if len(audio) < window:
            return False

        # Reset the model's internal (LSTM) state between utterances
        if hasattr(self._model, "reset_states"):
            self._model.reset_states()

        speech_windows = 0
        total_windows = 0
        with torch.no_grad():
            for start in range(0, len(audio) - window + 1, window):
                chunk = np.ascontiguousarray(audio[start:start + window])
                tensor = torch.from_numpy(chunk)
                confidence = self._model(tensor, VAD_SAMPLE_RATE).item()
                total_windows += 1
                if confidence >= threshold:
                    speech_windows += 1

        if total_windows == 0:
            return False
        # Treat as speech if at least ~10% of windows (min 2) are voiced
        return speech_windows >= max(2, total_windows // 10)

    async def downsample_for_stt(self, pcm_bytes: bytes) -> bytes:
        """Convert 48kHz stereo → 16kHz mono 16-bit PCM for STT providers."""
        return await asyncio.to_thread(_to_pcm16_mono_16k, pcm_bytes)


def _to_float_mono_16k(pcm: bytes) -> np.ndarray:
    """48kHz stereo 16-bit PCM → float32 mono 16kHz numpy array."""
    samples = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
    # De-interleave stereo → mono
    if CHANNELS == 2:
        samples = samples[::2]  # take left channel
    # Downsample 48k → 16k (simple decimation by 3)
    samples = samples[::3]
    return samples


def _to_pcm16_mono_16k(pcm: bytes) -> bytes:
    """Same as above but output as 16-bit PCM bytes."""
    arr = _to_float_mono_16k(pcm)
    return (arr * 32767).astype(np.int16).tobytes()
