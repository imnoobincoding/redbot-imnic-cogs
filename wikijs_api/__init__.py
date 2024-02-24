from redbot.core import commands, Config, tasks
import discord

class WikiJSCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=52545658902) 
        default_guild = {"channel_id": None}
        self.config.register_guild(**default_guild)

    @commands.group()
    async def wikijs(self, ctx):
        """WikiJS-Befehle."""
        pass

    @wikijs.command(name="setchannel")
    async def set_channel(self, ctx, channel: discord.TextChannel):
        """Setzt den Discord-Channel für Benachrichtigungen."""
        await self.config.guild(ctx.guild).channel_id.set(channel.id)
        await ctx.send(f"Benachrichtigungs-Channel auf {channel.mention} gesetzt.")

    @commands.Cog.listener()
    async def on_ready(self):
        """Wird aufgerufen, wenn der Bot bereit ist."""
        await self.check_wikijs_changes.start()

    @tasks.loop(minutes=5)  # Überprüfe alle 5 Minuten
    async def check_wikijs_changes(self):
        api_key = await self.config.user(self.bot.user).api_key()
        wiki_url = await self.config.user(self.bot.user).wiki_url()
        channel_id = await self.config.guild(self.bot.guilds[0]).channel_id()
        channel = self.bot.get_channel(channel_id)
        if channel:
            embed = discord.Embed(title="WikiJS-Änderung", description=f"Die Seite {page_name} wurde geändert.")
            embed.add_field(name="Link", value=f"{wiki_url}/{page_name}")
            await channel.send(embed=embed)
        else:
            print(f"Channel mit ID {channel_id} nicht gefunden.")

def setup(bot):
    bot.add_cog(WikiJSCog(bot))
