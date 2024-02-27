#!/usr/bin/env python3
"""testing the SCN cog"""

import unittest
import logging
import discord

from dotenv import load_dotenv

from netbot import NetBot
from cog_scn import SCNCog

import test_utils


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
        self.cog:SCNCog = self.bot.cogs["SCNCog"] # Note class name, note filename.


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


    async def test_block_user(self):
        # create a ticket
        ticket = self.create_test_ticket()
        try:
            # call block
            ctx = self.build_context()
            await self.cog.block(ctx, self.user.login)

            # confirmed blocked
            self.assertTrue(self.redmine.is_user_blocked(self.user))

            # confirm ticket rejected
            check_ticket = self.redmine.get_ticket(ticket.id)
            self.assertEqual("Reject", check_ticket.status.name)
        finally:
            # cleanup
            self.redmine.remove_ticket(ticket.id)


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
        self.redmine.append_message(ticket.id, self.user.login, message)

        # create mock message and thread
        message = unittest.mock.AsyncMock(discord.Message)
        message.content = f"This is a new note about ticket #{ticket.id} for test {self.tag}"
        message.author = unittest.mock.AsyncMock(discord.Member)
        message.author.name = self.discord_user

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
            await self.cog.sync_thread(thread)
            self.fail("No exception when one was expected")
        except Exception as ex:
            self.assertIn(f"Ticket {ticket.id}", str(ex))
            # pass: exception contains "Ticket id"

        # clean up
        del self.bot.ticket_locks[ticket.id]
        self.redmine.remove_ticket(ticket.id)


if __name__ == '__main__':
    # when running this main, turn on DEBUG
    logging.basicConfig(level=logging.DEBUG, format="{asctime} {levelname:<8s} {name:<16} {message}", style='{')
    logging.getLogger("urllib3.connectionpool").setLevel(logging.INFO)
    logging.getLogger("asyncio").setLevel(logging.ERROR)

    unittest.main()
