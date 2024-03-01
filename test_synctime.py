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
        user = self.redmine.find_user("philion") # FIXME: create a relaible test_user
        self.assertIsNotNone(user)
        subject = f"TEST ticket {tag}"
        ticket = self.redmine.create_ticket(user, subject, f"This for {self.id}-{tag}")
        updated = self.redmine.get_updated_field(ticket)

        test_channel = 4321
        sync_rec = self.redmine.get_sync_record(ticket, expected_channel=test_channel)
        self.assertIsNotNone(sync_rec)
        self.assertEqual(sync_rec.ticket_id, ticket.id)
        self.assertEqual(sync_rec.channel_id, test_channel)

        #### NOTE to morning self: catch 42 with get_sync_record returning None or a valid new erc with the wrong channel.
        #### FIX IN MORNING.

        # refetch ticket
        ticket2 = self.redmine.get_ticket(ticket.id)
        sync_rec2 = self.redmine.get_sync_record(ticket2, expected_channel=1111) # NOT the test_channel
        log.info(f"ticket updated={updated}, {synctime.age(updated)} ago, sync: {sync_rec}")

        self.assertIsNone(sync_rec2)

        # clean up
        self.redmine.remove_ticket(ticket.id)



if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format="{asctime} {levelname:<8s} {name:<16} {message}", style='{')
    logging.getLogger("urllib3.connectionpool").setLevel(logging.INFO)

    unittest.main()
