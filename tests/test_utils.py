#!/usr/bin/env python3
"""Utilities to help testing"""

import json
import time
import string
import random
import logging
import unittest
from unittest import mock

from dotenv import load_dotenv

import discord
from discord import ApplicationContext
from redmine.users import UserManager
from redmine.model import Message, User, NamedId, Ticket, TicketsResult, Team
from redmine.tickets import SCN_PROJECT_ID, TicketManager
from redmine.session import RedmineSession
from redmine.redmine import Client
from netbot.netbot import NetBot

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
    user = user_mgr.create(email, first, last, None)

    # create temp discord mapping with redmine api, assert
    # create_discord_mapping will cache the new user
    discord_user = "discord-" + tag ### <--
    user_mgr.create_discord_mapping(user, discord_user)

    # lookup based on login
    return user_mgr.get_by_name(user.login)


def mock_ticket(**kwargs) -> Ticket:
    with open('data/test-ticket.json', "r", encoding="utf-8") as ticket_file:
        data = json.load(ticket_file)
        ticket = Ticket(**data)
        ticket.id = random.randint(10000,99999)

        for key, value in kwargs.items():
            ticket.set_field(key, value)

        return ticket


def mock_user(tag: str) -> User:
    return User(
        id=5,
        login=f'test-{tag}',
        mail=f'{tag}@example.org',
        custom_fields=[ {"id": 2, "name":'Discord ID', "value":f'discord-{tag}'} ],
        admin=False,
        firstname='Test',
        lastname=tag,
        created_on='2020-07-29T00:37:38Z',
        updated_on='2020-02-21T02:14:12Z',
        last_login_on='2020-03-31T01:56:05Z',
        passwd_changed_on='2020-09-24T18:41:08Z',
        twofa_scheme=None,
        api_key='',
        status=''
    )


def mock_result(tickets: list[Ticket]) -> TicketsResult:
    return TicketsResult(len(tickets), 0, 25, tickets)


def mock_session() -> RedmineSession:
    return RedmineSession("http://example.com", "TeStInG-TOK-3N")


def custom_fields() -> dict:
    with open('data/custom-fields.json', "r", encoding="utf-8") as fields_file:
        return json.load(fields_file)


def remove_test_users(user_mgr:UserManager):
    for user in user_mgr.get_all():
        if user.login.startswith("test-") or user.login == "philion@acmerocket.com":
            log.info(f"Removing test user: {user.login}")
            user_mgr.remove(user)

# TODO delete test tickets and "Search for subject match in email threading" ticket. TAG with test too?


class MockUserManager(UserManager):
    """mock"""
    def get_all(self) -> list[User]:
        return []

    def get_all_teams(self, include_users: bool = True) -> dict[str, Team]:
        return {}


class MockTicketManager(TicketManager):
    """mock"""
    def __init__(self, sess: RedmineSession):
        super().__init__(sess, default_project=SCN_PROJECT_ID )


    def load_custom_fields(self) -> dict[str,NamedId]:
        """ override load_custom_fields to load expected custom fields. """
        result = {}
        with open('data/custom-fields.json', "r", encoding="utf-8") as fields_file:
            fields = json.load(fields_file)
            for name, value in fields.items():
                result[name] = NamedId(**value)

        log.debug(f"loading custom fields for test: {result}")
        return result


def create_mock_redmine():
    sess = mock_session()
    user_mgr = MockUserManager(sess)
    ticket_mgr = MockTicketManager(sess)
    return Client(sess, user_mgr, ticket_mgr)


class MockRedmineTestCase(unittest.TestCase):
    """Abstract base class for mocked redmine testing"""

    @classmethod
    def setUpClass(cls):
        cls.redmine = create_mock_redmine()
        cls.user_mgr = cls.redmine.user_mgr
        cls.tickets_mgr = cls.redmine.ticket_mgr
        cls.tag:str = tagstr()

        cls.user:User = mock_user(cls.tag)
        cls.user_mgr.cache.cache_user(cls.user)
        log.info(f"SETUP created mock user: {cls.user}")


    def create_message(self) -> Message:
        subject = f"TEST {self.tag} {unittest.TestCase.id(self)}"
        text = f"This is a ticket for {unittest.TestCase.id(self)} with {self.tag}."
        message = Message(self.user.mail, subject, f"to-{self.tag}@example.com", f"cc-{self.tag}@example.com")
        message.set_note(text)
        return message


    def message_from(self, ticket: Ticket) -> Message:
        message = Message(ticket.author.name, ticket.subject, f"to-{self.tag}@example.com", f"cc-{self.tag}@example.com")
        message.set_note(ticket.subject)
        return message


    def create_ticket(self) -> Ticket:
        return self.redmine.create_ticket(self.user, self.create_message())


class RedmineTestCase(unittest.TestCase):
    """Abstract base class for testing redmine features"""

    @classmethod
    def setUpClass(cls):
        sess = RedmineSession.fromenv()
        cls.redmine = Client.from_session(sess, SCN_PROJECT_ID)
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


    def create_test_ticket(self) -> Ticket:
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
        ctx.bot = mock.AsyncMock(NetBot)
        ctx.user = mock.AsyncMock(discord.Member)
        ctx.user.name = self.user.discord_id
        ctx.command = mock.AsyncMock(discord.ApplicationCommand)
        ctx.command.name = unittest.TestCase.id(self)
        log.debug(f"created ctx with {self.user.discord_id}: {ctx}")
        return ctx


def audit_expected_values():
    redmine = Client.from_session(RedmineSession.fromenv(), SCN_PROJECT_ID)

    # audit checks...
    # 1. make sure admin use exists
    user = redmine.user_mgr.find("admin") # TODO move to const
    if not user:
        log.error("Expected user not found: admin")

    # 2. custom fields exist
    for name in custom_fields():
        if name not in redmine.ticket_mgr.custom_fields:
            log.error("Expected custom field defination not found: %s", name)

    log.info("Audit complete.")


if __name__ == '__main__':
    # when running this main, turn on DEBUG
    logging.basicConfig(level=logging.INFO, format="{asctime} {levelname:<8s} {name:<16} {message}", style='{')
    logging.getLogger("urllib3.connectionpool").setLevel(logging.INFO)

    # load credentials
    load_dotenv()

    # construct the client and run the email check
    #client = RedmineSession.fromenv()
    #users = UserManager(client)

    #user = users.get_by_name("philion")

    #with open('data/test-user.json', 'w') as f:
    #    json.dump(user, f)

    #remove_test_users(users)

    #audit_expected_values()
