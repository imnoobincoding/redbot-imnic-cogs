import discord
from discord.ext import tasks, commands
from redbot.core import Config
from redbot.core.bot import Red
import aiohttp


class MangaNotifier(commands.Cog):
    """Manga Notifier to get updates on new episodes"""

    def __init__(self, bot: Red):
        super().__init__()
        self.bot = bot
        self.config = Config.get_conf(
            self, identifier=7852384562, force_registration=True)
        self.config.register_global(manga_list=[], channel_id=None)
        self.manga_check_loop.start()

    async def initialize(self):
        pass

    @tasks.loop(minutes=30)
    async def manga_check_loop(self):
        async with aiohttp.ClientSession() as session:
            manga_list = await self.config.manga_list()
            for manga in manga_list:
                manga_update = await self.check_mangadex(session, manga['name'])
                if not manga_update:
                    manga_update = await self.check_fallback_api(session, manga['name'])

                if manga_update:
                    latest_episode = manga_update.get('latest_episode', 0)
                    if latest_episode > manga['last_episode']:
                        await self.notify_new_episode(manga['name'], latest_episode)
                        manga['last_episode'] = latest_episode
                        await self.config.manga_list.set(manga_list)

    async def check_mangadex(self, session, manga_name):
        url = f"https://api.mangadex.org/manga?title={manga_name}"
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return {'latest_episode': data.get('latestChapter', 0)}
                else:
                    print(
                        f"Failed to fetch from MangaDex: HTTP {response.status}")
        except aiohttp.ClientConnectorError as e:
            print(f"MangaDex API connection error: {e}")
        except Exception as e:
            print(f"Unexpected error: {e}")
        return None

    async def check_fallback_api(self, session, manga_name):
        query = """
        query ($search: String) {
          Media(search: $search, type: MANGA) {
            id
            chapters
          }
        }
        """
        variables = {'search': manga_name}
        url = 'https://graphql.anilist.co'
        try:
            async with session.post(url, json={'query': query, 'variables': variables}) as response:
                if response.status == 200:
                    data = await response.json()
                    chapters = data['data']['Media'].get('chapters', 0)
                    return {'latest_episode': chapters}
                else:
                    print(
                        f"Failed to fetch from AniList: HTTP {response.status}")
        except aiohttp.ClientConnectorError as e:
            print(f"AniList API connection error: {e}")
        except Exception as e:
            print(f"Unexpected error: {e}")
        return None

    async def notify_new_episode(self, manga_name, episode):
        channel_id = await self.config.channel_id()
        if channel_id:
            channel = self.bot.get_channel(channel_id)
            if channel:
                await channel.send(f"New episode of {manga_name}: Episode {episode}")
            else:
                print(f"Channel ID {channel_id} not found.")
        else:
            print("Notification channel not set.")

    @commands.group()
    async def manga(self, ctx):
        """Manage your manga list"""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @manga.command(name="add")
    async def add(self, ctx, name: str):
        """Add a manga to the list and fetch its details"""
        manga_list = await self.config.manga_list()
        if any(m['name'] == name for m in manga_list):
            await ctx.send(f"{name} is already in the list.")
            return

        async with aiohttp.ClientSession() as session:
            manga_update = await self.check_mangadex(session, name)
            if not manga_update:
                manga_update = await self.check_fallback_api(session, name)
            if manga_update:
                manga_list.append(
                    {'name': name, 'last_episode': manga_update['latest_episode']})
                await self.config.manga_list.set(manga_list)
                await ctx.send(f"Added {name} to the list with latest episode {manga_update['latest_episode']}.")
            else:
                await ctx.send(f"Failed to fetch details for {name}.")

    @manga.command(name="remove")
    async def remove(self, ctx, name: str):
        """Remove a manga from the list"""
        manga_list = await self.config.manga_list()
        manga_list = [m for m in manga_list if m['name'] != name]
        await self.config.manga_list.set(manga_list)
        await ctx.send(f"Removed {name} from the list.")

    @manga.command(name="list")
    async def list(self, ctx):
        """List all mangas"""
        manga_list = await self.config.manga_list()
        if not manga_list:
            await ctx.send("The manga list is empty.")
            return
        await ctx.send("\n".join(m['name'] for m in manga_list))

    @manga.command(name="setchannel")
    async def setchannel(self, ctx, channel: discord.TextChannel):
        """Set the notification channel"""
        await self.config.channel_id.set(channel.id)
        await ctx.send(f"Notification channel set to {channel.mention}")

    @manga.command(name="info")
    async def info(self, ctx, name: str):
        """Get information about a manga"""
        async with aiohttp.ClientSession() as session:
            manga_update = await self.check_mangadex(session, name)
            if not manga_update:
                manga_update = await self.check_fallback_api(session, name)
            if manga_update:
                await ctx.send(f"{name} latest episode is {manga_update['latest_episode']}.")
            else:
                await ctx.send(f"Failed to fetch details for {name}.")

    async def cog_unload(self):
        self.manga_check_loop.cancel()


async def setup(bot: Red):
    cog = MangaNotifier(bot)
    await bot.add_cog(cog)
    await cog.initialize()
