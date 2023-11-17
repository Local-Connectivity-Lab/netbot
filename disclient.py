#!/usr/bin/env python3

import os
import logging
import discord

from discord.commands import option
from dotenv import load_dotenv
from discord.ext import commands

import redmine

#logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)

class Client(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.redmine = redmine.Client()
        self.channel_id = 1146220739314331698
        log.info("created client")

    async def on_ready(self):
        print(f"Logged in as {self.user} (ID: {self.user.id})")
        chan = self.get_channel(self.channel_id)
        print(f"channel: {chan}, {chan.type}")

    async def synchronize(self):
        log.info("starting sync")
        await self.run(os.getenv('DISCORD_TOKEN'))
        log.info("started")

        # query redmine to get tickets with discord threads
        threaded_tickets = self.discord_tickets()
        log.info(f"threading {threaded_tickets} tickets")

        for ticket in threaded_tickets:
            #print(ticket)
            channel = self.get_channel(self.channel_id)
            name = f"{ticket.project.name}-{ticket.id}"
            message = f"Creating new thread for ticket #{ticket.id}: [{ticket.id}]({ticket.url})"
            await channel.create_thread(name, message, auto_archive_duration=60, type=discord.ChannelType.text, reason=None)

        log.info("done discord sync")


    # tickets that have been marked for sync
    def discord_tickets(self):
        # todo: check updated field and track what's changed
        threaded_issue_query = "/issues.json?status_id=open&cf_1=1&sort=updated_on:desc"
        response = self.redmine.query(threaded_issue_query)

        if response.total_count > 0:
            return response.issues
        else:
            log.info(f"No open tickets found for: {response.request.url}")
            return None