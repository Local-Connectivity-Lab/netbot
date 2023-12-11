#!/usr/bin/env python3

import unittest
import time
import asyncio
import logging
import os, glob
import datetime as dt

from dotenv import load_dotenv

from typing import Callable, Any
from unittest import mock
from unittest.mock import AsyncMock

import discord
from discord import ApplicationContext, Interaction
from discord.ext.bridge import BridgeExtContext, Bot

from redmine import Client
from netbot import NetBot
from cog_tickets import TicketsCog, setup

#logging.basicConfig(level=logging.DEBUG)
logging.basicConfig(level=logging.DEBUG, 
                    format="{asctime} {levelname:<8s} {name:<16} {message}", style='{')
logging.getLogger("urllib3.connectionpool").setLevel(logging.INFO)
log = logging.getLogger(__name__)

test_username: str = "acmerocket"
test_username2: str = "infrared0"
test_user_id: int = 5




class TestTicketsCog(unittest.IsolatedAsyncioTestCase):
    
    def setUp(self):
        load_dotenv()
        self.redmine = Client()
        self.bot = NetBot(self.redmine)
        #self.bot = self.build_bot("setup")
        self.bot.load_extension("cog_tickets")
        self.cog = self.bot.cogs["TicketsCog"] # Note class name, note filename.

    #test utils

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

    async def test_new_ticket(self):
        # Test steps:
        # 1. create new test user name: test-12345@example.com, login test-12345
        tag = self.tagstr()
        username = "test-" + tag
        email = username + "@example.com"
        discord_user = "discord-" + tag 
        
        # 2. create new redmine user, using redmine api, assert
        user = self.redmine.create_user(email, username, "Testy")
        self.assertIsNotNone(user)
        
        # 3. create temp discord mapping with redmine api, assert 
        self.redmine.create_discord_mapping(user.login, discord_user)
        
        # reindex users and lookup based on login
        self.redmine.reindex_users()
        self.assertIsNotNone(self.redmine.find_user(user.login))
        self.assertIsNotNone(self.redmine.find_user(discord_user))
        
        # 4. create ticket with discord user, assert
        #test_title = "This is a test ticket."
        #ctx = self.build_context(tag, discord_user)
        #await self.cog.create_new_ticket(ctx, test_title)
        #await asyncio.sleep(1) # needed? smaller?
        
        # 5. delete ticket with redmine api, assert
        
        # 6. delete user with redmine api, assert
        self.redmine.remove_user(user.id)
        self.redmine.reindex_users()
        self.assertIsNone(self.redmine.find_user(user.login))
        self.assertIsNone(self.redmine.find_user(discord_user))

    
    def build_context(self, author_id: int, username: str) -> ApplicationContext:
        class MockedAuthor:
            def __init__(self, user_id: int, username: str):
                self.id = user_id
                self.name = username

        ctx = mock.AsyncMock(ApplicationContext)
        ctx.user = MockedAuthor(author_id, username)
        
        ctx.respond = AsyncMock(
            discord.ApplicationContext.respond,
            side_effect=lambda *args, **kwargs: self.build_response("mock_respond", *args, **kwargs))
        ctx.send = AsyncMock(
            discord.ApplicationContext.send,
            side_effect=lambda *args, **kwargs: self.build_response(f"mock_send", *args, **kwargs))
        return ctx
        
        
    def build_bot(self, cog_func) -> Bot:
        class MockChannel:
            def history(self, limit):
                return self

            def next(self):
                return self

            async def send(self, *args, **kwargs):
                return "sent"

        bot = mock.AsyncMock(Bot)
        bot.redmine = self.redmine
        
        user = mock.AsyncMock(discord.User)
        user.name = test_username
        user2 = mock.AsyncMock(discord.User)
        user2.name = test_username2
        bot.add_cog = AsyncMock(return_value=None, side_effect=lambda c: cog_func(c))
        bot.fetch_user = AsyncMock(bot.fetch_user, side_effect=lambda user_id: user if str(user_id) == test_user_id else user2)

        bot.get_channel = AsyncMock(discord.Bot.get_channel, return_value=MockChannel())
        return bot


    def mock_string_layout(self, value: Any) -> str:
        return "    " + str(value).replace("\n", "\n    ")
    

    def build_response(self, messagetype: str, *args, **kwargs):
        if len(args) > 0:
            print(f"{messagetype}:{{\n    {self.mock_string_layout(args[0])}\n}}")
        elif len(kwargs) > 0:
            print(f"{messagetype}:\n    empty message with kwargs content\n")
        else:
            raise RuntimeError("mock_respond:\n    EMPTY MESSAGE SENT")
        interaction = mock.AsyncMock(Interaction)
        interaction.delete_original_message = mock.AsyncMock(Interaction.delete_original_message)
        return interaction




if __name__ == '__main__':
    unittest.main()