#!/usr/bin/env python3
"""netbot"""

import os
import re
import logging
import asyncio
import discord
from dotenv import load_dotenv
from discord.ext import commands, tasks

from formatting import DiscordFormatter
from model import TicketNote, Ticket, NamedId
import synctime
import redmine


log = logging.getLogger(__name__)


_TRACKER_MAPPING = {
    "External-Comms-Intake": "admin-team",
    "Admin": "admin-team",
    "Comms": "outreach",
    "Infra-Config": "routing-and-infrastructure",
    "Infra-Field": "installs",
    "Software-Dev": "network-software",
    "Research": "uw-research-nsf",
}


class NetbotException(Exception):
    """netbot exception"""


class NetBot(commands.Bot):
    """netbot"""
    def __init__(self, client: redmine.Client):
        log.info(f'initializing {self}')
        intents = discord.Intents.default()
        intents.message_content = True

        self.lock = asyncio.Lock()
        self.ticket_locks = {}

        self.formatter = DiscordFormatter(client.url)
        self.trackers: dict[str,NamedId] = {}

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


    def initialize_tracker_mapping(self):
        # load the trackers, indexed by tracker name
        self.trackers = self.redmine.ticket_mgr.load_trackers()
        # update to include each mapping in
        for tracker_name, channel_name in _TRACKER_MAPPING.items():
            if tracker_name in self.trackers:
                self.trackers[channel_name] = self.trackers[tracker_name]
            else:
                log.debug(f"unmapped tracker: {tracker_name}")


    def run_bot(self):
        """start netbot"""
        log.info(f"starting {self}")

        self.initialize_tracker_mapping()

        super().run(os.getenv('DISCORD_TOKEN'))


    async def on_ready(self):
        #log.info(f"Logged in as {self.user} (ID: {self.user.id})")
        #log.debug(f"bot: {self}, guilds: {self.guilds}")

        # start the thread-syncer
        self.sync_all_threads.start() # pylint: disable=no-member

        # start the expriation checker
        ### FIXME self.check_expired_tickets.start() # pylint: disable=no-member
        log.debug(f"Initialized with {self.redmine}")


    async def on_message(self, message:discord.Message):
        if message.author.id != self.user.id:
            # not the bot user
            if isinstance(message.channel, discord.Thread):
                # IS a thread, check the name
                ticket_id = self.parse_thread_title(message.channel.name)
                if ticket_id:
                    user = self.redmine.user_mgr.find(message.author.name)
                    if user:
                        log.debug(f"known user commenting on ticket #{ticket_id}: redmine={user.login}, discord={message.author.name}")
                    else:
                        # ticket 480 - notify the user that they can add themselves to redmine
                        log.info(f"Unknown discord user, {message.author.name}, commenting on ticket #{ticket_id}")
                        await message.reply(f"User {message.author.name} not mapped to redmine. Use `/scn add` to create the mapping.")


    def parse_thread_title(self, title: str) -> int:
        """parse the thread title to get the ticket number"""
        match = re.match(r'^Ticket #(\d+)', title)
        if match:
            return int(match.group(1))


    async def gather_discord_notes(self, thread: discord.Thread, sync_rec:synctime.SyncRecord):
        log.debug(f"calling history with thread={thread}, after={sync_rec.last_sync}, ts={sync_rec.last_sync.timestamp()}")
        # TODO I'm sure there's a more python way to do this
        notes = []
        async for message in thread.history(after=sync_rec.last_sync, oldest_first=True):
            # ignore bot messages
            if message.author.id != self.user.id:
                notes.append(message)
        return notes


    def gather_redmine_notes(self, ticket, sync_rec:synctime.SyncRecord) -> list[TicketNote]:
        notes = []
        # get the new notes from the redmine ticket
        redmine_notes = self.redmine.get_notes_since(ticket.id, sync_rec.last_sync)
        for note in redmine_notes:
            if not note.notes.startswith('"Discord":'):
                # skip anything that start with the Discord tag
                notes.append(note)
        return notes


    def append_redmine_note(self, ticket, message: discord.Message) -> None:
        """Format a discord message for redmine"""
        # redmine link format: "Link Text":http://whatever

        # check user mapping exists
        user = self.redmine.user_mgr.find(message.author.name)
        if user:
            # format the note
            formatted = f'"Discord":{message.jump_url}: {message.content}'
            self.redmine.append_message(ticket.id, user.login, formatted)
        else:
            # no user mapping
            log.debug(f"SYNC unknown Discord user: {message.author.name}")
            formatted = f'"Discord":{message.jump_url} user *{message.author.name}* said: {message.content}'
            # force user_login to None to use default user based on token (the admin)
            self.redmine.append_message(ticket.id, user_login=None, note=formatted)


    async def synchronize_ticket(self, ticket, thread:discord.Thread) -> bool:
        """
        Synchronize a ticket to a thread
        returns True after a sucessful sync or if there are no changes, false if a sync is in progress.
        """
        # as this is an async method call, and we don't want to lock bot-level event processing,
        # we need to create a per-ticket lock to make sure the same

        # TODO Sync files and attachments discord -> redmine, use ticket query to get them

        dirty_flag: bool = False

        # get the self lock before checking the lock collection
        async with self.lock:
            if ticket.id in self.ticket_locks:
                log.info(f"ticket #{ticket.id} locked, skipping")
                return False # locked
            else:
                # create lock flag
                self.ticket_locks[ticket.id] = True
                log.debug(f"thread lock set, id: {ticket.id}, thread: {thread}")

        try:
            # start of the process, will become "last update"
            sync_start = synctime.now()
            sync_rec = ticket.get_sync_record(expected_channel=thread.id)

            if sync_rec:
                log.debug(f"sync record: {sync_rec}")

                # get the new notes from the redmine ticket
                redmine_notes = self.gather_redmine_notes(ticket, sync_rec)
                for note in redmine_notes:
                    # Write the note to the discord thread
                    dirty_flag = True
                    await thread.send(self.formatter.format_discord_note(note))
                log.debug(f"synced {len(redmine_notes)} notes from #{ticket.id} --> {thread}")

                # get the new notes from discord
                discord_notes = await self.gather_discord_notes(thread, sync_rec)
                for message in discord_notes:
                    dirty_flag = True
                    self.append_redmine_note(ticket, message)

                log.debug(f"synced {len(discord_notes)} notes from {thread} -> #{ticket.id}")

                # update the SYNC timestamp
                # only update if something has changed
                if dirty_flag:
                    sync_rec.last_sync = sync_start
                    self.redmine.update_sync_record(sync_rec)

                log.info(f"DONE sync {ticket.id} <-> {thread.name}, took {synctime.age_str(sync_start)}")
                return True # processed as expected
            else:
                log.info(f"empty sync_rec for channel={thread.id}, assuming mismatch and skipping")
                return False # not found
        finally:
            # unset the sync lock
            del self.ticket_locks[ticket.id]


    def get_channel_by_name(self, channel_name: str):
        for channel in self.get_all_channels():
            if isinstance(channel, discord.TextChannel) and channel_name == channel.name:
                return channel

        log.warning(f"Channel not found: {channel_name}")
        return None


    async def on_application_command_error(self, context: discord.ApplicationContext,
                                           exception: discord.DiscordException):
        """Bot-level error handler"""
        if isinstance(exception, commands.CommandOnCooldown):
            await context.respond("This command is currently on cooldown!")
        else:
            log.warning(f"{context.user}/{context.command} - {exception.__cause__}", exc_info=exception.__cause__)
            #raise error  # Here we raise other errors to ensure they aren't ignored
            await context.respond(f"Error processing due to: {exception.__cause__}")


    async def sync_thread(self, thread:discord.Thread):
        """syncronize an existing ticket thread with redmine"""
        # get the ticket id from the thread name
        ticket_id = self.parse_thread_title(thread.name)

        ticket = self.redmine.get_ticket(ticket_id, include_journals=True)
        if ticket:
            completed = await self.synchronize_ticket(ticket, thread)
            if completed:
                return ticket
            else:
                raise NetbotException(f"Ticket {ticket.id} is locked for syncronization.")
        else:
            log.debug(f"no ticket found for {thread.name}")

        return None


    @tasks.loop(minutes=1.0) # FIXME to 5.0 minutes. set to 1 min for testing
    async def sync_all_threads(self):
        """
        Configured to run every minute using the tasks.loop annotation.
        Get all Threads and sync each one.
        """
        log.info(f"sync_all_threads: starting for {self.guilds}")

        # get all threads
        for guild in self.guilds:
            for thread in guild.threads:
                try:
                    # try syncing each thread. if there's no ticket found, there's no thread to sync.
                    ticket = await self.sync_thread(thread)
                    if ticket:
                        # successful sync
                        log.debug(f"SYNC complete for ticket #{ticket.id} to {thread.name}")
                    #else:
                        #log.debug(f"no ticket found for {thread.name}")
                except NetbotException as ex:
                    # ticket is locked.
                    # skip gracefully
                    log.debug(f"Ticket locked, sync in progress: {thread}: {ex}")
                except Exception:
                    log.exception(f"Error syncing {thread}")


    async def expiration_notification(self, ticket: Ticket) -> None:
        """Notify the correct people and channels when a ticket expires.
        ticket-597
        When a ticket is about to expire, put a message in the related thread that it is about to expire.
        "In {hours}, this ticket will expire."
        """

        # first, check the syncdata.
        sync = ticket.get_sync_record()
        if sync and sync.channel_id > 0:
            notification = self.bot.formatter.format_expiration_notification(ticket)
            thread: discord.Thread = self.bot.get_channel(sync.channel_id)
            if thread:
                await thread.send(notification)
                # yield?
                return

        if str(ticket.tracker) in _TRACKER_MAPPING:
            # lookup channel
            channel_name = _TRACKER_MAPPING[str(ticket.tracker)]
            channel = self.get_channel_by_name(channel_name)
            if channel:
                channel.send(self.formatter.format_expiration_notification(ticket))
                return
            else:
                log.warning(f"Expiring ticket #{ticket.id} on unknown channel: {channel_name}")

        # shouldn't get here
        log.warning(f"Unable to find channel for ticket {ticket}, tracker={ticket.tracker}, defaulting to admin")
        channel = self.get_channel_by_name("admin-team")
        if channel:
            await channel.send(self.formatter.format_expiration_notification(ticket))


    async def notify_expiring_tickets(self):
        """Notify that tickets are about to expire.
        ticket-597
        """
        # get list of tickets that will expire (based on rules in ticket_mgr)
        for ticket in self.redmine.ticket_mgr.expiring_tickets():
            await self.expiration_notification(ticket)


    def expire_expired_tickets(self):
        for ticket in self.redmine.ticket_mgr.expired_tickets():
            # notification to discord, or just note provided by expire?
            # - for now, add note to ticket with expire info, and allow sync.
            self.redmine.ticket_mgr.expire(ticket)


    @commands.slash_command(name="notify", description="Force ticket notifications")
    async def force_notify(self, ctx: discord.ApplicationContext):
        log.debug(ctx)
        await self.check_expired_tickets()


    @tasks.loop(hours=24)
    async def check_expired_tickets(self):
        """Process expired tickets.
        Expected to run every 24hours to:
        - alert about tickets that are expiring
        - expire tickets that have expired
        Based on ticket-597
        """
        await self.notify_expiring_tickets()
        self.expire_expired_tickets()


    def lookup_tracker(self, tracker:str) -> NamedId:
        return self.trackers.get(tracker, None)


def main():
    """netbot main function"""
    log.info(f"loading .env for {__name__}")
    load_dotenv()

    client = redmine.Client.fromenv()
    bot = NetBot(client)

    # register cogs
    bot.load_extension("cog_scn")
    bot.load_extension("cog_tickets")

    # run the bot
    bot.run_bot()


def setup_logging():
    """set up logging for netbot"""
    logging.basicConfig(level=logging.DEBUG,
                        format="{asctime} {levelname:<8s} {name:<16} {message}", style='{')
    logging.getLogger("discord.gateway").setLevel(logging.WARNING)
    logging.getLogger("discord.http").setLevel(logging.WARNING)
    logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)
    logging.getLogger("discord.client").setLevel(logging.WARNING)
    logging.getLogger("discord.webhook.async_").setLevel(logging.WARNING)


if __name__ == '__main__':
    setup_logging()
    main()
