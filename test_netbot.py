#!/usr/bin/env python3
"""NetBot Test Suite"""

import unittest
import logging

import discord
from dotenv import load_dotenv

import netbot
from formatting import MAX_MESSAGE_LEN

import test_utils


logging.getLogger().setLevel(logging.ERROR)


log = logging.getLogger(__name__)


@unittest.skipUnless(load_dotenv(), "ENV settings not available")
class TestNetbot(test_utils.BotTestCase):
    """NetBot Test Suite"""

    def setUp(self):
        super().setUp()
        #netbot.setup_logging()
        self.bot = netbot.NetBot(self.redmine)

##- call setup_logging in a test, (just for cov)
##- and each of on_ready
##- comment out on_guild_join and on_thread_join (just info logs)
##- comment out sync_new_message
##- test-call sync with a *new* ticket, not existing
#- add test messages to thread.history for syncronize_ticket <<< !!! FIXME
#- add trivial test for on_application_command_error


    async def test_synchronize_ticket(self):
        # create a new ticket, identified by the tag, with a note
        body = f"Body for test {self.tag} {unittest.TestCase.id(self)}"
        ticket = self.create_test_ticket()
        self.redmine.append_message(ticket.id, self.user.login, body) # re-using tagged str

        # create mock message and thread
        message = unittest.mock.AsyncMock(discord.Message)
        message.content = f"This is a new note about ticket #{ticket.id} for test {self.tag}"
        message.author = unittest.mock.AsyncMock(discord.Member)
        message.author.name = self.user.discord_id

        thread = unittest.mock.AsyncMock(discord.Thread)
        thread.name = f"Ticket #{ticket.id}"
        # https://docs.python.org/3/library/unittest.mock-examples.html#mocking-asynchronous-iterators
        ### FIXME
        #thread.history = unittest.mock.AsyncMock(discord.iterators.HistoryIterator)
        #thread.history.__aiter__.return_value = [message, message]

        # synchronize!
        await self.bot.synchronize_ticket(ticket, thread)

        # assert method send called on mock thread, with the correct values
        self.assertIn(self.tag, thread.send.call_args.args[0])
        self.assertIn(self.user.name, thread.send.call_args.args[0])
        self.assertIn(body, thread.send.call_args.args[0])

        # get notes from redmine, assert tags in most recent
        check_ticket = self.redmine.get_ticket(ticket.id, include_journals=True) # get the notes
        self.assertIsNotNone(check_ticket)
        #log.info(f"### ticket: {ticket}")
        #self.assertIn(body, ticket.journals[-1].notes) NOT until thread history is working

        self.redmine.remove_ticket(ticket.id)


    async def test_sync_ticket_long_message(self):
        # create a new ticket, identified by the tag, with a note
        ticket = self.create_test_ticket()

        long_message = test_utils.randstr(3000) # random string 3000 chars long
        self.redmine.append_message(ticket.id, self.user.login, long_message)

        # create mock message and thread
        message = unittest.mock.AsyncMock(discord.Message)
        message.content = f"This is a new note about ticket #{ticket.id} for test {self.tag}"
        message.author = unittest.mock.AsyncMock(discord.Member)
        message.author.name = self.user.discord_id

        thread = unittest.mock.AsyncMock(discord.Thread)
        thread.name = f"Ticket #{ticket.id}"

        # synchronize!
        await self.bot.synchronize_ticket(ticket, thread)

        # assert method send called on mock thread, with the correct values
        log.debug(f"### call args: {thread.send.call_args}")
        self.assertIn(self.tag, thread.send.call_args.args[0])
        self.assertLessEqual(len(thread.send.call_args.args[0]), MAX_MESSAGE_LEN, "Message sent to Discord is too long")

        # clean up
        self.redmine.remove_ticket(ticket.id)


    async def test_on_application_command_error(self):
        ctx = self.build_context()
        error = netbot.NetbotException("this is exception " + self.tag)
        wrapper = discord.DiscordException("Discord Ex Wrapper")
        wrapper.__cause__ = error
        await self.bot.on_application_command_error(ctx, wrapper)
        self.assertIn(self.tag, ctx.respond.call_args.args[0])




if __name__ == '__main__':
    # when running this main, turn on DEBUG
    logging.basicConfig(level=logging.DEBUG, format="{asctime} {levelname:<8s} {name:<16} {message}", style='{')
    logging.getLogger("urllib3.connectionpool").setLevel(logging.INFO)
    logging.getLogger("asyncio").setLevel(logging.ERROR)

    unittest.main()
