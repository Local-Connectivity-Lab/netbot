#!/usr/bin/env python3
"""Utilities to help testing"""

import time
import string
import random
import logging
import unittest
from unittest import mock

from dotenv import load_dotenv

import discord
from discord import ApplicationContext
from users import User, UserManager
from model import Message
import session
import tickets
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


def randstr(length:int=12) -> str:
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))


def create_test_user(user_mgr:UserManager, tag:str):
    # create new test user name: test-12345@example.com, login test-12345
    first = "test-" + tag
    last = "Testy"
    #fullname = f"{first} {last}" ### <--
    email = first + "@example.com"

    # create new redmine user, using redmine api
    user = user_mgr.create(email, first, last)

    # create temp discord mapping with redmine api, assert
    # create_discord_mapping will cache the new user
    discord_user = "discord-" + tag ### <--
    user_mgr.create_discord_mapping(user, discord_user)

    # lookup based on login
    return user_mgr.get_by_name(user.login)


def remove_test_users(user_mgr:UserManager):
    for user in user_mgr.get_all():
        if user.login.startswith("test-") or user.login == "philion@acmerocket.com":
            log.info(f"Removing test user: {user.login}")
            user_mgr.remove(user)

# TODO delete test tickets and "Search for subject match in email threading" ticket. TAG with test too?


class RedmineTestCase(unittest.TestCase):
    """Abstract base class for testing redmine features"""

    @classmethod
    def setUpClass(cls):
        sess = session.RedmineSession.fromenv()
        cls.redmine = Client(sess)
        cls.user_mgr = cls.redmine.user_mgr
        cls.tickets_mgr = cls.redmine.ticket_mgr
        cls.tag:str = tagstr()
        cls.user:User = create_test_user(cls.user_mgr, cls.tag)
        cls.user_mgr.cache.cache_user(cls.user)
        log.info(f"SETUP created test user: {cls.user}")

    @classmethod
    def tearDownClass(cls):
        if cls.user:
            cls.user_mgr.remove(cls.user)
            log.info(f"TEARDOWN removed test user: {cls.user}")


    def create_test_ticket(self) -> tickets.Ticket:
        subject = f"TEST {self.tag} {unittest.TestCase.id(self)}"
        text = f"This is a ticket for {unittest.TestCase.id(self)} with {self.tag}."
        message = Message(self.user.mail, subject, f"to-{self.tag}@example.com", f"cc-{self.tag}@example.com")
        message.set_note(text)

        ticket = self.redmine.create_ticket(self.user, message)
        return ticket


class BotTestCase(RedmineTestCase, unittest.IsolatedAsyncioTestCase):
    """Abstract base class for testing Bot features"""

    def build_context(self) -> ApplicationContext:
        ctx = mock.AsyncMock(ApplicationContext)
        ctx.user = mock.AsyncMock(discord.Member)
        ctx.user.name = self.user.discord_id
        ctx.command = mock.AsyncMock(discord.ApplicationCommand)
        ctx.command.name = unittest.TestCase.id(self)
        log.debug(f"created ctx with {self.user.discord_id}: {ctx}")
        return ctx


if __name__ == '__main__':
    # when running this main, turn on DEBUG
    logging.basicConfig(level=logging.DEBUG, format="{asctime} {levelname:<8s} {name:<16} {message}", style='{')
    logging.getLogger("urllib3.connectionpool").setLevel(logging.INFO)

    # load credentials
    load_dotenv()

    # construct the client and run the email check
    client = session.RedmineSession.fromenv()
    users = UserManager(client)
    remove_test_users(users)
