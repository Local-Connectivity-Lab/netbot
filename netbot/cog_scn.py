#!/usr/bin/env python3
"""Cog to manage SCN-related functions"""
import logging

import discord

from discord.commands import option, SlashCommandGroup
from discord.ext import commands
from discord.utils import basic_autocomplete

from redmine.model import Message, User
from redmine.redmine import Client, BLOCKED_TEAM_NAME

from netbot.netbot import NetBot, default_ticket

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
    def __init__(self, redmine: Client, login: str, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.redmine = redmine
        self.login = login
        self.add_item(discord.ui.InputText(label="First Name"))
        self.add_item(discord.ui.InputText(label="Last Name"))
        self.add_item(discord.ui.InputText(label="Email"))


    async def callback(self, interaction: discord.Interaction):
        email = self.children[2].value
        first = self.children[0].value
        last = self.children[1].value

        log.debug(f"register user callback: email={email}, first={first}, last={last}")

        user = self.redmine.user_mgr.register(self.login, email, first, last)
        if user is None:
            log.error(f"Unable to create user for {self.login}, {first} {last}, {email}")
            await interaction.response.send_message(f"Unable to create user for {self.login}")
            return

        # create the mapping so it the discord user can be found
        self.redmine.user_mgr.create_discord_mapping(user, interaction.user.id, interaction.user.name)
        log.debug(f"mapped discord new user: {interaction.user.name} -> {user.login}")

        embed = discord.Embed(title="Registered User")
        embed.add_field(name="Login", value=self.login)
        embed.add_field(name="Name", value=f"{first} {last}")
        embed.add_field(name="Email", value=email)
        await interaction.response.send_message(embeds=[embed])


class ApproveButton(discord.ui.Button):
    """Discord button to approve specific users"""
    def __init__(self, bot_: discord.Bot, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.bot = bot_


    # TODO Move to user_mgr?
    def find_registered_user(self, discord_name:str) -> User:
        """Search registered users for a matching discord ID"""
        for user in self.bot.redmine.user_mgr.get_registered():
            if user.discord_id == discord_name:
                return user
        return None


    async def callback(self, interaction: discord.Interaction):
        name = self.label

        user = self.find_registered_user(name)
        if user:
            self.bot.redmine.user_mgr.approve(user)
            # assign default groups?
            await interaction.response.send_message(f"Approved registered user: @{name} {user.login} {user.name}")
        else:
            await interaction.response.send_message(f"User not found: {name}")


class ApproveUserView(discord.ui.View):
    """Approve registered users with Discord controls"""
    def __init__(self, bot_: discord.Bot, users: list[User]) -> None:
        self.bot = bot_
        super().__init__()

        # Add buttons by rows
        for user in users:
            self.add_item(ApproveButton(self.bot, label=user.discord))


    async def button_callback(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.send_message(f"ApproveUserView: {button} {interaction}")


    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"ApproveUserView: {interaction}")


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
        self.formatter = bot.formatter
        self.redmine: Client = bot.redmine

    # see https://github.com/Pycord-Development/pycord/blob/master/examples/app_commands/slash_cog_groups.py

    scn = SlashCommandGroup("scn",  "SCN admin commands")


    def is_admin(self, user: discord.Member) -> bool:
        """Check if the given Discord memeber is in a authorized role"""
        # search user for "auth" role
        for role in user.roles:
            if "auth" == role.name: ## FIXME
                return True

        # auth role not found
        return False


    # FIXME rename to "register"?
    @scn.command(description="Add a Discord user to redmine")
    @option("ticket_id", description="ticket ID", autocomplete=basic_autocomplete(default_ticket))
    @option("member", description="Discord member collaborating with ticket", optional=True)
    async def add(self, ctx:discord.ApplicationContext, redmine_login:str, member:discord.Member=None):
        """add a Discord user to the Redmine ticketing integration"""
        discord_id = ctx.user # by default, assume current user
        if member:
            log.info(f"Overriding current user={ctx.user.name} with member={member.name}")
            discord_id = member

        user = self.redmine.user_mgr.find(discord_id.name)
        if user:
            # check the
            id_from_user = user.discord_id
            if id_from_user.id > 0:
                # a valid
                await ctx.respond(f"Discord user: {discord_id} is fully configured as redmine user: {user.login}")
            else:
                # need to update
                self.redmine.user_mgr.create_discord_mapping(user, discord_id.id, discord_id.name)
                await ctx.respond(f"Discord user: {discord_id.id},{discord_id.name} has been paired with redmine user: {redmine_login}")
        else:
            user = self.redmine.user_mgr.find(redmine_login)
            if user and self.is_admin(ctx.user):
                self.redmine.user_mgr.create_discord_mapping(user, discord_id.id, discord_id.name)
                await ctx.respond(f"Discord user: {discord_id.name} has been paired with redmine user: {redmine_login}")
            else:
                # case: unknown redmine_login -> new user request: register new user
                modal = NewUserModal(self.redmine, redmine_login, title="Register new user")
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
                ticket_id = NetBot.parse_thread_title(thread.name)
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
                    tracker = self.bot.redmine.ticket_mgr.get_tracker(thread.parent.name)
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
        """reindex the all cached information"""
        self.redmine.reindex()
        #self.bot.reindex() FIXME, once roles are working
        await ctx.respond("Rebuilt redmine indices.")


    # REMOVE - handled by discord roles
    # @scn.command(description="join the specified team")
    # async def join(self, ctx:discord.ApplicationContext, teamname:str , member: discord.Member=None):
    #     discord_name = ctx.user.name # by default, assume current user
    #     if member:
    #         log.info(f"Overriding current user={ctx.user.name} with member={member.name}")
    #         discord_name = member.name

    #     user = self.redmine.user_mgr.find(discord_name)
    #     if user is None:
    #         await ctx.respond(f"Unknown user, no Discord mapping: {discord_name}")
    #     elif self.redmine.user_mgr.get_team_by_name(teamname) is None:
    #         await ctx.respond(f"Unknown team name: {teamname}")
    #     else:
    #         self.redmine.user_mgr.join_team(user, teamname)
    #         await ctx.respond(f"**{discord_name}** has joined *{teamname}*")

    # REMOVE - handled by discord roles
    # @scn.command(description="leave the specified team")
    # async def leave(self, ctx:discord.ApplicationContext, teamname:str, member: discord.Member=None):
    #     discord_name = ctx.user.name # by default, assume current user
    #     if member:
    #         log.info(f"Overriding current user={ctx.user.name} with member={member.name}")
    #         discord_name = member.name
    #     user = self.redmine.user_mgr.find(discord_name)

    #     if user:
    #         self.redmine.user_mgr.leave_team(user, teamname)
    #         await ctx.respond(f"**{discord_name}** has left *{teamname}*")
    #     else:
    #         await ctx.respond(f"Unknown Discord user: {discord_name}.")


    def find_role(self, ctx:discord.ApplicationContext, rolename:str) -> discord.Role | None:
        for role in ctx.guild.roles:
            if role.name == rolename:
                return role


    @scn.command(description="list teams and members")
    async def teams(self, ctx:discord.ApplicationContext, teamname:str=None):
        # list teams, with members
        if teamname:
            team = self.find_role(ctx, teamname)
            if team:
                await ctx.respond(self.formatter.format_team(team))
                return
            else:
                all_teams = [team.name for team in ctx.guild.roles]
                await ctx.respond(f"Unknown team name: {teamname}\nTeams: {all_teams}") # error
        else:
            # all teams
            #teams = self.redmine.user_mgr.cache.get_teams()
            teams = "\n- ".join([team.name for team in ctx.guild.roles])
            #buff = ""
            #for team in teams:
            #    buff += self.formatter.format_team(team)
            await ctx.respond("Available teams:\n-" + teams)


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
        await ctx.respond(embeds=self.bot.formatter.epics_embed(ctx, epics))

    @scn.command(description="list blocked email")
    async def blocked(self, ctx:discord.ApplicationContext):
        team = self.redmine.user_mgr.cache.get_team_by_name(BLOCKED_TEAM_NAME)
        if team:
            await ctx.respond(self.formatter.format_team(team))
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
            for ticket in self.redmine.ticket_mgr.get_by(user):
                self.redmine.ticket_mgr.reject_ticket(ticket.id)
            await ctx.respond(f"Blocked user: {user.login} and rejected all created tickets")
        else:
            log.debug("trying to block unknown user '{username}', ignoring")
            await ctx.respond(f"Unknown user: {username}")


    @scn.command(description="unblock specific a email address")
    async def unblock(self, ctx:discord.ApplicationContext, username:str):
        log.debug(f"Unblocking {username}")
        user = self.redmine.user_mgr.find(username)
        if user:
            self.redmine.user_mgr.unblock(user)
            await ctx.respond(f"Unblocked user: {user.login}")
        else:
            log.debug("trying to unblock unknown user '{username}', ignoring")
            await ctx.respond(f"Unknown user: {username}")


    @scn.command(name="force-notify", description="Force ticket notifications")
    async def force_remind(self, ctx:discord.ApplicationContext):
        await ctx.respond("Sending reminders for dusty tickets....")
        await self.bot.remind_dusty_tickets()


    @scn.command(name="force-recycle", description="Force ticket notifications")
    async def force_recycle(self, ctx:discord.ApplicationContext):
        await ctx.respond("Recycling dusty, old tickets....")
        await self.bot.recycle_tickets()


    @scn.command(description="List and approve registered new users")
    async def approve(self, ctx:discord.ApplicationContext):
        if self.is_admin(ctx.user):
            # get the registered users
            users = self.bot.redmine.user_mgr.get_registered()
            if len(users) > 0:
                await ctx.respond("Approve Registered Users", view=ApproveUserView(self.bot, users))
            else:
                await ctx.respond("No pending registered users.")

        else:
            await ctx.respond("Must be authorized admin to approve Redmine users.")
