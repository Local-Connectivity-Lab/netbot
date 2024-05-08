#!/usr/bin/env python3
"""Test case for the TicketsCog"""

import unittest
import logging
import re

import discord
from dotenv import load_dotenv

from netbot import NetBot
import test_utils


logging.getLogger().setLevel(logging.ERROR)


log = logging.getLogger(__name__)


@unittest.skipUnless(load_dotenv(), "ENV settings not available")
class TestTicketsCog(test_utils.BotTestCase):
    """Test suite for TicketsCog"""

    def setUp(self):
        super().setUp()
        self.bot = NetBot(self.redmine)
        self.bot.load_extension("cog_tickets")
        self.cog = self.bot.cogs["TicketsCog"] # Note class name, note filename.


    def parse_markdown_link(self, text:str) -> tuple[str, str]:
        regex = r"\[`#(\d+)`\]\((.+)\)"
        m = re.search(regex, text)
        self.assertIsNotNone(m, f"could not find ticket number in response str: {text}")

        ticket_id = m.group(1)
        url = m.group(2)
        return ticket_id, url


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
        self.redmine.remove_ticket(int(ticket_id))
        # check that the ticket has been removed
        self.assertIsNone(self.redmine.get_ticket(int(ticket_id)))

    async def test_ticket_unassign(self):
        ticket = self.create_test_ticket()

        # unassign the ticket
        ctx = self.build_context()
        await self.cog.unassign(ctx, ticket.id)
        response_str = ctx.respond.call_args.args[0]
        self.assertIn(str(ticket.id), response_str)

        # delete ticket with redmine api, assert
        self.redmine.remove_ticket(int(ticket.id))
        # check that the ticket has been removed
        self.assertIsNone(self.redmine.get_ticket(int(ticket.id)))

    # create thread/sync
    async def test_thread_sync(self):
        # create a ticket and add a note
        note = f"This is a test note tagged with {self.tag}"
        ticket = self.create_test_ticket()
        self.redmine.append_message(ticket.id, self.user.login, note)

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
        self.redmine.remove_ticket(ticket.id)


    async def test_resolve_query_term(self):
        ticket = self.create_test_ticket()

        # expected results:
        # 1. ticket ID
        result_1 = self.cog.resolve_query_term(ticket.id)
        self.assertEqual(ticket.id, result_1[0].id)

        # 2. ticket team
        result_2 = self.cog.resolve_query_term("ticket-intake")
        self.assertEqual(ticket.id, result_2[0].id)

        # 3. ticket user
        result_3 = self.cog.resolve_query_term(self.user.login)
        self.assertEqual(0, len(result_3)) # NOTHING ASSIGNED TO NEW TEST USER

        # 4. ticket query term
        result_4 = self.cog.resolve_query_term(self.tag)
        self.assertEqual(ticket.id, result_4[0].id)

        # delete the ticket
        self.redmine.remove_ticket(ticket.id)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format="{asctime} {levelname:<8s} {name:<16} {message}", style='{')
    logging.getLogger("urllib3.connectionpool").setLevel(logging.INFO)
    logging.getLogger("asyncio").setLevel(logging.ERROR)

    unittest.main()
