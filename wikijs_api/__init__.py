from redbot.core.bot import Red
from .wikijs_api import WikiJSCog

async def setup(bot: Red):
    """Adds the WikiJS cog to the bot."""
    cog = WikiJSCog(bot)
    bot.add_cog(cog, **cog.cog_options)
