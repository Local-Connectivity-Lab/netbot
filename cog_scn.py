#!/usr/bin/env python3
"""Cog to manage SCN-related functions"""
import logging

import discord

from discord.commands import SlashCommandGroup
from discord.ext import commands

from model import Message
from redmine import Client, BLOCKED_TEAM_NAME


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

        # create the new user with the ID of the redmine user to assure they have access.
        admin = self.redmine.user_mgr.find_discord_user(interaction.user.name)
        if admin is None:
            log.error(f"Unknown user: {interaction.user.name}, no redminw mapping")
            await interaction.response.send_message(f"Unknown user: {interaction.user.name}, does not have permissions to create users.")
            return

        user = self.redmine.user_mgr.create(email, first, last, user_login=admin.login)
        if user is None:
            log.error(f"Unable to create user from {first}, {last}, {email}, {interaction.user.name}")
            await interaction.response.send_message(f"Unable to create user for {email}")
            return

        self.redmine.user_mgr.create_discord_mapping(user, interaction.user.name)
        embed = discord.Embed(title="Created User")
        embed.add_field(name="First", value=first)
        embed.add_field(name="Last", value=last)
        embed.add_field(name="Email", value=email)
        await interaction.response.send_message(embeds=[embed])


# FIXME Not yet implemented
class IntakeView(discord.ui.View):
    """Perform intake"""
    # to build, need:
    # - list of trackers
    # - list or priorities
    # - ticket subject
    # - from email
    # build intake view
    # 1. Assign: (popup with potential assignments)
    # 2. Priority: (popup with priorities)
    # 3. (Reject) Subject
    # 4. (Block) email-addr
    def __init__(self, bot_: discord.Bot) -> None:
        self.bot = bot_
        super().__init__()

        # Adds the dropdown to our View object
        #self.add_item(PrioritySelect(self.bot))
        #self.add_item(discord.ui.InputText(label="Subject", row=1))
        #self.add_item(TrackerSelect(self.bot))


        self.add_item(discord.ui.Button(label="Assign", row=4))
        self.add_item(discord.ui.Button(label="Reject ticket subject", row=4))
        self.add_item(discord.ui.Button(label="Block email@address.com", row=4))

    async def select_callback(self, select, interaction): # the function called when the user is done selecting options
        await interaction.response.send_message(f"IntakeView.select_callback() selected: {select.values[0]}")

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"IntakeView.allback() {interaction.data}")


class SCNCog(commands.Cog):
    """Cog to mange SCN-related functions"""
    def __init__(self, bot):
        self.bot = bot
        self.redmine: Client = bot.redmine

    # see https://github.com/Pycord-Development/pycord/blob/master/examples/app_commands/slash_cog_groups.py

    scn = SlashCommandGroup("scn",  "SCN admin commands")


    def is_admin(self, user: discord.Member) -> bool:
        """Check if the given Discord memeber is in a authorized role"""
        # search user for "auth" role
        for role in user.roles:
            log.debug(f"### ROLE {role}")
            if "auth" == role.name: ## FIXME
                return True

        # auth role not found
        return False


    @scn.command()
    async def add(self, ctx:discord.ApplicationContext, redmine_login:str, member:discord.Member=None):
        """add a Discord user to the Redmine ticketing integration"""
        discord_name = ctx.user.name # by default, assume current user
        if member:
            log.info(f"Overriding current user={ctx.user.name} with member={member.name}")
            discord_name = member.name

        user = self.redmine.user_mgr.find(discord_name)
        if user:
            await ctx.respond(f"Discord user: {discord_name} is already configured as redmine user: {user.login}")
        else:
            user = self.redmine.user_mgr.find(redmine_login)
            if user and self.is_admin(ctx.user):
                self.redmine.user_mgr.create_discord_mapping(user, discord_name)
                await ctx.respond(f"Discord user: {discord_name} has been paired with redmine user: {redmine_login}")
            else:
                admin = self.redmine.user_mgr.find(ctx.user.name)
                # TODO: This is only checking exists. Add "admin" check: redmine.user_mgr.is_admin(user.login)
                if not admin:
                    log.error(f"Unknown Discord user {ctx.user.name}")
                    await ctx.response.send_message(f"Unknown Discord user {ctx.user.name}. You must be an admin to add new users to Redmine.")
                    return
                # no user exists for that login
                modal = NewUserModal(self.redmine, title="Create new user")
                await ctx.send_modal(modal)
            # reindex users after changes
            self.redmine.user_mgr.reindex_users()


    @scn.command()
    async def sync(self, ctx:discord.ApplicationContext):
        """syncronize an existing ticket thread with redmine"""
        if isinstance(ctx.channel, discord.Thread):
            thread = ctx.channel
            ticket = await self.bot.sync_thread(thread)
            if ticket:
                await ctx.respond(f"SYNC ticket {ticket.id} to thread: {thread.name} complete")
            else:
                # double-check thread name
                ticket_id = self.bot.parse_thread_title(thread.name)
                if ticket_id:
                    await ctx.respond(f"No ticket (#{ticket_id}) found for thread named: {thread.name}")
                else:
                    # create new ticket
                    subject = thread.name
                    user = self.redmine.user_mgr.find(ctx.user.name)
                    message = Message(user.login, subject) # user.mail?
                    message.note = subject + "\n\nCreated by netbot by syncing Discord thread with same name."
                    ticket = self.redmine.ticket_mgr.create(user, message)
                    # set tracker
                    # TODO: search up all parents in hierarchy?
                    tracker = self.bot.lookup_tracker(thread.parent.name)
                    if tracker:
                        log.debug(f"found {thread.parent.name} => {tracker}")
                        params = {
                            "tracker_id": str(tracker.id),
                            "notes": f"Setting tracker based on channel name: {thread.parent.name}"
                        }
                        self.redmine.ticket_mgr.update(ticket.id, params, user.login)
                    else:
                        log.debug(f"not tracker for {thread.parent.name}")

                    # rename thread
                    await thread.edit(name=f"Ticket #{ticket.id}: {ticket.subject}")

                    # sync the thread
                    ticket = await self.bot.sync_thread(thread) # refesh the ticket
                    await ctx.respond(self.bot.formatter.format_ticket(ticket))

                #OLD await ctx.respond(f"Cannot find ticket# in thread name: {ctx.channel.name}") # error
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
            self.redmine.user_mgr.join_team(user, teamname)
            await ctx.respond(f"**{discord_name}** has joined *{teamname}*")


    @scn.command(description="leave the specified team")
    async def leave(self, ctx:discord.ApplicationContext, teamname:str, member: discord.Member=None):
        discord_name = ctx.user.name # by default, assume current user
        if member:
            log.info(f"Overriding current user={ctx.user.name} with member={member.name}")
            discord_name = member.name
        user = self.redmine.user_mgr.find(discord_name)

        if user:
            self.redmine.user_mgr.leave_team(user, teamname)
            await ctx.respond(f"**{discord_name}** has left *{teamname}*")
        else:
            await ctx.respond(f"Unknown Discord user: {discord_name}.")


    @scn.command(description="list teams and members")
    async def teams(self, ctx:discord.ApplicationContext, teamname:str=None):
        # list all teams, with members

        if teamname:
            team = self.redmine.get_team(teamname)
            if team:
                await ctx.respond(self.format_team(team))
            else:
                await ctx.respond(f"Unknown team name: {teamname}") # error
        else:
            # all teams
            teams = self.redmine.user_mgr.cache.get_teams()
            buff = ""
            for team in teams:
                buff += self.format_team(team)
            await ctx.respond(buff[:2000]) # truncate!


    #@scn.command()
    #async def intake(self, ctx:discord.ApplicationContext):
    #    """perform intake"""
    #    # check team? admin?, provide reasonable error msg.
    #    await ctx.respond("INTAKE #{ticket.id}", view=IntakeView(self.bot))


    @scn.command(description="list all open epics")
    async def epics(self, ctx:discord.ApplicationContext):
        """List all the epics, grouped by tracker"""
        # get the epics.
        epics = self.redmine.ticket_mgr.get_epics()
        # format the epics and respond
        msg = self.bot.formatter.format_epics(epics)
        await ctx.respond(msg)

    @scn.command(description="list blocked email")
    async def blocked(self, ctx:discord.ApplicationContext):
        team = self.redmine.get_team(BLOCKED_TEAM_NAME)
        if team:
            await ctx.respond(self.format_team(team))
        else:
            await ctx.respond(f"Expected team {BLOCKED_TEAM_NAME} not configured") # error


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
        log.debug(f"### unblocking {username}")
        user = self.redmine.user_mgr.find(username)
        if user:
            self.redmine.user_mgr.unblock(user)
            await ctx.respond(f"Unblocked user: {user.login}")
        else:
            log.debug("trying to unblock unknown user '{username}', ignoring")
            await ctx.respond(f"Unknown user: {username}")


    @scn.command(name="force-notify", description="Force ticket notifications")
    async def force_notify(self, ctx: discord.ApplicationContext):
        log.debug(ctx)
        await self.bot.notify_expiring_tickets()


    ## FIXME move to DiscordFormatter

    async def print_team(self, ctx, team):
        msg = f"> **{team.name}**\n"
        for user_rec in team.users:
            #user = self.redmine.get_user(user_rec.id)
            #discord_user = user.custom_fields[0].value or ""  # FIXME cf_* lookup
            msg += f"{user_rec.name}, "
            #msg += f"[{user.id}] **{user_rec.name}** {user.login} {user.mail} {user.custom_fields[0].value}\n"
        msg = msg[:-2] + '\n\n'
        await ctx.channel.send(msg)


    def format_team(self, team) -> str:
        # single line format: teamname: member1, member2
        skip_teams = ["blocked", "users"]

        if team and team.name not in skip_teams:
            return f"**{team.name}**: {', '.join([user.name for user in team.users])}\n"
        else:
            return ""
