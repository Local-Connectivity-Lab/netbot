#!/usr/bin/env python3
"""Redmine test cases"""

import unittest
import logging

from dotenv import load_dotenv

import redmine
import test_utils


log = logging.getLogger(__name__)


@unittest.skipUnless(load_dotenv(), "ENV settings not available")
class TestRedmine(unittest.TestCase):
    """Test suite for Redmine client"""

    def setUp(self):
        self.redmine = redmine.Client.fromenv()


    def test_blocked_user(self):
        # create test user
        tag = test_utils.tagstr()
        user = test_utils.create_test_user(self.redmine, tag)

        # block
        self.redmine.user_mgr.block(user)
        self.assertTrue(self.redmine.user_mgr.is_blocked(user))

        # unblock
        self.redmine.user_mgr.unblock(user)
        self.assertFalse(self.redmine.user_mgr.is_blocked(user))

        # remove the test user
        self.redmine.user_mgr.remove(user)


    def test_blocked_create_ticket(self):
        # create test user
        tag = test_utils.tagstr()
        user = test_utils.create_test_user(self.redmine, tag)

        try:
            # block
            self.redmine.user_mgr.block(user)
            self.assertTrue(self.redmine.user_mgr.is_blocked(user))

            # create ticket for blocked
            ticket = self.redmine.create_ticket(user, "subject", "body")
            self.assertEqual("Reject", ticket.status.name)

        finally:
            # remove the test user
            self.redmine.user_mgr.remove(user)


    def test_client_timeout(self):
        # construct an invalid client to try to get a timeout
        try:
            client = redmine.Client("http://192.168.1.42/", "bad-token")
            log.info(client)
        except TimeoutError:
            self.fail("Got unexpected timeout")


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format="{asctime} {levelname:<8s} {name:<16} {message}", style='{')
    logging.getLogger("urllib3.connectionpool").setLevel(logging.INFO)

    unittest.main()
