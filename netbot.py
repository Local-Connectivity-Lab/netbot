#!/usr/bin/env python3

import os
import re
import logging
import datetime as dt

import discord
import redmine


from dotenv import load_dotenv

from discord.ext import commands


def setup_logging():
    logging.basicConfig(level=logging.DEBUG,
                        format="{asctime} {levelname:<8s} {name:<16} {message}", style='{')

    logging.getLogger("discord.gateway").setLevel(logging.WARNING)
    logging.getLogger("discord.http").setLevel(logging.INFO)
    logging.getLogger("urllib3.connectionpool").setLevel(logging.INFO)
    logging.getLogger("discord.client").setLevel(logging.INFO)
    logging.getLogger("discord.webhook.async_").setLevel(logging.INFO)


log = logging.getLogger(__name__)

log.info('initializing bot')

class NetBot(commands.Bot):
    def __init__(self, redmine: redmine.Client):
        log.info(f'initializing {self}')
        intents = discord.Intents.default()
        intents.message_content = True

        self.redmine = redmine
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

    def run(self):
        log.info(f"starting {self}")
        super().run(os.getenv('DISCORD_TOKEN'))

    async def on_ready(self):
        log.info(f"Logged in as {self.user} (ID: {self.user.id})")
        
    async def on_guild_join(self, guild):
        log.info(f"Joined guild: {guild}, id={guild.id}")

    async def on_thread_join(self, thread):
        await thread.join()
        log.info(f"Joined thread: {thread}")
        

    def parse_thread_title(self, title: str) -> int:
        match = re.match(r'^Ticket #(\d+):', title)
        if match:
            return int(match.group(1))


    async def on_message(self, message: discord.Message):
        # Make sure we won't be replying to ourselves.
        # if message.author.id == bot.user.id:
        #    return
        if isinstance(message.channel, discord.Thread):
            # get the ticket id from the thread name
            ticket_id = self.parse_thread_title(message.channel.name)
            
            if ticket_id:
                await self.sync_new_message(ticket_id, message)
            # else just a normal thread, do nothing


    async def sync_new_message(self, ticket_id: int, message: discord.Message):
        # ticket = redmine.get_ticket(ticket_id, include_journals=True)
        # create a note with translated discord user id with the update (or one big one?)
        # double-check that self.id <> author.id?
        user = self.redmine.find_discord_user(message.author.name)
        if user:
            self.redmine.append_message(ticket_id, user.login, message.content)
            log.debug(
                f"SYNCED: ticket={ticket_id}, user={user.login}, msg={message.content}")
        else:
            log.warning(
                f"sync_new_message - unknown discord user: {message.author.name}, skipping message")


    async def synchronize_ticket(self, ticket, thread, ctx: discord.ApplicationContext):
        last_sync = self.redmine.get_field(ticket, "sync")
        log.debug(f"ticket {ticket.id} last sync: {last_sync}, age: {self.redmine.get_field(ticket, 'age')}")

        # start of the process, will become "last update"
        timestamp = dt.datetime.now(dt.timezone.utc)  # UTC

        notes = self.redmine.get_notes_since(ticket.id, last_sync)
        log.info(f"syncing {len(notes)} notes from {ticket.id} --> {thread.name}")

        for note in notes:
            msg = f"> **{note.user.name}** at *{note.created_on}*\n\n{note.notes}\n"
            await thread.send(msg)

        # query discord for updates to thread since last-update
        # see https://docs.pycord.dev/en/stable/api/models.html#discord.Thread.history
        log.debug("calling history with thread={thread}, after={last_sync}")
        #messages = await thread.history(after=last_sync, oldest_first=True).flatten()
        async for message in thread.history(after=last_sync, oldest_first=True):
            # ignore bot messages!
            if message.author.id != self.user.id:
                # for each, create a note with translated discord user id with the update (or one big one?)
                user = self.redmine.find_discord_user(message.author.name)

                if user:
                    log.debug(f"SYNC: ticket={ticket.id}, user={user.login}, msg={message.content}")
                    self.redmine.append_message(ticket.id, user.login, message.content)
                else:
                    log.warning(
                        f"synchronize_ticket - unknown discord user: {message.author.name}, skipping message")
        else:
            log.debug(f"No new discord messages found since {last_sync}")

        # update the SYNC timestamp
        self.redmine.update_syncdata(ticket.id, timestamp)
        log.info(f"completed sync for {ticket.id} <--> {thread.name}")
        
    async def on_application_command_error(self, ctx: discord.ApplicationContext, error: discord.DiscordException):
        """Bot-level error handler"""
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.respond("This command is currently on cooldown!")
        else:
            log.error(f"{error.__cause__}", exc_info=True)
            #raise error  # Here we raise other errors to ensure they aren't ignored
            await ctx.respond(f"{error.__cause__}")


def main():
    setup_logging()
    
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
