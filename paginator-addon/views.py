from typing import List

import discord
from discord.ui import Button, Select, View
from redbot.core import commands

from .utils import Page


class ViewDisableOnTimeout(View):
    def __init__(self, **kwargs):
        self.message: discord.Message = None
        self.ctx: commands.Context = kwargs.pop("ctx", None)
        self.timeout_message: str = kwargs.pop("timeout_message", None)
        super().__init__(**kwargs)

    async def on_timeout(self):
        if self.message:
            disable_items(self)
            await self.message.edit(view=self)
            if self.timeout_message and self.ctx:
                await self.ctx.send(self.timeout_message)
        self.stop()


def disable_items(self: View):
    for i in self.children:
        i.disabled = True


async def interaction_check(ctx: commands.Context, interaction: discord.Interaction):
    if not ctx.author.id == interaction.user.id:
        await interaction.response.send_message(
            "You aren't allowed to interact with this. Back off!", ephemeral=True
        )
        return False
    return True


class CloseButton(Button):
    def __init__(self):
        super().__init__(style=discord.ButtonStyle.red, label="Close", emoji="❎")

    async def callback(self, interaction: discord.Interaction):
        await self.view.message.delete()
        self.view.stop()


class PaginatorButton(Button):
    def __init__(self, *, emoji=None, label=None):
        super().__init__(style=discord.ButtonStyle.green, label=label, emoji=emoji)


class ForwardButton(PaginatorButton):
    def __init__(self):
        super().__init__(emoji="\N{BLACK RIGHT-POINTING TRIANGLE}\N{VARIATION SELECTOR-16}")

    async def callback(self, interaction: discord.Interaction):
        if self.view.index == len(self.view.contents) - 1:
            self.view.index = 0
        else:
            self.view.index += 1
        await self.view.edit_message(interaction)


class BackwardButton(PaginatorButton):
    def __init__(self):
        super().__init__(emoji="\N{BLACK LEFT-POINTING TRIANGLE}\N{VARIATION SELECTOR-16}")

    async def callback(self, interaction: discord.Interaction):
        if self.view.index == 0:
            self.view.index = len(self.view.contents) - 1
        else:
            self.view.index -= 1
        await self.view.edit_message(interaction)


class LastItemButton(PaginatorButton):
    def __init__(self):
        super().__init__(
            emoji="\N{BLACK RIGHT-POINTING DOUBLE TRIANGLE WITH VERTICAL BAR}\N{VARIATION SELECTOR-16}"
        )

    async def callback(self, interaction: discord.Interaction):
        self.view.index = len(self.view.contents) - 1
        await self.view.edit_message(interaction)


class FirstItemButton(PaginatorButton):
    def __init__(self):
        super().__init__(
            emoji="\N{BLACK LEFT-POINTING DOUBLE TRIANGLE WITH VERTICAL BAR}\N{VARIATION SELECTOR-16}"
        )

    async def callback(self, interaction: discord.Interaction):
        self.view.index = 0
        await self.view.edit_message(interaction)


class PageButton(Button):
    def __init__(self):
        super().__init__(style=discord.ButtonStyle.gray, disabled=True)

    def _change_label(self):
        self.label = f"Page {self.view.index + 1}/{len(self.view.contents)}"


class PaginatorSelect(Select):
    def __init__(self, *, placeholder: str = "Select a page:", length: int):
        options = [
            discord.SelectOption(label=f"{i+1}", value=str(i), description=f"Go to page {i+1}")
            for i in range(length)
        ]
        super().__init__(options=options, placeholder=placeholder)

    async def callback(self, interaction: discord.Interaction):
        self.view.index = int(self.values[0])
        await self.view.edit_message(interaction)


class PaginationView(ViewDisableOnTimeout):
    def __init__(
        self,
        context: commands.Context,
        contents: List[Page],
        timeout: int = 30,
        use_select: bool = False,
        delete_on_timeout: bool = False,
    ):
        super().__init__(timeout=timeout, ctx=context, timeout_message=None)
        self.ctx = context
        self.contents = contents
        self.use_select = use_select
        self.delete_on_timeout = delete_on_timeout
        self.index = 0

        if self.use_select and len(self.contents) > 1:
            self.add_item(PaginatorSelect(placeholder="Select a page:", length=len(contents)))

        buttons_to_add = []
        if len(self.contents) == 1:
            # Single page -> just a Close button
            pass
        elif len(self.contents) == 2:
            # Minimal nav needed
            buttons_to_add = [BackwardButton, PageButton, ForwardButton]
        else:
            # Full suite
            buttons_to_add = [FirstItemButton, BackwardButton, PageButton, ForwardButton, LastItemButton]

        for btn_cls in buttons_to_add:
            self.add_item(btn_cls())
        self.add_item(CloseButton())
        self.update_items()

    def update_items(self):
        for item in self.children:
            if isinstance(item, PageButton):
                item._change_label()
            elif isinstance(item, FirstItemButton):
                item.disabled = self.index == 0
            elif isinstance(item, LastItemButton):
                item.disabled = self.index == len(self.contents) - 1

    async def start(self, index=None):
        if index is not None:
            self.index = index
        page = self.current_page()
        self.message = await self.ctx.send(**page, view=self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return await interaction_check(self.ctx, interaction)

    def current_page(self):
        return self.contents[self.index]

    async def edit_message(self, inter: discord.Interaction):
        self.update_items()
        page = self.current_page()
        await inter.response.edit_message(**page, view=self)

    async def on_timeout(self):
        if self.delete_on_timeout:
            await self.message.delete()
        else:
            await super().on_timeout()
