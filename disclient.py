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

class Client(): ## discord.Client()
    def __init__(self):
        self.redmine = redmine.Client()
        pass

    def synchronize(self):
        # query redmine to get tickets with discord threads
        threaded_tickets = self.discord_tickets()
        for ticket in threaded_tickets:
            print(ticket)

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