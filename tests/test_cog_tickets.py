#!/usr/bin/env python3
"""Test case for the TicketsCog"""

import unittest
import logging
import re
import json
import datetime as dt
from unittest.mock import AsyncMock, patch

import discord
from dotenv import load_dotenv

from redmine import synctime
from netbot.netbot import NetBot
from netbot.cog_tickets import TicketsCog, get_priorities, get_trackers, EditDescriptionModal
from tests import test_utils


log = logging.getLogger(__name__)

class TestTicketCogUnitTests(unittest.TestCase):
    """Unit tests for TicketsCog"""

    @staticmethod
    def add_months(d: dt.date, months:int) -> dt.date:
        return d.replace(
            month = (d.month + months) % 12,
            year = d.year + (d.month + months) // 12)


    def test_human_dates(self):
        today = dt.date.today()
        expected_results = [
            # input, expected-date
            ["10/31/2025", dt.date.fromisoformat("2025-10-31")],
            ["invalid-date", ""],
            ["next week", today + dt.timedelta(weeks=1)],
            ["tomorrow", today + dt.timedelta(days=1)],
            ["2 months", TestTicketCogUnitTests.add_months(today, 2)],
            ["2/1/2025", dt.date.fromisoformat("2025-02-01")],
            ["in 5 days", today + dt.timedelta(days=5)],
            ["April 1, 2025", dt.date.fromisoformat("2025-04-01")],
        ]

        for check in expected_results:
            result = TicketsCog.parse_human_date(check[0])
            expected = check[1]
            if expected:
                log.debug(f">>> parse_human_date: {result} --> {expected}")
                self.assertEqual(synctime.date_str(expected), synctime.date_str(result))
            else:
                # invalid result
                self.assertIsNone(result, "Invalid dates expected to return empty result")


class TestTicketsCog(test_utils.MockBotTestCase):
    """TicketsCog feature tests use mock redmine session"""

    def setUp(self):
        super().setUp()
        self.bot = NetBot(self.redmine)
        self.bot.load_extension("netbot.cog_tickets")
        self.bot.formatter.post_setup(test_utils.mock_guilds())
        self.cog: TicketsCog = self.bot.cogs["TicketsCog"]


    async def test_new_ticket(self):
        # create a new ticket in the "network-software" channel
        ticket = self.mock_ticket()
        data = {
            'issue': ticket.asdict()
        }
        ctx = self.mock_context()
        ctx.channel = self.mock_channel(2424, "network-software")
        ctx.channel_id = ctx.channel.id

        # need to mock a thread for the ticket to create
        thread = self.mock_ticket_thread(2323, ticket.id)
        ctx.channel.create_thread = AsyncMock(return_value=thread)

        with patch.object(test_utils.MockSession, 'post', return_value=data) as patched_post:
            await self.cog.create_new_ticket(ctx, ticket.subject)

        # make sure it was created with the correct tracker
        patched_post.assert_called_once()
        response = json.loads(patched_post.call_args.args[1])
        log.debug(f"RESP: {response}")
        self.assertEqual(response['issue']['tracker_id'], 4)


@unittest.skipUnless(load_dotenv(), "ENV settings not available")
class IntegrationTestTicketsCog(test_utils.BotTestCase):
    """Integration test suite for TicketsCog"""

    def setUp(self):
        super().setUp()
        self.bot: NetBot = NetBot(self.redmine)
        self.bot.load_extension("netbot.cog_tickets")
        self.bot.formatter.post_setup(test_utils.mock_guilds())
        self.cog: TicketsCog = self.bot.cogs["TicketsCog"]


    def parse_markdown_link(self, text:str) -> tuple[str, str]:
        regex = r"\[`#(\d+)`\]\((.+)\)"
        m = re.search(regex, text)
        self.assertIsNotNone(m, f"could not find ticket number in response str: {text}")

        ticket_id = m.group(1)
        url = m.group(2)
        return ticket_id, url


    async def test_new_ticket(self):
        # create ticket with discord user, assert
        rand_str = test_utils.randstr(36)
        test_title = f"{rand_str} TEST {rand_str}"
        ctx = self.build_context()
        ctx.channel = unittest.mock.AsyncMock(discord.TextChannel)
        ctx.channel.name = f"channel-{self.tag}"
        ctx.channel.id = 4321

        await self.cog.create_new_ticket(ctx, test_title)
        response_str = ctx.respond.call_args.args[0]

        log.debug(f">>> {response_str}")

        ticket_id, url = self.parse_markdown_link(response_str)
        log.debug(f"created ticket: {ticket_id}, {url}")

        # get the ticket using id
        ctx = self.build_context()

        await self.cog.query(ctx, ticket_id)
        title = ctx.respond.call_args.kwargs['embed'].title
        self.assertIn(ticket_id, title)
        self.assertIn(test_title, title)

        # get the ticket using subject
        ctx = self.build_context()
        await self.cog.query(ctx, test_title)
        title = ctx.respond.call_args.kwargs['embed'].title
        self.assertIn(ticket_id, title)
        self.assertIn(test_title, title)

        # assign the ticket
        ctx = self.build_context()
        await self.cog.assign(ctx, ticket_id)
        embed = ctx.respond.call_args.kwargs['embed']
        self.assertIn(ticket_id, embed.title)
        self.assertIn(test_title, embed.title)
        found = False
        for field in embed.fields:
            if field.name == "Status":
                self.assertTrue(field.value.endswith(" New"))
                found = True
            if field.name == "Owner":
                self.assertIn(str(self.user.discord_id.id), field.value)
                found = True
        self.assertTrue(found, "Owner field not found in embed")

        # "progress" the ticket, setting it in-progress and assigning it to "me"
        ctx = self.build_context()
        await self.cog.progress(ctx, ticket_id)
        embed: discord.embed.Embed = ctx.respond.call_args.kwargs['embed']
        self.assertIn(ticket_id, embed.title)
        self.assertIn(test_title, embed.title)
        found = False
        for field in embed.fields:
            if field.name == "Status":
                self.assertTrue(field.value.endswith(" In Progress"))
                found = True
            if field.name == "Owner":
                self.assertIn(str(self.user.discord_id.id), field.value)
                found = True
        self.assertTrue(found, "Owner field not found in embed")

        # resolve the ticket
        ctx = self.build_context()
        await self.cog.resolve(ctx, ticket_id)
        embed: discord.embed.Embed = ctx.respond.call_args.kwargs['embed']
        self.assertIn(ticket_id, embed.title)
        self.assertIn(test_title, embed.title)
        found = False
        for field in embed.fields:
            if field.name == "Status":
                self.assertTrue(field.value.endswith(" Resolved"))
                found = True
            if field.name == "Owner":
                self.assertIn(str(self.user.discord_id.id), field.value)
                found = True
        self.assertTrue(found, "Owner field not found in embed")

        # delete ticket with redmine api, assert
        self.redmine.ticket_mgr.remove(int(ticket_id))
        # check that the ticket has been removed
        self.assertIsNone(self.redmine.ticket_mgr.get(int(ticket_id)))


    async def test_ticket_unassign(self):
        ticket = self.create_test_ticket()

        # unassign the ticket
        ctx = self.build_context()


        await self.cog.unassign(ctx, ticket.id)
        embed = ctx.respond.call_args.kwargs['embed']
        self.assertIn(str(ticket.id), embed.title)
        self.assertIn(ticket.subject, embed.title)
        found = False
        for field in embed.fields:
            if field.name == "Status":
                self.assertTrue(field.value.endswith(" New"))
                found = True
            if field.name == "Owner":
                self.fail("Owner name specified in epic for unassigned ticket")
        self.assertTrue(found, "Status field not found in embed")

        # delete ticket with redmine api, assert
        self.redmine.ticket_mgr.remove(ticket.id)
        self.assertIsNone(self.redmine.ticket_mgr.get(ticket.id))


    async def test_ticket_collaborate(self):
        ticket = self.create_test_ticket()
        discord_id = self.user.discord_id.id

        # add a collaborator
        ctx = self.build_context()
        await self.cog.collaborate(ctx, ticket.id)
        embed = ctx.respond.call_args.kwargs['embed']
        self.assertIn(str(ticket.id), embed.title)
        self.assertIn(ticket.subject, embed.title)

        # Check for list of collaborators
        found = False
        for field in embed.fields:
            if field.name == "Collaborators":
                self.assertIn(str(discord_id), field.value)
                found = True
        self.assertTrue(found, "Collaborators field not found in embed")

        # delete ticket with redmine api, assert
        self.redmine.ticket_mgr.remove(ticket.id)
        self.assertIsNone(self.redmine.ticket_mgr.get(int(ticket.id)))


    # create thread/sync
    async def test_thread_sync(self):
        # create a ticket and add a note
        note = f"This is a test note tagged with {self.tag}"
        ticket = self.create_test_ticket()
        self.redmine.ticket_mgr.append_message(ticket.id, self.user.login, note)

        # thread the ticket using
        ctx = self.build_context()
        ctx.channel = unittest.mock.AsyncMock(discord.TextChannel)
        ctx.channel.name = f"Test Channel {self.tag}"

        thread = unittest.mock.AsyncMock(discord.Thread)
        thread.name = f"Ticket #{ticket.id}: {ticket.subject}"

        ctx.channel.create_thread = unittest.mock.AsyncMock(return_value=thread)

        # TODO setup history with a message from the user - disabled while I work out the history mock.
        #thread.history = unittest.mock.AsyncMock(name="history")
        #thread.history.flatten = unittest.mock.AsyncMock(name="flatten", return_value=[message])

        await self.cog.thread(ctx, ticket.id)

        thread_response = str(ctx.channel.create_thread.call_args) # FIXME
        self.assertIn(str(ticket.id), thread_response)
        self.assertIn(ticket.subject, thread_response)

        # delete the ticket
        self.redmine.ticket_mgr.remove(ticket.id)


    async def test_query_term(self):
        ticket = self.create_test_ticket()

        # expected results:
        # 1. ticket ID
        result_1 = self.cog.resolve_query_term(ticket.id)
        self.assertEqual(ticket.id, result_1[0].id)

        # 2. ticket team
        # FIXME not stable, returns oldest intake, not newest
        #result_2 = self.cog.resolve_query_term("ticket-intake")
        #self.assertEqual(ticket.id, result_2[0].id)

        # 3. ticket user
        #result_3 = self.cog.resolve_query_term(self.user.login)
        #self.assertEqual(0, len(result_3)) # NOTHING ASSIGNED TO NEW TEST USER

        # 4. ticket query term
        #result_4 = self.cog.resolve_query_term(self.tag)
        #self.assertEqual(ticket.id, result_4[0].id)

        # delete the ticket
        self.redmine.ticket_mgr.remove(ticket.id)


    async def test_resolve_invalid_discord_user(self):
        ticket = self.create_test_ticket()

        ctx = self.build_context()
        test_name = "not-the-test-user" # invalid discord user
        ctx.user.name = test_name

        await self.cog.resolve(ctx, ticket.id)
        self.assertIn(test_name, ctx.respond.call_args.args[0])
        self.assertIn("/scn add", ctx.respond.call_args.args[0])

        # delete the ticket and confirm
        self.redmine.ticket_mgr.remove(ticket.id)
        self.assertIsNone(self.redmine.ticket_mgr.get(ticket.id))


    async def test_unassign_invalid_discord_user(self):
        ticket = self.create_test_ticket()

        ctx = self.build_context()
        test_name = "not-the-test-user" # invalid discord user
        ctx.user.name = test_name

        await self.cog.unassign(ctx, ticket.id)
        self.assertIn(test_name, ctx.respond.call_args.args[0])
        self.assertIn("/scn add", ctx.respond.call_args.args[0])

        # delete the ticket and confirm
        self.redmine.ticket_mgr.remove(ticket.id)
        self.assertIsNone(self.redmine.ticket_mgr.get(ticket.id))


    async def test_progress_invalid_discord_user(self):
        ticket = self.create_test_ticket()

        ctx = self.build_context()
        test_name = "not-the-test-user" # invalid discord user
        ctx.user.name = test_name

        await self.cog.progress(ctx, ticket.id)
        self.assertIn(test_name, ctx.respond.call_args.args[0])
        self.assertIn("/scn add", ctx.respond.call_args.args[0])

        # delete the ticket and confirm
        self.redmine.ticket_mgr.remove(ticket.id)
        self.assertIsNone(self.redmine.ticket_mgr.get(ticket.id))


    async def test_assign_invalid_discord_user(self):
        ticket = self.create_test_ticket()

        ctx = self.build_context()
        test_name = "not-the-test-user" # invalid discord user
        ctx.user.name = test_name

        await self.cog.assign(ctx, ticket.id)
        self.assertIn(test_name, ctx.respond.call_args.args[0])
        self.assertIn("/scn add", ctx.respond.call_args.args[0])

        # delete the ticket and confirm
        self.redmine.ticket_mgr.remove(ticket.id)
        self.assertIsNone(self.redmine.ticket_mgr.get(ticket.id))


    async def test_create_invalid_discord_user(self):
        ctx = self.build_context()
        test_name = "not-the-test-user" # invalid discord user
        ctx.user.name = test_name

        await self.cog.create_new_ticket(ctx, "test title")
        self.assertIn(test_name, ctx.respond.call_args.args[0])
        self.assertIn("/scn add", ctx.respond.call_args.args[0])


    async def test_get_trackers(self):
        ctx = AsyncMock(discord.AutocompleteContext)
        ctx.bot = self.bot
        ctx.value = ""
        trackers = get_trackers(ctx)
        self.assertTrue("Software-Dev" in trackers)

        ctx.value = "Ext"
        trackers = get_trackers(ctx)
        self.assertTrue("External-Comms-Intake" in trackers)


    async def test_get_priorities(self):
        ctx = AsyncMock(discord.AutocompleteContext)
        ctx.bot = self.bot
        ctx.value = ""
        priorities = get_priorities(ctx)
        self.assertTrue("EPIC" in priorities)

        ctx.value = "Lo"
        priorities = get_priorities(ctx)
        self.assertTrue("Low" in priorities)


    async def test_new_epic_use_case(self):
        #setup_logging()

        # build the context
        ctx = self.build_context()
        ctx.channel = unittest.mock.AsyncMock(discord.TextChannel)
        ctx.channel.name = f"channel-{self.tag}"
        ctx.channel.id = 4242

        # create a new epic
        await self.cog.create_new_ticket(ctx, f"test_new_epic_use_case {self.tag}")
        response_str = ctx.respond.call_args.args[0]

        ticket_id, url = self.parse_markdown_link(response_str)
        log.debug(f"created ticket: {ticket_id}, {url}")

        # set the priority
        await self.cog.priority(ctx, ticket_id, "EPIC")

        # get the ticket and validate priority
        check = self.redmine.ticket_mgr.get(int(ticket_id))
        self.assertIsNotNone(check)
        self.assertEqual(check.priority.name, "EPIC")

        # create ticket thread context
        ctx2 = self.build_context()
        ctx2.channel = unittest.mock.AsyncMock(discord.TextChannel)
        ctx2.channel.name = f"Ticket #{ticket_id}"
        ctx2.channel.id = 4242

        # create a sub-ticket
        await self.cog.create_new_ticket(ctx2, f"sub1 test_new_epic_use_case {self.tag}")
        response_str = ctx2.respond.call_args.args[0]
        sub1_id, url = self.parse_markdown_link(response_str)
        log.debug(f"created sub-ticket of ticket {ticket_id}: {sub1_id}, {url}")

        # confirm the parent
        check2 = self.redmine.ticket_mgr.get(int(sub1_id))
        self.assertIsNotNone(check2)
        self.assertIsNotNone(check2.parent, f"Ticket #{check2.id} has no parent.")
        self.assertEqual(check2.parent.id, int(ticket_id))

        # delete all the tickets
        self.redmine.ticket_mgr.remove(int(ticket_id))
        #self.redmine.ticket_mgr.remove(int(sub1_id))
        # check they've been removed
        self.assertIsNone(self.redmine.ticket_mgr.get(int(ticket_id)))
        self.assertIsNone(self.redmine.ticket_mgr.get(int(sub1_id)))


    async def test_description_modal_init(self):
        try:
            # build the context, including ticket
            ticket = self.create_test_ticket()
            ctx = self.build_context()
            ctx.channel = AsyncMock(discord.TextChannel)
            ctx.channel.name = f"Ticket #{ticket.id}"
            ctx.channel.id = test_utils.randint()
            ctx.send_modal = AsyncMock()
            await self.cog.edit_description(ctx)

            # scrape the model object from the mock context
            modal: EditDescriptionModal = ctx.send_modal.call_args[0][0]

            self.assertIn(str(ticket.id), modal.title)
            self.assertIsNotNone(modal.redmine)
            self.assertEqual(modal.children[0].value, ticket.description)
        finally:
            if ticket:
                # delete the ticket and confirm
                self.redmine.ticket_mgr.remove(ticket.id)
                self.assertIsNone(self.redmine.ticket_mgr.get(ticket.id))


    async def test_due_command(self):
        try:
            # create a ticket
            # set an invalid due date
            # check for error
            # set a valid dute date
            # check for valid due
            # check for discord callback...

            ticket = self.create_test_ticket()
            invalid_date = "blah blah blah"
            valid_date = "next week" # week + 7 days
            due_date = dt.date.today() + dt.timedelta(weeks=1)
            due_str = synctime.date_str(due_date)

            # A. build the context without ticket. should fail
            ctx = self.build_context()
            ctx.channel = AsyncMock(discord.TextChannel)
            ctx.channel.name = "Invalid Channel Name"
            await self.cog.due(ctx, valid_date)
            self.assertIn("Command only valid in ticket thread.", ctx.respond.call_args.args[0])

            # B. build the context including ticket, use invalid date
            ctx2 = self.build_context()
            ctx2.channel = AsyncMock(discord.TextChannel)
            ctx2.channel.name = f"Ticket #{ticket.id}"
            ctx2.channel.id = test_utils.randint()
            await self.cog.due(ctx2, invalid_date)
            response_str = ctx2.respond.call_args.args[0]
            self.assertIn(invalid_date, response_str)
            self.assertIn("Invalid date", response_str)

            # C. build a context using ticket, and valid date
            ctx3 = self.build_context()
            ctx3.channel = AsyncMock(discord.TextChannel)
            ctx3.channel.name = f"Ticket #{ticket.id}"
            ctx3.channel.id = test_utils.randint()
            ctx3.guild = AsyncMock(discord.Guild)
            ctx3.guild.fetch_scheduled_events.return_value = AsyncMock(list[discord.ScheduledEvent])

            await self.cog.due(ctx3, valid_date)
            response_3 = ctx3.respond.call_args.args[0]

            self.assertIn(due_str, response_3)
            self.assertIn("Updated due date", response_3)
            self.assertIn(str(ticket.id), response_3)

            # confirm create_scheduled_event TODO with correct date
            #event = await ctx3.guild.create_scheduled_event()
            #event.assert_called_once()

            # check the ticket
            updated = self.tickets_mgr.get(ticket.id)
            self.assertIsNotNone(updated)
            self.assertIsNotNone(updated.due_date)
            self.assertEqual(due_date, updated.due_date.date())
        finally:
            if ticket:
                # delete the ticket and confirm
                self.redmine.ticket_mgr.remove(ticket.id)
                self.assertIsNone(self.redmine.ticket_mgr.get(ticket.id))


    async def test_parent_command(self):
        parent_ticket = child_ticket = None
        try:
            # create a parent ticket
            # create a child ticket
            # invoke the `parent` command
            # validate the parent ticket has subticket child.
            parent_ticket = self.create_test_ticket()
            child_ticket = self.create_test_ticket()

            # build the context without ticket. should fail
            ctx = self.build_context()
            ctx.channel = AsyncMock(discord.TextChannel)
            ctx.channel.name = "Invalid Channel Name"
            await self.cog.parent(ctx, parent_ticket.id)
            self.assertIn("Command only valid in ticket thread.", ctx.respond.call_args.args[0])

            # build the context including ticket, use invalid date
            ctx2 = self.build_context()
            ctx2.channel = AsyncMock(discord.TextChannel)
            ctx2.channel.name = f"Ticket #{child_ticket.id}"
            ctx2.channel.id = test_utils.randint()
            await self.cog.parent(ctx2, parent_ticket.id)
            embed = ctx2.respond.call_args.kwargs['embed']
            self.assertIn(str(child_ticket.id), embed.title)
            # This checks the field in the embed, BUT it's not mocked correctly in the context
            # found = False
            # for field in embed.fields:
            #     if field.name == "Parent":
            #         print(f"---------- {field.value}")
            #         self.assertTrue(field.value.endswith(parent_ticket.id))
            #         found = True
            # self.assertTrue(found, "Parent field not found in embed")

            # validate the ticket
            check = self.redmine.ticket_mgr.get(child_ticket.id)
            self.assertIsNotNone(check.parent)
            self.assertEqual(parent_ticket.id, check.parent.id)

        finally:
            if child_ticket:
                # delete the ticket and confirm
                self.redmine.ticket_mgr.remove(child_ticket.id)
                self.assertIsNone(self.redmine.ticket_mgr.get(child_ticket.id))
            if parent_ticket:
                # delete the ticket and confirm
                self.redmine.ticket_mgr.remove(parent_ticket.id)
                self.assertIsNone(self.redmine.ticket_mgr.get(parent_ticket.id))
