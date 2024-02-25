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
        self.redmine = redmine.Client()


    def test_blocked_user(self):
        # create test user
        tag = test_utils.tagstr()
        user = test_utils.create_test_user(self.redmine, tag)

        # block
        self.redmine.block_user(user)
        self.assertTrue(self.redmine.is_user_blocked(user))

        # unblock
        self.redmine.unblock_user(user)
        self.assertFalse(self.redmine.is_user_blocked(user))

        # remove the test user
        self.redmine.remove_user(user)


    def test_blocked_create_ticket(self):
        # create test user
        tag = test_utils.tagstr()
        user = test_utils.create_test_user(self.redmine, tag)

        # block
        self.redmine.block_user(user)
        self.assertTrue(self.redmine.is_user_blocked(user))

        # create ticket, expect exception
        # NOPE self.assertRaises(redmine.RedmineException, self.redmine.create_ticket(user, "subject", "body"))
        try:
            self.redmine.create_ticket(user, "subject", "body")
            self.fail("Expected exception, none thrown.")
        except redmine.RedmineException as ex:
            self.assertEqual("[blocked]", ex.request_id)
        finally:
            # remove the test user
            self.redmine.remove_user(user)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format="{asctime} {levelname:<8s} {name:<16} {message}", style='{')
    logging.getLogger("urllib3.connectionpool").setLevel(logging.INFO)

    unittest.main()
