#!/usr/bin/env python3
"""Redmine test cases"""

import unittest
import logging

from dotenv import load_dotenv

from redmine.model import Message
from redmine.redmine import DEFAULT_TRACKER

from tests import test_utils


log = logging.getLogger(__name__)


class TestRedmine(test_utils.MockRedmineTestCase):
    """Mocked testing of redmine function"""

    def test_enumerations(self):
        p = self.redmine.ticket_mgr.get_priority("EPIC")
        self.assertIsNotNone(p, "Expected EPIC priority, not found.")

        t = self.redmine.ticket_mgr.get_tracker("Software-Dev")
        self.assertIsNotNone(t, "Expected Software-Dev tracker, not found.")

    def test_get_ticket(self):
        ticket = self.redmine.ticket_mgr.get(595)
        self.assertIsNotNone(ticket)
        self.assertEqual(len(ticket.children), 8)

    def test_reindex(self):
        self.redmine.reindex()

    def test_find_tracker(self):
        message = Message("test@example.com", "[Infra-Config] Test Subject")
        message.set_note("tracker=Research")

        tracker = self.redmine.find_tracker_in_message(message)
        self.assertEqual(tracker.name, "Infra-Config")

        message2 = Message("test@example.com", "[IMPORTANT] Test Subject 2")
        self.assertEqual(self.redmine.find_tracker_in_message(message2).name, DEFAULT_TRACKER)


@unittest.skipUnless(load_dotenv(), "ENV settings not available")
class TestRedmineIntegration(test_utils.RedmineTestCase):
    """Test suite for Redmine client"""

    def test_block_user(self):
        # block
        self.user_mgr.block(self.user)
        self.assertTrue(self.user_mgr.is_blocked(self.user))

        # unblock
        self.user_mgr.unblock(self.user)
        self.assertFalse(self.user_mgr.is_blocked(self.user))


    def test_blocked_create_ticket(self):
        # block
        self.user_mgr.block(self.user)
        log.debug(f"blocked user: {self.user}")

        self.assertTrue(self.user_mgr.is_blocked(self.user))

        # create ticket for blocked
        # test specific implementation of Client.create_ticket
        ticket = self.redmine.create_ticket(self.user, self.create_test_message())
        self.assertIsNotNone(ticket)
        log.debug(f"ticket: {ticket}")
        self.assertEqual("Reject", ticket.status.name)

        # remove the ticket and unbluck the user
        self.tickets_mgr.remove(ticket.id)
        self.user_mgr.unblock(self.user)
        self.assertFalse(self.user_mgr.is_blocked(self.user))


    def test_ticket_query(self):
        # create a ticket with the tag in the body, not the subject
        ticket = self.create_test_ticket()
        self.assertIsNotNone(ticket)

        # search for the ticket
        tickets = self.redmine.ticket_mgr.search(self.tag)

        self.assertIsNotNone(tickets)
        self.assertEqual(1, len(tickets))
        self.assertEqual(ticket.id, tickets[0].id)

        # clean up
        self.redmine.ticket_mgr.remove(ticket.id)
