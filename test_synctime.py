#!/usr/bin/env python3
"""unittest for time"""

import unittest
import logging

from dotenv import load_dotenv

import datetime as dt
import synctime
import test_utils



log = logging.getLogger(__name__)


@unittest.skipUnless(load_dotenv(), "ENV settings not available")
class TestTime(test_utils.RedmineTestCase):
    """testing time functions"""

    def test_redmine_times(self):
        # create a new ticket with unique subject
        ticket = self.create_test_ticket()

        test_channel = 4321
        sync_rec = ticket.validate_sync_record(expected_channel=test_channel)
        self.assertIsNotNone(sync_rec)
        self.assertEqual(sync_rec.ticket_id, ticket.id)
        self.assertEqual(sync_rec.channel_id, test_channel)

        # apply the new sync back to the ticket in test context!
        # happens aytomatically in sync context
        self.redmine.ticket_mgr.update_sync_record(sync_rec)

        # refetch ticket
        ticket2 = self.redmine.get_ticket(ticket.id)
        sync_rec2 = ticket2.validate_sync_record(expected_channel=1111) # NOT the test_channel
        log.info(f"ticket2 updated={ticket2.updated_on}, {synctime.age_str(ticket2.updated_on)} ago, channel: {sync_rec.channel_id}")

        self.assertIsNone(sync_rec2)

        # clean up
        self.redmine.remove_ticket(ticket.id)


    def test_redmine_isoformat(self):
        date_str = "2024-03-14T17:45:11Z"
        date = synctime.parse_str(date_str)
        self.assertIsNotNone(date)
        self.assertEqual(2024, date.year)
        self.assertEqual(3, date.month)
        self.assertEqual(14, date.day)

        date2 = dt.datetime.fromisoformat(date_str)
        self.assertIsNotNone(date2)
        self.assertEqual(2024, date2.year)
        self.assertEqual(3, date2.month)
        self.assertEqual(14, date2.day)




if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format="{asctime} {levelname:<8s} {name:<16} {message}", style='{')
    logging.getLogger("urllib3.connectionpool").setLevel(logging.INFO)

    unittest.main()
