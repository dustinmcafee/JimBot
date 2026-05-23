import asyncio
import os
import subprocess
import tempfile
from pathlib import Path
from providers.base import TTSProvider

# Project root = parent of this file's directory
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_PIPER_EXE = _PROJECT_ROOT / "bin" / "piper.exe"


class PiperProvider(TTSProvider):
    """Local TTS via Piper. Requires piper binary and an .onnx voice model.
    See wiki/Installation.md for setup instructions."""

    def __init__(self, cfg: dict):
        model_path = cfg.get("piper_model_path", "models/piper/en_US-lessac-medium.onnx")
        # Resolve relative paths from project root so the bot can be run from anywhere
        self._model_path = str((_PROJECT_ROOT / model_path).resolve())
        self._piper_exe = str(_PIPER_EXE)

    async def synthesize(self, text: str) -> bytes:
        return await asyncio.to_thread(self._run_piper, text)

    def _run_piper(self, text: str) -> bytes:
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".wav")
        os.close(tmp_fd)

        try:
            proc = subprocess.run(
                [self._piper_exe, "--model", self._model_path, "--output_file", tmp_path],
                input=text.encode(),
                capture_output=True,
                timeout=30,
            )
            if proc.returncode != 0:
                raise RuntimeError(f"Piper failed: {proc.stderr.decode()}")

            with open(tmp_path, "rb") as f:
                return f.read()
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
