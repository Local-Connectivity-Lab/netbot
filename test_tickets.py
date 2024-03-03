#!/usr/bin/env python3
"""Redmine tickets manager test cases"""

import unittest
import logging

from dotenv import load_dotenv

import session
import tickets
import users
import test_utils


log = logging.getLogger(__name__)


@unittest.skipUnless(load_dotenv(), "ENV settings not available")
class TestTicketManager(unittest.TestCase):
    """Test suite for Redmine ticket manager"""

    def setUp(self):
        redmine_seesion = session.RedmineSession.fromenv()
        self.tickets_mgr = tickets.TicketManager(redmine_seesion)
        self.user_mgr = users.UserManager(redmine_seesion)


    def test_create_ticket(self):
        # create test user
        tag = test_utils.tagstr()
        subject = f"Test {tag} subject"
        body = f"Test {tag} body"

        user = test_utils.create_test_user(self.user_mgr, tag)

        ticket = None
        try:
            # create ticket
            ticket = self.tickets_mgr.create(user, subject, body)
            self.assertIsNotNone(ticket)
            self.assertEqual(subject, ticket.subject)
            self.assertEqual(body, ticket.description)

            check = self.tickets_mgr.get(ticket.id)
            self.assertIsNotNone(check)
            self.assertEqual(subject, check.subject)
            self.assertEqual(body, check.description)

            check2 = self.tickets_mgr.search(subject) # returns list
            self.assertIsNotNone(check2)
            self.assertEqual(1, len(check2))
            self.assertEqual(ticket.id, check2[0].id)
        finally:
            # delete ticket
            if ticket:
                self.tickets_mgr.remove(ticket.id)
                check3 = self.tickets_mgr.get(ticket.id)
                self.assertIsNone(check3)

            # remove the test user
            self.user_mgr.remove(user)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format="{asctime} {levelname:<8s} {name:<16} {message}", style='{')
    logging.getLogger("urllib3.connectionpool").setLevel(logging.INFO)

    unittest.main()
