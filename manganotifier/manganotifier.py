import discord
from discord.ext import tasks
from redbot.core import commands, Config
from redbot.core.bot import Red
import aiohttp


class MangaNotifier(commands.Cog):
    """Manga Notifier to get updates on new episodes"""

    def __init__(self, bot: Red):
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
                        await self.notify_new_episode(manga['name'], latest_episode, manga_update['url'], manga_update.get('cover_image'), manga_update.get('description'))
                        manga['last_episode'] = latest_episode
                        await self.config.manga_list.set(manga_list)

    async def check_mangadex(self, session, manga_name):
        url = f"https://api.mangadex.org/manga?title={manga_name}"
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    if data and 'data' in data:
                        manga_data = data['data']
                        if manga_data:
                            print(f"MangaDex response data: {manga_data}")
                            latest_chapter = None
                            cover_image = None
                            description = None
                            for manga in manga_data:
                                if 'attributes' in manga:
                                    latest_chapter = manga['attributes'].get(
                                        'latestChapter', '')
                                    cover_art_relationship = next(
                                        (rel for rel in manga['relationships'] if rel['type'] == 'cover_art'), None)
                                    if cover_art_relationship:
                                        cover_image_id = cover_art_relationship['id']
                                        cover_image = f"https://og.mangadex.org/og-image/manga/{cover_image_id}"
                                    description = manga['attributes'].get(
                                        'description', {}).get('en', 'No description available.')
                                    url = f"https://mangadex.org/title/{manga['id']}"
                                    break
                            if latest_chapter and latest_chapter.isdigit():
                                return {
                                    'latest_episode': int(latest_chapter),
                                    'cover_image': cover_image,
                                    'description': description,
                                    'url': url
                                }
                            else:
                                print(
                                    f"No valid latestChapter found for {manga_name}")
                    else:
                        print(
                            f"MangaDex response data not found or malformed: {data}")
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
                    if data and 'data' in data and 'Media' in data['data']:
                        media_data = data['data']['Media']
                        print(f"AniList response data: {media_data}")
                        chapters = media_data.get('chapters', 0)
                        if chapters:
                            return {'latest_episode': chapters}
                        else:
                            print(
                                f"No chapters found for {manga_name} in AniList response")
                    else:
                        print(
                            f"AniList response data not found or malformed: {data}")
                else:
                    print(
                        f"Failed to fetch from AniList: HTTP {response.status}")
        except aiohttp.ClientConnectorError as e:
            print(f"AniList API connection error: {e}")
        except Exception as e:
            print(f"Unexpected error: {e}")
        return None

    async def notify_new_episode(self, manga_name, episode, url, cover_image, description):
        channel_id = await self.config.channel_id()
        if channel_id:
            channel = self.bot.get_channel(channel_id)
            if channel:
                embed = discord.Embed(
                    title=f"New episode of {manga_name}",
                    description=description,
                    url=url,
                    color=discord.Color.blue()
                )
                if cover_image:
                    embed.set_image(url=cover_image)
                embed.add_field(name="Latest Episode",
                                value=f"Episode {episode}", inline=True)
                embed.set_footer(text="MangaNotifier")
                await channel.send(embed=embed)
            else:
                print(f"Channel ID {channel_id} not found.")
        else:
            print("Notification channel not set.")

    @commands.group()
    async def manganotifier(self, ctx):
        """Manage your manga list"""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @manganotifier.command(name="add")
    async def add(self, ctx, *, name: str):
        """Add a manga to the list and fetch its details"""
        manga_list = await self.config.manga_list()
        if any(m['name'].lower() == name.lower() for m in manga_list):
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
                embed = discord.Embed(
                    title="Manga Added",
                    description=f"Added {name} to the list with the latest episode {manga_update['latest_episode']}.",
                    color=discord.Color.green()
                )
                if manga_update.get('cover_image'):
                    embed.set_image(url=manga_update['cover_image'])
                await ctx.send(embed=embed)
            else:
                await ctx.send(f"Failed to fetch details for {name}.")

    @manganotifier.command(name="remove")
    async def remove(self, ctx, *, name: str):
        """Remove a manga from the list"""
        manga_list = await self.config.manga_list()
        manga_list = [m for m in manga_list if m['name'].lower()
                      != name.lower()]
        await self.config.manga_list.set(manga_list)
        embed = discord.Embed(

            title="Manga Removed",
            description=f"Removed {name} from the list.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)

    @manganotifier.command(name="list")
    async def list(self, ctx):
        """List all mangas"""
        manga_list = await self.config.manga_list()
        if not manga_list:
            await ctx.send("The manga list is empty.")
            return
        embed = discord.Embed(
            title="Manga List",
            description="\n".join(m['name'] for m in manga_list),
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed)

    @manganotifier.command(name="setchannel")
    async def setchannel(self, ctx, channel: discord.TextChannel):
        """Set the notification channel"""
        await self.config.channel_id.set(channel.id)
        embed = discord.Embed(
            title="Notification Channel Set",
            description=f"Notification channel set to {channel.mention}",
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed)

    @manganotifier.command(name="info")
    async def info(self, ctx, *, name: str):
        """Get information about a manga"""
        async with aiohttp.ClientSession() as session:
            manga_update = await self.check_mangadex(session, name)
            if not manga_update:
                manga_update = await self.check_fallback_api(session, name)
            if manga_update:
                embed = discord.Embed(
                    title=f"{name} Info",
                    description=f"Latest episode: {manga_update['latest_episode']}",
                    color=discord.Color.green()
                )
                if manga_update.get('cover_image'):
                    embed.set_image(url=manga_update['cover_image'])
                await ctx.send(embed=embed)
            else:
                await ctx.send(f"Failed to fetch details for {name}.")

    async def cog_unload(self):
        self.manga_check_loop.cancel()


async def setup(bot: Red):
    cog = MangaNotifier(bot)
    await bot.add_cog(cog)
    await cog.initialize()
