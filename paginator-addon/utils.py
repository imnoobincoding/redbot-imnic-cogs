
import asyncio
import json
import re
from typing import Literal, TypedDict, Union

import discord
import yaml
from redbot.core import commands
from redbot.core.utils import chat_formatting as cf
from redbot.core.utils import menus

__all__ = ["Page", "PageGroup", "StringToPage", "PastebinConverter", "PrivatebinConverter"]

# Page & Group type definitions
class Page(TypedDict, total=False):
    content: str
    embeds: list[discord.Embed]

class PageGroup(TypedDict):
    pages: list[Page]
    timeout: int
    reactions: Union[list[str], bool]
    delete_on_timeout: bool

# Regex for Pastebin
PASTEBIN_RE = re.compile(r"(?:https?://(?:www\.)?)?pastebin\.com/(?:raw/)?([a-zA-Z0-9]+)")

# Regex for PrivateBin
# Adjust your domain/instance if you have a unique pattern:
PRIVATEBIN_RE = re.compile(
    r"(?:https?://(?:www\.)?)?(?P<domain>[^/]+)/?\??(?P<paste_id>[a-zA-Z0-9_-]+)"
)


class StringToPage(commands.Converter[Page]):
    """
    Base converter for turning JSON/YAML strings into a Page (content + embeds).
    """

    def __init__(
        self, *, conversion_type: Literal["json", "yaml"] = "json", validate: bool = True
    ):
        self.CONVERSION_TYPES = {
            "json": self.load_from_json,
            "yaml": self.load_from_yaml,
        }
        self.validate = validate
        self.conversion_type = conversion_type.lower()
        try:
            self.converter = self.CONVERSION_TYPES[self.conversion_type]
        except KeyError as exc:
            raise ValueError(
                f"{conversion_type} is not a valid conversion type for Page conversion."
            ) from exc

    def __call__(self, *args, **kwargs):
        return self.convert(*args, **kwargs)

    async def convert(self, ctx: commands.Context, argument: str) -> Page:
        data = argument.strip("`")
        data = await self.converter(ctx, data)
        content = data.get("content")

        # Basic validation
        if not content and not data.get("embeds") and not data.get("embed"):
            raise commands.BadArgument(
                f"No 'content' or 'embeds' found in {self.conversion_type.upper()} data."
            )

        # If there's "embed" present, move it into "embeds"
        if data.get("embed") and data.setdefault("embeds", []):
            raise commands.BadArgument("Only one of `embed` or `embeds` can be used (not both).")

        # Convert single embed -> list of embeds
        if embed := data.pop("embed", None):
            data.setdefault("embeds", []).append(embed)

        # Alternatively if there's a list of embed dicts
        if embs := data.pop("embeds", []):
            if not isinstance(embs, list):
                raise commands.BadArgument("Expected 'embeds' to be a list of embed objects.")
            for embed_data in embs:
                e = await self.create_embed(ctx, embed_data)
                data.setdefault("embeds", []).append(e)

        # Validate final embed(s) length
        if len(data.get("embeds", [])) > 10:
            raise commands.BadArgument("Discord only supports up to 10 embeds per message.")

        if self.validate:
            await self.validate_data(ctx, data.get("embeds", []), content=content)

        return data

    async def load_from_json(self, ctx: commands.Context, data: str, **kwargs) -> dict:
        try:
            data = json.loads(data)
        except json.decoder.JSONDecodeError as error:
            await self.embed_convert_error(ctx, "JSON Parse Error", error)
        if not isinstance(data, dict):
            raise commands.BadArgument("The provided JSON does not represent a valid dictionary.")
        return data

    async def load_from_yaml(self, ctx: commands.Context, data: str, **kwargs) -> dict:
        try:
            data = yaml.safe_load(data)
        except Exception as error:
            await self.embed_convert_error(ctx, "YAML Parse Error", error)
        if not isinstance(data, dict):
            raise commands.BadArgument("The provided YAML does not represent a valid dictionary.")
        return data

    async def create_embed(self, ctx: commands.Context, data: dict):
        try:
            if timestamp := data.get("timestamp"):
                data["timestamp"] = timestamp.strip("Z")
            e = discord.Embed.from_dict(data)
            length = len(e)  # This checks embed length constraints
        except Exception as error:
            await self.embed_convert_error(ctx, "Embed Parse Error", error)

        if length > 6000:
            raise commands.BadArgument(
                f"Embed size exceeds Discord limit of 6000 characters ({length})."
            )
        return e

    async def validate_data(
        self, ctx: commands.Context, embeds: list[discord.Embed], *, content: str = None
    ):
        # Attempt a test send in ephemeral form
        try:
            await ctx.channel.send(content, embeds=embeds)
        except discord.errors.HTTPException as error:
            await self.embed_convert_error(ctx, "Embed Send Error", error)

    @staticmethod
    async def embed_convert_error(ctx: commands.Context, error_type: str, error: Exception):
        if await ctx.embed_requested():
            message = discord.Embed(
                color=await ctx.embed_color(),
                title=f"{error_type}: `{type(error).__name__}`",
                description=f"```py\n{error}\n```",
            )
            message.set_footer(
                text=f"Use `{ctx.prefix}help {ctx.command.qualified_name}` to see an example"
            )
        else:
            message = f"# {error_type}: {type(error).__name__}\n```py\n{error}\n```"
        asyncio.create_task(menus.menu(ctx, [message], {"❌": menus.close_menu}))
        raise commands.CheckFailure()


class PastebinMixin:
    async def convert(self, ctx: commands.Context, argument: str) -> str:
        match = PASTEBIN_RE.match(argument)
        if not match:
            raise commands.BadArgument(f"`{argument}` is not a valid Pastebin link.")
        paste_id = match.group(1)
        async with ctx.cog.session.get(f"https://pastebin.com/raw/{paste_id}") as resp:
            if resp.status != 200:
                raise commands.BadArgument(f"`{argument}` returned HTTP {resp.status}.")
            send_data = await resp.text()
        return await super().convert(ctx, send_data)


class PastebinConverter(PastebinMixin, StringToPage):
    """
    Converter for Pastebin -> JSON/YAML -> Page
    """


# ------------- PrivateBin Implementation -------------
import os
PRIVATEBIN_URL = os.getenv("PRIVATEBIN_URL", "https://your-privatebin-instance")
PRIVATEBIN_ENDPOINT = os.getenv("PRIVATEBIN_ENDPOINT", "api/v1/paste")

class PrivatebinMixin:
    async def convert(self, ctx: commands.Context, argument: str) -> str:
        # Attempt to parse the domain and paste ID from the argument
        match = PRIVATEBIN_RE.match(argument)
        if not match:
            raise commands.BadArgument(f"`{argument}` does not look like a valid PrivateBin link.")
        domain = match.group("domain")
        paste_id = match.group("paste_id")
        # Build the raw URL for your PrivateBin instance.
        # Adjust as needed if your PrivateBin doesn't use domain/<paste_id>
        # or if you rely on the environment variable specifically.
        # e.g. something like: f"{PRIVATEBIN_URL}/{PRIVATEBIN_ENDPOINT}/{paste_id}"
        # or, if the link is already a full 'raw' link, just do direct GET.

        # For demonstration, let's assume the user just pastes the full link:
        # "https://privatebin.domain/?pasteID..."
        # We'll do a direct GET on that link:
        async with ctx.cog.session.get(argument) as resp:
            if resp.status != 200:
                raise commands.BadArgument(
                    f"`{argument}` returned HTTP {resp.status} from PrivateBin."
                )
            send_data = await resp.text()

        # Now pass the data (json or yaml) upward for conversion
        return await super().convert(ctx, send_data)


class PrivatebinConverter(PrivatebinMixin, StringToPage):
    """
    Converter for PrivateBin -> JSON/YAML -> Page
    Detects a PrivateBin link, fetches raw data, 
    and delegates to StringToPage to parse it as JSON or YAML.
    """
