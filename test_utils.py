#test utils
"""Utilities to help testing"""

import time
import logging
import unittest
from unittest import mock

import discord
from discord import ApplicationContext
from redmine import Client


log = logging.getLogger(__name__)


# from https://github.com/tonyseek/python-base36/blob/master/base36.py
def dumps(num:int)-> str:
    """dump an in as a base36 lower-case string"""
    alphabet = '0123456789abcdefghijklmnopqrstuvwxyz'
    if not isinstance(num, int):
        raise TypeError('number must be an integer')

    if num < 0:
        return '-' + dumps(-num)

    value = ''

    while num != 0:
        num, index = divmod(num, len(alphabet))
        value = alphabet[index] + value

    return value or '0'


def tagstr() -> str:
    """convert the current timestamp in seconds to a base36 str"""
    return dumps(int(time.time()))

def create_test_user(redmine:Client, tag:str):
    # create new test user name: test-12345@example.com, login test-12345
    first = "test-" + tag
    last = "Testy"
    #fullname = f"{first} {last}" ### <--
    email = first + "@example.com"

    # create new redmine user, using redmine api
    user = redmine.create_user(email, first, last)

    # create temp discord mapping with redmine api, assert
    discord_user = "discord-" + tag ### <--
    redmine.create_discord_mapping(user.login, discord_user)

    # reindex users and lookup based on login
    redmine.reindex_users()
    return redmine.find_user(user.login)


class BotTestCase(unittest.IsolatedAsyncioTestCase):
    """Abstract base class for testing Bot features"""
    redmine = None
    usertag = None
    user = None

    @classmethod
    def setUpClass(cls):
        log.info("Setting up test fixtures")
        cls.redmine = Client()
        cls.usertag = tagstr()
        cls.user = create_test_user(cls.redmine, cls.usertag)
        log.info(f"Created test user: {cls.user}")


    @classmethod
    def tearDownClass(cls):
        log.info(f"Tearing down test fixtures: {cls.user}")
        cls.redmine.remove_user(cls.user.id)


    def build_context(self) -> ApplicationContext:
        ctx = mock.AsyncMock(ApplicationContext)
        ctx.user = mock.AsyncMock(discord.Member)
        ctx.user.name = self.discord_user
        log.debug(f"created ctx with {self.discord_user}: {ctx}")
        return ctx


    def create_test_ticket(self):
        subject = f"{unittest.TestCase.id(self)} {self.tag}"
        text = f"This is a ticket for {unittest.TestCase.id(self)} with {self.tag}."
        return self.redmine.create_ticket(self.user, subject, text)


    def setUp(self):
        self.tag = self.__class__.usertag # TODO just rename usertag to tag - represents the suite run
        self.assertIsNotNone(self.tag)
        self.assertIsNotNone(self.user)

        self.full_name = self.user.firstname + " " +  self.user.lastname
        self.discord_user = self.redmine.get_discord_id(self.user)

        self.assertIsNotNone(self.redmine.find_user(self.user.login))
        self.assertIsNotNone(self.redmine.find_user(self.discord_user))

        log.debug(f"setUp user {self.user.login} {self.discord_user}")
