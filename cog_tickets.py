#!/usr/bin/env python3

"""encapsulate Discord ticket functions"""

import logging

import discord

from discord.commands import option
from discord.ext import commands, tasks

from model import Message, Ticket
from redmine import Client


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


def setup(bot):
    bot.add_cog(TicketsCog(bot))
    log.info("initialized tickets cog")


class TicketsCog(commands.Cog):
    """encapsulate Discord ticket functions"""
    def __init__(self, bot):
        self.bot = bot
        self.redmine: Client = bot.redmine

        # start the expriation checker
        self.check_expired_tickets.start() # pylint: disable=no-member
        log.debug(f"Initialized with {self.redmine}")

    # see https://github.com/Pycord-Development/pycord/blob/master/examples/app_commands/slash_cog_groups.py


    # figure out what the term refers to
    # could be ticket#, team name, user name or search term
    def resolve_query_term(self, term):
        # special cases: ticket num and team name
        try:
            int_id = int(term)
            ticket = self.redmine.get_ticket(int_id)
            return [ticket]
        except ValueError:
            # not a numeric id, check team
            if self.redmine.user_mgr.is_user_or_group(term):
                return self.redmine.tickets_for_team(term)
            else:
                # assume a search term
                return self.redmine.search_tickets(term)

    @commands.slash_command()     # guild_ids=[...] # Create a slash command for the supplied guilds.
    async def tickets(self, ctx: discord.ApplicationContext, params: str = ""):
        """List tickets for you, or filtered by parameter"""
        # different options: none, me (default), [group-name], intake, tracker name
        # buid index for trackers, groups
        # add groups to users.

        # lookup the user
        user = self.redmine.user_mgr.find(ctx.user.name)
        log.debug(f"found user mapping for {ctx.user.name}: {user}")

        args = params.split()

        if len(args) == 0 or args[0] == "me":
            await self.bot.formatter.print_tickets("My Tickets", self.redmine.my_tickets(user.login), ctx)
        elif len(args) == 1:
            query = args[0]
            results = self.resolve_query_term(query)
            await self.bot.formatter.print_tickets(f"Search for '{query}'", results, ctx)


    @commands.slash_command()
    async def ticket(self, ctx: discord.ApplicationContext, ticket_id:int, action:str="show"):
        """Update status on a ticket, using: unassign, resolve, progress"""
        try:
            # lookup the user
            user = self.redmine.user_mgr.find(ctx.user.name)
            log.debug(f"found user mapping for {ctx.user.name}: {user}")

            match action:
                case "show":
                    ticket = self.redmine.get_ticket(ticket_id)
                    if ticket:
                        await self.bot.formatter.print_ticket(ticket, ctx)
                    else:
                        await ctx.respond(f"Ticket {ticket_id} not found.")
                case "details":
                    # FIXME
                    ticket = self.redmine.get_ticket(ticket_id)
                    if ticket:
                        await self.bot.formatter.print_ticket(ticket, ctx)
                    else:
                        await ctx.respond(f"Ticket {ticket_id} not found.")
                case "unassign":
                    self.redmine.unassign_ticket(ticket_id, user.login)
                    await self.bot.formatter.print_ticket(self.redmine.get_ticket(ticket_id), ctx)
                case "resolve":
                    self.redmine.resolve_ticket(ticket_id, user.login)
                    await self.bot.formatter.print_ticket(self.redmine.get_ticket(ticket_id), ctx)
                case "progress":
                    self.redmine.progress_ticket(ticket_id, user.login)
                    await self.bot.formatter.print_ticket(self.redmine.get_ticket(ticket_id), ctx)
                #case "note":
                #    msg = ???
                #    self.redmine.append_message(ticket_id, user.login, msg)
                case "assign":
                    self.redmine.assign_ticket(ticket_id, user.login)
                    await self.bot.formatter.print_ticket(self.redmine.get_ticket(ticket_id), ctx)
                case _:
                    await ctx.respond("unknown command: {action}")
        except Exception as e:
            log.exception(e)
            await ctx.respond(f"Error {action} {ticket_id}: {e}")


    @commands.slash_command(name="new", description="Create a new ticket")
    @option("title", description="Title of the new SCN ticket")
    @option("add_thread", description="Create a Discord thread for the new ticket", default=False)
    async def create_new_ticket(self, ctx: discord.ApplicationContext, title:str):
        user = self.redmine.user_mgr.find(ctx.user.name)
        if user is None:
            await ctx.respond(f"Unknown user: {ctx.user.name}")
            return

        # text templating
        text = f"ticket created by Discord user {ctx.user.name} -> {user.login}, with the text: {title}"
        message = Message(from_addr=user.mail, subject=title, to=ctx.channel.name)
        message.set_note(text)
        ticket = self.redmine.create_ticket(user, message)
        if ticket:
            await self.bot.formatter.print_ticket(ticket, ctx)
        else:
            await ctx.respond(f"error creating ticket with title={title}")


    async def create_thread(self, ticket:Ticket, ctx:discord.ApplicationContext):
        log.info(f"creating a new thread for ticket #{ticket.id} in channel: {ctx.channel}")
        thread_name = f"Ticket #{ticket.id}: {ticket.subject}"
        thread = await ctx.channel.create_thread(name=thread_name)
        # ticket-614: Creating new thread should post the ticket details to the new thread
        await thread.send(self.bot.formatter.format_ticket_details(ticket))
        return thread


    @commands.slash_command(name="thread", description="Create a Discord thread for the specified ticket")
    @option("ticket_id", description="ID of tick to create thread for")
    async def thread_ticket(self, ctx: discord.ApplicationContext, ticket_id:int):
        ticket = self.redmine.get_ticket(ticket_id)
        if ticket:
            # create the thread...
            thread = await self.create_thread(ticket, ctx)

            # update the discord flag on tickets, add a note with url of thread; thread.jump_url
            # TODO message templates
            note = f"Created Discord thread: {thread.name}: {thread.jump_url}"
            user = self.redmine.user_mgr.find_discord_user(ctx.user.name)
            log.debug(f">>> found {user} for {ctx.user.name}")
            self.redmine.enable_discord_sync(ticket.id, user, note)

            # ticket-614: add ticket link to thread response
            ticket_link = self.bot.formatter.format_link(ticket)
            await ctx.respond(f"Created new thread {thread.jump_url} for ticket {ticket_link}")
        else:
            await ctx.respond(f"ERROR: Unkown ticket ID: {ticket_id}")


    async def expiration_notification(self, ticket: Ticket):
        """Notify the correct people and channels when a ticket expires.
        ticket-597
        When a ticket is about to expire, put a message in the related thread that it is about to expire.
        "In {hours}, this ticket will expire."
        """

        # first, check the syncdata.
        sync = ticket.get_sync_record()
        if sync:
            notification = self.bot.formatter.format.format_expiration_notification(ticket)
            thread: discord.Thread = self.bot.get_channel(sync.channel_id)
            thread.send(notification)
        elif str(ticket.tracker) in _TRACKER_MAPPING:
            # lookup channel
            channel_name = _TRACKER_MAPPING[str(ticket.tracker)]
            channel = self.bot.get_channel_by_name(channel_name)
            if channel:
                channel.send(self.bot.formatter.format_expiring_alert(ticket))
        else:
            log.error(f"EXPIRED ticket #{ticket.id} on unknown channel: {channel_name}")


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
