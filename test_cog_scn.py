#!/usr/bin/env python3

import os
import unittest
import logging
import discord
import asyncio

from dotenv import load_dotenv

from typing import Any

from redmine import Client
from netbot import NetBot

import test_utils

#logging.basicConfig(level=logging.INFO)
logging.basicConfig(level=logging.ERROR, 
                    format="{asctime} {levelname:<8s} {name:<16} {message}", style='{')
logging.getLogger("urllib3.connectionpool").setLevel(logging.INFO)
logging.getLogger("asyncio").setLevel(logging.ERROR)

log = logging.getLogger(__name__)

test_username: str = "acmerocket"
test_username2: str = "freddy"
test_user_id: int = 5


@unittest.skipUnless(load_dotenv(), "ENV settings not available")
class TestSCNCog(test_utils.BotTestCase):
        
    def setUp(self):
        super().setUp()
        
        self.bot.load_extension("cog_scn")
        self.cog = self.bot.cogs["SCNCog"] # Note class name, note filename.
        
        
    async def test_team_join_leave(self):
        test_team_name = "test-team"
                
        # create temp discord mapping with scn add
        ctx = self.build_context()
        await self.cog.add(ctx, self.user.login) # invoke cog to add uer
        
        # check add result
        #ctx.respond.assert_called_with(
        #    f"Discord user: {self.discord_user} has been paired with redmine user: {self.user.login}")
        
        # reindex using cog
        ctx = self.build_context()
        await self.cog.reindex(ctx) # invoke cog to add uer
        await asyncio.sleep(0.01) # needed? smaller?
        # 4.5 check reindex result, and lookup based on login and discord id
        ctx.respond.assert_called_with("Rebuilt redmine indices.")
        self.assertIsNotNone(self.redmine.find_user(self.user.login))
        self.assertIsNotNone(self.redmine.find_user(self.discord_user))
        
        # join team users
        ctx = self.build_context()
        #member = unittest.mock.AsyncMock(discord.Member) # for forced use case
        #member.name = discord_user
        await self.cog.join(ctx, test_team_name)

        # confirm via mock callback and API
        #ctx.respond.assert_called_with(f"Unknown team name: {test_team_name}") # unknown team response!
        ctx.respond.assert_called_with(f"**{self.discord_user}** has joined *{test_team_name}*")
        self.assertTrue(self.redmine.is_user_in_team(self.user.login, test_team_name), f"{self.user.login} not in team {test_team_name}")
    
        # confirm in team via cog teams response
        ctx = self.build_context()
        await self.cog.teams(ctx, test_team_name)
        self.assertIn(self.fullName, str(ctx.respond.call_args))

        # leave team users
        ctx = self.build_context()
        await self.cog.leave(ctx, test_team_name)

        # confirm via API and callback
        self.assertFalse(self.redmine.is_user_in_team(self.user.login, test_team_name), f"{self.user.login} *in* team {test_team_name}")
        ctx.respond.assert_called_with(f"**{self.discord_user}** has left *{test_team_name}*")
        
        # confirm not in team via cog teams response
        ctx = self.build_context()
        await self.cog.teams(ctx, test_team_name)
        self.assertNotIn(self.fullName, str(ctx.respond.call_args))
        

    async def test_thread_sync(self):
        test_ticket = 218
        
        ctx = self.build_context()
        ctx.channel = unittest.mock.AsyncMock(discord.Thread)
        ctx.channel.name = f"Ticket #{test_ticket}"
        ctx.channel.id = self.tag
        
        await self.cog.sync(ctx)
        ctx.respond.assert_called_with(f"SYNC ticket {test_ticket} to thread: {ctx.channel.name} complete")
        # check for actual changes! updated timestamp!


if __name__ == '__main__':
    unittest.main()