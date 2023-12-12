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

logging.basicConfig(level=logging.ERROR)


#logging.basicConfig(level=logging.DEBUG)
#logging.basicConfig(level=logging.DEBUG, 
#                    format="{asctime} {levelname:<8s} {name:<16} {message}", style='{')
#logging.getLogger("urllib3.connectionpool").setLevel(logging.INFO)

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
        
        # create a test user. this could be a fixture!
        # create new test user name: test-12345@example.com, login test-12345
        tag = test_utils.tagstr()
        first = "test-" + tag
        last = "Testy"
        self.fullName = f"{first} {last}"
        email = first + "@example.com"
        self.discord_user = "discord-" + tag 
        # create new redmine user, using redmine api
        self.user = self.redmine.create_user(email, first, last)
        self.assertIsNotNone(self.user)
        self.assertEqual(email, self.user.login)
        
        
    def tearDown(self):
        # delete user with redmine api, assert
        self.redmine.remove_user(self.user.id)
        self.redmine.reindex_users()
        self.assertIsNone(self.redmine.find_user(self.user.login))
        self.assertIsNone(self.redmine.find_user(self.discord_user))
        
        
    async def test_team_join_leave(self):
        test_team_name = "test-team"
                
        # create temp discord mapping with scn add
        ctx = test_utils.build_context(test_user_id, self.discord_user)
        await self.cog.add(ctx, self.user.login) # invoke cog to add uer
        
        # check add result
        ctx.respond.assert_called_with(
            f"Discord user: {self.discord_user} has been paired with redmine user: {self.user.login}")
        
        # reindex using cog
        ctx = test_utils.build_context(test_user_id, self.discord_user)
        await self.cog.reindex(ctx) # invoke cog to add uer
        await asyncio.sleep(0.01) # needed? smaller?
        # 4.5 check reindex result, and lookup based on login and discord id
        ctx.respond.assert_called_with("Rebuilt redmine indices.")
        self.assertIsNotNone(self.redmine.find_user(self.user.login))
        self.assertIsNotNone(self.redmine.find_user(self.discord_user))
        
        # join team users
        ctx = test_utils.build_context(test_user_id, self.discord_user)
        #member = unittest.mock.AsyncMock(discord.Member) # for forced use case
        #member.name = discord_user
        await self.cog.join(ctx, test_team_name)

        # confirm via mock callback and API
        #ctx.respond.assert_called_with(f"Unknown team name: {test_team_name}") # unknown team response!
        ctx.respond.assert_called_with(f"**{self.discord_user}** has joined *{test_team_name}*")
        self.assertTrue(self.redmine.is_user_in_team(self.user.login, test_team_name), f"{self.user.login} not in team {test_team_name}")
    
        # confirm in team via cog teams response
        ctx = test_utils.build_context(test_user_id, self.discord_user)
        await self.cog.teams(ctx, test_team_name)
        self.assertIn(self.fullName, str(ctx.respond.call_args))

        # leave team users
        ctx = test_utils.build_context(test_user_id, self.discord_user)
        await self.cog.leave(ctx, test_team_name)

        # confirm via API and callback
        self.assertFalse(self.redmine.is_user_in_team(self.user.login, test_team_name), f"{self.user.login} *in* team {test_team_name}")
        ctx.respond.assert_called_with(f"**{self.discord_user}** has left *{test_team_name}*")
        
        # confirm not in team via cog teams response
        ctx = test_utils.build_context(test_user_id, self.discord_user)
        await self.cog.teams(ctx, test_team_name)
        self.assertNotIn(self.fullName, str(ctx.respond.call_args))
        

    async def test_thread_sync(self):
        # TODO
        # test threading 
        pass
        

if __name__ == '__main__':
    unittest.main()