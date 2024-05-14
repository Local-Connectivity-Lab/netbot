#!/usr/bin/env python3

"""encapsulate Discord ticket functions"""

import logging

import discord

from discord.commands import option, SlashCommandGroup

from discord.ext import commands

from model import Message, Ticket
from redmine import Client


log = logging.getLogger(__name__)


def setup(bot):
    bot.add_cog(TicketsCog(bot))
    log.info("initialized tickets cog")


class TicketsCog(commands.Cog):
    """encapsulate Discord ticket functions"""
    def __init__(self, bot):
        self.bot = bot
        self.redmine: Client = bot.redmine

    # see https://github.com/Pycord-Development/pycord/blob/master/examples/app_commands/slash_cog_groups.py
    ticket = SlashCommandGroup("ticket",  "ticket commands")


    # figure out what the term refers to
    # could be ticket#, team name, user name or search term
    def resolve_query_term(self, term):
        # special cases: ticket num and team name
        try:
            int_id = int(term)
            ticket = self.redmine.get_ticket(int_id)
            return [ticket]
        except ValueError:
            # ignore
            pass

        # not a numeric id, check for known user or group
        user_team = self.redmine.user_mgr.find(term)
        if user_team:
            log.debug(f"{term} -> {user_team}")
            result = self.redmine.ticket_mgr.tickets_for_team(user_team)
            if result:
                return result
            # note: fall thru for empty result from team query.

        # assume a search term
        log.debug(f"QUERY {term}")
        return self.redmine.search_tickets(term)


    @ticket.command(description="Query tickets")
    @option("term", description="Ticket query term, should includes ticket ID, ticket owner, team or any term used for a text match.")
    async def query(self, ctx: discord.ApplicationContext, term: str):
        """List tickets for you, or filtered by parameter"""
        # different options: none, me (default), [group-name], intake, tracker name
        # buid index for trackers, groups
        # add groups to users.

        # lookup the user
        user = self.redmine.user_mgr.find(ctx.user.name)
        log.debug(f"found user mapping for {ctx.user.name}: {user}")

        args = term.split()

        if args[0] == "me":
            await self.bot.formatter.print_tickets("My Tickets", self.redmine.my_tickets(user.login), ctx)
        elif len(args) == 1:
            query = args[0]
            results = self.resolve_query_term(query)
            await self.bot.formatter.print_tickets(f"Search for '{query}'", results, ctx)


    @ticket.command(description="Get ticket details")
    @option("term", description="ticket ID")
    async def details(self, ctx: discord.ApplicationContext, ticket_id:int):
        """Update status on a ticket, using: unassign, resolve, progress"""
        #log.debug(f"found user mapping for {ctx.user.name}: {user}")
        ticket = self.redmine.get_ticket(ticket_id)
        if ticket:
            await self.bot.formatter.print_ticket(ticket, ctx)
        else:
            await ctx.respond(f"Ticket {ticket_id} not found.") # print error


    @ticket.command(description="Unassign a ticket")
    @option("ticket_id", description="ticket ID")
    async def unassign(self, ctx: discord.ApplicationContext, ticket_id:int):
        """Update status on a ticket, using: unassign, resolve, progress"""
        # lookup the user
        user = self.redmine.user_mgr.find(ctx.user.name)
        if not user:
            await ctx.respond(f"User {ctx.user.name} not mapped to redmine. Use `/scn add` to create the mapping.") # error
            return
        ticket = self.redmine.get_ticket(ticket_id)
        if ticket:
            self.redmine.unassign_ticket(ticket_id, user.login)
            await self.bot.formatter.print_ticket(self.redmine.get_ticket(ticket_id), ctx)
        else:
            await ctx.respond(f"Ticket {ticket_id} not found.") # print error


    @ticket.command(description="Resolve a ticket")
    @option("ticket_id", description="ticket ID")
    async def resolve(self, ctx: discord.ApplicationContext, ticket_id:int):
        """Update status on a ticket, using: unassign, resolve, progress"""
        # lookup the user
        user = self.redmine.user_mgr.find(ctx.user.name)
        if not user:
            await ctx.respond(f"User {ctx.user.name} not mapped to redmine. Use `/scn add` to create the mapping.") # error
            return
        ticket = self.redmine.get_ticket(ticket_id)
        if ticket:
            self.redmine.resolve_ticket(ticket_id, user.login)
            await self.bot.formatter.print_ticket(self.redmine.get_ticket(ticket_id), ctx)
        else:
            await ctx.respond(f"Ticket {ticket_id} not found.") # print error


    @ticket.command(description="Mark a ticket in-progress")
    @option("ticket_id", description="ticket ID")
    async def progress(self, ctx: discord.ApplicationContext, ticket_id:int):
        """Update status on a ticket, using: unassign, resolve, progress"""
        # lookup the user
        user = self.redmine.user_mgr.find(ctx.user.name)
        if not user:
            await ctx.respond(f"User {ctx.user.name} not mapped to redmine. Use `/scn add` to create the mapping.") # error
            return

        ticket = self.redmine.get_ticket(ticket_id)
        if ticket:
            self.redmine.progress_ticket(ticket_id, user.login)
            await self.bot.formatter.print_ticket(self.redmine.get_ticket(ticket_id), ctx)
        else:
            await ctx.respond(f"Ticket {ticket_id} not found.") # print error


    @ticket.command(description="Assign a ticket")
    @option("ticket_id", description="ticket ID")
    async def assign(self, ctx: discord.ApplicationContext, ticket_id:int):
        """Update status on a ticket, using: unassign, resolve, progress"""
        # lookup the user
        user = self.redmine.user_mgr.find(ctx.user.name)
        if not user:
            await ctx.respond(f"User {ctx.user.name} not mapped to redmine. Use `/scn add` to create the mapping.") # error
            return

        ticket = self.redmine.get_ticket(ticket_id)
        if ticket:
            self.redmine.assign_ticket(ticket_id, user.login)
            await self.bot.formatter.print_ticket(self.redmine.get_ticket(ticket_id), ctx)
        else:
            await ctx.respond(f"Ticket {ticket_id} not found.") # print error


    async def create_thread(self, ticket:Ticket, ctx:discord.ApplicationContext):
        log.info(f"creating a new thread for ticket #{ticket.id} in channel: {ctx.channel}")
        thread_name = f"Ticket #{ticket.id}: {ticket.subject}"
        # added public_thread type param
        thread = await ctx.channel.create_thread(name=thread_name, type=discord.ChannelType.public_thread)
        # ticket-614: Creating new thread should post the ticket details to the new thread
        await thread.send(self.bot.formatter.format_ticket_details(ticket))
        return thread


    @ticket.command(name="new", description="Create a new ticket")
    @option("title", description="Title of the new SCN ticket")
    @option("add_thread", description="Create a Discord thread for the new ticket", default=False)
    async def create_new_ticket(self, ctx: discord.ApplicationContext, title:str):
        user = self.redmine.user_mgr.find(ctx.user.name)
        if not user:
            await ctx.respond(f"User {ctx.user.name} not mapped to redmine. Use `/scn add` to create the mapping.") # error
            return

        channel_name = ctx.channel.name
        text = f"ticket created by Discord user {ctx.user.name} -> {user.login}, with the text: {title}"
        message = Message(from_addr=user.mail, subject=title, to=ctx.channel.name)
        message.set_note(text)
        ## TODO cleanup with cogscn.sync: both have complex ticket creation
        ticket = self.redmine.create_ticket(user, message)
        if ticket:
            # ticket created, set tracker
            # set tracker
            # TODO: search up all parents in hierarchy?
            tracker = self.bot.lookup_tracker(channel_name)
            if tracker:
                log.debug(f"found {channel_name} => {tracker}")
                params = {
                    "tracker_id": str(tracker.id),
                    "notes": f"Setting tracker based on channel name: {channel_name}"
                }
                self.redmine.ticket_mgr.update(ticket.id, params, user.login)
            else:
                log.debug(f"not tracker for {channel_name}")
            # create related discord thread
            await self.thread(ctx, ticket.id)
            #await self.bot.formatter.print_ticket(ticket, ctx)
        else:
            await ctx.respond(f"Error creating ticket with title={title}")


    @ticket.command(description="Thread a Redmine ticket in Discord")
    @option("ticket_id", description="ID of tick to create thread for")
    async def thread(self, ctx: discord.ApplicationContext, ticket_id:int):
        ticket = self.redmine.get_ticket(ticket_id)
        if ticket:
            ticket_link = self.bot.formatter.format_link(ticket)

            # check if sync data exists for a different channel
            synced = ticket.get_sync_record()
            if synced and synced.channel_id != ctx.channel_id:
                thread = self.bot.get_channel(synced.channel_id)
                if thread:
                    await ctx.respond(f"Ticket {ticket_link} already synced with {thread.jump_url}")
                    return # stop processing
                else:
                    log.info(f"Ticket {ticket_id} synced with unknown thread ID {synced.channel_id}. Recovering.")
                    # delete the sync record
                    self.redmine.ticket_mgr.remove_sync_record(synced)
                    # fall thru to create thread and sync

            # create the thread...
            thread = await self.create_thread(ticket, ctx)

            # update the discord flag on tickets, add a note with url of thread; thread.jump_url
            note = f"Created Discord thread: {thread.name}: {thread.jump_url}"
            user = self.redmine.user_mgr.find_discord_user(ctx.user.name)
            self.redmine.enable_discord_sync(ticket.id, user, note)

            # ticket-614: add ticket link to thread response
            await ctx.respond(f"Created new thread {thread.jump_url} for ticket {ticket_link}")
        else:
            await ctx.respond(f"ERROR: Unkown ticket ID: {ticket_id}")
