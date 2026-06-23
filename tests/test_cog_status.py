#!/usr/bin/env python3
"""Test case for the StatusCog (/status digest)"""

import logging
from unittest.mock import AsyncMock, patch

import discord

from redmine import synctime
from redmine.model import NamedId, Team
from redmine.tickets import TICKET_DUSTY_AGE
from netbot.netbot import NetBot
from netbot.cog_status import StatusCog, StatusView
from tests import test_utils


log = logging.getLogger(__name__)


def make_ticket(priority_name:str, days:int, assigned:bool=True, subject:str="Test ticket"):
    """Build a mock ticket with a controlled priority, age and assignee."""
    return test_utils.mock_ticket(
        subject=subject,
        priority=NamedId(1, priority_name),
        updated_on=synctime.ago(days=days),
        assigned_to=NamedId(5, "someone") if assigned else None,
    )


def sample_tickets() -> list:
    """6 tickets: high=1, normal=3, low=2, stale=2 (and 6 > page size -> 2 pages)."""
    stale = TICKET_DUSTY_AGE + 3
    fresh = 2
    return [
        make_ticket("High", fresh, assigned=False, subject="Update matrix server"),
        make_ticket("Normal", fresh, subject="Assignee field definition"),
        make_ticket("Normal", fresh, subject="LDAP apache server hangs"),
        make_ticket("Normal", stale, subject="Review quoted response"),   # stale #1
        make_ticket("Low", fresh, subject="Low priority item"),
        make_ticket("Low", stale, subject="Email-only users"),            # stale #2
    ]


class TestStatusFormatter(test_utils.MockBotTestCase):
    """Unit tests for the status formatter methods."""

    def setUp(self):
        super().setUp()
        self.bot = NetBot(self.redmine)
        self.formatter = self.bot.formatter

    def test_status_summary_counts(self):
        counts = self.formatter.status_summary(sample_tickets())
        self.assertEqual(counts["open"], 6)
        self.assertEqual(counts["high"], 1)
        self.assertEqual(counts["normal"], 3)
        self.assertEqual(counts["low"], 2)
        self.assertEqual(counts["stale"], 2)

    def test_status_bucket(self):
        self.assertEqual(self.formatter.status_bucket(make_ticket("High", 2)), "high")
        self.assertEqual(self.formatter.status_bucket(make_ticket("Normal", 2)), "normal")
        self.assertEqual(self.formatter.status_bucket(make_ticket("Low", 2)), "low")
        # stale takes precedence over priority
        self.assertEqual(self.formatter.status_bucket(make_ticket("High", TICKET_DUSTY_AGE + 1)), "stale")

    def test_status_embed_paging(self):
        tickets = sample_tickets()
        embed = self.formatter.status_embed("software-dev-team", tickets, page=0)
        self.assertEqual(embed.title, "software-dev-team — daily digest")
        self.assertEqual(embed.footer.text, "Page 1/2")

        fields = {f.name: f.value for f in embed.fields}
        self.assertEqual(fields["open"], "6")
        self.assertEqual(fields["high"], "1")
        self.assertIn("Needs attention", fields)
        # page 0 lists the first 5 of 6
        self.assertEqual(fields["Needs attention"].count("\n"), 4)

        # page 1 has the remaining single ticket
        embed2 = self.formatter.status_embed("software-dev-team", tickets, page=1)
        self.assertEqual(embed2.footer.text, "Page 2/2")
        fields2 = {f.name: f.value for f in embed2.fields}
        self.assertEqual(fields2["Needs attention"].count("\n"), 0)

    def test_status_line_detail(self):
        assigned = make_ticket("Normal", 5, assigned=True)
        unassigned = make_ticket("High", 1, assigned=False)
        self.assertIn("5d", self.formatter.status_line(assigned))
        self.assertIn("unassigned", self.formatter.status_line(unassigned))


class TestStatusView(test_utils.MockBotTestCase):
    """Tests for the pagination view."""

    def setUp(self):
        super().setUp()
        self.bot = NetBot(self.redmine)

    async def test_pagination_navigation(self):
        view = StatusView(self.bot.formatter, "software-dev-team", sample_tickets())
        self.assertEqual(view.total_pages, 2)
        self.assertTrue(view.prev_button.disabled)      # first page
        self.assertFalse(view.next_button.disabled)
        self.assertEqual(view.page_button.label, "Page 1/2")

        interaction = AsyncMock()
        await view.next_button.callback(interaction)
        self.assertEqual(view.page, 1)
        self.assertFalse(view.prev_button.disabled)
        self.assertTrue(view.next_button.disabled)      # last page
        self.assertEqual(view.page_button.label, "Page 2/2")
        interaction.response.edit_message.assert_called_once()

        # next on the last page clamps (button would be disabled in Discord)
        await view.next_button.callback(AsyncMock())
        self.assertEqual(view.page, 1)

        # prev returns to the first page
        await view.prev_button.callback(AsyncMock())
        self.assertEqual(view.page, 0)


class TestStatusCog(test_utils.MockBotTestCase):
    """StatusCog feature tests using the mock redmine session."""

    def setUp(self):
        super().setUp()
        self.bot = NetBot(self.redmine)
        self.bot.load_extension("netbot.cog_status")
        self.cog: StatusCog = self.bot.cogs["StatusCog"]

    async def test_status_mapped_channel(self):
        tickets = sample_tickets()
        team = Team(id=42, name="software-dev-team")
        ctx = self.mock_context()
        ctx.channel = self.mock_channel(1, "network-software")

        with patch.object(self.redmine.user_mgr, "get_team_by_name", return_value=team) as p_team, \
             patch.object(self.redmine.ticket_mgr, "tickets_for_team", return_value=tickets) as p_tix:
            await self.cog.status(ctx)

        p_team.assert_called_once_with("software-dev-team")
        p_tix.assert_called_once()
        ctx.respond.assert_called_once()
        embed = ctx.respond.call_args.kwargs["embed"]
        self.assertEqual(embed.title, "software-dev-team — daily digest")
        # more than one page of tickets -> a pagination view is attached.
        # (load_extension re-imports the module, so compare against the stable base class)
        self.assertIsInstance(ctx.respond.call_args.kwargs["view"], discord.ui.View)

    async def test_status_unmapped_channel(self):
        tickets = sample_tickets()
        ctx = self.mock_context()
        ctx.channel = self.mock_channel(2, "random-channel")

        with patch.object(self.redmine.ticket_mgr, "tickets", return_value=tickets) as p_tix:
            await self.cog.status(ctx)

        p_tix.assert_called_once()
        embed = ctx.respond.call_args.kwargs["embed"]
        self.assertEqual(embed.title, "all open — daily digest")

    async def test_status_no_tickets(self):
        ctx = self.mock_context()
        ctx.channel = self.mock_channel(3, "random-channel")

        with patch.object(self.redmine.ticket_mgr, "tickets", return_value=[]):
            await self.cog.status(ctx)

        ctx.respond.assert_called_once()
        msg = ctx.respond.call_args.args[0]
        self.assertIn("No open tickets", msg)

    async def test_status_single_page_no_view(self):
        # 3 tickets (<= page size) -> embed only, no pagination view
        tickets = sample_tickets()[:3]
        ctx = self.mock_context()
        ctx.channel = self.mock_channel(4, "random-channel")

        with patch.object(self.redmine.ticket_mgr, "tickets", return_value=tickets):
            await self.cog.status(ctx)

        self.assertNotIn("view", ctx.respond.call_args.kwargs)
