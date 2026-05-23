import asyncio
import io
import logging
import os
import tempfile
import time
from typing import TYPE_CHECKING

import discord

from voice.sink import UserAudioSink
from voice.vad import SileroVAD
from personality import generate_roast

if TYPE_CHECKING:
    from bot import JimBot
    from commands.voice import VoiceSession

log = logging.getLogger(__name__)

# How long of silence (seconds) to wait before treating audio as a complete utterance
SILENCE_TIMEOUT = 1.2
# Minimum audio length (seconds) to bother running STT on
MIN_AUDIO_SECONDS = 0.5
# How frequently the poll loop checks each user's buffer
POLL_INTERVAL = 0.4
# 48kHz stereo 16-bit = 192000 bytes/sec
BYTES_PER_SEC = 48_000 * 2 * 2


class VoicePipeline:
    """Orchestrates voice receive → VAD → STT → LLM → TTS → playback.

    Runs as a long-lived asyncio task for the duration of a voice session.
    """

    def __init__(self, bot, session, guild_id: int):
        self.bot = bot
        self.session = session
        self.guild_id = guild_id
        self._vad = SileroVAD()
        self._last_roast_time: float = 0.0
        # user_id -> timestamp of last time NEW audio arrived
        self._last_audio_time: dict[int, float] = {}
        # user_id -> buffer size (bytes) seen at last poll, to detect growth
        self._last_buffer_size: dict[int, int] = {}
        # user_id -> asyncio.Task currently processing their utterance
        self._processing: dict[int, asyncio.Task] = {}

    async def run(self) -> None:
        vc = self.session.vc
        sink = UserAudioSink()

        log.info("Voice pipeline: starting recording for guild %s", self.guild_id)
        try:
            vc.start_recording(sink, self._on_recording_stop)
        except Exception as exc:
            log.error("start_recording failed: %s", exc, exc_info=True)
            return

        log.info("Voice pipeline started for guild %s", self.guild_id)

        try:
            while vc.is_connected():
                await asyncio.sleep(POLL_INTERVAL)

                now = time.monotonic()

                # Mark users whose buffer GREW since last poll as "still speaking".
                # Discord stops sending RTP when a user is silent (DTX), so a buffer
                # that stops growing means the utterance is complete.
                for user_id in sink.users_with_audio():
                    current_size = sink.buffer_size(user_id)
                    if current_size > self._last_buffer_size.get(user_id, 0):
                        self._last_audio_time[user_id] = now
                        self._last_buffer_size[user_id] = current_size

                # Check if any user has gone silent long enough to process
                for user_id, last_t in list(self._last_audio_time.items()):
                    already_processing = (
                        user_id in self._processing
                        and not self._processing[user_id].done()
                    )
                    if already_processing:
                        continue

                    silence_duration = now - last_t
                    if silence_duration < SILENCE_TIMEOUT:
                        continue

                    # Utterance complete — drain and reset tracking
                    pcm = sink.drain(user_id)
                    self._last_buffer_size[user_id] = 0
                    self._last_audio_time.pop(user_id, None)

                    if len(pcm) < int(MIN_AUDIO_SECONDS * BYTES_PER_SEC):
                        continue

                    log.debug("Utterance complete for %s: %d bytes", user_id, len(pcm))
                    task = asyncio.create_task(
                        self._process_utterance(vc, user_id, pcm)
                    )
                    self._processing[user_id] = task

        except asyncio.CancelledError:
            pass
        finally:
            if vc.is_connected():
                vc.stop_recording()
            sink.cleanup()
            log.info("Voice pipeline stopped for guild %s", self.guild_id)

    def _on_recording_stop(self, sink: UserAudioSink, *args):
        sink.cleanup()

    async def _process_utterance(
        self, vc: discord.VoiceClient, user_id: int, pcm: bytes
    ) -> None:
        if self.session.muted:
            return

        if user_id in self.bot.opted_out:
            return

        # Enforce cooldown (shared across all users in the channel)
        now = time.monotonic()
        cooldown = self.bot.cfg["behavior"].get("roast_cooldown_seconds", 8)
        if now - self._last_roast_time < cooldown:
            return

        # Resolve display name for the speaker
        try:
            member = vc.channel.guild.get_member(user_id)
            speaker_name = member.display_name if member else "someone"
        except Exception:
            speaker_name = "someone"

        try:
            # Downsample 48kHz stereo → 16kHz mono for STT
            pcm_16k = await self._vad.downsample_for_stt(pcm)

            # Check that there's actual speech (not silence/noise)
            has_speech = await self._vad.has_speech(pcm)
            if not has_speech:
                return

            # Transcribe
            transcript = await self.bot.stt.transcribe(pcm_16k, sample_rate=16_000)
            if not transcript:
                return

            log.info("[%s] transcribed: %s", speaker_name, transcript)

            # Optionally only respond when bot name is mentioned
            if self.bot.cfg["behavior"].get("respond_only_when_addressed", False):
                trigger = self.bot.cfg["behavior"].get("bot_name_trigger", "jimbot").lower()
                if trigger not in transcript.lower():
                    return

            # Generate roast
            savage = self.session.savage_level or self.bot.cfg["behavior"]["savage_level"]
            reply = await generate_roast(
                llm=self.bot.llm,
                text=transcript,
                savage_level=savage,
                speaker_name=speaker_name,
                guild_id=self.guild_id,
            )

            log.info("[JimBot->%s] %s", speaker_name, reply)

            # Synthesize and play
            audio_bytes = await self.bot.tts.synthesize(reply)
            self._last_roast_time = time.monotonic()
            await _play_audio(vc, audio_bytes)

        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.error("Pipeline error for user %s: %s", user_id, exc, exc_info=True)


async def _play_audio(vc: discord.VoiceClient, audio_bytes: bytes) -> None:
    """Wait for any current playback to finish, then play new audio."""
    deadline = time.monotonic() + 30
    while vc.is_playing() and time.monotonic() < deadline:
        await asyncio.sleep(0.1)

    if not vc.is_connected():
        return

    # Write to a real temp file — BytesIO has no fileno() so FFmpeg can't use it as stdin
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".wav")
    try:
        os.write(tmp_fd, audio_bytes)
        os.close(tmp_fd)
        source = discord.FFmpegPCMAudio(tmp_path)
        done_event = asyncio.Event()
        vc.play(source, after=lambda _: done_event.set())
        await done_event.wait()
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
