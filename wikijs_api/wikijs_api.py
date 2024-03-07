import asyncio
import aiohttp
import discord
from redbot.core import commands, Config
from discord.ext import tasks
from datetime import datetime

class WikiJSCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=self.qualified_name)
        default_guild = {"channel_id": None, "last_update": None}
        self.config.register_guild(**default_guild)
        self.cog_options = {
            "command_prefix": "wikijs",
            "db_url": None,
            "red_context": True,
            "red_environment": True,
        }

    @commands.group()
    async def wikijs(self, ctx):
        """WikiJS-Befehle."""
        pass

    @wikijs.command(name="setchannel")
    async def set_channel(self, ctx, channel: discord.TextChannel):
        """Setzt den Discord-Channel für Benachrichtigungen."""
        await self.config.guild(ctx.guild).channel_id.set(channel.id)
        await ctx.send(f"Benachrichtigungs-Channel auf {channel.mention} gesetzt.")

    @wikijs.command(name="setapikey")
    async def set_api_key(self, ctx, api_key: str):
        """Setzt den API-Schlüssel für die WikiJS-API."""
        await self.config.guild(ctx.guild).api_key.set(api_key)
        await ctx.send("API-Schlüssel erfolgreich gesetzt.")

    @wikijs.command(name="setwikiurl")
    async def set_wiki_url(self, ctx, wiki_url: str):
        """Setzt die URL der WikiJS-Website."""
        await self.config.guild(ctx.guild).wiki_url.set(wiki_url)
        await ctx.send("Wiki-URL erfolgreich gesetzt.")

    @commands.Cog.listener()
    async def on_ready(self):
        """Wird aufgerufen, wenn der Bot bereit ist."""
        await self.check_wikijs_changes.start()

    @tasks.loop(minutes=5)
    async def check_wikijs_changes(self):
        print("Loop check_wikijs_changes aufgerufen")
        api_key = await self.config.user(self.bot.user).api_key()
        wiki_url = await self.config.user(self.bot.user).wiki_url()
        guild = self.bot.guilds[0]
        channel_id = await self.config.guild(guild).channel_id()
        last_update = await self.config.guild(guild).last_update()

        if channel_id is None or last_update is None:
            return

        channel = guild.get_channel(channel_id)
        if not channel:
            return

        # Führe eine API-Anfrage an WikiJS durch
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(f"{wiki_url}/api/recent-changes?api_key={api_key}") as response:
                    data = await response.json()
                    # Verarbeite die API-Antwort und erstelle ein Embed
                    # Beispiel: Extrahiere die neuesten Änderungen und erstelle ein Embed
                    changes = data.get("changes", [])
                    if changes:
                        embed = discord.Embed(title="WikiJS-Updates", description="Hier sind die neuesten Änderungen:")
                        for change in changes:
                            title = change.get("title", "Unbekannter Artikel")
                            url = f"{wiki_url}/page/{title}"
                            embed.add_field(name=title, value=f"Link zum Artikel", inline=False)
                        await channel.send(embed=embed)
            except Exception as e:
                print(f"Fehler bei der API-Anfrage: {e}")

        # Speichere das aktuelle Datum als letztes Update
        await self.config.guild(guild).last_update.set(str(datetime.now()))
