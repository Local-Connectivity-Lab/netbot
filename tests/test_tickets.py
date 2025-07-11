#!/usr/bin/env python3
"""Redmine tickets manager test cases"""

import datetime
import unittest
import logging
import json
from unittest.mock import patch, AsyncMock

from dotenv import load_dotenv

from redmine.model import ParentTicket, synctime, TicketStatus, Ticket
from redmine.tickets import TICKET_DUSTY_AGE, TICKET_MAX_AGE

from tests import test_utils


log = logging.getLogger(__name__)


class TestTicketManager(test_utils.MockRedmineTestCase):
    """Mocked testing of ticket manager"""

    def test_dusty_tickets(self):
        # to find dusty tickets, a dusty ticket needs to be created.
        ticket1 = self.mock_ticket(
            status=TicketStatus(id=2,name="In Progress",is_closed=False),
            updated_on=synctime.ago(days=TICKET_DUSTY_AGE+1),
        )
        # cache a search result
        self.session.cache_results([ticket1])

        self.assertGreaterEqual(synctime.age(ticket1.updated_on), datetime.timedelta(days=TICKET_DUSTY_AGE))

        dusty_tickets = self.tickets_mgr.dusty()
        self.assertGreaterEqual(len(dusty_tickets), 1, "No dusty tickets found")
        for ticket in dusty_tickets:
            age = synctime.age(ticket.updated_on)
            self.assertGreaterEqual(age.days, TICKET_DUSTY_AGE)
            self.assertEqual(ticket.status.name, "In Progress")


    def test_recyclable_tickets(self):
        # to find dusty tickets, a dusty ticket needs to be created.
        ticket1 = self.mock_ticket(
            status=TicketStatus(id=2,name="In Progress",is_closed=False),
            updated_on=synctime.ago(days=TICKET_MAX_AGE+1),
        )
        # cache a search result
        self.session.cache_results([ticket1])

        self.assertGreaterEqual(synctime.age(ticket1.updated_on), datetime.timedelta(days=TICKET_DUSTY_AGE))

        dusty_tickets = self.tickets_mgr.dusty()
        self.assertGreaterEqual(len(dusty_tickets), 1, "No recyclable tickets found")
        for ticket in dusty_tickets:
            age = synctime.age(ticket.updated_on)
            self.assertGreaterEqual(age.days, TICKET_MAX_AGE)
            self.assertEqual(ticket.status.name, "In Progress")


    @patch('tests.mock_session.MockSession.post')
    def test_default_project_id(self, mock_post:AsyncMock):
        test_proj_id = "42"

        msg = self.create_message()
        # note to future self: mock response to create should have content of crete request

        # setup the mock tickets
        ticket = test_utils.mock_ticket()
        mock_post.return_value = { "issue": ticket.asdict() }

        self.tickets_mgr.create(self.user, msg, test_proj_id)

        resp_ticket = json.loads(mock_post.call_args[0][1])["issue"]

        mock_post.assert_called_once()
        self.assertEqual(test_proj_id, resp_ticket['project_id'])


    # note: patching 'get' instead of 'post': the get gets the new ticket
    @patch('tests.mock_session.MockSession.post')
    def test_create_sub_ticket(self, mock_post:AsyncMock):

        # setup the mock tickets
        ticket = test_utils.mock_ticket(parent=ParentTicket(id=4242, subject="Test Parent Ticket"))
        mock_post.return_value = { "issue": ticket.asdict() }

        msg = self.message_from(ticket)
        check = self.tickets_mgr.create(self.user, msg, parent_issue_id=4242)

        post_json = json.loads(mock_post.call_args[0][1])["issue"]
        self.assertEqual(4242, post_json['parent_issue_id'])

        mock_post.assert_called_once()
        self.assertEqual(4242, check.parent.id)


    def test_updated_by_note(self):
        with open("data/1712.json", 'rb') as file:
            data = json.load(file)
            ticket = Ticket(**data['issue'])

            self.assertIsNotNone(ticket)
            self.assertEqual(1712, ticket.id)


# The integration test suite is only run if the ENV settings are configured correctly
@unittest.skipUnless(load_dotenv(), "ENV settings not available")
class TestIntegrationTicketManager(test_utils.RedmineTestCase):
    """Test suite for Redmine ticket manager"""

    def test_create_ticket(self):
        ticket = None
        try:
            # create ticket
            ticket = self.create_test_ticket()
            self.assertIsNotNone(ticket)
            #self.assertEqual(subject, ticket.subject)
            #self.assertEqual(body, ticket.description)

            check = self.tickets_mgr.get(ticket.id)
            self.assertIsNotNone(check)
            self.assertEqual(ticket.subject, check.subject)
            self.assertEqual(ticket.id, check.id)

            check2 = self.tickets_mgr.search(ticket.subject) # returns list
            self.assertIsNotNone(check2)
            self.assertEqual(1, len(check2))
            self.assertEqual(ticket.id, check2[0].id)
        finally:
            # delete ticket
            if ticket:
                self.tickets_mgr.remove(ticket.id)
                check3 = self.tickets_mgr.get(ticket.id)
                self.assertIsNone(check3)


    def test_ticket_unassign(self):
        ticket = self.create_test_ticket()

        # unassign the ticket
        self.tickets_mgr.unassign(ticket.id)

        check = self.tickets_mgr.get(ticket.id)
        self.assertEqual("New", check.status.name)
        self.assertEqual("", check.assigned)

        # delete ticket with redmine api, assert
        self.redmine.ticket_mgr.remove(int(ticket.id))
        self.assertIsNone(self.redmine.ticket_mgr.get(int(ticket.id)))


    def test_ticket_progress(self):
        ticket = self.create_test_ticket()

        #print(">>>>> ", self.tickets_mgr.)

        # progress the ticket
        check = self.tickets_mgr.progress_ticket(ticket.id, self.user.login)
        self.assertEqual(check.assigned_to.id, self.user.id)
        self.assertEqual(check.status.name, "In Progress")

        # delete ticket with redmine api, assert
        self.redmine.ticket_mgr.remove(ticket.id)
        self.assertIsNone(self.redmine.ticket_mgr.get(ticket.id))


    def test_ticket_collaborate(self):
        ticket = self.create_test_ticket()

        # unassign the ticket
        self.tickets_mgr.collaborate(ticket.id, self.user)

        check = self.tickets_mgr.get(ticket.id, include="watchers")
        self.assertEqual(self.user.name, check.watchers[0].name)
        self.assertEqual(self.user.id, check.watchers[0].id)

        # delete ticket with redmine api, assert
        self.redmine.ticket_mgr.remove(int(ticket.id))
        self.assertIsNone(self.redmine.ticket_mgr.get(int(ticket.id)))


    def test_epics(self):
        check_id = 1049
        check = self.tickets_mgr.get_epics()

        self.assertEqual(10, len(check))

        found = None
        for e in check:
            if e.id == check_id:
                found = e
                break

        self.assertTrue(found, f"Ticket {check_id} not found in epics")
        #self.assertEqual(found.id, check_id)
        #self.assertEqual(len(found.children), 8)
        # check which are open vs closed.


    def test_create_sub_ticket(self):
        # get an epic
        epic = self.tickets_mgr.get_epics()[0]

        # get the admin user
        user = self.user_mgr.find(test_utils.TEST_ADMIN)

        ticket = self.create_test_ticket(user, parent_issue_id=epic.id)
        self.assertIsNotNone(ticket)
        self.assertIsNotNone(ticket.parent, f"ticket {ticket.id} has no parent")
        self.assertEqual(epic.id, ticket.parent.id)

        # delete ticket with redmine api, assert
        self.redmine.ticket_mgr.remove(ticket.id)
        self.assertIsNone(self.redmine.ticket_mgr.get(ticket.id))


    def test_dusty_tickets(self):
        dusty = self.tickets_mgr.dusty()
        for ticket in dusty:
            log.info(f"{ticket.id} age:{ticket.age_str} - {ticket.subject}")
