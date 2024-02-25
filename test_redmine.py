#!/usr/bin/env python3
"""Redmine test cases"""

import unittest
import logging

from dotenv import load_dotenv

import redmine


log = logging.getLogger(__name__)


@unittest.skipUnless(load_dotenv(), "ENV settings not available")
class TestRedmine(unittest.TestCase):
    """Test suite for Redmine client"""

    def setUp(self):
        self.redmine = redmine.Client()


    def test_custom_fields(self):

        # create test ticket
        admin = self.redmine.find_user("admin")
        ticket = self.redmine.create_ticket(admin, subject="subject", body="body")
        # delete test ticket
        self.redmine.remove_ticket(ticket.id)

        fields = self.redmine.get_custom_fields("scn")
        log.debug(f"fields: {fields}")
        self.assertEqual(fields["syncdata"], 4)

        self.redmine.add_custom_field("cf_yoyo")
        fields2 = self.redmine.get_custom_fields("scn")
        self.assertIsNotNone(fields2["cf_yoyo"])

        # delete?





if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format="{asctime} {levelname:<8s} {name:<16} {message}", style='{')
    logging.getLogger("urllib3.connectionpool").setLevel(logging.INFO)

    unittest.main()
