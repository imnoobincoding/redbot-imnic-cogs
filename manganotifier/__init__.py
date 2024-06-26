from .manganotifier import MangaNotifier


async def setup(bot: Red):
    await bot.add_cog(MangaNotifier(bot))
