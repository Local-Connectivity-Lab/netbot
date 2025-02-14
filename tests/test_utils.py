#!/usr/bin/env python3
"""Utilities to help testing"""

import json
import os
import time
import string
import random
import logging
import unittest
from urllib.parse import urlparse
from unittest import mock

import discord
from discord import ApplicationContext
from redmine.users import UserManager
from redmine.model import Message, User, Ticket, TicketsResult
from redmine.tickets import SCN_PROJECT_ID
from redmine.session import RedmineSession
from redmine.redmine import Client
from netbot.netbot import NetBot


log = logging.getLogger(__name__)


TEST_DATA = "data" # dir with test data


TEST_ADMIN = "test-admin"
TEST_USER = "test-user"


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
    return dumps(int(time.time()))[::-1]


def randstr(length:int=12) -> str:
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))


def randint(maxval:int=9999999) -> int:
    minval = 999 if maxval > 1000 else 0
    return random.randint(minval, maxval)


def load_json(filename:str):
    #with open(os.path.join(TEST_DATA, filename), 'r', encoding="utf-8") as file:
    with open(TEST_DATA + filename, 'r', encoding="utf-8") as file:
        return json.load(file)


def load_file(filename:str):
    with open(os.path.join(TEST_DATA, filename), 'r', encoding="utf-8") as file:
        return file.read()


def lookup_test_user(user_mgr:UserManager) -> User:
    user = user_mgr.find(TEST_USER)
    if not user:
        log.critical("No test user found! Name unknown: %s", TEST_USER)
    return user


def mock_ticket(**kwargs) -> Ticket:
    #return json_ticket('test-ticket.json', **kwargs)
    return json_ticket('issues/595.json', **kwargs)


def json_ticket(file:str, **kwargs) -> Ticket:
    with open('data/' + file, "r", encoding="utf-8") as ticket_file:
        data = json.load(ticket_file)
        ticket = Ticket(**data['issue'])
        ticket.id = random.randint(10000,99999)

        for key, value in kwargs.items():
            ticket.set_field(key, value)

        return ticket


def mock_user(tag: str) -> User:
    return User(
        id=random.randint(1000, 9999),
        login=f'test-{tag}',
        mail=f'{tag}@example.org',
        #custom_fields=[ {"id": 2, "name":'Discord ID', "value":f'discord-{tag}'} ],
        custom_fields=[],
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
    with open('data/custom_fields.json', "r", encoding="utf-8") as fields_file:
        return json.load(fields_file)


def remove_test_users(user_mgr:UserManager):
    for user in user_mgr.get_all():
        if user.login.startswith("test-") or user.login == "philion@acmerocket.com":
            log.info(f"Removing test user: {user.login}")
            user_mgr.remove(user)

# TODO delete test tickets and "Search for subject match in email threading" ticket. TAG with test too?


class MockSession(RedmineSession):
    """Magic session handling for test"""
    def __init__(self, token:str):
        super().__init__("http://example.com", token)
        self.test_cache = {}


    def get(self, query:str, impersonate_id:str|None=None):
        log.info(f"GET {query}, id={impersonate_id}")
        try:
            path = urlparse(query).path
            # check for cache?

            return load_json(path)
        except FileNotFoundError:
            return super().get(query, impersonate_id)
        except Exception as ex:
            log.error(f"{ex}")
            return None


    # def put(self, resource: str, data:str, impersonate_id:str|None=None) -> None:
    #     log.info(f"PUT {resource}, data={data} id={impersonate_id}")
    #     # UDATE!
    #     path = urlparse(resource).path
    #     self.test_cache[path] = data
    #     #raise RedmineException(f"PUT {resource} by {impersonate_id} failed, status=[{r.status_code}] {r.reason}", r.headers['X-Request-Id'])


    # def post(self, resource: str, data:str, user_login: str|None = None, files: list|None = None) -> dict|None:
    #     log.info(f"POST {resource}, data={data} user_login={user_login}")
    #     path = urlparse(resource).path
    #     # NEED A NEW ID!
    #     self.test_cache[path] = data
    #     #raise RedmineException(f"POST failed, status=[{r.status_code}] {r.reason}", r.headers['X-Request-Id'])


    # def delete(self, resource: str) -> None:
    #     log.info(f"DELETE {resource}")
    #     path = urlparse(resource).path
    #     if path in self.test_cache:
    #         log.debug(f"deleted {path}")
    #         del self.test_cache[path]


class MockRedmineTestCase(unittest.TestCase):
    """Abstract base class for mocked redmine testing"""

    @classmethod
    def setUpClass(cls):
        cls.tag:str = tagstr()
        session = MockSession(cls.tag)
        cls.redmine = Client.from_session(session, default_project=1)
        cls.user_mgr = cls.redmine.user_mgr
        cls.tickets_mgr = cls.redmine.ticket_mgr

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
        cls.user:User = lookup_test_user(cls.user_mgr)
        cls.user_mgr.cache.cache_user(cls.user)
        log.info("SETUP complete.")


    def create_test_message(self) -> Message:
        subject = f"TEST {self.tag} {unittest.TestCase.id(self)} {randint()}"
        text = f"This is a ticket for {unittest.TestCase.id(self)} with {self.tag}."
        message = Message(self.user.mail, subject, f"to-{self.tag}@example.com", f"cc-{self.tag}@example.com")
        message.set_note(text)

        return message


    def create_test_ticket(self, user:User = None, **params) -> Ticket:
        if user is None:
            user = self.user

        message = self.create_test_message()
        return self.redmine.ticket_mgr.create(user, message, **params)


class BotTestCase(RedmineTestCase, unittest.IsolatedAsyncioTestCase):
    """Abstract base class for testing Bot features"""

    def build_context(self) -> ApplicationContext:
        ctx = mock.AsyncMock(ApplicationContext)
        ctx.bot = mock.AsyncMock(NetBot)
        ctx.bot.redmine = self.redmine
        ctx.user = mock.AsyncMock(discord.Member)
        ctx.user.name = self.user.discord_id.name
        ctx.user.id = self.user.discord_id.id
        ctx.command = mock.AsyncMock(discord.ApplicationCommand)
        ctx.command.name = unittest.TestCase.id(self)
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


#if __name__ == '__main__':
    # when running this main, turn on DEBUG

    # load credentials
    #load_dotenv()

    # construct the client and run the email check
    #client = RedmineSession.fromenv()
    #users = UserManager(client)

    #user = users.get_by_name("philion")

    #with open('data/test-user.json', 'w') as f:
    #    json.dump(user, f)

    #remove_test_users(users)

    #audit_expected_values()
