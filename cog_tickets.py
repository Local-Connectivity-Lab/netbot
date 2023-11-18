#!/usr/bin/env python3

import os
import re
import logging
import datetime as dt

import discord
import redmine

from discord.commands import option
from discord.commands import SlashCommandGroup

from dotenv import load_dotenv

from discord.ext import commands

log = logging.getLogger(__name__)

# scn add redmine_login - setup discord userid in redmine
# scn sync - manually sychs the current thread, or replies with warning 
# scn sync 

# scn join teamname - discord user joins team teamname (and maps user id)
# scn leave teamname - discord user leaves team teamname (and maps user id)

# scn reindex

def setup(bot):
    bot.add_cog(TicketsCog(bot))



class TicketsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.redmine = bot.redmine

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
            id = int(term)
            ticket = self.redmine.get_ticket(id)
            return [ticket]
        except ValueError:
            # not a numeric id, check team
            if self.redmine.is_user_or_group(term):
                return self.redmine.tickets_for_team(term)
            else:
                # assume a search term
                return self.redmine.search_tickets(term)
            
    @commands.slash_command()     # guild_ids=[...] # Create a slash command for the supplied guilds.
    async def tickets(self, ctx: discord.ApplicationContext, params: str = ""):
        # different options: none, me (default), [group-name], intake, tracker name
        # buid index for trackers, groups
        # add groups to users.

        # lookup the user
        user = self.redmine.find_discord_user(ctx.user.name)
        log.debug(f"found user mapping for {ctx.user.name}: {user}")

        args = params.split()

        if len(args) == 0 or args[0] == "me":
            await self.print_tickets(self.redmine.my_tickets(user.login), ctx)
        elif len(args) == 1:
            await self.print_tickets(self.resolve_query_term(args[0]), ctx)
            

    @commands.slash_command()
    async def ticket(self, ctx: discord.ApplicationContext, ticket_id:int, action:str="show"):
        try:
            # lookup the user
            user = self.redmine.find_discord_user(ctx.user.name)
            log.debug(f"found user mapping for {ctx.user.name}: {user}")

            match action:
                case "show":
                    #FIXME
                    await ctx.respond("not implemented")
                case "details":
                    # FIXME
                    await ctx.respond("not implemented")
                case "unassign":
                    self.redmine.unassign_ticket(id, user.login)
                    await self.print_ticket(self.redmine.get_ticket(id), ctx)
                case "resolve":
                    self.redmine.resolve_ticket(id, user.login)
                    await self.print_ticket(self.redmine.get_ticket(id), ctx)
                case "progress":
                    self.progress_ticket(id, user.login)
                    await self.print_ticket(self.redmine.get_ticket(id), ctx)
                case "note":
                    await ctx.respond("not implemented")
                case "sync":
                    await ctx.respond("not implemented")
                case "assign":
                    await ctx.respond("not implemented")
                case _:
                    await ctx.respond("unknown command: {action}")
        except Exception as e:
            msg = f"Error {action} {ticket_id}: {e}"
            log.error(msg)
            await ctx.respond(msg)


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
