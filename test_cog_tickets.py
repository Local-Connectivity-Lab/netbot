#!/usr/bin/env python3

import unittest
import logging
import re
import os

from dotenv import load_dotenv

from typing import Any

from redmine import Client
from netbot import NetBot
import discord
import test_utils

#logging.basicConfig(level=logging.DEBUG)

logging.basicConfig(level=logging.DEBUG, 
                    format="{asctime} {levelname:<8s} {name:<16} {message}", style='{')
logging.getLogger("urllib3.connectionpool").setLevel(logging.INFO)
logging.getLogger("asyncio").setLevel(logging.ERROR)

log = logging.getLogger(__name__)


@unittest.skipUnless(load_dotenv(), "ENV settings not available")
class TestTicketsCog(test_utils.CogTestCase):
        
    def setUp(self):
        super().setUp()

        self.bot.load_extension("cog_tickets")
        self.cog = self.bot.cogs["TicketsCog"] # Note class name, note filename.
    
    
    def parse_markdown_link(self, text:str) -> (str, str):
        regex = "^\[(\d+)\]\((.+)\)"
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
        self.assertIn(self.fullName, response_str)
        
        # "progress" the ticket, setting it in-progress and assigning it to "me"
        ctx = self.build_context()
        await self.cog.ticket(ctx, ticket_id, "progress")
        response_str = ctx.respond.call_args.args[0]
        self.assertIn(ticket_id, response_str)
        self.assertIn(url, response_str)
        self.assertIn(self.fullName, response_str)
        
        # resolve the ticket
        ctx = self.build_context()
        await self.cog.ticket(ctx, ticket_id, "resolve")
        response_str = ctx.respond.call_args.args[0]
        self.assertIn(ticket_id, response_str)
        self.assertIn(url, response_str)
        self.assertIn(self.fullName, response_str)
        
        # delete ticket with redmine api, assert
        self.redmine.remove_ticket(int(ticket_id))
        # check that the ticket has been removed
        self.assertIsNone(self.redmine.get_ticket(int(ticket_id)))

    # create thread/sync 
    async def test_thread_sync(self):
        # create a ticket
        title = f"Test Thread Ticket {self.tag}"
        text = f"This is a test thread ticket tagges with {self.tag}"
        ticket = self.redmine.create_ticket(self.user, title, text)
        
        # thread the ticket using 
        ctx = self.build_context()
        ctx.channel = unittest.mock.AsyncMock(discord.Thread)
        ctx.channel.name = f"Test Channel {self.tag}"
        ctx.channel.id = self.tag
        thread = unittest.mock.AsyncMock(discord.Thread)
        #thread.
        ctx.channel.create_thread = unittest.mock.AsyncMock(name="create_thread", return_value=thread)
        
        await self.cog.thread(ctx, ticket.id)
        response = ctx.respond.call_args.args[0]
        self.assertIn(str(ticket.id), response)
        
        # add a note
        # ...
        
        # delete the ticket
        self.redmine.remove_ticket(ticket.id)


if __name__ == '__main__':
    unittest.main()