#!/usr/bin/env python3
"""Cog to manage SCN-related functions"""
import logging

import discord

from discord.commands import SlashCommandGroup
from discord.ext import commands, tasks

from netbot import NetbotException
from redmine import Client


log = logging.getLogger(__name__)

# scn add redmine_login - setup discord userid in redmine
# scn sync - manually sychs the current thread, or replies with warning
# scn sync

# scn join teamname - discord user joins team teamname (and maps user id)
# scn leave teamname - discord user leaves team teamname (and maps user id)

# scn reindex

def setup(bot):
    bot.add_cog(SCNCog(bot))
    log.info("initialized SCN cog")

class NewUserModal(discord.ui.Modal):
    """modal dialog to collect new user info"""
    def __init__(self, redmine: Client, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.redmine = redmine
        self.add_item(discord.ui.InputText(label="First Name"))
        self.add_item(discord.ui.InputText(label="Last Name"))
        self.add_item(discord.ui.InputText(label="Email"))

    async def callback(self, interaction: discord.Interaction):
        email = self.children[2].value
        first = self.children[0].value
        last = self.children[1].value

        log.debug(f"new user callback: email={email}, first={first}, last={last}")

        embed = discord.Embed(title="Created User")
        embed.add_field(name="First", value=first)
        embed.add_field(name="Last", value=last)
        embed.add_field(name="Email", value=email)

        user = self.redmine.create_user(email, first, last)

        if user is None:
            log.error(f"Unable to create user from {first}, {last}, {email}, {interaction.user.name}")
        else:
            self.redmine.create_discord_mapping(user.login, interaction.user.name)
            await interaction.response.send_message(embeds=[embed])


class SCNCog(commands.Cog):
    """Cog to mange SCN-related functions"""
    def __init__(self, bot):
        self.bot = bot
        self.redmine: Client = bot.redmine
        self.sync_all_threads.start() # pylint: disable=no-member

    # see https://github.com/Pycord-Development/pycord/blob/master/examples/app_commands/slash_cog_groups.py

    scn = SlashCommandGroup("scn",  "SCN admin commands")

    @scn.command()
    async def add(self, ctx:discord.ApplicationContext, redmine_login:str, member:discord.Member=None):
        """add Discord user information to redmine"""
        discord_name = ctx.user.name # by default, assume current user
        if member:
            log.info(f"Overriding current user={ctx.user.name} with member={member.name}")
            discord_name = member.name

        user = self.redmine.user_mgr.find(discord_name)

        if user:
            await ctx.respond(f"Discord user: {discord_name} is already configured as redmine user: {user.login}")
        else:
            user = self.redmine.user_mgr.find(redmine_login)
            if user:
                self.redmine.create_discord_mapping(redmine_login, discord_name)
                await ctx.respond(f"Discord user: {discord_name} has been paired with redmine user: {redmine_login}")
            else:
                # no user exists for that login
                modal = NewUserModal(self.redmine, title="Create new user in Redmine")
                await ctx.send_modal(modal)
            # reindex users after changes
            self.redmine.reindex_users()


    async def sync_thread(self, thread:discord.Thread):
        """syncronize an existing ticket thread with redmine"""
        # get the ticket id from the thread name
        ticket_id = self.bot.parse_thread_title(thread.name)

        ticket = self.redmine.get_ticket(ticket_id, include_journals=True)
        if ticket:
            completed = await self.bot.synchronize_ticket(ticket, thread)
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
        log.info(f"sync_all_threads: starting for {self.bot.guilds}")

        # get all threads
        for guild in self.bot.guilds:
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
            await ctx.respond("Not a thread.") # error


    @scn.command()
    async def reindex(self, ctx:discord.ApplicationContext):
        """reindex the user and team information"""
        self.redmine.user_mgr.reindex()
        await ctx.respond("Rebuilt redmine indices.")


    @scn.command(description="join the specified team")
    async def join(self, ctx:discord.ApplicationContext, teamname:str , member: discord.Member=None):
        discord_name = ctx.user.name # by default, assume current user
        if member:
            log.info(f"Overriding current user={ctx.user.name} with member={member.name}")
            discord_name = member.name

        user = self.redmine.user_mgr.find(discord_name)
        if user is None:
            await ctx.respond(f"Unknown user, no Discord mapping: {discord_name}")
        elif self.redmine.user_mgr.get_team_by_name(teamname) is None:
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
        user = self.redmine.user_mgr.find(discord_name)

        if user:
            self.redmine.leave_team(user.login, teamname)
            await ctx.respond(f"**{discord_name}** has left *{teamname}*")
        else:
            await ctx.respond(f"Unknown Discord user: {discord_name}.")


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


    # ticket 484 - http://10.10.0.218/issues/484
    # block users based on name (not discord membership)
    @scn.command(description="block specific a email address and reject all related tickets")
    async def block(self, ctx:discord.ApplicationContext, username:str):
        log.debug(f"blocking {username}")
        #user = self.redmine.lookup_user(username)
        user = self.redmine.user_mgr.find(username)
        if user:
            # add the user to the blocked list
            self.redmine.user_mgr.block(user)
            # search and reject all tickets from that user
            for ticket in self.redmine.get_tickets_by(user):
                self.redmine.reject_ticket(ticket.id)
            await ctx.respond(f"Blocked user: {user.login} and rejected all created tickets")
        else:
            log.debug("trying to block unknown user '{username}', ignoring")
            await ctx.respond(f"Unknown user: {username}")


    @scn.command(description="unblock specific a email address")
    async def unblock(self, ctx:discord.ApplicationContext, username:str):
        log.debug(f"unblocking {username}")
        user = self.redmine.user_mgr.find(username)
        if user:
            self.redmine.unblock_user(user)
            await ctx.respond(f"Unblocked user: {user.login}")
        else:
            log.debug("trying to unblock unknown user '{username}', ignoring")
            await ctx.respond(f"Unknown user: {username}")


    async def print_team(self, ctx, team):
        msg = f"> **{team.name}**\n"
        for user_rec in team.users:
            #user = self.redmine.get_user(user_rec.id)
            #discord_user = user.custom_fields[0].value or ""  # FIXME cf_* lookup
            msg += f"{user_rec.name}, "
            #msg += f"[{user.id}] **{user_rec.name}** {user.login} {user.mail} {user.custom_fields[0].value}\n"
        msg = msg[:-2] + '\n\n'
        await ctx.channel.send(msg)


    def format_team(self, team):
        # single line format: teamname: member1, member2
        if team:
            return f"**{team.name}**: {', '.join([user.name for user in team.users])}\n"
