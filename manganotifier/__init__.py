from redbot.core.bot import Red
from .manganotifier import MangaNotifier


async def setup(bot):
    await bot.add_cog(MangaNotifier(bot))
