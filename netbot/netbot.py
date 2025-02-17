#!/usr/bin/env python3
"""netbot"""

import os
import sys
import re
import logging
import asyncio
import discord
from dotenv import load_dotenv
from discord.ext import commands, tasks

from redmine.model import TicketNote, Ticket, NamedId, Team
from redmine import synctime
from redmine.redmine import Client

from .formatting import DiscordFormatter


log = logging.getLogger(__name__)


CHANNEL_MAPPING = {
    "intake": "External-Comms-Intake",
    "admin-team": "Admin",
    "outreach": "Comms",
    "routing-and-infrastructure": "Infra-Config",
    "installs": "Infra-Field",
    "network-software": "Software-Dev",
    "uw-research-nsf": "Research",
}

TEAM_MAPPING = {
    "intake": "intake-team",
    "admin-team": "admin-team",
    "outreach": "comms-team",
    "routing-and-infrastructure": "infra-config-team",
    "installs": "infra-field-team",
    "network-software": "software-dev-team",
    "uw-research-nsf": "uw-research-nsf-team",
}

FALLBACK_TEAM = "admin-team"


# utility method to get a list of (one) ticket from the title of the channel, or empty list
def default_ticket(ctx: discord.AutocompleteContext) -> list[int]:
    # examine the thread
    ticket_id = NetBot.parse_thread_title(ctx.interaction.channel.name)
    if ticket_id:
        return [ticket_id]
    else:
        return []


class NetbotException(Exception):
    """netbot exception"""


class NetBot(commands.Bot):
    """netbot"""
    def __init__(self, client: Client):
        log.info(f'initializing {self}')
        intents = discord.Intents.default()
        intents.message_content = True

        self.run_sync = True # ticket sync on by default
        self.lock = asyncio.Lock()
        self.ticket_locks = {}

        self.formatter = DiscordFormatter(client.url)

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
                ticket_id = NetBot.parse_thread_title(message.channel.name)
                if ticket_id:
                    user = self.redmine.user_mgr.find(message.author.name)
                    if user:
                        log.debug(f"known user commenting on ticket #{ticket_id}: redmine={user.login}, discord={message.author.name}")
                    else:
                        # ticket 480 - notify the user that they can add themselves to redmine
                        log.info(f"Unknown discord user, {message.author.name}, commenting on ticket #{ticket_id}")
                        await message.reply(f"User {message.author.name} not mapped to redmine. Use `/scn add` to create the mapping.")


    @staticmethod
    def parse_thread_title(title: str) -> int:
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
        redmine_notes = self.redmine.ticket_mgr.get_notes_since(ticket.id, sync_rec.last_sync)
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
            self.redmine.ticket_mgr.append_message(ticket.id, user.login, formatted)
        else:
            # no user mapping
            log.debug(f"SYNC unknown Discord user: {message.author.name}")
            formatted = f'"Discord":{message.jump_url} user *{message.author.name}* said: {message.content}'
            # force user_login to None to use default user based on token (the admin)
            self.redmine.ticket_mgr.append_message(ticket.id, user_login=None, note=formatted)


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
                log.debug(f"LOCK thread - id: {ticket.id}, thread: {thread}")

        try:
            # start of the process, will become "last update"
            sync_start = synctime.now()
            sync_rec = ticket.validate_sync_record(expected_channel=thread.id)

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
                    self.redmine.ticket_mgr.update_sync_record(sync_rec)

                log.info(f"DONE sync {ticket.id} <-> {thread.name}, took {synctime.age_str(sync_start)}")
                return True # processed as expected
            else:
                log.info(f"empty sync_rec for channel={thread.id}, assuming mismatch and skipping")
                return False # not found
        finally:
            # unset the sync lock
            del self.ticket_locks[ticket.id]
            log.debug(f"UNLOCK thread - id: {ticket.id}, thread: {thread}")


    def get_channel_by_name(self, channel_name: str) -> discord.TextChannel:
        for channel in self.get_all_channels():
            if isinstance(channel, discord.TextChannel) and channel_name == channel.name:
                return channel

        log.warning(f"Channel not found: {channel_name}")
        return None


    def get_role_by_name(self, role_name: str) -> discord.Role:
        # Noting: "guild" maps to discord server, and the API is designed to run on many "Discord servers" concurrently
        for guild in self.guilds:
            for role in guild.roles:
                if role_name == role.name:
                    return role


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
        ticket_id = NetBot.parse_thread_title(thread.name)

        ticket = self.redmine.ticket_mgr.get(ticket_id, include="journals")
        if ticket:
            completed = await self.synchronize_ticket(ticket, thread)
            # note: synchronize_ticket returns True only when successfully completing a sync
            # it can fail due to: lock, missing or mismatched sync record, network, remote service.
            # all these are ignored due to the lock.... not the best option.
            # need to think deeper about the pre-condition and desired outcome:
            # - What are the possible states and what causes them?
            # - Can all unexpected states be recovered?
            # - If not, what are the edge conditions and what data is needed to recover?
            # - (the answer is usually: this data conflict with old values. align to new values or old?)
            # reasonable outcomes are:
            # - temporary failure, will try again: self-resolves due to job-nature (lock, network, http)
            # - user input error: flag error in response, expect re-entry with valid input. OPPORTUNITY: "did you mean?"
            # - missing sync, reasonable recovery: create new.
            # - missmatch sync implies human by-hand changes in thread names/locations or bad code.
            #     as "bad code" is not a "reasonable" outcome, it should be fixed, so the only outcomes are:
            # - troubleshoot if it's a bug or
            # - note out-of-sync unexpected results: thread-name or whatever.
            # In this situation, "locked" is not unexpected (per se) but channel-mismatch is.
            # Implies a "user-error" exception to report back to the user specific conditions.
            # NetbotException is general, NetbotUserException
            if completed:
                return ticket
            else:
                raise NetbotException(f"Ticket {ticket.id} is locked for syncronization.")
        else:
            log.debug(f"no ticket found for {thread.name}")

        return None


    @tasks.loop(minutes=5.0) # to 5.0 minutes. set to 1 min for testing
    async def sync_all_threads(self):
        """
        Configured to run every minute using the tasks.loop annotation.
        Get all Threads and sync each one.
        """
        if not self.run_sync:
            log.debug("SYNC disabled, skipping")
            return

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
                except NetbotException as ex:
                    # ticket is locked.
                    # skip gracefully
                    log.debug(str(ex))
                except Exception:
                    log.exception(f"Error syncing {thread}")


    def channel_for_ticket(self, ticket: Ticket) -> discord.TextChannel:
        # first, check the syncdata.
        sync = ticket.validate_sync_record()
        if sync and sync.channel_id > 0:
            thread = self.bot.get_channel(sync.channel_id)
            if thread:
                return thread

        # no syncdata, no thread. fallback to tracker-based channel
        channel = self.channel_for_tracker(ticket.tracker)
        if channel:
            return channel

        # shouldn't get here. this is a desperate fallback
        log.warning(f"No channel for ticket: {ticket.id}, {ticket.tracker} - using {FALLBACK_TEAM}")
        return self.get_channel_by_name(FALLBACK_TEAM)


    async def remind_dusty_ticket(self, ticket: Ticket) -> None:
        """Remind the correct people and channels when a ticket is dusty."""
        discord_ids = self.extract_ids_from_ticket(ticket)
        reminder = self.formatter.format_dusty_reminder(ticket, discord_ids)
        channel = self.channel_for_ticket(ticket)
        await channel.send(reminder)


    async def remind_dusty_tickets(self):
        """Notify that tickets are about to expire."""
        # ticket-1608
        # get list of tickets that will expire (based on rules in ticket_mgr)
        for ticket in self.redmine.ticket_mgr.dusty():
            await self.remind_dusty_ticket(ticket)


    def tracker_for_channel(self, channel:str) -> NamedId:
        tracker_name = CHANNEL_MAPPING.get(channel, None)
        return self.redmine.ticket_mgr.get_tracker(tracker_name)


    def channel_for_tracker(self, tracker: NamedId) -> discord.TextChannel:
        for channel_name, tracker_name in CHANNEL_MAPPING.items():
            if tracker.name == tracker_name:
                return self.get_channel_by_name(channel_name)


    def team_for_tracker(self, tracker: NamedId) -> Team:
        """For a tracker, look up a team"""
        for channel_name, tracker_name in CHANNEL_MAPPING.items():
            if tracker.name == tracker_name:
                # lookup team from channel
                team_name = TEAM_MAPPING.get(channel_name, None)
                if team_name:
                    team = self.redmine.user_mgr.get_team_by_name(team_name)
                    if team:
                        return team
                    else:
                        log.error(f"Unable to find team for {tracker} and {team_name}")
                        return None
                else:
                    log.error(f"Unable to find channel mapping for {tracker} and {channel_name}")
                    return None

        # fallthru: not found
        log.error(f"Unable to find channel for {tracker}")
        return None


    async def recycle_ticket(self, ticket: Ticket):
        """ Recycle recycle an old dusty tickets.
        From ticket-1608: After 3 weeks of inactivity, the ticket
        is put in "new" state and reassigned to the tracker-based
        group. The team members are reminded of this status change.
        """
        new_owner = self.team_for_tracker(ticket.tracker)
        self.redmine.ticket_mgr.recycle(ticket, new_owner)

        # new_owner is a team. get the members for reminder
        discord_ids = self.discord_ids_for_team(new_owner)
        reminder = self.formatter.format_recycled_reminder(ticket, discord_ids)
        channel = self.channel_for_ticket(ticket)
        await channel.send(reminder)


    async def recycle_tickets(self):
        """ Recycle old dusty tickets."""
        for ticket in self.redmine.ticket_mgr.recyclable():
            await self.recycle_ticket(ticket)


    @commands.slash_command(name="notify", description="Force ticket notifications")
    async def force_notify(self):
        await self.remind_dusty_tickets()


    @tasks.loop(hours=24)
    async def run_daily_tasks(self):
        """Process dusty and recycled tickets.
        Expected to run every 24 hours to:
        - recycle tickets that have expired
        - remind owners of dusty tickets
        for ticket-1608
        """
        self.recycle_tickets()
        await self.remind_dusty_tickets()


    def find_ticket_thread(self, ticket_id:int) -> discord.Thread|None:
        """Search thru thread titles looking for a matching ticket ID"""
        # search thru all threads for:
        title_prefix = f"Ticket #{ticket_id}"
        for guild in self.guilds:
            for thread in guild.threads:
                if thread.name.startswith(title_prefix):
                    return thread

        return None # not found


    def discord_ids_for_team(self, team: Team) -> set[int]:
        """Extract the Discord IDs from users in a team"""

        if len(team.users) == 0:
            log.warning(f"TEAM with no users: {team}")

        discord_ids = set()
        for named in team.users:
            user = self.redmine.user_mgr.cache.get(named.id) #expected to be cached
            if user:
                if user.discord_id:
                    discord_ids.add(user.discord_id.id)
                else:
                    log.info(f"No Discord ID for {named}")
            elif self.redmine.user_mgr.is_team(named.name):
                # a team, look up role it.
                team = self.get_role_by_name(named.name)
                if team:
                    discord_ids.add(f"&{team.id}")
                else:
                    log.warning(f"Team name {named} has no matching Discord role.")
            else:
                log.info(f"ERROR: user ID {named} not found")

        return discord_ids


    def extract_ids_from_ticket(self, ticket: Ticket) -> set[int]:
        """Extract the Discord IDs from users interested in a ticket,
           using owner and collaborators"""
         # owner and watchers
        interested: list[NamedId] = []
        if ticket.assigned_to:
            interested.append(ticket.assigned_to)
        if ticket.watchers:
            interested.extend(ticket.watchers)

        discord_ids = set()
        for named in interested:
            user = self.redmine.user_mgr.cache.get(named.id) #expected to be cached
            if user:
                if user.discord_id:
                    discord_ids.add(user.discord_id.id)
                else:
                    log.info(f"No Discord ID for {named}")
            elif self.redmine.user_mgr.is_team(named.name):
                # a team, look up role it.
                team = self.get_role_by_name(named.name)
                if team:
                    discord_ids.add(f"&{team.id}")
                else:
                    log.warning(f"Team name {named} has no matching Discord role.")
            else:
                log.info(f"ERROR: user ID {named} not found")

        return discord_ids


    def is_admin(self, user: discord.Member) -> bool:
        """Check if the given Discord memeber is in a authorized role"""
        # search user for "auth" role
        for role in user.roles:
            if "auth" == role.name: ## FIXME
                return True

        # auth role not found
        return False


def main():
    """netbot main function"""
    log.info(f"loading .env for {__name__}")
    load_dotenv()

    client = Client.fromenv()
    bot = NetBot(client)

    for arg in sys.argv:
        if arg.lower() == "sync-off":
            log.info("Disabling ticket sync, due to 'sync-off' param")
            bot.run_sync = False

    # register cogs
    bot.load_extension("netbot.cog_scn")
    bot.load_extension("netbot.cog_tickets")

    # sanity check!
    client.sanity_check()

    # run the bot
    bot.run_bot()


def setup_logging():
    """set up logging for netbot"""
    log_level = logging.INFO
    # check args. cheap, I know.
    for arg in sys.argv:
        if arg.lower() == "debug":
            log_level = logging.DEBUG

    logging.basicConfig(level=log_level,
                        format="{asctime} {levelname:<8s} {name:<16} {message}",
                        style='{')
    logging.getLogger("discord.gateway").setLevel(logging.WARNING)
    logging.getLogger("discord.http").setLevel(logging.WARNING)
    logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)
    logging.getLogger("discord.client").setLevel(logging.WARNING)
    logging.getLogger("discord.webhook.async_").setLevel(logging.WARNING)

    log.debug("log level set to debug")

if __name__ == '__main__':
    setup_logging()
    main()
