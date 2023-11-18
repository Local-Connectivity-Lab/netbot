#!/usr/bin/env python3

import os
import re
import logging
import datetime as dt

import discord
import redmine
#import netbox

from discord.commands import option
from dotenv import load_dotenv

from discord.ext import commands

logging.basicConfig(level=logging.DEBUG, 
    format="{asctime} {levelname:<8s} {name:<16} {message}", style='{')

logging.getLogger("discord.gateway").setLevel(logging.WARNING)
logging.getLogger("discord.http").setLevel(logging.WARNING)

log = logging.getLogger(__name__)

log.info('initializing bot')

class NetBot(commands.Bot):
    def __init__(self, redmine: redmine.Client):
        log.info(f'initializing {self}')
        intents = discord.Intents.default()
        intents.message_content = True

        self.redmine = redmine

        super().__init__(
            command_prefix=commands.when_mentioned_or("!"), intents=intents
        )

    def run(self):
        log.info(f"starting {self}")
        super().run(os.getenv('DISCORD_TOKEN'))

    async def on_ready(self):
        log.info(f"Logged in as {self.user} (ID: {self.user.id})")

    async def on_thread_join(self, thread):
        await thread.join()
        log.info(f"Joined thread: {thread}")

    async def on_message(self, message: discord.Message):
        # Make sure we won't be replying to ourselves.
        #if message.author.id == bot.user.id:
        #    return
        if isinstance(message.channel, discord.Thread):
            # get the ticket id from the thread name
            ticket_id = self.parse_thread_title(message.channel.name)
            if ticket_id:
                await self.sync_new_message(ticket_id, message)
            # else just a normal thread, do nothing
            
    async def sync_new_message(self, ticket_id:int, message: discord.Message):
        #ticket = redmine.get_ticket(ticket_id, include_journals=True)
        # create a note with translated discord user id with the update (or one big one?)
        # double-check that self.id <> author.id?
        user = self.redmine.find_discord_user(message.author.name)
        if user:
            self.redmine.append_message(ticket_id, user.login, message.content)
            log.debug(f"SYNCED: ticket={ticket_id}, user={user.login}, msg={message.content}")
        else:
            log.error("Unknown discord user: {message.author.name}, skipping message")

    async def synchronize_ticket(self, ticket, thread, ctx: discord.ApplicationContext):
        last_sync = self.redmine.get_field(ticket, "sync")
        
        # start of the process, will become "last update"
        timestamp = dt.datetime.utcnow().astimezone(dt.timezone.utc)

        notes = self.redmine.get_notes_since(ticket.id, last_sync)
        log.info(f"syncing {len(notes)} notes from {ticket.id} --> {thread}")

        for note in notes:
            msg = f"> **{note.user.name}** at *{note.created_on}*\n\n{note.notes}\n"
            await thread.send(msg)

        # query discord for updates to thread since last-update
        # see https://docs.pycord.dev/en/stable/api/models.html#discord.Thread.history
        async for message in thread.history(after=last_sync):
            # ignore bot messages!
            if message.author.id != self.user.id:
                # for each, create a note with translated discord user id with the update (or one big one?)
                user = self.redmine.find_discord_user(message.author.name)
                if user:
                    log.debug(f"SYNC: ticket={ticket.id}, user={user.login}, msg={message.content}")
                    self.redmine.append_message(ticket.id, user.login, message.content)
                else:
                    log.error("Unknown discord user: {message.author.name}, skipping message")
        else:
            log.debug(f"No new discord messages found since {last_sync}")

        # update the SYNC timestamp
        self.redmine.update_syncdata(ticket.id, timestamp)
        log.info(f"completed sync for {ticket.id} <--> {thread}")

    def parse_thread_title(self, title:str) -> int:
        match = re.match(r'^Ticket #(\d+):', title)
        if match:
            return int(match.group(1))


def main():
    log.info(f"initializing {__name__}")
    load_dotenv()

    client = redmine.Client()
    bot = NetBot(client)

    # register cogs
    bot.load_extension("cog_scn")
    bot.load_extension("cog_tickets")

    # run the bot
    bot.run()


if __name__ == '__main__':
    main()
