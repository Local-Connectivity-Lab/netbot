#!/usr/bin/env python3
"""Redmine user manager test cases"""

import unittest
import logging
import json
from unittest.mock import MagicMock, patch

from dotenv import load_dotenv

from redmine.model import NamedId, DISCORD_ID_FIELD

from tests import test_utils


log = logging.getLogger(__name__)

class TestUserManager(test_utils.MockRedmineTestCase):
    """Mocked testing of user manager"""

    @patch('redmine.session.RedmineSession.get')
    @patch('redmine.session.RedmineSession.put')
    def test_create_discord_mapping(self, mock_put:MagicMock, mock_get:MagicMock):
        # create a new user
        user = test_utils.mock_user(unittest.TestCase.id(self))

        # add discord details
        discord_id = test_utils.randint()
        discord_name = test_utils.randstr()
        user.set_custom_field(2, DISCORD_ID_FIELD, f"{discord_id}|{discord_name}")

        # set up mock get return with the updated user
        mock_get.return_value = { "user": user.asdict() }

        # TEST create the discord mapping
        updated = self.user_mgr.create_discord_mapping(user, discord_id, discord_name)

        # this should call put on session.
        # mock_put ... use to test for proper calling info
        mock_put.assert_called_once()
        # check params to PUT?

        # get is called after the PUT to get a fresh user, mocked above.
        # confirm it is correct
        self.assertIsNotNone(updated)
        self.assertIsNotNone(updated.discord_id)
        self.assertEqual(discord_id, updated.discord_id.id)
        self.assertEqual(discord_name, updated.discord_id.name)

        mock_get.assert_called_once()
