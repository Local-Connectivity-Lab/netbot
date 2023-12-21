#!/usr/bin/env python3

import unittest
import logging
import discord
import asyncio

from dotenv import load_dotenv

import netbot

import test_utils


log = logging.getLogger(__name__)


@unittest.skipUnless(load_dotenv(), "ENV settings not available")
class TestNetbot(test_utils.BotTestCase):
        
    def setUp(self):
        super().setUp()
        netbot.setup_logging() # for coverage?
        
        
    async def test_new_message_synced_thread(self):
        test_ticket = 218
        note = f"This is a new note about ticket #{test_ticket} for test {self.tag}"
        
        # create temp discord mapping with scn add
        ctx = self.build_context()
        
        message = unittest.mock.AsyncMock(discord.Message)
        message.content = note
        message.channel = unittest.mock.AsyncMock(discord.Thread)
        message.channel.name = f"Ticket #{test_ticket}: Search for subject match in email threading"
        message.author = unittest.mock.AsyncMock(discord.Member)
        message.author.name = self.discord_user
        
        await self.bot.on_message(message)
        
        # check result in redmine, last note on ticket 218.
        ticket = self.redmine.get_ticket(218, include_journals=True) # get the notes
        self.assertIsNotNone(ticket)
        self.assertIn(note, ticket.journals[-1].notes)
    

if __name__ == '__main__':
    unittest.main()