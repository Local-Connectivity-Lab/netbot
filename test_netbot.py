#!/usr/bin/env python3
"""NetBot Test Suite"""

import unittest
import logging
import discord

from dotenv import load_dotenv

import netbot

import test_utils


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
        subject = f"Testing {self.tag} {unittest.TestCase.id(self)}"
        body = f"Body for test {self.tag} {unittest.TestCase.id(self)}"
        ticket = self.redmine.create_ticket(self.user, subject, body)
        self.redmine.append_message(ticket.id, self.user.login, body) # re-using tagged str

        # create mock message and thread
        message = unittest.mock.AsyncMock(discord.Message)
        message.content = f"This is a new note about ticket #{ticket.id} for test {self.tag}"
        message.author = unittest.mock.AsyncMock(discord.Member)
        message.author.name = self.discord_user

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
        self.assertIn(self.full_name, thread.send.call_args.args[0])
        self.assertIn(body, thread.send.call_args.args[0])

        # get notes from redmine, assert tags in most recent
        check_ticket = self.redmine.get_ticket(ticket.id, include_journals=True) # get the notes
        self.assertIsNotNone(check_ticket)
        #log.info(f"### ticket: {ticket}")
        #self.assertIn(body, ticket.journals[-1].notes) NOT until thread history is working


    async def test_on_application_command_error(self):
        ctx = self.build_context()
        error = discord.DiscordException("this is exception " + self.tag)
        await self.bot.on_application_command_error(ctx, error)
        self.assertIn(self.tag, ctx.respond.call_args.args[0])



if __name__ == '__main__':
    unittest.main()
