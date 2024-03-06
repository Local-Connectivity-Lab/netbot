#!/usr/bin/env python3
"""unittest for time"""

import unittest
import logging

from dotenv import load_dotenv

import redmine
import synctime
import test_utils



log = logging.getLogger(__name__)


@unittest.skipUnless(load_dotenv(), "ENV settings not available")
class TestTime(unittest.TestCase):
    """testing"""
    def setUp(self):
        self.redmine = redmine.Client.fromenv()

    def test_redmine_times(self):
        #start = synctime.now()

        # create a new ticket with unique subject
        tag = test_utils.tagstr()
        user = self.redmine.user_mgr.find("admin") # FIXME: create a relaible test_user
        self.assertIsNotNone(user)
        subject = f"TEST ticket {tag}"
        ticket = self.redmine.create_ticket(user, subject, f"This for {self.id}-{tag}") # FIXME standard way to create test ticket!

        test_channel = 4321
        sync_rec = ticket.get_sync_record(expected_channel=test_channel)
        self.assertIsNotNone(sync_rec)
        self.assertEqual(sync_rec.ticket_id, ticket.id)
        self.assertEqual(sync_rec.channel_id, test_channel)

        # apply the new sync back to the ticket in test context!
        # happens aytomatically in sync context
        self.redmine.ticket_mgr.update_sync_record(sync_rec)

        # refetch ticket
        ticket2 = self.redmine.get_ticket(ticket.id)
        sync_rec2 = ticket2.get_sync_record(expected_channel=1111) # NOT the test_channel
        log.info(f"ticket2 updated={ticket2.updated_on}, {synctime.age_str(ticket2.updated_on)} ago, channel: {sync_rec.channel_id}")

        self.assertIsNone(sync_rec2)

        # clean up
        self.redmine.remove_ticket(ticket.id)



if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format="{asctime} {levelname:<8s} {name:<16} {message}", style='{')
    logging.getLogger("urllib3.connectionpool").setLevel(logging.INFO)

    unittest.main()
