#!/usr/bin/env python3
"""Redmine tickets manager test cases"""

import unittest
import logging
from unittest.mock import MagicMock, patch

from dotenv import load_dotenv

from tickets import TicketManager

import test_utils


log = logging.getLogger(__name__)

class TestTicketManager(unittest.TestCase):
    """Mocked testing of ticket manager"""
    def mock_mgr(self):
        return TicketManager(test_utils.mock_session())

    @patch('tickets.TicketManager.load_custom_fields')
    @patch('session.RedmineSession.get')
    def test_expired_tickets(self, mock_get:MagicMock, mock_cf:MagicMock):
        # setup custom fields
        mock_cf.return_value = test_utils.custom_fields() # TODO move to mgr setup

        # setup the mock tickets
        ticket = test_utils.mock_ticket()
        result = test_utils.mock_result([
            ticket,
            test_utils.mock_ticket(),
        ])
        mock_get.return_value = result.asdict()

        expired = self.mock_mgr().expired_tickets()
        self.assertGreater(len(expired), 0)
        expired_ids = [ticket.id for ticket in expired]
        self.assertIn(ticket.id, expired_ids)
        mock_get.assert_called_once()


# The integration test suite is only run if the ENV settings are configured correctly
@unittest.skipUnless(load_dotenv(), "ENV settings not available")
class TestIntegrationTicketManager(test_utils.RedmineTestCase):
    """Test suite for Redmine ticket manager"""

    def test_create_ticket(self):
        ticket = None
        try:
            # create ticket
            ticket = self.create_test_ticket()
            self.assertIsNotNone(ticket)
            #self.assertEqual(subject, ticket.subject)
            #self.assertEqual(body, ticket.description)

            check = self.tickets_mgr.get(ticket.id)
            self.assertIsNotNone(check)
            self.assertEqual(ticket.subject, check.subject)
            self.assertEqual(ticket.id, check.id)

            check2 = self.tickets_mgr.search(ticket.subject) # returns list
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
