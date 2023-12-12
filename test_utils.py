#test utils

import time
import logging

from typing import Any
import unittest
from unittest import mock
from unittest.mock import AsyncMock
from dotenv import load_dotenv

from typing import Any

from redmine import Client
from netbot import NetBot
import discord
from discord import ApplicationContext, Interaction
from discord.ext.bridge import Bot


log = logging.getLogger(__name__)


test_username: str = "acmerocket"
test_username2: str = "infrared0"
test_user_id: int = 5

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


def build_context(author_id: int, username: str) -> ApplicationContext:
        class MockedAuthor:
            def __init__(self, user_id: int, username: str):
                self.id = user_id
                self.name = username

        ctx = mock.AsyncMock(ApplicationContext)
        ctx.user = MockedAuthor(author_id, username)
        
        #ctx.respond = AsyncMock(
        #    discord.ApplicationContext.respond,
        #    side_effect=lambda *args, **kwargs: build_response("mock_respond", *args, **kwargs))
        #ctx.send = AsyncMock(
        #    discord.ApplicationContext.send,
        #    side_effect=lambda *args, **kwargs: build_response("mock_send", *args, **kwargs))
        return ctx
        
        
## not used, yet?
def build_bot(cog_func) -> Bot:
    class MockChannel:
        def history(self, limit):
            return self

        def next(self):
            return self

        async def send(self, *args, **kwargs):
            return "sent"

    bot = mock.AsyncMock(Bot)
    #bot.redmine = self.redmine
    
    user = mock.AsyncMock(discord.User)
    user.name = test_username
    user2 = mock.AsyncMock(discord.User)
    user2.name = test_username2
    bot.add_cog = AsyncMock(return_value=None, side_effect=lambda c: cog_func(c))
    bot.fetch_user = AsyncMock(bot.fetch_user, side_effect=lambda user_id: user if str(user_id) == test_user_id else user2)

    bot.get_channel = AsyncMock(discord.Bot.get_channel, return_value=MockChannel())
    return bot


def mock_string_layout(value: Any) -> str:
    return "    " + str(value).replace("\n", "\n    ")


def build_response(messagetype: str, *args, **kwargs):
    log.debug(f"build_response: {args}, {kwargs}, {messagetype}")
    if len(args) > 0:
        print(f"{messagetype}:{{\n    {mock_string_layout(args[0])}\n}}")
    elif len(kwargs) > 0:
        print(f"{messagetype}:\n    empty message with kwargs content\n")
    else:
        raise RuntimeError("mock_respond:\n    EMPTY MESSAGE SENT")
    interaction = mock.AsyncMock(Interaction)
    interaction.delete_original_message = mock.AsyncMock(Interaction.delete_original_message)
    return interaction


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
        self.redmine = Client()
        self.bot = NetBot(self.redmine)
        self.bot.load_extension("cog_tickets")
        self.cog = self.bot.cogs["TicketsCog"] # Note class name, note filename.

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
    