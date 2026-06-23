#!/usr/bin/env python3

"""Discord /status command: a per-team open-ticket digest."""

import logging

import discord
from discord.ext import commands

from redmine.redmine import Client
from redmine.tickets import DEFAULT_SORT
from netbot.netbot import NetBot, TEAM_MAPPING
from netbot.formatting import DiscordFormatter, STATUS_PER_PAGE


log = logging.getLogger(__name__)


def setup(bot:NetBot):
    bot.add_cog(StatusCog(bot))


class StatusView(discord.ui.View):
    """Paginated controls for the /status digest."""
    def __init__(self, formatter:DiscordFormatter, title:str, tickets:list,
                 per_page:int=STATUS_PER_PAGE, timeout:float=300):
        super().__init__(timeout=timeout)
        self.formatter = formatter
        self.title = title
        self.tickets = tickets
        self.per_page = per_page
        self.page = 0
        self.total_pages = max(1, (len(tickets) + per_page - 1) // per_page)
        self._sync_buttons()


    def _sync_buttons(self):
        """Update button labels and enabled state for the current page."""
        self.prev_button.disabled = self.page <= 0
        self.next_button.disabled = self.page >= self.total_pages - 1
        self.page_button.label = f"Page {self.page + 1}/{self.total_pages}"


    async def _refresh(self, interaction:discord.Interaction):
        self._sync_buttons()
        embed = self.formatter.status_embed(self.title, self.tickets, self.page, self.per_page)
        await interaction.response.edit_message(embed=embed, view=self)


    @discord.ui.button(label="◀ Prev", style=discord.ButtonStyle.secondary)
    async def prev_button(self, button:discord.ui.Button, interaction:discord.Interaction):
        if self.page > 0:
            self.page -= 1
        await self._refresh(interaction)


    @discord.ui.button(label="Page 1/1", style=discord.ButtonStyle.secondary, disabled=True)
    async def page_button(self, button:discord.ui.Button, interaction:discord.Interaction):
        # disabled page indicator; never invoked
        pass


    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary)
    async def next_button(self, button:discord.ui.Button, interaction:discord.Interaction):
        if self.page < self.total_pages - 1:
            self.page += 1
        await self._refresh(interaction)


class StatusCog(commands.Cog):
    """Cog for the /status open-ticket digest."""
    def __init__(self, bot:NetBot):
        self.bot:NetBot = bot
        self.redmine: Client = bot.redmine


    def resolve_scope(self, ctx: discord.ApplicationContext) -> tuple[str, list]:
        """Determine the digest title and ticket list from the channel.

        Mapped team channel -> that team's open tickets; otherwise all open tickets.
        """
        ch_name = ctx.channel.name
        if ch_name in TEAM_MAPPING:
            team_name = TEAM_MAPPING[ch_name]
            team = self.redmine.user_mgr.get_team_by_name(team_name)
            if team:
                return team_name, self.redmine.ticket_mgr.tickets_for_team(team)

        # fallback: all open tickets, no group filter
        tickets = self.redmine.ticket_mgr.tickets(status_id="open", sort=DEFAULT_SORT, limit=100)
        return "all open", tickets


    @discord.slash_command(name="status", description="Open-ticket digest for this channel's team")
    async def status(self, ctx: discord.ApplicationContext):
        """Show an open-ticket digest scoped to the current channel's team."""
        title, tickets = self.resolve_scope(ctx)

        if not tickets:
            await ctx.respond(f"No open tickets for **{title}**.")
            return

        embed = self.bot.formatter.status_embed(title, tickets, 0)
        if len(tickets) > STATUS_PER_PAGE:
            view = StatusView(self.bot.formatter, title, tickets)
            await ctx.respond(embed=embed, view=view)
        else:
            await ctx.respond(embed=embed)
