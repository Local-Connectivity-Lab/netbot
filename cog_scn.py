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
    bot.add_cog(SCNCog(bot))

class SCNCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.redmine = bot.redmine

    # see https://github.com/Pycord-Development/pycord/blob/master/examples/app_commands/slash_cog_groups.py

    scn = SlashCommandGroup("scn",  "SCN admin commands")

    @scn.command()
    async def add(self, ctx:discord.ApplicationContext, redmine_login:str, member:discord.Member=None):
        discord_name = ctx.user.name # by default, assume current user
        if member:
            log.info(f"Overriding current user={ctx.user.name} with member={member.name}")
            discord_name = member.name

        user = self.redmine.find_discord_user(discord_name)
        
        if user:
            await ctx.respond(f"Discord user: {discord_name} is already configured as redmine user: {user.login}")
        else:
            redmine.create_discord_mapping(redmine_login, discord_name)


    @scn.command()
    async def sync(self, ctx:discord.ApplicationContext):
        if isinstance(ctx.channel, discord.Thread):
            # get the ticket id from the thread name
            # FIXME: notice the series of calls to "self.bot": could be better encapsulated
            ticket_id = self.bot.parse_thread_title(ctx.channel.name)
            ticket = self.bot.get_ticket(ticket_id, include_journals=True)
            if ticket:
                await self.bot.synchronize_ticket(ticket, ctx.channel, ctx)
                await ctx.respond(f"SYNC ticket {ticket.id} to thread id: {ctx.channel.id} complete")
            else:
                await ctx.respond(f"cant find ticket# in thread name: {ctx.channel.name}") # error
        else:
            await ctx.respond(f"not a thread") # error


    @scn.command()
    async def reindex(self, ctx:discord.ApplicationContext):
        self.redmine.reindex()
        await ctx.send(f"Rebuilt redmine indices.")


    @scn.command()
    async def join(self, ctx:discord.ApplicationContext, teamname:str , member: discord.Member=None):
        discord_name = ctx.user.name # by default, assume current user
        if member:
            log.info(f"Overriding current user={ctx.user.name} with member={member.name}")
            discord_name = member.name
        user = self.redmine.find_discord_user(discord_name)
        
        if user:
            self.redmine.join_team(user.login, teamname)
            await ctx.respond(f"**{discord_name}** has joined *{teamname}*")
        else:
            await ctx.respond(f"Unknown Discord user: {discord_name}.")
        pass


    @scn.command()
    async def leave(self, ctx:discord.ApplicationContext, teamname:str, member: discord.Member=None):
        discord_name = ctx.user.name # by default, assume current user
        if member:
            log.info(f"Overriding current user={ctx.user.name} with member={member.name}")
            discord_name = member.name
        user = self.redmine.find_discord_user(discord_name)
        
        if user:
            self.redmine.leave_team(user.login, teamname)
            await ctx.respond(f"**{discord_name}** has left *{teamname}*")
        else:
            await ctx.respond(f"Unknown Discord user: {discord_name}.")
        pass