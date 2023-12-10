#!/usr/bin/env python3

import unittest
import logging
import os, glob
import datetime as dt

from dotenv import load_dotenv

from typing import Callable, Any
from unittest import mock
from unittest.mock import AsyncMock, MagicMock

import discord
from discord import ApplicationContext, Interaction
from discord.ext.bridge import BridgeExtContext, Bot


from cog_tickets import TicketsCog, setup

#logging.basicConfig(level=logging.DEBUG)
#logging.basicConfig(level=logging.DEBUG, 
#    format="{asctime} {levelname:<8s} {name:<16} {message}", style='{')
#logging.getLogger("urllib3.connectionpool").setLevel(logging.INFO)
log = logging.getLogger(__name__)

test_discord_username: str = "TEST_DISCORD_USERNAME"
test_discord_username2: str = "TEST_DISCORD_USERNAME2"
test_user_id: str = "0"


class TestTicketsCog(unittest.TestCase):
    
    def setUp(self):
        #self.client = redmine.Client()
        bot = self.build_bot(setup)
        self.cog = TicketsCog(bot)

    
    def test_new_ticket(self):
        test_title = "This is a test ticket."
        ctx = self.build_context()
        self.cog.create_new_ticket(ctx, test_title)

        # then get ticket and confirm it was created
        
        
    def build_bot(self, cog_func) -> Bot:
        class MockChannel:
            def history(self, limit):
                return self

            def next(self):
                return self

            async def send(self, *args, **kwargs):
                return "sent"

        bot = mock.MagicMock(Bot)
        user = mock.MagicMock(discord.User)
        user.name = test_discord_username
        user2 = mock.MagicMock(discord.User)
        user2.name = test_discord_username2
        bot.add_cog = MagicMock(return_value=None, side_effect=lambda c: cog_func(c))
        #bot.fetch_user = AsyncMock(bot.fetch_user, side_effect=lambda user_id: user if str(user_id) == test_user_id else user2)

        bot.get_channel = MagicMock(discord.Bot.get_channel, return_value=MockChannel())
        return bot

    def mock_string_layout(value: Any) -> str:
        return "    " + str(value).replace("\n", "\n    ")


    def build_response(self, messagetype: str, *args, **kwargs):
        if len(args) > 0:
            print(f"{messagetype}:{{\n    {self.mock_string_layout(args[0])}\n}}")
        elif len(kwargs) > 0:
            print(f"{messagetype}:\n    empty message with kwargs content\n")
        else:
            raise RuntimeError("mock_respond:\n    EMPTY MESSAGE SENT")
        interaction = mock.MagicMock(Interaction)
        interaction.delete_original_message = mock.AsyncMock(Interaction.delete_original_message)
        return interaction

    def build_context(self, author_id: int) -> ApplicationContext:
        class MockedAuthor:
            def __init__(self, user_id: int):
                self.id = user_id

        ctx = mock.MagicMock(ApplicationContext)
        ctx.author = MockedAuthor(author_id)
        ctx.respond = AsyncMock(
            discord.ApplicationContext.respond,
            side_effect=lambda *args, **kwargs: self.build_response("mock_respond", *args, **kwargs))
        ctx.send = AsyncMock(
            discord.ApplicationContext.send,
            side_effect=lambda *args, **kwargs: self.build_response(f"mock_send", *args, **kwargs))
        return ctx


if __name__ == '__main__':
    unittest.main()