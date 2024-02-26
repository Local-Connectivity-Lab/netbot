#!/usr/bin/env python3
"""testing the SCN cog"""

import asyncio
import unittest
import logging
import discord

from dotenv import load_dotenv

from netbot import NetBot

import test_utils


logging.basicConfig(level=logging.FATAL)

log = logging.getLogger(__name__)

test_username: str = "acmerocket"
test_username2: str = "freddy"
test_user_id: int = 5


@unittest.skipUnless(load_dotenv(), "ENV settings not available")
class TestSCNCog(test_utils.BotTestCase):
    """testing scn cog"""

    def setUp(self):
        super().setUp()
        self.bot = NetBot(self.redmine)
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
        #await asyncio.sleep(0.01) # needed? smaller?

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
        self.assertIn(self.full_name, str(ctx.respond.call_args))

        # leave team users
        ctx = self.build_context()
        await self.cog.leave(ctx, test_team_name)

        # confirm via API and callback
        self.assertFalse(self.redmine.is_user_in_team(self.user.login, test_team_name), f"{self.user.login} *in* team {test_team_name}")
        ctx.respond.assert_called_with(f"**{self.discord_user}** has left *{test_team_name}*")

        # confirm not in team via cog teams response
        ctx = self.build_context()
        await self.cog.teams(ctx, test_team_name)
        self.assertNotIn(self.full_name, str(ctx.respond.call_args))


    async def test_thread_sync(self):
        subject = f"Test Sync Ticket {self.tag}"
        text = f"This is a test sync ticket tagged with {self.tag}."
        ticket = self.redmine.create_ticket(self.user, subject, text)

        ctx = self.build_context()
        ctx.channel = unittest.mock.AsyncMock(discord.Thread)
        ctx.channel.name = f"Ticket #{ticket.id}"
        #ctx.channel.id = 4321

        await self.cog.sync(ctx)
        ctx.respond.assert_called_with(f"SYNC ticket {ticket.id} to thread: {ctx.channel.name} complete")
        # check for actual changes! updated timestamp!

        # cleanup
        self.redmine.remove_ticket(ticket.id)


if __name__ == '__main__':
    # when running this main, turn on DEBUG
    logging.basicConfig(level=logging.DEBUG, format="{asctime} {levelname:<8s} {name:<16} {message}", style='{')
    logging.getLogger("urllib3.connectionpool").setLevel(logging.INFO)
    logging.getLogger("asyncio").setLevel(logging.ERROR)

    unittest.main()
