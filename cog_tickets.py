#!/usr/bin/env python3

"""encapsulate Discord ticket functions"""

import logging

import discord

from discord.commands import option
from discord.ext import commands

from redmine import Client


log = logging.getLogger(__name__)

# scn add redmine_login - setup discord userid in redmine
# scn sync - manually sychs the current thread, or replies with warning
# scn sync

# scn join teamname - discord user joins team teamname (and maps user id)
# scn leave teamname - discord user leaves team teamname (and maps user id)

# scn reindex

def setup(bot):
    bot.add_cog(TicketsCog(bot))
    log.info("initialized tickets cog")


class TicketsCog(commands.Cog):
    """encapsulate Discord ticket functions"""
    def __init__(self, bot):
        self.bot = bot
        self.redmine: Client = bot.redmine
        log.debug(f"Initialized with {self.redmine}")

    # see https://github.com/Pycord-Development/pycord/blob/master/examples/app_commands/slash_cog_groups.py

#tickets - all the queries

#ticket # show (default) - show ticket info
#ticket # notes - show ticket will all notes (in a decent format)
#ticket # note - add a note to the specific ticket. same as commenting in the ticket thread (if there is one, works without)
#ticket # sync - creates new synced thread for ticket in the current text channel, or errors

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
            await self.print_tickets("My Tickets", self.redmine.my_tickets(user.login), ctx)
        elif len(args) == 1:
            query = args[0]
            results = self.resolve_query_term(query)
            await self.print_tickets(f"Search for '{query}'", results, ctx)


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
                        await ctx.respond(self.format_ticket(ticket)[:2000]) #trunc
                    else:
                        await ctx.respond(f"Ticket {ticket_id} not found.")
                case "details":
                    # FIXME
                    ticket = self.redmine.get_ticket(ticket_id)
                    if ticket:
                        await ctx.respond(self.format_ticket(ticket)[:2000]) #trunc
                    else:
                        await ctx.respond(f"Ticket {ticket_id} not found.")
                case "unassign":
                    self.redmine.unassign_ticket(ticket_id, user.login)
                    await self.print_ticket(self.redmine.get_ticket(ticket_id), ctx)
                case "resolve":
                    self.redmine.resolve_ticket(ticket_id, user.login)
                    await self.print_ticket(self.redmine.get_ticket(ticket_id), ctx)
                case "progress":
                    self.redmine.progress_ticket(ticket_id, user.login)
                    await self.print_ticket(self.redmine.get_ticket(ticket_id), ctx)
                #case "note":
                #    msg = ???
                #    self.redmine.append_message(ticket_id, user.login, msg)
                case "assign":
                    self.redmine.assign_ticket(ticket_id, user.login)
                    await self.print_ticket(self.redmine.get_ticket(ticket_id), ctx)
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
        ticket = self.redmine.create_ticket(user, title, text)
        if ticket:
            await ctx.respond(self.format_ticket(ticket)[:2000]) #trunc
        # error handling? exception?
        else:
            await ctx.respond(f"error creating ticket with title={title}")


    async def create_thread(self, ticket, ctx):
        log.info(f"creating a new thread for ticket #{ticket.id} in channel: {ctx.channel}")
        name = f"Ticket #{ticket.id}: {ticket.subject}"
        msg_txt = f"Syncing ticket {self.redmine.get_field(ticket, 'url')} to new thread '{name}'"
        message = await ctx.send(msg_txt)
        thread = await message.create_thread(name=name)
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
            self.redmine.enable_discord_sync(ticket.id, user, note)

            await ctx.respond(f"Created new thread for {ticket.id}: {thread}") # todo add some fancy formatting
        else:
            await ctx.respond(f"ERROR: Unkown ticket ID: {ticket_id}") # todo add some fancy formatting


    ### formatting ###

    async def print_tickets(self, title, tickets, ctx):
        msg = self.format_tickets(title, tickets)

        if len(msg) > 2000:
            log.warning("message over 2000 chars. truncing.")
            msg = msg[:2000]
        await ctx.respond(msg)


    async def print_ticket(self, ticket, ctx):
        msg = self.format_ticket(ticket)

        if len(msg) > 2000:
            log.warning("message over 2000 chars. truncing.")
            msg = msg[:2000]
        await ctx.respond(msg)


    def format_tickets(self, title, tickets, fields=None, max_len=2000):
        if tickets is None:
            return "No tickets found."

        if fields is None:
            fields = ["link","priority","updated_on","assigned_to","subject"]

        section = "**" + title + "**\n"
        for ticket in tickets:
            ticket_line = self.format_ticket(ticket, fields)
            if len(section) + len(ticket_line) + 1 < max_len:
                # make sure the lenght is less that the max
                section += ticket_line + "\n" # append each ticket
            else:
                break # max_len hit

        return section.strip()


    def format_ticket(self, ticket, fields=None):
        section = ""
        if fields is None:
            fields = ["link","priority","updated_on","assigned_to","subject"]

        for field in fields:
            section += str(self.redmine.get_field(ticket, field)) + " " # spacer, one space
        return section.strip() # remove trailing whitespace
