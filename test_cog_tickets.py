#!/usr/bin/env python3

import unittest
import logging
import re

from dotenv import load_dotenv

from typing import Any

from redmine import Client
from netbot import NetBot
import test_utils

#logging.basicConfig(level=logging.DEBUG)
logging.basicConfig(level=logging.DEBUG, 
                    format="{asctime} {levelname:<8s} {name:<16} {message}", style='{')
logging.getLogger("urllib3.connectionpool").setLevel(logging.INFO)
logging.getLogger("asyncio").setLevel(logging.ERROR)

log = logging.getLogger(__name__)


@unittest.skipUnless(load_dotenv(), "ENV settings not available")
class TestTicketsCog(test_utils.CogTestCase):
    
    def __init__(self, methodName: str = "runTest") -> None:
        super().__init__(methodName)
        
        self.redmine = Client()
        self.bot = NetBot(self.redmine)
        self.bot.load_extension("cog_tickets")
        self.cog = self.bot.cogs["TicketsCog"] # Note class name, note filename.
    
    
    async def test_new_ticket(self):
        # create ticket with discord user, assert
        test_title = "This is a test ticket"
        ctx = self.build_context()
        await self.cog.create_new_ticket(ctx, test_title)
        response_str = ctx.respond.call_args.args[0]
        
        regex = "^\[(\d+)\]\((.+)\)"
        m = re.match(regex, response_str)
        self.assertIsNotNone(m, f"could not find ticket number in response str: {response_str}")

        ticket_id = m.group(1)
        url = m.group(2)
        log.debug(f"created ticket {ticket_id}, {url}")

        # get the ticket using a new context
        ctx = self.build_context()
        await self.cog.tickets(ctx, ticket_id)
        response_str = ctx.respond.call_args.args[0]
        self.assertIn(ticket_id, response_str)
        self.assertIn(url, response_str)
        
        # delete ticket with redmine api, assert
        self.redmine.remove_ticket(int(ticket_id))
        # TODO check that the ticket has been removed
        


if __name__ == '__main__':
    unittest.main()