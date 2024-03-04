#!/usr/bin/env python3
"""Test case for the TicketsCog"""

import unittest
import logging
import re

import discord
from dotenv import load_dotenv

from netbot import NetBot
import test_utils


logging.basicConfig(level=logging.FATAL)

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
        regex = r"^\[(\d+)\]\((.+)\)"
        m = re.match(regex, text)
        self.assertIsNotNone(m, f"could not find ticket number in response str: {text}")

        ticket_id = m.group(1)
        url = m.group(2)
        return ticket_id, url


    async def test_new_ticket(self):
        # create ticket with discord user, assert
        test_title = f"This is a test ticket {self.tag}"
        ctx = self.build_context()
        await self.cog.create_new_ticket(ctx, test_title)
        response_str = ctx.respond.call_args.args[0]

        ticket_id, url = self.parse_markdown_link(response_str)
        log.debug(f"created ticket: {ticket_id}, {url}")

        # get the ticket using id
        ctx = self.build_context()
        await self.cog.tickets(ctx, ticket_id)
        response_str = ctx.respond.call_args.args[0]
        self.assertIn(ticket_id, response_str)
        self.assertIn(url, response_str)

        # get the ticket using tag
        ctx = self.build_context()
        await self.cog.tickets(ctx, self.tag)
        response_str = ctx.respond.call_args.args[0]
        self.assertIn(ticket_id, response_str)
        self.assertIn(url, response_str)

        # assign the ticket
        ctx = self.build_context()
        await self.cog.ticket(ctx, ticket_id, "assign")
        response_str = ctx.respond.call_args.args[0]
        self.assertIn(ticket_id, response_str)
        self.assertIn(url, response_str)
        self.assertIn(test_title, response_str)

        # "progress" the ticket, setting it in-progress and assigning it to "me"
        ctx = self.build_context()
        await self.cog.ticket(ctx, ticket_id, "progress")
        response_str = ctx.respond.call_args.args[0]
        self.assertIn(ticket_id, response_str)
        self.assertIn(url, response_str)
        self.assertIn(test_title, response_str)

        # resolve the ticket
        ctx = self.build_context()
        await self.cog.ticket(ctx, ticket_id, "resolve")
        response_str = ctx.respond.call_args.args[0]
        self.assertIn(ticket_id, response_str)
        self.assertIn(url, response_str)
        self.assertIn(test_title, response_str)

        # delete ticket with redmine api, assert
        self.redmine.remove_ticket(int(ticket_id))
        # check that the ticket has been removed
        self.assertIsNone(self.redmine.get_ticket(int(ticket_id)))

    # create thread/sync
    async def test_thread_sync(self):
        #timestamp = dt.datetime.now().astimezone(dt.timezone.utc).replace(microsecond=0) # strip microseconds

        # create a ticket and add a note
        subject = f"Test Thread Ticket {self.tag}"
        text = f"This is a test thread ticket tagged with {self.tag}"
        note = f"This is a test note tagged with {self.tag}"
        old_message = f"This is a sync message with {self.tag}"

        ticket = self.redmine.create_ticket(self.user, subject, text)
        self.redmine.append_message(ticket.id, self.user.login, note)

        # thread the ticket using
        ctx = self.build_context()
        ctx.channel = unittest.mock.AsyncMock(discord.TextChannel)
        ctx.channel.name = f"Test Channel {self.tag}"
        #ctx.channel.id = self.tag

        thread = unittest.mock.AsyncMock(discord.Thread)
        thread.name = f"Ticket #{ticket.id}: {subject}"

        member = unittest.mock.AsyncMock(discord.Member)
        member.name=self.discord_user

        message = unittest.mock.AsyncMock(discord.Message)
        message.channel = ctx.channel
        message.content = old_message
        message.author = member
        message.create_thread = unittest.mock.AsyncMock(return_value=thread)

        # TODO setup history with a message from the user - disabled while I work out the history mock.
        #thread.history = unittest.mock.AsyncMock(name="history")
        #thread.history.flatten = unittest.mock.AsyncMock(name="flatten", return_value=[message])

        ctx.send = unittest.mock.AsyncMock(return_value=message)

        await self.cog.thread_ticket(ctx, ticket.id)

        response = ctx.send.call_args.args[0]
        thread_response = str(message.create_thread.call_args) # FIXME
        self.assertIn(str(ticket.id), response)
        self.assertIn(str(ticket.id), thread_response)
        self.assertIn(subject, thread_response)

        # delete the ticket
        self.redmine.remove_ticket(ticket.id)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format="{asctime} {levelname:<8s} {name:<16} {message}", style='{')
    logging.getLogger("urllib3.connectionpool").setLevel(logging.INFO)
    logging.getLogger("asyncio").setLevel(logging.ERROR)

    unittest.main()
