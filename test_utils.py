#test utils

import time
import logging
import unittest
import discord
from discord import ApplicationContext
from unittest import mock

log = logging.getLogger(__name__)


class CogTestCase(unittest.IsolatedAsyncioTestCase):
    
    # from https://github.com/tonyseek/python-base36/blob/master/base36.py
    def dumps(self, num:int)-> str:
        """dump an in as a base36 lower-case string"""
        alphabet = '0123456789abcdefghijklmnopqrstuvwxyz'
        if not isinstance(num, int):
            raise TypeError('number must be an integer')

        if num < 0:
            return '-' + self.dumps(-num)

        value = ''

        while num != 0:
            num, index = divmod(num, len(alphabet))
            value = alphabet[index] + value

        return value or '0'

    def tagstr(self) -> str:
        """convert the current timestamp in seconds to a base36 str"""
        return self.dumps(int(time.time()))
    
    
    def build_context(self) -> ApplicationContext:
        ctx = mock.AsyncMock(ApplicationContext)
        ctx.user = mock.AsyncMock(discord.Member)
        ctx.user.name = self.discord_user
        log.debug(f"created ctx with {self.discord_user}: {ctx}")
        return ctx
    
    
    def setUp(self):
        # create a test user. this could be a fixture!
        # create new test user name: test-12345@example.com, login test-12345
        self.tag = self.tagstr()
        first = "test-" + self.tag
        last = "Testy"
        self.fullName = f"{first} {last}"
        email = first + "@example.com"
        self.discord_user = "discord-" + self.tag 
        # create new redmine user, using redmine api
        self.user = self.redmine.create_user(email, first, last)
        self.assertIsNotNone(self.user)
        self.assertEqual(email, self.user.login)
        # create temp discord mapping with redmine api, assert 
        self.redmine.create_discord_mapping(self.user.login, self.discord_user)
        # reindex users and lookup based on login
        self.redmine.reindex_users()
        self.assertIsNotNone(self.redmine.find_user(self.user.login))
        self.assertIsNotNone(self.redmine.find_user(self.discord_user))


    def tearDown(self):
        # delete user with redmine api, assert
        self.redmine.remove_user(self.user.id)
        self.redmine.reindex_users()
        self.assertIsNone(self.redmine.find_user(self.user.login))
        self.assertIsNone(self.redmine.find_user(self.discord_user))
    