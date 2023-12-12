#!/usr/bin/env python3

import unittest
import logging
import discord
import asyncio

from dotenv import load_dotenv

from typing import Any

from redmine import Client
from netbot import NetBot

import test_utils

#logging.basicConfig(level=logging.DEBUG)
logging.basicConfig(level=logging.DEBUG, 
                    format="{asctime} {levelname:<8s} {name:<16} {message}", style='{')
logging.getLogger("urllib3.connectionpool").setLevel(logging.INFO)
log = logging.getLogger(__name__)

test_username: str = "acmerocket"
test_username2: str = "infrared0"
test_user_id: int = 5


class TestSCNCog(unittest.IsolatedAsyncioTestCase):
    
    def setUp(self):
        load_dotenv()
        self.redmine = Client()
        self.bot = NetBot(self.redmine)
        self.bot.load_extension("cog_scn")
        self.cog = self.bot.cogs["SCNCog"] # Note class name, note filename.

    #@unittest.skip
    async def test_team_join_leave(self):
        test_team_name = "users"
        
        # Test steps:
        # 1. create new test user name: test-12345@example.com, login test-12345
        tag = test_utils.tagstr()
        username = "test-" + tag
        email = username + "@example.com"
        discord_user = "discord-" + tag 
        
        # 2. create new redmine user, using redmine api
        user = self.redmine.create_user(email, username, "Testy")
        self.assertIsNotNone(user)
        
        # 3. create temp discord mapping with redmine api 
        self.redmine.create_discord_mapping(user.login, discord_user)
        
        # 4. reindex users and lookup based on login and discord
        self.redmine.reindex_users()
        self.assertIsNotNone(self.redmine.find_user(user.login))
        self.assertIsNotNone(self.redmine.find_user(discord_user))
        
        # 5. join team users
        ctx = test_utils.build_context(test_user_id, discord_user)
        #member = unittest.mock.AsyncMock(discord.Member) # for forced use case
        #member.name = discord_user
        await self.cog.join(ctx, test_team_name)
        await asyncio.sleep(0.01) # needed? smaller?

        # 6. confirm via mock callback and API
        #ctx.respond.assert_called_with(f"Unknown team name: {test_team_name}") # unknown team response!
        ctx.respond.assert_called_with(f"**{discord_user}** has joined *{test_team_name}*")
        self.assertTrue(self.redmine.is_user_in_team(user.login, test_team_name), f"{user.login} not in team {test_team_name}")
        
        # 7. leave team users
        ctx = test_utils.build_context(test_user_id, discord_user)
        await self.cog.leave(ctx, test_team_name)
        await asyncio.sleep(0.01) # needed? smaller?

        # 8. confirm via API and callback
        self.assertFalse(self.redmine.is_user_in_team(user.login, test_team_name), f"{user.login} *in* team {test_team_name}")
        ctx.respond.assert_called_with(f"**{discord_user}** has left *{test_team_name}*")

        # 9. delete user with redmine api, assert
        self.redmine.remove_user(user.id)
        self.redmine.reindex_users()
        self.assertIsNone(self.redmine.find_user(user.login))
        self.assertIsNone(self.redmine.find_user(discord_user))


if __name__ == '__main__':
    unittest.main()