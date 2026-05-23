import discord
from discord.ext import commands
from discord import option

from personality import generate_roast


class TextCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── Slash command: /roast ─────────────────────────────────────────────────

    @discord.slash_command(name="roast", description="Make JimBot roast a message or person.")
    @option("target", description="What or who to roast", required=True)
    async def roast(self, ctx: discord.ApplicationContext, target: str):
        await ctx.defer()
        reply = await generate_roast(
            llm=self.bot.llm,
            text=target,
            savage_level=self.bot.cfg["behavior"]["savage_level"],
            speaker_name=ctx.author.display_name,
            guild_id=ctx.guild_id or 0,
        )
        await ctx.followup.send(reply)

    # ── Slash command: /ping ───────────────────────────────────────────────────

    @discord.slash_command(name="ping", description="Check if JimBot is alive.")
    async def ping(self, ctx: discord.ApplicationContext):
        await ctx.respond(
            f"Still alive, unfortunately. Latency: {round(self.bot.latency * 1000)}ms"
        )

    # ── @mention handler ──────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if self.bot.user not in message.mentions:
            return

        text = message.clean_content.replace(f"@{self.bot.user.display_name}", "").strip()
        if not text:
            text = "nothing useful"

        async with message.channel.typing():
            reply = await generate_roast(
                llm=self.bot.llm,
                text=text,
                savage_level=self.bot.cfg["behavior"]["savage_level"],
                speaker_name=message.author.display_name,
                guild_id=message.guild.id if message.guild else 0,
            )
        await message.reply(reply, mention_author=False)


def setup(bot: commands.Bot):
    bot.add_cog(TextCog(bot))
