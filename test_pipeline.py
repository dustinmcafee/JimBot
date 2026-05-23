"""Local end-to-end test of the voice pipeline components (no Discord needed).

Synthesizes speech with the configured TTS, converts it to the exact
48kHz-stereo-16bit PCM format Discord's voice sink delivers, then runs it
through the real VAD -> STT -> LLM chain and prints the result at each stage.

Run:  .env\\Scripts\\python.exe test_pipeline.py
"""
import asyncio
import os
import subprocess
import sys
import tempfile
from pathlib import Path

# Make bin/ (ffmpeg) discoverable, same as bot.py does
_BIN = Path(__file__).parent / "bin"
if _BIN.exists():
    os.environ["PATH"] = str(_BIN) + os.pathsep + os.environ["PATH"]

from config_loader import load_config
from factory import build_llm, build_stt, build_tts
from voice.vad import SileroVAD
from personality import generate_roast

TEST_SENTENCE = "Hey Jim Bot, I honestly think you are completely useless today."


def wav_to_discord_pcm(wav_bytes: bytes) -> bytes:
    """Convert arbitrary WAV -> 48kHz stereo signed-16 little-endian raw PCM,
    matching what pycord's voice receiver hands to the sink."""
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".wav")
    os.write(tmp_fd, wav_bytes)
    os.close(tmp_fd)
    try:
        proc = subprocess.run(
            ["ffmpeg", "-y", "-i", tmp_path,
             "-f", "s16le", "-acodec", "pcm_s16le",
             "-ar", "48000", "-ac", "2", "pipe:1"],
            capture_output=True, timeout=60,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {proc.stderr.decode(errors='ignore')[:500]}")
        return proc.stdout
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


async def main() -> int:
    cfg = load_config()
    tts = build_tts(cfg)
    stt = build_stt(cfg)
    llm = build_llm(cfg)

    print(f"[1/5] Synthesizing test speech: {TEST_SENTENCE!r}")
    wav = await tts.synthesize(TEST_SENTENCE)
    print(f"      TTS produced {len(wav)} bytes of WAV")

    print("[2/5] Converting to 48kHz stereo PCM (Discord format)...")
    pcm = wav_to_discord_pcm(wav)
    secs = len(pcm) / (48_000 * 2 * 2)
    print(f"      {len(pcm)} bytes (~{secs:.2f}s of 48kHz stereo audio)")

    print("[3/5] Running Silero VAD has_speech()...")
    vad = SileroVAD()
    has_speech = await vad.has_speech(pcm)
    print(f"      has_speech = {has_speech}")
    if not has_speech:
        print("      !! VAD did not detect speech in real synthesized speech — FAIL")
        return 1

    print("[4/5] Downsampling + STT transcribe...")
    pcm_16k = await vad.downsample_for_stt(pcm)
    transcript = await stt.transcribe(pcm_16k, sample_rate=16_000)
    print(f"      transcript = {transcript!r}")
    if not transcript or not transcript.strip():
        print("      !! STT returned empty transcript — FAIL")
        return 1

    print("[5/5] Generating roast via LLM...")
    roast = await generate_roast(
        llm=llm,
        text=transcript,
        savage_level=cfg["behavior"]["savage_level"],
        speaker_name="TestUser",
        guild_id=0,
    )
    print(f"      roast = {roast!r}")
    if not roast or not roast.strip():
        print("      !! LLM returned empty roast — FAIL")
        return 1

    print("\nALL STAGES PASSED — VAD -> STT -> LLM chain works end to end.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
