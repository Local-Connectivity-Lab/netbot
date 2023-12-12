#!/usr/bin/env python3

import unittest
import logging

from dotenv import load_dotenv

from typing import Any

from redmine import Client
from netbot import NetBot

#logging.basicConfig(level=logging.DEBUG)
logging.basicConfig(level=logging.DEBUG, 
                    format="{asctime} {levelname:<8s} {name:<16} {message}", style='{')
logging.getLogger("urllib3.connectionpool").setLevel(logging.INFO)
log = logging.getLogger(__name__)


class TestTicketsCog(unittest.IsolatedAsyncioTestCase):
    
    def setUp(self):
        load_dotenv()
        self.redmine = Client()
        self.bot = NetBot(self.redmine)
        #self.bot = self.build_bot("setup")
        self.bot.load_extension("cog_tickets")
        self.cog = self.bot.cogs["TicketsCog"] # Note class name, note filename.

    @unittest.skip
    async def test_new_ticket(self):
        # Test steps:
        # 1. create new test user name: test-12345@example.com, login test-12345
        tag = self.tagstr()
        username = "test-" + tag
        email = username + "@example.com"
        discord_user = "discord-" + tag 
        
        # 2. create new redmine user, using redmine api, assert
        user = self.redmine.create_user(email, username, "Testy")
        self.assertIsNotNone(user)
        
        # 3. create temp discord mapping with redmine api, assert 
        self.redmine.create_discord_mapping(user.login, discord_user)
        
        # reindex users and lookup based on login
        self.redmine.reindex_users()
        self.assertIsNotNone(self.redmine.find_user(user.login))
        self.assertIsNotNone(self.redmine.find_user(discord_user))
        
        # 4. create ticket with discord user, assert
        #test_title = "This is a test ticket."
        #ctx = self.build_context(tag, discord_user)
        #await self.cog.create_new_ticket(ctx, test_title)
        #await asyncio.sleep(1) # needed? smaller?
        
        # 5. delete ticket with redmine api, assert
        
        # 6. delete user with redmine api, assert
        self.redmine.remove_user(user.id)
        self.redmine.reindex_users()
        self.assertIsNone(self.redmine.find_user(user.login))
        self.assertIsNone(self.redmine.find_user(discord_user))


if __name__ == '__main__':
    unittest.main()