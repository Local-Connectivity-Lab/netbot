#!/usr/bin/env python3
"""Redmine tickets manager test cases"""

import unittest
import logging
import json
from unittest.mock import MagicMock, patch

from dotenv import load_dotenv

from redmine.model import ParentTicket

from tests import test_utils


log = logging.getLogger(__name__)

class TestTicketManager(test_utils.MockRedmineTestCase):
    """Mocked testing of ticket manager"""

    @unittest.skip # FIXME currently rewriting
    @patch('redmine.session.RedmineSession.get')
    def test_expired_tickets(self, mock_get:MagicMock):
        # setup the mock tickets
        ticket = test_utils.mock_ticket()
        result = test_utils.mock_result([
            ticket,
            test_utils.mock_ticket(),
        ])
        mock_get.return_value = result.asdict()

        expired = self.tickets_mgr.expired_tickets()
        self.assertGreater(len(expired), 0)
        expired_ids = [ticket.id for ticket in expired]
        self.assertIn(ticket.id, expired_ids)
        #FIXME mock_get.assert_called_once()


    @unittest.skip # FIXME currently breaking mock testing
    @patch('redmine.session.RedmineSession.post')
    def test_default_project_id(self, mock_post:MagicMock):
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


    @unittest.skip
    # note: patching 'get' instead of 'post': the get gets the new ticket
    @patch('redmine.session.RedmineSession.post')
    def test_create_sub_ticket(self, mock_post:MagicMock):

        # setup the mock tickets
        ticket = test_utils.mock_ticket(parent=ParentTicket(id=4242, subject="Test Parent Ticket"))
        mock_post.return_value = { "issue": ticket.asdict() }

        msg = self.message_from(ticket)
        check = self.tickets_mgr.create(self.user, msg, parent_issue_id=4242)

        post_json = json.loads(mock_post.call_args[0][1])["issue"]
        self.assertEqual(4242, post_json['parent_issue_id'])

        mock_post.assert_called_once()
        self.assertEqual(4242, check.parent.id)

    # needs to patch 10 calls to GET
    # @patch('redmine.session.RedmineSession.get')
    # def test_epics(self, mock_get:MagicMock):
    #     # setup the mock tickets
    #     mock_get.return_value = test_utils.load_json("/epics.json")

    #     check = self.tickets_mgr.get_epics()
    #     self.assertEqual(10, len(check))
    #     #self.assertEqual(9, len(check[0].children))


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
