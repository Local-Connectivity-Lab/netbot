#!/usr/bin/env python3
"""netbot"""

import os
import re
import logging
import asyncio
import discord
from dotenv import load_dotenv
from discord.ext import commands

import synctime
import redmine


def setup_logging():
    """set up logging for netbot"""
    logging.basicConfig(level=logging.DEBUG,
                        format="{asctime} {levelname:<8s} {name:<16} {message}", style='{')
    logging.getLogger("discord.gateway").setLevel(logging.WARNING)
    logging.getLogger("discord.http").setLevel(logging.WARNING)
    logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)
    logging.getLogger("discord.client").setLevel(logging.WARNING)
    logging.getLogger("discord.webhook.async_").setLevel(logging.WARNING)


log = logging.getLogger(__name__)


log.info('initializing netbot')

class NetBot(commands.Bot):
    """netbot"""
    def __init__(self, client: redmine.Client):
        log.info(f'initializing {self}')
        intents = discord.Intents.default()
        intents.message_content = True

        self.lock = asyncio.Lock()
        self.ticket_locks = {}

        self.redmine = client
        #guilds = os.getenv('DISCORD_GUILDS').split(', ')
        #if guilds:
        #    log.info(f"setting guilds: {guilds}")
        #else:
        #    log.error("No guild restriction set.")
        #    # exit?

        super().__init__(
            command_prefix=commands.when_mentioned_or("!"),
            intents=intents,
        #    debug_guilds = guilds
        )

    def run_bot(self):
        """start netbot"""
        log.info(f"starting {self}")
        super().run(os.getenv('DISCORD_TOKEN'))

    #async def on_ready(self):
    #    log.info(f"Logged in as {self.user} (ID: {self.user.id})")
    #    log.debug(f"bot: {self}, guilds: {self.guilds}")


    def parse_thread_title(self, title: str) -> int:
        """parse the thread title to get the ticket number"""
        match = re.match(r'^Ticket #(\d+)', title)
        if match:
            return int(match.group(1))


    async def synchronize_ticket(self, ticket, thread:discord.Thread):
        """
        Synchronize a ticket to a thread
        """
        # as this is an async method call, and we don't want to lock bot-level event processing,
        # we need to create a per-ticket lock to make sure the same
        # TODO per-ticket lock? trying bot-level lock first

        # get the self lock before checking the lock collection
        async with self.lock:
            if ticket.id in self.ticket_locks:
                log.debug(f"ticket #{ticket.id} locked, skipping")
                return
            else:
                # create lock flag
                self.ticket_locks[ticket.id] = True
                log.debug(f"thread lock set, id: {ticket.id}, thread: {thread}")

        # start of the process, will become "last update"
        sync_start = synctime.now()
        sync_rec = self.redmine.get_sync_record(ticket, expected_channel=thread.id)
        log.debug(f"sync record: {sync_rec}")

        # get the new notes from the ticket
        notes = self.redmine.get_notes_since(ticket.id, sync_rec.last_sync)
        # TODO between last_sync and sync_start
        log.debug(f"syncing {len(notes)} notes from {ticket.id} --> {thread.name}")

        for note in notes:
            # Write the note to the discord thread
            msg = f"> **{note.user.name}** at *{note.created_on}*\n> {note.notes}\n\n"
            await thread.send(msg)
            # TODO: How do I make sure all these complete before moving on?

        # query discord for updates to thread since last-update
        # see https://docs.pycord.dev/en/stable/api/models.html#discord.Thread.history
        log.debug(f"calling history with thread={thread}, after={sync_rec}")
        async for message in thread.history(after=sync_rec.last_sync, oldest_first=True):
            # TODO between last_sync and sync_start, and flatten
            # ignore bot messages!
            if message.author.id != self.user.id:
                # for each, create a note with translated discord user id
                # with the update (or one big one?)
                user = self.redmine.find_discord_user(message.author.name)
                if user:
                    log.debug(f"SYNC: ticket={ticket.id}, user={user.login}, msg={message.content}")
                    self.redmine.append_message(ticket.id, user.login, message.content)
                else:
                    # FIXME
                    log.info(f"SYNC unknown Discord user: {message.author.name}, skipping")
        else:
            log.debug(f"No new discord messages found since {sync_rec}")

        # update the SYNC timestamp
        sync_rec.last_sync = sync_start
        self.redmine.update_sync_record(sync_rec)

        # unset the sync lock
        del self.ticket_locks[ticket.id]

        log.info(f"DONE sync {ticket.id} <-> {thread.name}, took {synctime.age_str(sync_start)}")


    async def on_application_command_error(self, context: discord.ApplicationContext,
                                           exception: discord.DiscordException):
        """Bot-level error handler"""
        if isinstance(exception, commands.CommandOnCooldown):
            await context.respond("This command is currently on cooldown!")
        else:
            log.error(f"{context} - {exception}", exc_info=True)
            #raise error  # Here we raise other errors to ensure they aren't ignored
            await context.respond(f"Error processing your request: {exception}")


def main():
    """netbot main function"""
    setup_logging()

    log.info(f"initializing {__name__}")
    load_dotenv()

    client = redmine.Client()
    bot = NetBot(client)

    # register cogs
    bot.load_extension("cog_scn")
    bot.load_extension("cog_tickets")

    # run the bot
    bot.run_bot()


if __name__ == '__main__':
    main()
