#!/usr/bin/env python3
"""Redmine tickets manager test cases"""

import unittest
import logging

from dotenv import load_dotenv


import test_utils


log = logging.getLogger(__name__)


@unittest.skipUnless(load_dotenv(), "ENV settings not available")
class TestTicketManager(test_utils.RedmineTestCase):
    """Test suite for Redmine ticket manager"""

    def test_create_ticket(self):
        # create test user
        subject = f"Test {self.tag} subject"
        body = f"Test {self.tag} body"

        ticket = None
        try:
            # create ticket
            ticket = self.tickets_mgr.create(self.user, subject, body)
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


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG,
                        format="{asctime} {levelname:<8s} {name:<16} {message}",
                        datefmt='%Y-%m-%d %H:%M:%S',
                        style='{')
    logging.getLogger("urllib3.connectionpool").setLevel(logging.INFO)

    unittest.main()
