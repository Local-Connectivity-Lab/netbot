#!/usr/bin/env python3
"""Redmine test cases"""

import unittest
import logging
#from unittest.mock import patch

from dotenv import load_dotenv

from redmine import redmine
from redmine import session
from tests import test_utils



logging.getLogger().setLevel(logging.ERROR)


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
        self.assertTrue(self.user_mgr.is_blocked(self.user))

        # create ticket for blocked
        ticket = self.create_test_ticket()
        self.assertIsNotNone(ticket)
        log.info(f"ticket: {ticket}")
        self.assertEqual("Reject", ticket.status.name)

        # remove the ticket and unbluck the user
        self.tickets_mgr.remove(ticket.id)
        self.user_mgr.unblock(self.user)
        self.assertFalse(self.user_mgr.is_blocked(self.user))


    @unittest.skip("takes too long and fills the log with junk")
    def test_client_timeout(self):
        # construct an invalid client to try to get a timeout
        try:
            bad_session = session.RedmineSession("http://192.168.1.42/", "bad-token")
            client = redmine.Client.from_session(bad_session, default_project=1)
            self.assertIsNotNone(client)
            #log.info(client)
        except Exception:
            self.fail("Got unexpected timeout")


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


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format="{asctime} {levelname:<8s} {name:<16} {message}", style='{')
    logging.getLogger("urllib3.connectionpool").setLevel(logging.INFO)

    unittest.main()
