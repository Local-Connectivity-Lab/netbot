#!/usr/bin/env python3
"""testing the SCN cog"""

import unittest
import logging
import discord

from dotenv import load_dotenv

from netbot.netbot import NetBot
from netbot.cog_scn import SCNCog

from tests import test_utils


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
        self.bot.load_extension("netbot.cog_scn")
        self.cog:SCNCog = self.bot.cogs["SCNCog"] # Note class name, note filename.


    @unittest.skip("Disabled until user registration is added to test suite")
    async def test_add_self(self):
        # invoke "add" to add a discord mapping for the test user.
        # setup: remove existing mapping
        discord_id = self.user.discord_id.name
        self.user_mgr.remove_discord_mapping(self.user)
        self.user_mgr.reindex_users() # to remove the discord ID from the cache

        ctx = self.build_context()
        await self.cog.add(ctx, self.user.login) # invoke cog to add uer

        expected = f"Discord user: {discord_id} has been paired with redmine user: {self.user.login}"
        ctx.respond.assert_called_with(expected)


    @unittest.skip("Disabled until user registration is added to test suite")
    async def test_team_join_leave(self):
        test_team_name = "test-team"

        # create temp discord mapping with scn add
        ctx = self.build_context()
        await self.cog.add(ctx, self.user.login) # invoke cog to add uer

        # check add result
        #ctx.respond.assert_called_with(
        #    f"Discord user: {self.user.discord_id} has been paired with redmine user: {self.user.login}")

        # reindex using cog
        ctx = self.build_context()
        await self.cog.reindex(ctx) # invoke cog to add uer
        #await asyncio.sleep(0.01) # needed? smaller?

        # 4.5 check reindex result, and lookup based on login and discord id
        ctx.respond.assert_called_with("Rebuilt redmine indices.")
        self.assertIsNotNone(self.redmine.user_mgr.find(self.user.login))
        self.assertIsNotNone(self.redmine.user_mgr.find(self.user.discord_id))

        # join team users
        ctx = self.build_context()
        #member = unittest.mock.AsyncMock(discord.Member) # for forced use case
        #member.name = discord_user
        await self.cog.join(ctx, test_team_name)
        self.redmine.user_mgr.reindex_teams()

        # confirm via mock callback and API
        #ctx.respond.assert_called_with(f"Unknown team name: {test_team_name}") # unknown team response!
        ctx.respond.assert_called_with(f"**{self.user.discord_id}** has joined *{test_team_name}*")
        self.assertTrue(self.redmine.user_mgr.is_user_in_team(self.user, test_team_name), f"{self.user.login} not in team {test_team_name}")

        # confirm in team via cog teams response
        ctx = self.build_context()
        await self.cog.teams(ctx, test_team_name)
        self.assertIn(self.user.name, str(ctx.respond.call_args))

        # leave team users
        ctx = self.build_context()
        await self.cog.leave(ctx, test_team_name)
        self.redmine.user_mgr.reindex_teams()

        # confirm via API and callback
        self.assertFalse(self.redmine.user_mgr.is_user_in_team(self.user, test_team_name), f"{self.user.login} *in* team {test_team_name}")
        ctx.respond.assert_called_with(f"**{self.user.discord_id}** has left *{test_team_name}*")

        # confirm not in team via cog teams response
        ctx = self.build_context()
        await self.cog.teams(ctx, test_team_name)
        self.assertNotIn(self.user.name, str(ctx.respond.call_args))

        # ticket-1036: confirm teams "blocked", "users" and "test-team" is not included
        ctx = self.build_context()
        await self.cog.teams(ctx)
        for ignored_team in ["blocked", "users"]:
            self.assertNotIn(ignored_team, str(ctx.respond.call_args))

    async def test_thread_sync(self):
        ticket = self.create_test_ticket()

        ctx = self.build_context()
        ctx.channel = unittest.mock.AsyncMock(discord.Thread)
        ctx.channel.name = f"Ticket #{ticket.id}"
        #ctx.channel.id = 4321

        await self.cog.sync(ctx)
        ctx.respond.assert_called_with(f"SYNC ticket {ticket.id} to thread: {ctx.channel.name} complete")
        # check for actual changes! updated timestamp!

        # cleanup
        self.redmine.ticket_mgr.remove(ticket.id)


    async def test_block_user(self):
        # create a ticket
        ticket = self.create_test_ticket()
        try:
            # call block
            ctx = self.build_context()
            await self.cog.block(ctx, self.user.login)

            # confirmed blocked
            self.assertTrue(self.redmine.user_mgr.is_blocked(self.user))

            # confirm ticket rejected
            check_ticket = self.redmine.ticket_mgr.get(ticket.id)
            self.assertEqual("Reject", check_ticket.status.name)
        finally:
            # cleanup
            self.redmine.ticket_mgr.remove(ticket.id)


    async def test_unblock_user(self):
        # call block
        ctx = self.build_context()
        await self.cog.block(ctx, self.user.login)

        # confirmed blocked
        self.assertTrue(self.redmine.user_mgr.is_blocked(self.user))

        # unblock
        await self.cog.unblock(ctx, self.user.login)
        self.assertFalse(self.redmine.user_mgr.is_blocked(self.user))


    async def test_locked_during_sync_ticket(self):
        """
        Unhandled exception in internal background task 'sync_all_threads'.
        Traceback (most recent call last):
        File "/usr/local/lib/python3.11/site-packages/discord/ext/tasks/__init__.py", line 169, in _loop
            await self.coro(*args, **kwargs)
        File "/cog_scn.py", line 124, in sync_all_threads
            ticket = await self.sync_thread(thread)
                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
        File "/cog_scn.py", line 106, in sync_thread
            raise NetbotException(f"Ticket {ticket.id} is locked for syncronization.")
        netbot.NetbotException: Ticket 195 is locked for syncronization.
        --
        This test intends to try to reproduce by locking a ticket before starting the sync.
        """
        # create a new ticket, identified by the tag, with a note
        ticket = self.create_test_ticket()
        message = f"Message for {self.tag}"
        self.redmine.ticket_mgr.append_message(ticket.id, self.user.login, message)

        # create mock message and thread
        message = unittest.mock.AsyncMock(discord.Message)
        message.content = f"This is a new note about ticket #{ticket.id} for test {self.tag}"
        message.author = unittest.mock.AsyncMock(discord.Member)
        message.author.name = self.user.discord_id.name

        thread = unittest.mock.AsyncMock(discord.Thread)
        thread.name = f"Ticket #{ticket.id}: {ticket.subject}"

        # Lock the ticket...
        # TODO - this could be encapsulated in Ticket or Netbot
        log.debug("locking ticket")
        async with self.bot.lock:
            if ticket.id in self.bot.ticket_locks:
                self.fail(f"New ticket {ticket.id} is already locked?")
            else:
                # create lock flag
                self.bot.ticket_locks[ticket.id] = True

        try:
            # synchronize thread
            await self.bot.sync_thread(thread)
            self.fail("No exception when one was expected")
        except Exception as ex:
            self.assertIn(f"Ticket {ticket.id}", str(ex))
            # pass: exception contains "Ticket id"

        # clean up
        del self.bot.ticket_locks[ticket.id]
        self.redmine.ticket_mgr.remove(ticket.id)
