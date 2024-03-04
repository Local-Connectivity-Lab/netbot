#!/usr/bin/env python3
"""Redmine test cases"""

import unittest
import logging

from dotenv import load_dotenv

import redmine
import test_utils


logging.getLogger().setLevel(logging.ERROR)


log = logging.getLogger(__name__)


@unittest.skipUnless(load_dotenv(), "ENV settings not available")
class TestRedmine(test_utils.RedmineTestCase):
    """Test suite for Redmine client"""

    def test_block_user(self):
        # block
        self.user_mgr.block(self.user)
        self.assertTrue(self.user_mgr.is_blocked(self.user))

        # unblock
        self.user_mgr.unblock(self.user)
        self.assertFalse(self.user_mgr.is_blocked(self.user))

    """
    def test_blocked_create_ticket(self):
        try:
            # block
            self.user_mgr.block(self.user)
            self.assertTrue(self.redmine.user_mgr.is_blocked(self.user))

            # create ticket for blocked
            ticket = self.create_ticket(self.user, "subject", "body")
            self.assertEqual("Reject", ticket.status.name)

        finally:
            # remove the test user
            self.redmine.user_mgr.remove(user)
    """


    def test_client_timeout(self):
        # construct an invalid client to try to get a timeout
        try:
            client = redmine.Client("http://192.168.1.42/", "bad-token")
            self.assertIsNotNone(client)
            #log.info(client)
        except Exception:
            self.fail("Got unexpected timeout")


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format="{asctime} {levelname:<8s} {name:<16} {message}", style='{')
    logging.getLogger("urllib3.connectionpool").setLevel(logging.INFO)

    unittest.main()
