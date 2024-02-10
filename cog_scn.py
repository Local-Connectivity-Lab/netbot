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

from discord.ext import commands, tasks

log = logging.getLogger(__name__)

# scn add redmine_login - setup discord userid in redmine
# scn sync - manually sychs the current thread, or replies with warning 
# scn sync 

# scn join teamname - discord user joins team teamname (and maps user id)
# scn leave teamname - discord user leaves team teamname (and maps user id)

# scn reindex

def setup(bot):
    bot.add_cog(SCNCog(bot))
    log.info(f"initialized SCN cog")

class SCNCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.redmine = bot.redmine
        self.sync_all_threads.start() # start the sync task

    # see https://github.com/Pycord-Development/pycord/blob/master/examples/app_commands/slash_cog_groups.py

    scn = SlashCommandGroup("scn",  "SCN admin commands")

    @scn.command()
    async def add(self, ctx:discord.ApplicationContext, redmine_login:str, member:discord.Member=None):
        """add Discord user information to redmine"""
        discord_name = ctx.user.name # by default, assume current user
        if member:
            log.info(f"Overriding current user={ctx.user.name} with member={member.name}")
            discord_name = member.name

        user = self.redmine.find_discord_user(discord_name)
        
        if user:
            await ctx.respond(f"Discord user: {discord_name} is already configured as redmine user: {user.login}")
        else:
            self.redmine.create_discord_mapping(redmine_login, discord_name)
            await ctx.respond(f"Discord user: {discord_name} has been paired with redmine user: {redmine_login}")


    async def sync_thread(self, thread:discord.Thread):
        """syncronize an existing ticket thread with redmine"""
        # get the ticket id from the thread name
        # FIXME: notice the series of calls to "self.bot": could be better encapsulated
        ticket_id = self.bot.parse_thread_title(thread.name)
        ticket = self.redmine.get_ticket(ticket_id, include_journals=True)
        if ticket:
            await self.bot.synchronize_ticket(ticket, thread)
            return ticket
        else:
            return None


    """
    Configured to run every 5 minutes using the tasks.loop annotation.
    Get all Threads and sync each one.
    """
    @tasks.loop(minutes=1.0) # FIXME to 5.0 minutes. set to 1 min for testing
    async def sync_all_threads(self):
        log.info(f"sync_all_threads: starting for {self.bot.guilds}")
        # LOCK acquire sync lock. - 1 lock, bot-level, to block

        # get all threads
        for guild in self.bot.guilds:
            for thread in guild.threads:
                #log.debug(f"THREAD: guild:{guild}, thread:{thread}")
                # sync each thread, 
                ticket = await self.sync_thread(thread)
                if ticket:
                    # successful sync
                    log.debug(f"SYNC: thread:{thread.name} with ticket {ticket.id}")
                else:
                    log.debug(f"no ticket found for {thread.name}")


    @scn.command()
    async def sync(self, ctx:discord.ApplicationContext):
        """syncronize an existing ticket thread with redmine"""
        if isinstance(ctx.channel, discord.Thread):
            ticket = await self.sync_thread(ctx.channel)
            if ticket:
                await ctx.respond(f"SYNC ticket {ticket.id} to thread: {ctx.channel.name} complete")
            else:
                await ctx.respond(f"Cannot find ticket# in thread name: {ctx.channel.name}") # error
        else:
            await ctx.respond(f"Not a thread.") # error


    @scn.command()
    async def reindex(self, ctx:discord.ApplicationContext):
        """reindex the user and team information"""
        self.redmine.reindex()
        await ctx.respond(f"Rebuilt redmine indices.")


    @scn.command(description="join the specified team")
    async def join(self, ctx:discord.ApplicationContext, teamname:str , member: discord.Member=None):
        discord_name = ctx.user.name # by default, assume current user
        if member:
            log.info(f"Overriding current user={ctx.user.name} with member={member.name}")
            discord_name = member.name
            
        user = self.redmine.find_discord_user(discord_name)
        if user is None:
            await ctx.respond(f"Unknown user, no Discord mapping: {discord_name}")
        elif self.redmine.find_team(teamname) is None:
            await ctx.respond(f"Unknown team name: {teamname}")
        else:
            self.redmine.join_team(user.login, teamname)
            await ctx.respond(f"**{discord_name}** has joined *{teamname}*")


    @scn.command(description="leave the specified team")
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


    @scn.command(description="list teams and members")
    async def teams(self, ctx:discord.ApplicationContext, teamname:str=None):
        # list all teams, with members

        if teamname:
            team = self.redmine.get_team(teamname)
            if team:
                #await self.print_team(ctx, team)
                await ctx.respond(self.format_team(team))
            else:
                await ctx.respond(f"Unknown team name: {teamname}") # error
        else:
            # all teams
            teams = self.redmine.get_teams()
            buff = ""
            for teamname in teams:
                team = self.redmine.get_team(teamname)
                #await self.print_team(ctx, team)
                buff += self.format_team(team)
            await ctx.respond(buff[:2000]) # truncate!


    async def print_team(self, ctx, team):
        msg = f"> **{team.name}**\n"
        for user_rec in team.users:
            user = self.redmine.get_user(user_rec.id)
            #discord_user = user.custom_fields[0].value or ""  # FIXME cf_* lookup
            msg += f"{user_rec.name}, " 
            #msg += f"[{user.id}] **{user_rec.name}** {user.login} {user.mail} {user.custom_fields[0].value}\n"
        msg = msg[:-2] + '\n\n'
        await ctx.channel.send(msg)


    def format_team(self, team):
        # single line format: teamname: member1, member2
        if team:
            return f"**{team.name}**: {', '.join([user.name for user in team.users])}\n"