#!/usr/bin/env python3
"""Test case for the TicketsCog"""

import unittest
import logging
import re
from unittest.mock import MagicMock

import discord
from dotenv import load_dotenv

from netbot.netbot import NetBot
from netbot.cog_tickets import TicketsCog, get_priorities, get_trackers
from tests import test_utils


log = logging.getLogger(__name__)


@unittest.skipUnless(load_dotenv(), "ENV settings not available")
class TestTicketsCog(test_utils.BotTestCase):
    """Test suite for TicketsCog"""

    def setUp(self):
        super().setUp()
        self.bot: NetBot = NetBot(self.redmine)
        self.bot.load_extension("netbot.cog_tickets")
        self.cog: TicketsCog = self.bot.cogs["TicketsCog"]


    def parse_markdown_link(self, text:str) -> tuple[str, str]:
        regex = r"\[`#(\d+)`\]\((.+)\)"
        m = re.search(regex, text)
        self.assertIsNotNone(m, f"could not find ticket number in response str: {text}")

        ticket_id = m.group(1)
        url = m.group(2)
        return ticket_id, url


    @unittest.skip
    async def test_new_ticket(self):
        # create ticket with discord user, assert
        test_title = f"This is a test ticket {self.tag}"
        ctx = self.build_context()
        ctx.channel = unittest.mock.AsyncMock(discord.TextChannel)
        ctx.channel.name = f"channel-{self.tag}"
        ctx.channel.id = 4321

        await self.cog.create_new_ticket(ctx, test_title)
        response_str = ctx.respond.call_args.args[0]

        ticket_id, url = self.parse_markdown_link(response_str)
        log.debug(f"created ticket: {ticket_id}, {url}")

        # get the ticket using id
        ctx = self.build_context()
        await self.cog.query(ctx, ticket_id)
        response_str = ctx.respond.call_args.args[0]
        self.assertIn(ticket_id, response_str)
        self.assertIn(url, response_str)

        # get the ticket using tag
        ctx = self.build_context()
        await self.cog.query(ctx, self.tag)
        response_str = ctx.respond.call_args.args[0]
        self.assertIn(ticket_id, response_str)
        self.assertIn(url, response_str)

        # assign the ticket
        ctx = self.build_context()
        await self.cog.assign(ctx, ticket_id)
        response_str = ctx.respond.call_args.args[0]
        self.assertIn(ticket_id, response_str)
        self.assertIn(url, response_str)
        self.assertIn(test_title, response_str)

        # "progress" the ticket, setting it in-progress and assigning it to "me"
        ctx = self.build_context()
        await self.cog.progress(ctx, ticket_id)
        response_str = ctx.respond.call_args.args[0]
        self.assertIn(ticket_id, response_str)
        self.assertIn(url, response_str)
        self.assertIn(test_title, response_str)

        # resolve the ticket
        ctx = self.build_context()
        await self.cog.resolve(ctx, ticket_id)
        response_str = ctx.respond.call_args.args[0]
        self.assertIn(ticket_id, response_str)
        self.assertIn(url, response_str)
        self.assertIn(test_title, response_str)

        # delete ticket with redmine api, assert
        self.redmine.ticket_mgr.remove(int(ticket_id))
        # check that the ticket has been removed
        self.assertIsNone(self.redmine.ticket_mgr.get(int(ticket_id)))

    @unittest.skip
    async def test_ticket_unassign(self):
        ticket = self.create_test_ticket()

        # unassign the ticket
        ctx = self.build_context()
        await self.cog.unassign(ctx, ticket.id)
        response_str = ctx.respond.call_args.args[0]
        self.assertIn(str(ticket.id), response_str)

        # delete ticket with redmine api, assert
        self.redmine.ticket_mgr.remove(int(ticket.id))
        self.assertIsNone(self.redmine.ticket_mgr.get(int(ticket.id)))


    @unittest.skip
    async def test_ticket_collaborate(self):
        ticket = self.create_test_ticket()

        # add a collaborator
        ctx = self.build_context()
        await self.cog.collaborate(ctx, ticket.id)
        response_str = ctx.respond.call_args.args[0]
        self.assertIn(str(ticket.id), response_str)

        # delete ticket with redmine api, assert
        self.redmine.ticket_mgr.remove(ticket.id)
        self.assertIsNone(self.redmine.ticket_mgr.get(int(ticket.id)))

    # create thread/sync
    async def test_thread_sync(self):
        # create a ticket and add a note
        note = f"This is a test note tagged with {self.tag}"
        ticket = self.create_test_ticket()
        self.redmine.ticket_mgr.append_message(ticket.id, self.user.login, note)

        # thread the ticket using
        ctx = self.build_context()
        ctx.channel = unittest.mock.AsyncMock(discord.TextChannel)
        ctx.channel.name = f"Test Channel {self.tag}"

        thread = unittest.mock.AsyncMock(discord.Thread)
        thread.name = f"Ticket #{ticket.id}: {ticket.subject}"

        ctx.channel.create_thread = unittest.mock.AsyncMock(return_value=thread)

        # TODO setup history with a message from the user - disabled while I work out the history mock.
        #thread.history = unittest.mock.AsyncMock(name="history")
        #thread.history.flatten = unittest.mock.AsyncMock(name="flatten", return_value=[message])

        await self.cog.thread(ctx, ticket.id)

        thread_response = str(ctx.channel.create_thread.call_args) # FIXME
        self.assertIn(str(ticket.id), thread_response)
        self.assertIn(ticket.subject, thread_response)

        # delete the ticket
        self.redmine.ticket_mgr.remove(ticket.id)


    async def test_query_term(self):
        ticket = self.create_test_ticket()

        # expected results:
        # 1. ticket ID
        result_1 = self.cog.resolve_query_term(ticket.id)
        self.assertEqual(ticket.id, result_1[0].id)

        # 2. ticket team
        # FIXME not stable, returns oldest intake, not newest
        #result_2 = self.cog.resolve_query_term("ticket-intake")
        #self.assertEqual(ticket.id, result_2[0].id)

        # 3. ticket user
        #result_3 = self.cog.resolve_query_term(self.user.login)
        #self.assertEqual(0, len(result_3)) # NOTHING ASSIGNED TO NEW TEST USER

        # 4. ticket query term
        #result_4 = self.cog.resolve_query_term(self.tag)
        #self.assertEqual(ticket.id, result_4[0].id)

        # delete the ticket
        self.redmine.ticket_mgr.remove(ticket.id)


    async def test_resolve_invalid_discord_user(self):
        ticket = self.create_test_ticket()

        ctx = self.build_context()
        test_name = "not-the-test-user" # invalid discord user
        ctx.user.name = test_name

        await self.cog.resolve(ctx, ticket.id)
        self.assertIn(test_name, ctx.respond.call_args.args[0])
        self.assertIn("/scn add", ctx.respond.call_args.args[0])


    async def test_unassign_invalid_discord_user(self):
        ticket = self.create_test_ticket()

        ctx = self.build_context()
        test_name = "not-the-test-user" # invalid discord user
        ctx.user.name = test_name

        await self.cog.unassign(ctx, ticket.id)
        self.assertIn(test_name, ctx.respond.call_args.args[0])
        self.assertIn("/scn add", ctx.respond.call_args.args[0])


    async def test_progress_invalid_discord_user(self):
        ticket = self.create_test_ticket()

        ctx = self.build_context()
        test_name = "not-the-test-user" # invalid discord user
        ctx.user.name = test_name

        await self.cog.progress(ctx, ticket.id)
        self.assertIn(test_name, ctx.respond.call_args.args[0])
        self.assertIn("/scn add", ctx.respond.call_args.args[0])


    async def test_assign_invalid_discord_user(self):
        ticket = self.create_test_ticket()

        ctx = self.build_context()
        test_name = "not-the-test-user" # invalid discord user
        ctx.user.name = test_name

        await self.cog.assign(ctx, ticket.id)
        self.assertIn(test_name, ctx.respond.call_args.args[0])
        self.assertIn("/scn add", ctx.respond.call_args.args[0])


    async def test_create_invalid_discord_user(self):
        ctx = self.build_context()
        test_name = "not-the-test-user" # invalid discord user
        ctx.user.name = test_name

        await self.cog.create_new_ticket(ctx, "test title")
        self.assertIn(test_name, ctx.respond.call_args.args[0])
        self.assertIn("/scn add", ctx.respond.call_args.args[0])


    async def test_get_trackers(self):
        ctx = MagicMock(discord.AutocompleteContext)
        ctx.bot = self.bot
        ctx.value = ""
        trackers = get_trackers(ctx)
        self.assertTrue("Software-Dev" in trackers)

        ctx.value = "Ext"
        trackers = get_trackers(ctx)
        self.assertTrue("External-Comms-Intake" in trackers)


    async def test_get_priorities(self):
        ctx = MagicMock(discord.AutocompleteContext)
        ctx.bot = self.bot
        ctx.value = ""
        priorities = get_priorities(ctx)
        self.assertTrue("EPIC" in priorities)

        ctx.value = "Lo"
        priorities = get_priorities(ctx)
        self.assertTrue("Low" in priorities)


    async def test_new_epic_use_case(self):
        #setup_logging()

        # build the context
        ctx = self.build_context()
        ctx.channel = unittest.mock.AsyncMock(discord.TextChannel)
        ctx.channel.name = f"channel-{self.tag}"
        ctx.channel.id = 4242

        # create a new epic
        await self.cog.create_new_ticket(ctx, f"test_new_epic_use_case {self.tag}")
        response_str = ctx.respond.call_args.args[0]

        ticket_id, url = self.parse_markdown_link(response_str)
        log.debug(f"created ticket: {ticket_id}, {url}")

        # set the priority
        await self.cog.priority(ctx, ticket_id, "EPIC")

        # get the ticket and validate priority
        check = self.redmine.ticket_mgr.get(int(ticket_id))
        self.assertIsNotNone(check)
        self.assertEqual(check.priority.name, "EPIC")

        # create ticket thread context
        ctx2 = self.build_context()
        ctx2.channel = unittest.mock.AsyncMock(discord.TextChannel)
        ctx2.channel.name = f"Ticket #{ticket_id}"
        ctx2.channel.id = 4242

        # create a sub-ticket
        await self.cog.create_new_ticket(ctx2, f"sub1 test_new_epic_use_case {self.tag}")
        response_str = ctx2.respond.call_args.args[0]
        sub1_id, url = self.parse_markdown_link(response_str)
        log.debug(f"created sub-ticket of ticket {ticket_id}: {sub1_id}, {url}")

        # confirm the parent
        check2 = self.redmine.ticket_mgr.get(int(sub1_id))
        self.assertIsNotNone(check2)
        self.assertIsNotNone(check2.parent, f"Ticket #{check2.id} has no parent.")
        self.assertEqual(check2.parent.id, int(ticket_id))

        # delete all the tickets
        self.redmine.ticket_mgr.remove(int(ticket_id))
        #self.redmine.ticket_mgr.remove(int(sub1_id))
        # check they've been removed
        self.assertIsNone(self.redmine.ticket_mgr.get(int(ticket_id)))
        self.assertIsNone(self.redmine.ticket_mgr.get(int(sub1_id)))
