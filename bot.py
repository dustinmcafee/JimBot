import asyncio
import logging
import os
import sys
from pathlib import Path

import discord
from discord.ext import commands

from config_loader import load_config
from factory import build_llm, build_stt, build_tts

_SHUTDOWN_FLAG = Path(__file__).parent / "shutdown.flag"


async def _watch_shutdown(bot: commands.Bot) -> None:
    """Poll for a shutdown.flag file and do a clean voice disconnect before exit."""
    while not bot.is_closed():
        await asyncio.sleep(2)
        if _SHUTDOWN_FLAG.exists():
            log.info("Shutdown flag detected — disconnecting voice clients cleanly...")
            for vc in list(bot.voice_clients):
                try:
                    await vc.disconnect(force=True)
                    log.info("Voice disconnected in %s", getattr(vc.channel, "name", "?"))
                except Exception as exc:
                    log.warning("Voice disconnect error: %s", exc)
            try:
                _SHUTDOWN_FLAG.unlink()
            except OSError:
                pass
            log.info("Graceful shutdown complete — closing bot.")
            await bot.close()
            return

# Add local bin/ to PATH so ffmpeg/ffprobe are found without a system install
_BIN_DIR = Path(__file__).parent / "bin"
if _BIN_DIR.exists():
    os.environ["PATH"] = str(_BIN_DIR) + os.pathsep + os.environ["PATH"]


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("jimbot.log", encoding="utf-8"),
        ],
    )
    # Quiet noisy libs
    logging.getLogger("discord").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    # Voice pipeline debug
    logging.getLogger("voice.pipeline").setLevel(logging.DEBUG)


log = logging.getLogger(__name__)


def create_bot(cfg: dict) -> commands.Bot:
    intents = discord.Intents.default()
    intents.message_content = True
    intents.voice_states = True

    bot = commands.Bot(command_prefix=cfg["discord"].get("command_prefix", "!"), intents=intents)

    bot.cfg = cfg
    bot.llm = build_llm(cfg)
    bot.stt = build_stt(cfg)
    bot.tts = build_tts(cfg)

    bot.voice_sessions = {}  # guild_id -> VoiceSession
    bot.opted_out = set()    # user_ids who opted out of voice roasting

    @bot.event
    async def on_ready():
        await bot.sync_commands()
        log.info("JimBot online as %s (ID: %s)", bot.user, bot.user.id)
        log.info("  LLM : %s / %s", cfg["llm"]["provider"], cfg["llm"]["model"])
        log.info("  STT : %s", cfg["stt"]["provider"])
        log.info("  TTS : %s", cfg["tts"]["provider"])

        # Log any guilds where we're still shown in voice (will be handled on /join)
        for guild in bot.guilds:
            if guild.me and guild.me.voice:
                log.info("Stale voice presence in guild %s — will move on /join", guild.id)

        # Start the clean-shutdown watcher
        asyncio.create_task(_watch_shutdown(bot))

    @bot.event
    async def on_application_command_error(ctx: discord.ApplicationContext, error: Exception):
        log.error("Slash command error in /%s: %s", ctx.command.name, error, exc_info=True)
        msg = "Something broke. Even I'm embarrassed."
        try:
            if ctx.response.is_done():
                await ctx.followup.send(msg, ephemeral=True)
            else:
                await ctx.respond(msg, ephemeral=True)
        except Exception:
            pass

    return bot


def load_cogs(bot: commands.Bot) -> None:
    bot.load_extension("commands.text")
    bot.load_extension("commands.voice")


async def main() -> None:
    setup_logging()
    # Clear any leftover shutdown flag so we don't immediately re-trigger shutdown
    try:
        _SHUTDOWN_FLAG.unlink()
        log.info("Cleared leftover shutdown.flag")
    except FileNotFoundError:
        pass

    try:
        cfg = load_config()
    except ValueError as e:
        log.error("Config error: %s", e)
        sys.exit(1)

    bot = create_bot(cfg)
    load_cogs(bot)

    log.info("Starting JimBot...")
    try:
        await bot.start(cfg["discord_token"])
    except KeyboardInterrupt:
        pass
    finally:
        # Graceful shutdown: disconnect all voice clients so Discord expires
        # the session immediately rather than leaving it open for ~60 seconds.
        log.info("Shutting down — disconnecting voice clients...")
        for vc in bot.voice_clients:
            try:
                await vc.disconnect(force=True)
            except Exception:
                pass
        if not bot.is_closed():
            await bot.close()
        log.info("JimBot offline.")


if __name__ == "__main__":
    asyncio.run(main())
