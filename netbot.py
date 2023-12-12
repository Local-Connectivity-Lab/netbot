#!/usr/bin/env python3

import os
import re
import logging
import datetime as dt
import io

import discord
import redmine
import humanize

# using https://pypi.org/project/rich/ for terminal formatting
from rich.console import Console
from rich.table import Table
from rich import box

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
                f"Unknown discord user: {message.author.name}, skipping message")

    async def synchronize_ticket(self, ticket, thread, ctx: discord.ApplicationContext):
        last_sync = self.redmine.get_field(ticket, "sync")
        #log.debug(f"ticket {ticket.id} last sync: {last_sync} {age(last_sync)} ")

        # start of the process, will become "last update"
        timestamp = dt.datetime.now(dt.timezone.utc)  # UTC

        notes = self.redmine.get_notes_since(ticket.id, last_sync)
        log.info(f"syncing {len(notes)} notes from {ticket.id} --> {thread.name}")

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
                    log.debug(
                        f"SYNC: ticket={ticket.id}, user={user.login}, msg={message.content}")
                    self.redmine.append_message(
                        ticket.id, user.login, message.content)
                else:
                    log.warning(
                        f"Unknown discord user: {message.author.name}, skipping message")
        else:
            log.debug(f"No new discord messages found since {last_sync}")

        # update the SYNC timestamp
        self.redmine.update_syncdata(ticket.id, timestamp)
        log.info(f"completed sync for {ticket.id} <--> {thread.name}")


    ### FORMATTING ###
    
    # the table version
    def print_ticket_table(self, tickets, fields=["link","status","priority","age","assigned","subject"]):
        if not tickets:
            print("no tickets found")
            return
        elif len(tickets) == 1:
            self.print_ticket(tickets[0])
            return

        console = Console(file=io.StringIO(), width=80, color_system=None)

        table = Table(show_header=True, width=80, box=box.SIMPLE_HEAD, collapse_padding=True, header_style="bold magenta")
        for field in fields:
            #table.add_column("Date", style="dim", width=12)
            table.add_column(field)

        for ticket in tickets:
            row = []
            for field in fields:
                row.append(self.get_formatted_field(ticket, field))
            table.add_row(*row)

        for line in console.file.getvalue():
            print(f"---- {line}")
        
    
    

    async def print_tickets(self, tickets, ctx):
        msg = self.format_tickets(tickets)
        
        if len(msg) > 2000:
            log.warning("message over 2000 chars. truncing.")
            msg = msg[:2000]
        await ctx.respond(msg)

    def format_tickets(self, tickets, fields=["link","priority","updated","assigned","subject"]):
        if tickets is None:
            return "No tickets found."
        
        section = ""
        for ticket in tickets:
            section += self.format_ticket(ticket, fields) + "\n" # append each ticket
        return section.strip()

    def format_ticket(self, ticket, fields):
        section = ""
        for field in fields:
            section += self.redmine.get_field(ticket, field) + " " # spacer, one space
        return section.strip() # remove trailing whitespace

    def format_section(self, tickets, status):
        section = ""
        section += f"> {status}\n"
        for ticket in tickets:
            if ticket.status.name == status:
                url = self.redmine.get_field(ticket, "url")
                assigned = self.redmine.get_field(ticket, "assigned")
                section += f"[**`{ticket.id:>4}`**]({url})`  {ticket.priority.name:<6}  {ticket.updated_on[:10]}\
                        {assigned[:20]:<20}  {ticket.subject}`\n"
        return section


    def parse_thread_title(self, title: str) -> int:
        match = re.match(r'^Ticket #(\d+):', title)
        if match:
            return int(match.group(1))
        
    
    async def on_application_command_error(self, ctx: discord.ApplicationContext, error: discord.DiscordException):
        """Bot-level error handler"""
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.respond("This command is currently on cooldown!")
        else:
            log.error(f"{error}")
            #raise error  # Here we raise other errors to ensure they aren't ignored
            await ctx.respond(f"{error}")



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


def age(time: dt.datetime):
    age = dt.datetime.utcnow().astimezone(dt.timezone.utc) - time
    return humanize.naturaldelta(age)


if __name__ == '__main__':
    main()
