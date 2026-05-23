import asyncio
import io
import logging
import os
import tempfile
import discord
from discord.ext import commands
from discord import option

from personality import generate_roast, clear_history

log = logging.getLogger(__name__)


class VoiceSession:
    """Tracks active voice state for one guild."""
    def __init__(self, vc: discord.VoiceClient):
        self.vc = vc
        self.pipeline_task: asyncio.Task | None = None
        self.muted = False
        self.savage_level: int | None = None  # None = use config default


class VoiceCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _savage(self, session: VoiceSession) -> int:
        if session.savage_level is not None:
            return session.savage_level
        return self.bot.cfg["behavior"]["savage_level"]

    async def _play_tts(self, vc: discord.VoiceClient, text: str) -> None:
        """Synthesize text and play it into the voice channel."""
        log.info("TTS synthesizing: %r", text[:60])
        audio_bytes = await self.bot.tts.synthesize(text)
        log.info("TTS got %d bytes, writing temp file", len(audio_bytes))
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".wav")
        try:
            os.write(tmp_fd, audio_bytes)
            os.close(tmp_fd)
            log.info("Playing audio via FFmpeg from %s", tmp_path)
            source = discord.FFmpegPCMAudio(tmp_path)
            if vc.is_playing():
                vc.stop()
            done = asyncio.Event()
            play_error = []
            def _after(err):
                if err:
                    log.error("FFmpeg playback error: %s", err)
                    play_error.append(err)
                done.set()
            vc.play(source, after=_after)
            await done.wait()
            log.info("Playback finished (errors: %s)", play_error)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    # ── /join ─────────────────────────────────────────────────────────────────

    @discord.slash_command(name="join", description="JimBot joins your voice channel and starts roasting.")
    async def join(self, ctx: discord.ApplicationContext):
        print(f"[JOIN] called by {ctx.author} guild={ctx.guild_id}", flush=True)
        log.info("/join called by %s in guild %s", ctx.author, ctx.guild_id)
        if not ctx.author.voice:
            await ctx.respond("You're not in a voice channel, genius.", ephemeral=True)
            return

        channel = ctx.author.voice.channel
        guild_id = ctx.guild_id

        # Disconnect any existing session
        if guild_id in self.bot.voice_sessions:
            await self._cleanup_session(guild_id)

        await ctx.defer()

        # ── Step 1: handle any existing pycord voice client ──────────────────
        # After a failed connect (e.g. 4006), pycord leaves a broken VoiceClient
        # registered to the guild.  move_to() on a broken client appears to succeed
        # but the underlying WebSocket is dead (_MissingSentinel), so all audio ops
        # fail.  Only reuse a client that is_connected(); otherwise tear it down.
        existing_vc = ctx.guild.voice_client
        if existing_vc is not None:
            if existing_vc.is_connected():
                log.info("Reusing live voice client via move_to()")
                try:
                    await existing_vc.move_to(channel)
                    vc = existing_vc
                    log.info("Voice ready in %s (moved)", channel.name)
                except discord.errors.ConnectionClosed as e:
                    log.error("move_to failed with code %d", e.code)
                    await ctx.followup.send(
                        f"Voice connection failed (code {e.code}). Please try `/join` again.",
                        ephemeral=True,
                    )
                    return
            else:
                # Broken/dead client — disconnect so pycord stops tracking it,
                # then fall through to a fresh connect below.
                log.info("Disconnecting broken voice client before fresh connect")
                try:
                    await existing_vc.disconnect(force=True)
                except Exception:
                    pass
                existing_vc = None

        if existing_vc is None:
            # ── Step 2: always send a gateway leave before connecting ─────────
            # The gateway clears stale voice presence quickly, but Discord's voice
            # server keeps the old session alive much longer.  An unconditional
            # leave here ensures the voice server knows we're gone before we try
            # to create a new session.
            await ctx.guild.change_voice_state(channel=None)
            try:
                await self.bot.wait_for(
                    "voice_state_update",
                    check=lambda m, b, a: m.id == self.bot.user.id and a.channel is None,
                    timeout=5.0,
                )
                log.info("Gateway confirmed voice leave")
            except asyncio.TimeoutError:
                log.info("No leave confirmation (bot was not in voice)")

            # ── Step 3: connect; auto-retry once on 4006 ─────────────────────
            # On 4006 pycord registers a broken VoiceClient — disconnect it
            # before retrying so channel.connect() doesn't throw "already connected".
            log.info("Connecting to %s", channel.name)
            try:
                vc = await channel.connect(reconnect=False)
                log.info("Voice ready in %s", channel.name)
            except discord.errors.ConnectionClosed as e:
                if e.code != 4006:
                    log.error("Voice connect failed with code %d", e.code)
                    await ctx.followup.send(
                        f"Voice connection failed (code {e.code}).", ephemeral=True
                    )
                    return

                # 4006 — clean up the broken VC pycord registered, then retry
                log.warning("4006 on first attempt — cleaning up and retrying")
                broken_vc = ctx.guild.voice_client
                if broken_vc is not None:
                    try:
                        await broken_vc.disconnect(force=True)
                    except Exception:
                        pass

                await ctx.guild.change_voice_state(channel=None)
                try:
                    await self.bot.wait_for(
                        "voice_state_update",
                        check=lambda m, b, a: m.id == self.bot.user.id and a.channel is None,
                        timeout=5.0,
                    )
                    log.info("Gateway confirmed leave before retry")
                except asyncio.TimeoutError:
                    log.info("No leave confirmation before retry — proceeding")

                try:
                    vc = await channel.connect(reconnect=False)
                    log.info("Voice ready in %s (retry)", channel.name)
                except discord.errors.ConnectionClosed as e2:
                    log.error("Voice connect failed on retry with code %d", e2.code)
                    await ctx.followup.send(
                        f"Voice connection failed (code {e2.code}) even after retry.",
                        ephemeral=True,
                    )
                    return
                except Exception as e2:
                    log.error("Unexpected error on retry: %s", e2, exc_info=True)
                    await ctx.followup.send("Unexpected error on retry.", ephemeral=True)
                    return
            except Exception as e:
                log.error("Unexpected voice connect error: %s", e, exc_info=True)
                await ctx.followup.send("Unexpected error joining voice.", ephemeral=True)
                return

        session = VoiceSession(vc)
        self.bot.voice_sessions[guild_id] = session

        # Announce join
        if self.bot.cfg["behavior"].get("announce_when_joining", True):
            await self._play_tts(vc, "Hello.")

        # Start the voice pipeline
        from voice.pipeline import VoicePipeline
        pipeline = VoicePipeline(
            bot=self.bot,
            session=session,
            guild_id=guild_id,
        )
        import logging
        _log = logging.getLogger(__name__)

        session.pipeline_task = asyncio.create_task(pipeline.run())

        def _on_pipeline_done(t: asyncio.Task):
            if t.cancelled():
                return
            exc = t.exception()
            if exc:
                _log.error("Voice pipeline crashed: %s", exc, exc_info=exc)

        session.pipeline_task.add_done_callback(_on_pipeline_done)

        await ctx.followup.send(f"Joined **{channel.name}**. Prepare to be mocked.")

    # ── /leave ────────────────────────────────────────────────────────────────

    @discord.slash_command(name="leave", description="Kick JimBot out of voice.")
    async def leave(self, ctx: discord.ApplicationContext):
        guild_id = ctx.guild_id
        if guild_id not in self.bot.voice_sessions:
            await ctx.respond("I'm not even in a voice channel. Can't leave what you were never invited to.", ephemeral=True)
            return

        await self._cleanup_session(guild_id)
        clear_history(guild_id)
        await ctx.respond("Fine. I'll go. You'll miss me.")

    # ── /fix4006 ──────────────────────────────────────────────────────────────

    @discord.slash_command(name="fix4006", description="Clear a stale voice session that's causing 4006 errors.")
    async def fix4006(self, ctx: discord.ApplicationContext):
        """Force-clears the bot's voice state on Discord's end, then waits for the
        voice server session to expire so the next /join works cleanly."""
        await ctx.defer(ephemeral=True)
        guild_id = ctx.guild_id

        # Clean up any tracked session
        if guild_id in self.bot.voice_sessions:
            await self._cleanup_session(guild_id)

        # Disconnect pycord voice client if present
        existing_vc = ctx.guild.voice_client
        if existing_vc is not None:
            log.info("/fix4006: disconnecting existing pycord voice client")
            try:
                await existing_vc.disconnect(force=True)
            except Exception as exc:
                log.warning("/fix4006: disconnect error: %s", exc)

        # Force a gateway-level leave regardless of whether we think we're in voice
        log.info("/fix4006: sending gateway voice-leave")
        try:
            await ctx.guild.change_voice_state(channel=None)
        except Exception as exc:
            log.warning("/fix4006: change_voice_state failed: %s", exc)

        # Wait for Discord's voice server to expire the stale session (~5s is usually enough
        # after a clean leave signal; 4006 sessions from force-killed processes may need longer)
        log.info("/fix4006: waiting 6s for voice server session to expire")
        await asyncio.sleep(6)
        log.info("/fix4006: done")
        await ctx.followup.send(
            "Voice state cleared. Try `/join` now.",
            ephemeral=True,
        )

    # ── /mute ─────────────────────────────────────────────────────────────────

    @discord.slash_command(name="mute", description="Toggle JimBot's voice responses on/off.")
    async def mute(self, ctx: discord.ApplicationContext):
        guild_id = ctx.guild_id
        session = self.bot.voice_sessions.get(guild_id)
        if not session:
            await ctx.respond("I'm not in a voice channel right now.", ephemeral=True)
            return

        session.muted = not session.muted
        state = "muted" if session.muted else "unmuted"
        await ctx.respond(f"Voice responses {state}. Text commands still work.")

    # ── /savage ───────────────────────────────────────────────────────────────

    @discord.slash_command(name="savage", description="Set roast intensity (1=mild, 2=sarcastic, 3=brutal).")
    @option("level", description="1, 2, or 3", required=True, choices=[1, 2, 3])
    async def savage(self, ctx: discord.ApplicationContext, level: int):
        guild_id = ctx.guild_id
        session = self.bot.voice_sessions.get(guild_id)
        if session:
            session.savage_level = level
        else:
            # Apply globally even outside voice
            self.bot.cfg["behavior"]["savage_level"] = level

        labels = {1: "mild teasing", 2: "full sarcasm", 3: "BRUTAL"}
        await ctx.respond(f"Savage level set to **{level}** ({labels[level]}).")

    # ── /optout ───────────────────────────────────────────────────────────────

    @discord.slash_command(name="optout", description="Toggle whether JimBot roasts you in voice.")
    async def optout(self, ctx: discord.ApplicationContext):
        uid = ctx.author.id
        if uid in self.bot.opted_out:
            self.bot.opted_out.discard(uid)
            await ctx.respond("You're back in. Masochist.", ephemeral=True)
        else:
            self.bot.opted_out.add(uid)
            await ctx.respond("Fine, I'll leave you alone. For now.", ephemeral=True)

    # ── cleanup ───────────────────────────────────────────────────────────────

    async def _cleanup_session(self, guild_id: int) -> None:
        session = self.bot.voice_sessions.pop(guild_id, None)
        if session:
            if session.pipeline_task and not session.pipeline_task.done():
                session.pipeline_task.cancel()
                try:
                    await session.pipeline_task
                except (asyncio.CancelledError, Exception):
                    pass
            if session.vc.is_connected():
                await session.vc.disconnect()

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before, after):
        """Auto-disconnect if JimBot is left alone in the channel."""
        guild_id = member.guild.id
        session = self.bot.voice_sessions.get(guild_id)
        if not session:
            return

        vc_channel = session.vc.channel
        non_bot_members = [m for m in vc_channel.members if not m.bot]
        if len(non_bot_members) == 0:
            await self._cleanup_session(guild_id)
            clear_history(guild_id)


def setup(bot: commands.Bot):
    bot.add_cog(VoiceCog(bot))
