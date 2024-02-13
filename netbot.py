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


log = logging.getLogger(__name__)


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


    async def gather_discord_notes(self, thread: discord.Thread, sync_rec:synctime.SyncRecord):
        log.debug(f"calling history with thread={thread}, after={sync_rec}")
        # TODO I'm sure there's a more python way to do this
        notes = []
        async for message in thread.history(after=sync_rec.last_sync, oldest_first=True):
            # ignore bot messages
            if message.author.id != self.user.id:
                notes.append(message)
        return notes


    def format_discord_note(self, note):
        """Format a note for Discord"""
        age = synctime.age(synctime.parse_str(note.created_on))
        return f"> **{note.user.name}** *{age} ago*\n> {note.notes}\n\n"
        #TODO Move format table


    def gather_redmine_notes(self, ticket, sync_rec:synctime.SyncRecord):
        notes = []
        # get the new notes from the redmine ticket
        redmine_notes = self.redmine.get_notes_since(ticket.id, sync_rec.last_sync)
        for note in redmine_notes:
            if not note.notes.startswith('"Discord":'):
                # skip anything that start with the Discord tag
                notes.append(note)
        return notes


    def format_redmine_note(self, message: discord.Message):
        """Format a discord message for redmine"""
        # redmine link format: "Link Text":http://whatever
        return f'"Discord":{message.jump_url}: {message.content}' # NOTE: message.clean_content


    async def synchronize_ticket(self, ticket, thread:discord.Thread):
        """
        Synchronize a ticket to a thread
        """
        # as this is an async method call, and we don't want to lock bot-level event processing,
        # we need to create a per-ticket lock to make sure the same

        # TODO Sync files and attachments discord -> redmine, use ticket query to get them

        dirty_flag: bool = False

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
        if sync_rec:
            log.debug(f"sync record: {sync_rec}")

            # get the new notes from the redmine ticket
            redmine_notes = self.gather_redmine_notes(ticket, sync_rec)
            for note in redmine_notes:
                # Write the note to the discord thread
                dirty_flag = True
                await thread.send(self.format_discord_note(note))
            log.debug(f"synced {len(redmine_notes)} notes from #{ticket.id} --> {thread}")

            # get the new notes from discord
            discord_notes = await self.gather_discord_notes(thread, sync_rec)
            for message in discord_notes:
                # make sure a user mapping exists
                user = self.redmine.find_discord_user(message.author.name)
                if user:
                    # format and write the note
                    dirty_flag = True
                    log.debug(f"SYNC: ticket={ticket.id}, user={user.login}, msg={message.content}")
                    formatted = self.format_redmine_note(message)
                    self.redmine.append_message(ticket.id, user.login, formatted)
                else:
                    # FIXME
                    log.info(f"SYNC unknown Discord user: {message.author.name}, skipping")
            log.debug(f"synced {len(discord_notes)} notes from {thread} -> #{ticket.id}")

            # update the SYNC timestamp
            # only update if something has changed
            if dirty_flag:
                sync_rec.last_sync = sync_start
                self.redmine.update_sync_record(sync_rec)

            # unset the sync lock
            del self.ticket_locks[ticket.id]

            log.info(f"DONE sync {ticket.id} <-> {thread.name}, took {synctime.age_str(sync_start)}")
        else:
            log.debug(f"empty sync_rec for channel={thread.id}, assuming mismatch and skipping")


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
    log.info(f"loading .env for {__name__}")
    load_dotenv()

    client = redmine.Client()
    bot = NetBot(client)

    # register cogs
    bot.load_extension("cog_scn")
    bot.load_extension("cog_tickets")

    # run the bot
    bot.run_bot()


def setup_logging():
    """set up logging for netbot"""
    logging.basicConfig(level=logging.DEBUG, format="{asctime} {levelname:<8s} {name:<16} {message}", style='{')
    logging.getLogger("discord.gateway").setLevel(logging.WARNING)
    logging.getLogger("discord.http").setLevel(logging.WARNING)
    logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)
    logging.getLogger("discord.client").setLevel(logging.WARNING)
    logging.getLogger("discord.webhook.async_").setLevel(logging.WARNING)


if __name__ == '__main__':
    setup_logging()
    main()
