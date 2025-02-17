#!/usr/bin/env python3
"""NetBot Test Suite"""

import json
import unittest
from unittest.mock import patch
import logging

import discord
from dotenv import load_dotenv

from redmine import synctime
from redmine.tickets import TICKET_MAX_AGE, TICKET_DUSTY_AGE
from redmine.model import TicketStatus, NamedId
from netbot import netbot
from netbot.formatting import MAX_MESSAGE_LEN

from tests import test_utils
from tests.mock_session import MockSession


log = logging.getLogger(__name__)

INTAKE_TEAM = "intake-team"


class TestNetbot(test_utils.MockBotTestCase):
    """NetBot Mock Test Suite"""

    def setUp(self):
        super().setUp()
        self.bot = netbot.NetBot(self.redmine)


    def test_group_for_tracker(self):
        trackers = self.bot.redmine.ticket_mgr.get_trackers()
        for tracker in trackers.values():
            if tracker.name not in ["Test-Reject"]:
                team = self.bot.team_for_tracker(tracker)
                self.assertIsNotNone(team)


    async def test_dusty_reminder(self):
        # 1. setup mock session to return a dusty tickets
        ticket = self.mock_ticket(
            assigned_to=NamedId(id=self.user.id,name=self.user.name),
            status=TicketStatus(id=2,name="In Progress",is_closed=False),
            updated_on=synctime.ago(days=TICKET_DUSTY_AGE+1),
        )
        self.session.cache_results([ticket])
        # and a mock channel
        channel_id = ticket.get_sync_record().channel_id
        channel = self.mock_channel(channel_id, ticket.id)

        # 2. invoke dusty reminder
        with patch.object(netbot.NetBot, 'channel_for_tracker', return_value=channel) as mock_method:
            await self.bot.remind_dusty_tickets()

        # 3. confirm reminder is sent for dusty ticket - mock ctx invoked
        reminder_str = channel.method_calls[0].args[0]
        log.debug(f"Dusty reminder: {reminder_str}")
        self.assertTrue(str(ticket.id) in reminder_str)

        log.debug(f"USER: {self.user.discord_id} {self.user}")
        self.assertIn(str(self.user.discord_id.id), reminder_str)
        mock_method.assert_called_once()


    async def test_recycle_tickets(self):
        # to find old tickets, an old ticket needs to be created.
        ticket = self.mock_ticket(
            assigned_to=NamedId(id=self.user.id,name=self.user.name),
            status=TicketStatus(id=2,name="In Progress",is_closed=False),
            updated_on=synctime.ago(days=TICKET_MAX_AGE+1),
        )
        self.session.cache_results([ticket])
        # and a mock channel
        channel_id = ticket.get_sync_record().channel_id
        channel = self.mock_channel(channel_id, ticket.id)

        # 2. invoke recycle with patches for reminder channel and
        with patch.object(netbot.NetBot, 'channel_for_tracker', return_value=channel) as patched_channel:
            with patch.object(MockSession, 'put') as patched_put:
                # recycle tickets
                await self.bot.recycle_tickets()

        # 3. confirm reminder is sent for dusty ticket
        #    and patched channel invoked
        patched_put.assert_called_once()
        response = json.loads(patched_put.call_args.args[1])
        self.assertEqual(response['issue']['assigned_to_id'], "software-dev-team")
        self.assertEqual(response['issue']['status_id'], "1")

        reminder_str = channel.method_calls[0].args[0]
        self.assertTrue(str(ticket.id) in reminder_str)

        test_user = test_utils.lookup_test_user(self.redmine.user_mgr)
        self.assertIn(f"<@{test_user.discord_id.id}>", reminder_str)
        patched_channel.assert_called_once()


@unittest.skipUnless(load_dotenv(), "ENV settings not available")
class TestNetbotIntegration(test_utils.BotTestCase):
    """NetBot Integration Test Suite"""

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


    def test_recycle_ticket(self):
        # create test ticket
        ticket = self.create_test_ticket()

        # look up team
        test_team = self.bot.redmine.user_mgr.get_team_by_name(INTAKE_TEAM)

        # recycle the ticket
        recycled = self.bot.redmine.ticket_mgr.recycle(ticket, test_team.id)

        self.assertEqual(recycled.assigned_to.id, test_team.id)
        self.assertEqual(recycled.status.name, "New")

        # remove the test ticket
        self.redmine.ticket_mgr.remove(ticket.id)


    async def test_synchronize_ticket(self):
        # create a new ticket, identified by the tag, with a note
        body = f"Body for test {self.tag} {unittest.TestCase.id(self)}"
        ticket = self.create_test_ticket()
        self.redmine.ticket_mgr.append_message(ticket.id, self.user.login, body) # re-using tagged str

        # create mock message and thread
        message = unittest.mock.AsyncMock(discord.Message)
        message.content = f"This is a new note about ticket #{ticket.id} for test {self.tag}"
        message.author = unittest.mock.AsyncMock(discord.Member)
        message.author.name = self.user.discord_id.name

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
        check_ticket = self.redmine.ticket_mgr.get(ticket.id, include="journals") # get the notes
        self.assertIsNotNone(check_ticket)
        #self.assertIn(body, ticket.journals[-1].notes) NOT until thread history is working

        self.redmine.ticket_mgr.remove(ticket.id)


    async def test_sync_ticket_long_message(self):
        # create a new ticket, identified by the tag, with a note
        ticket = self.create_test_ticket()

        long_message = test_utils.randstr(3000) # random string 3000 chars long
        self.redmine.ticket_mgr.append_message(ticket.id, self.user.login, long_message)

        # create mock message and thread
        message = unittest.mock.AsyncMock(discord.Message)
        message.content = f"This is a new note about ticket #{ticket.id} for test {self.tag}"
        message.author = unittest.mock.AsyncMock(discord.Member)
        message.author.name = self.user.discord_id.name

        thread = unittest.mock.AsyncMock(discord.Thread)
        thread.name = f"Ticket #{ticket.id}"

        # synchronize!
        await self.bot.synchronize_ticket(ticket, thread)

        # assert method send called on mock thread, with the correct values
        #log.debug(f"### call args: {thread.send.call_args}")
        self.assertIn(self.user.name, thread.send.call_args.args[0])
        self.assertLessEqual(len(thread.send.call_args.args[0]), MAX_MESSAGE_LEN, "Message sent to Discord is too long")

        # clean up
        self.redmine.ticket_mgr.remove(ticket.id)


    async def test_on_application_command_error(self):
        ctx = self.build_context()
        error = netbot.NetbotException("this is exception " + self.tag)
        wrapper = discord.DiscordException("Discord Ex Wrapper")
        wrapper.__cause__ = error
        await self.bot.on_application_command_error(ctx, wrapper)
        self.assertIn(self.tag, ctx.respond.call_args.args[0])
