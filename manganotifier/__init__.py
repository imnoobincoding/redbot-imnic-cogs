from redbot.core import commands
from .manganotifier import MangaNotifier

__red_end_user_data_statement__ = "This cog does not persistently store data or metadata about users."


async def setup(bot: commands.Bot):
    n = MangaNotifier(bot)
    await bot.add_cog(n)
    await n.initialize()
