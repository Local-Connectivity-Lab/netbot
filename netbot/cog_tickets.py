#!/usr/bin/env python3

"""encapsulate Discord ticket functions"""

import logging
import datetime as dt
import math

import discord
from discord import ScheduledEvent, OptionChoice
from discord.commands import option, SlashCommandGroup
from discord.ext import commands
from discord.enums import InputTextStyle
from discord.ui.item import Item, V
import discord.utils
from discord.ext import tasks


import dateparser

from redmine.model import Message, Ticket
from redmine import synctime
from redmine.redmine import Client
from netbot.netbot import NetBot, TEAM_MAPPING, CHANNEL_MAPPING, default_ticket
from . import config

# FIXME
# try for empty responses.
# await interaction.response.defer()



log = logging.getLogger(__name__)

# cached data for fast option-choices popup menus
_programs: list[OptionChoice] = [
    OptionChoice("Community Networks (General)", value=15),
    OptionChoice("Grant: Seattle TMF 2023-4", value=16),
    OptionChoice("Grant: Benton Fellowship 2024", value=17),
]
#_bot = None

def setup(bot:NetBot):
    #_programs = get_program_options()
    #log.warning(f"initilized programs: {_programs}")
    bot.add_cog(TicketsCog(bot))

    log.info("initialized tickets cog")


def get_program_options() -> list[OptionChoice]:
    programs = []
    for k, v in config.programs.items():
        programs.append(OptionChoice(k, value=v))
    return programs


def get_trackers(ctx: discord.AutocompleteContext):
    """Returns a list of trackers that begin with the characters entered so far."""
    trackers = ctx.bot.redmine.ticket_mgr.get_trackers() # this is expected to be cached
    # .lower() is used to make the autocomplete case-insensitive
    return [tracker for tracker in trackers.keys() if tracker.lower().startswith(ctx.value.lower())]


def get_priorities(ctx: discord.AutocompleteContext):
    """Returns a list of priorities that begin with the characters entered so far."""
    priorities = ctx.bot.redmine.ticket_mgr.get_priorities() # this is expected to be cached
    # .lower() is used to make the autocomplete case-insensitive
    return [priority for priority in priorities.keys() if priority.lower().startswith(ctx.value.lower())]


def get_statuses(ctx: discord.AutocompleteContext):
    """Returns a list of priorities that begin with the characters entered so far."""
    statuses = ["New", "In Progress", "Standing", "Resolved", "Backburner"]
    # .lower() is used to make the autocomplete case-insensitive
    return [status for status in statuses if status.lower().startswith(ctx.value.lower())]


class PrioritySelect(discord.ui.Select):
    """Popup menu to select ticket priority"""
    def __init__(self, bot_: discord.Bot):
        # For example, you can use self.bot to retrieve a user or perform other functions in the callback.
        # Alternatively you can use Interaction.client, so you don't need to pass the bot instance.
        self.bot = bot_

        # Get the possible priorities
        options = []
        for priority in self.bot.redmine.ticket_mgr.get_priorities():
            options.append(discord.SelectOption(label=priority['name'], default=priority['is_default']))

        # The placeholder is what will be shown when no option is selected.
        # The min and max values indicate we can only pick one of the three options.
        # The options parameter, contents shown above, define the dropdown options.
        super().__init__(
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        # Use the interaction object to send a response message containing
        # the user's favourite colour or choice. The self object refers to the
        # Select object, and the values attribute gets a list of the user's
        # selected options. We only want the first one.
        log.info(f"{interaction.user} {interaction.data}")
        await interaction.response.send_message(
            f"PrioritySelect.callback() - selected priority {self.values[0]}"
        )


class TrackerSelect(discord.ui.Select):
    """Popup menu to select ticket tracker"""
    def __init__(self, bot_: discord.Bot):
        # For example, you can use self.bot to retrieve a user or perform other functions in the callback.
        # Alternatively you can use Interaction.client, so you don't need to pass the bot instance.
        self.bot = bot_

        # Get the possible trackers
        options = []
        for tracker in self.bot.redmine.ticket_mgr.get_trackers():
            options.append(discord.SelectOption(label=tracker['name']))

        # The placeholder is what will be shown when no option is selected.
        # The min and max values indicate we can only pick one of the three options.
        # The options parameter, contents shown above, define the dropdown options.
        super().__init__(
            placeholder="Select tracker...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        # Use the interaction object to send a response message containing
        # the user's favourite colour or choice. The self object refers to the
        # Select object, and the values attribute gets a list of the user's
        # selected options. We only want the first one.
        log.info(f"{interaction.user} {interaction.data}")
        await interaction.response.send_message(
            f"TrackerSelect.callback() - selected tracker {self.values[0]}"
        )


class ProgramSelect(discord.ui.Select):
    """Popup menu to select ticket tracker"""
    def __init__(self, bot: discord.Bot):
        self.bot = bot

        # Get the possible trackers
        options = []
        for name, value in self.bot.redmine.ticket_mgr.get_programs().items():
            options.append(discord.SelectOption(label=name))

        # The placeholder is what will be shown when no option is selected.
        # The min and max values indicate we can only pick one of the three options.
        # The options parameter, contents shown above, define the dropdown options.
        super().__init__(
            placeholder="Select program...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        # Use the interaction object to send a response message containing
        # the user's favourite colour or choice. The self object refers to the
        # Select object, and the values attribute gets a list of the user's
        # selected options. We only want the first one.
        log.info(f"PROGRAM SELECT {interaction.user} {interaction.data}")
        await interaction.response.send_message(f"ProgramSelect.callback() - selected program {self.values[0]}")

class StatusSelect(discord.ui.Select):
    """Popup menu to select ticket status"""
    def __init__(self, bot: discord.Bot):
        self.bot = bot

        super().__init__(
            placeholder="Select ticket status...",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption("New"),
                discord.SelectOption("In Progress"),
                discord.SelectOption("Standing"),
                discord.SelectOption("Resolved"),
                discord.SelectOption("Backburner"),
            ],
        )

    async def callback(self, interaction: discord.Interaction):
        log.info(f"{interaction.user} {interaction.data}")
        await interaction.response.send_message(
            f"TrackerSelect.callback() - selected tracker {self.values[0]}"
        )


class SubjectEdit(discord.ui.InputText, Item[V]):
    """Popup menu to select ticket tracker"""
    def __init__(self, bot_: discord.Bot, ticket: Ticket):
        # For example, you can use self.bot to retrieve a user or perform other functions in the callback.
        # Alternatively you can use Interaction.client, so you don't need to pass the bot instance.
        self.bot = bot_
        self.ticket = ticket

        # Get the possible trackers
        options = []
        for tracker in self.bot.redmine.ticket_mgr.get_trackers():
            options.append(discord.SelectOption(label=tracker['name']))

        # The placeholder is what will be shown when no option is selected.
        # The min and max values indicate we can only pick one of the three options.
        # The options parameter, contents shown above, define the dropdown options.
        super().__init__(
            placeholder=self.ticket.subject,
            label="Subject"
        )

    async def callback(self, interaction: discord.Interaction):
        # Use the interaction object to send a response message containing
        # the user's favourite colour or choice. The self object refers to the
        # Select object, and the values attribute gets a list of the user's
        # selected options. We only want the first one.
        log.info(f"{interaction.user} {interaction.data}")
        await interaction.response.send_message(
            f"SubjectEdit.callback() - selected tracker {self.value}"
        )


class EditSubjectAndDescModal(discord.ui.Modal):
    """modal dialog to edit the ticket subject and description"""
    def __init__(self, redmine: Client, ticket: Ticket, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.redmine = redmine
        self.ticket = ticket
        self.add_item(discord.ui.InputText(label="Subject"))
        self.add_item(discord.ui.InputText(label="Description", style=InputTextStyle.paragraph))


    async def callback(self, interaction: discord.Interaction):
        subject = self.children[0].value
        description = self.children[1].value

        log.debug(f"callback: {subject}, {description}")

        embed = discord.Embed(title="Updated ticket")
        embed.add_field(name="Subject", value=subject)
        embed.add_field(name="Description", value=description)

        #user = self.redmine.user_mgr.create(email, first, last)
        # TODO Update subject and description in redmine

        #if user is None:
        #    log.error(f"Unable to create user from {first}, {last}, {email}, {interaction.user.name}")
        #else:
        #    self.redmine.user_mgr.create_discord_mapping(user, interaction.user.name)
        await interaction.response.send_message(embeds=[embed])


# class EditDescriptionModal(discord.ui.Modal):
#     """modal dialog to edit the ticket subject and description"""
#     def __init__(self, redmine: Client, ticket: Ticket, *args, **kwargs) -> None:
#         super().__init__(*args, **kwargs)
#         # Note: redmine must be available in callback, as the bot is not
#         # available thru the Interaction.
#         self.redmine = redmine
#         self.ticket_id = ticket.id
#         self.add_item(discord.ui.InputText(label="Description",
#                                            value=ticket.description,
#                                            style=InputTextStyle.paragraph))


#     async def callback(self, interaction: discord.Interaction):
#         description = self.children[0].value
#         log.debug(f"callback: {description}")

#         user = self.redmine.user_mgr.find_discord_user(interaction.user.name)

#         fields = {
#             "description": description,
#         }
#         ticket = self.redmine.ticket_mgr.update(self.ticket_id, fields, user.login)

#         embed = discord.Embed(title=f"Updated ticket {ticket.id} description")
#         embed.add_field(name="Description", value=ticket.description)

#         await interaction.response.send_message(embeds=[embed])

class EditDescriptionModal(discord.ui.Modal):
    """modal dialog to edit the ticket subject and description"""
    def __init__(self, redmine: Client, ticket: Ticket, bot: NetBot, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.redmine = redmine
        self.ticket_id = ticket.id
        self.bot = bot
        self.add_item(discord.ui.InputText(
            label="Description",
            value=ticket.get_custom_field("unredacted") or ticket.description,
            style=InputTextStyle.paragraph
        ))

    async def callback(self, interaction: discord.Interaction):
        from redaction_queue import RedactionQueue

        description = self.children[0].value
        log.debug(f"Edit callback for ticket #{self.ticket_id}")

        queue = RedactionQueue()

        # Check if ticket is locked
        # if queue.is_locked(self.ticket_id):
        #     await interaction.response.send_message(
        #         "Can't edit right now. Please wait and try again in a few minutes.",
        #         ephemeral=True
        #     )
        #     return

        # Get user info
        user = self.redmine.user_mgr.find_discord_user(interaction.user.name)
        user_info = {
            "name": user.name if user else interaction.user.name,
            "login": user.login if user else None,
            "discord_id": interaction.user.id
        }

        # Add to queue
        job_id = queue.add_edit_job(self.ticket_id, description, user_info)

        await interaction.response.send_message(
            f"Your edit has been queued for redaction.\n"
            f"This will take approximately 15-20 minutes.\n\n"
            f"Ticket #{self.ticket_id} is locked during this process.",
            ephemeral=True
        )

        log.info(f"Queued edit job {job_id} for ticket #{self.ticket_id}")


# distinct from above. takes app-context
def default_term(ctx: discord.ApplicationContext) -> str:
    # examine the thread
    ch_name = ctx.channel.name
    ticket_id = NetBot.parse_thread_title(ch_name)
    if ticket_id:
        return str(ticket_id)
    elif ch_name in TEAM_MAPPING:
        return TEAM_MAPPING[ch_name]
    elif ch_name in CHANNEL_MAPPING:
        return CHANNEL_MAPPING[ch_name]


class PrevButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="◀ Prev", style=discord.ButtonStyle.secondary)

    async def callback(self, interaction: discord.Interaction):
        view: StatusView = self.view
        view.page = max(0, view.page - 1)
        view.refresh_buttons()
        embed = view.bot.formatter.status_embed(
            view.title, view.buckets, view.page, view.total_pages, view.truncated
        )
        await interaction.response.edit_message(embed=embed, view=view)


class NextButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Next ▶", style=discord.ButtonStyle.secondary)

    async def callback(self, interaction: discord.Interaction):
        view: StatusView = self.view
        view.page = min(view.total_pages - 1, view.page + 1)
        view.refresh_buttons()
        embed = view.bot.formatter.status_embed(
            view.title, view.buckets, view.page, view.total_pages, view.truncated
        )
        await interaction.response.edit_message(embed=embed, view=view)


class StatusView(discord.ui.View):
    """Paginating view for the /status digest embed."""

    TIMEOUT = 180  # seconds

    def __init__(self, bot, title: str, buckets: dict, truncated: bool = False):
        super().__init__(timeout=self.TIMEOUT)
        self.bot = bot
        self.title = title
        self.buckets = buckets
        self.truncated = truncated
        self.page = 0
        self.total_pages = max(1, math.ceil(len(buckets["sorted_tickets"]) / 5))

        self.prev_btn = PrevButton()
        self.next_btn = NextButton()
        self.add_item(self.prev_btn)
        self.add_item(self.next_btn)
        self.refresh_buttons()

    def refresh_buttons(self):
        self.prev_btn.disabled = (self.page == 0)
        self.next_btn.disabled = (self.page >= self.total_pages - 1)

    async def on_timeout(self):
        self.prev_btn.disabled = True
        self.next_btn.disabled = True
        self.stop()


class TicketsCog(commands.Cog):
    """encapsulate Discord ticket functions"""
    def __init__(self, bot:NetBot):
        self.bot:NetBot = bot
        self.redmine: Client = bot.redmine

    # see https://github.com/Pycord-Development/pycord/blob/master/examples/app_commands/slash_cog_groups.py
    ticket = SlashCommandGroup("ticket",  "ticket commands")


    @commands.Cog.listener()
    async def on_ready(self):
        # start the tasks running
        self.poll_new_tickets.start()
        log.info("Initialized ticket polling")


    # figure out what the term refers to
    # could be ticket#, team name, user name or search term
    def resolve_query_term(self, term) -> list[Ticket]:
        log.debug(f"QQQ>: {term}")
        # special cases: ticket num and team name
        try:
            int_id = int(term)
            ticket = self.redmine.ticket_mgr.get(int_id, include="children") # get the children
            if ticket:
                log.debug(f"QQQ<: {ticket}")
                return [ticket]
        except ValueError:
            # ignore, not a ticket number
            pass

        # not a numeric id, check for known user or group
        user_team = self.redmine.user_mgr.find(term)
        if user_team:
            log.debug(f"{term} -> Team-or-user:{user_team}")
            result = self.redmine.ticket_mgr.tickets_for_team(user_team) # owner = team name assigned_to_id
            if result and len(result) > 0:
                return result
            # note: fall thru for empty result from team query.

        if term in CHANNEL_MAPPING:
            tracker = self.bot.redmine.ticket_mgr.get_tracker(CHANNEL_MAPPING[term])
            if tracker:
                result = self.redmine.ticket_mgr.tickets(tracker_id=tracker.id)
                log.debug(f"QQQ<: {result}")
                if result and len(result) > 0:
                    return result
            # note: fall thru for empty result from team query.

        # assume a search term
        log.debug(f"QUERY {term}")
        return self.redmine.ticket_mgr.search(term)


    @ticket.command(description="Query tickets")
    @option(name="term",
            description="Query can include ticket ID, owner, team or any term used for a text match.",
            default="")
    async def query(self, ctx: discord.ApplicationContext, term:str = ""):
        """List tickets for you, or filtered by parameter"""
        # different options: none, me (default), [group-name], intake, tracker name
        # buid index for trackers, groups
        # add groups to users.

        # lookup the user
        user = self.redmine.user_mgr.find(ctx.user.name)
        if not user:
            log.info(f"Unknown user name: {ctx.user.name}")
            # TODO make this a standard error.
            await ctx.respond(f"Discord member **{ctx.user.name}** is not provisioned in redmine. Use `/scn add [redmine-user]` to provision.")
            return

        log.debug(f"found user mapping for {ctx.user.name}: {user}")

        if term == "":
            # empty param, try to derive from channel name
            term = default_term(ctx)
            if term is None:
                # still none, default to...
                term = "me"

        if term == "me":
            results = self.redmine.ticket_mgr.my_tickets(user.login)
        else:
            results = self.resolve_query_term(term)

        if results and len(results) > 0:
            await self.bot.formatter.print_tickets(f"{term}", results, ctx)
        else:
            await ctx.respond(f"Zero results for: `{term}`")

    @ticket.command(description="Get ticket details")
    @option("ticket_id", description="ticket ID", autocomplete=discord.utils.basic_autocomplete(default_ticket))
    async def details(self, ctx: discord.ApplicationContext, ticket_id:int):
        """Update status on a ticket, using: unassign, resolve, progress"""
        #log.debug(f"found user mapping for {ctx.user.name}: {user}")
        ticket = self.redmine.ticket_mgr.get(ticket_id, include="children,watchers")

        if not ticket:
            await ctx.respond(f"Ticket {ticket_id} not found.", ephemeral=True)
            return

        if self.is_pii_admin(ctx.user):
            #pull original PII from unredacted CF and swap into description for UI DISPLAY ONLY
            unredacted_value = ticket.get_custom_field("unredacted")
            if unredacted_value:
                ticket.description = unredacted_value

        await ctx.respond(
            embed=self.bot.formatter.ticket_embed(ctx, ticket),
            ephemeral=True
        )


    @ticket.command(description="Collaborate on a ticket")
    @option("ticket_id", description="ticket ID", autocomplete=discord.utils.basic_autocomplete(default_ticket))
    @option("member", description="Discord member collaborating with ticket", optional=True)
    async def collaborate(self, ctx: discord.ApplicationContext, ticket_id:int, member:discord.Member=None):
        """Add yourself as a collaborator on a ticket"""
        # lookup the user
        user_name = ctx.user.name
        if member:
            if self.bot.is_admin(ctx.user):
                log.info(f"ADMIN: {ctx.user.name} invoked collaborate on behalf of {member.name}")
                user_name = member.name
        user = self.redmine.user_mgr.find(user_name)
        if not user:
            await ctx.respond(f"User {ctx.user.name} not mapped to redmine. Use `/scn add [redmine-user]` to create the mapping.")
            return

        ticket = self.redmine.ticket_mgr.get(ticket_id)
        if ticket:
            self.redmine.ticket_mgr.collaborate(ticket.id, user)
            updated = self.redmine.ticket_mgr.get(ticket.id, include="watchers")
            await self.bot.formatter.print_ticket(updated, ctx)
        else:
            await ctx.respond(f"Ticket {ticket_id} not found.") # print error


    @ticket.command(description="Unassign a ticket")
    @option("ticket_id", description="ticket ID", autocomplete=discord.utils.basic_autocomplete(default_ticket))
    async def unassign(self, ctx: discord.ApplicationContext, ticket_id:int):
        """Update status on a ticket, using: unassign, resolve, progress"""
        # lookup the user
        user = self.redmine.user_mgr.find(ctx.user.name)
        if not user:
            await ctx.respond(f"User {ctx.user.name} not mapped to redmine. Use `/scn add` to create the mapping.") # error
            return

        ticket = self.redmine.ticket_mgr.get(ticket_id)
        if ticket:
            self.redmine.ticket_mgr.unassign(ticket.id, user.login)
            await self.bot.formatter.print_ticket(self.redmine.ticket_mgr.get(ticket.id), ctx)
        else:
            await ctx.respond(f"Ticket {ticket_id} not found.") # print error


    @ticket.command(description="Resolve a ticket")
    @option("ticket_id", description="ticket ID", autocomplete=discord.utils.basic_autocomplete(default_ticket))
    async def resolve(self, ctx: discord.ApplicationContext, ticket_id:int):
        """Update status on a ticket, using: unassign, resolve, progress"""
        # lookup the user
        user = self.redmine.user_mgr.find(ctx.user.name)
        if not user:
            await ctx.respond(f"User {ctx.user.name} not mapped to redmine. Use `/scn add` to create the mapping.") # error
            return

        ticket = self.redmine.ticket_mgr.get(ticket_id)
        if ticket:
            updated = self.redmine.ticket_mgr.resolve(ticket_id, user.login)
            ticket_link = self.bot.formatter.redmine_link(ticket)
            await ctx.respond(
                f"Updated {ticket_link}, status: {ticket.status} -> {updated.status}",
                embed=self.bot.formatter.ticket_embed(ctx, updated))
        else:
            await ctx.respond(f"Ticket {ticket_id} not found.") # print error


    @ticket.command(description="Mark a ticket in-progress")
    @option("ticket_id", description="ticket ID", autocomplete=discord.utils.basic_autocomplete(default_ticket))
    @option("member", description="Discord member taking ownership", optional=True)
    async def progress(self, ctx: discord.ApplicationContext, ticket_id:int, member:discord.Member=None):
        """Update status on a ticket, using: progress"""
        # lookup the user
        user_name = ctx.user.name
        if member:
            if self.bot.is_admin(ctx.user):
                log.info(f"ADMIN: {ctx.user.name} invoked progress on behalf of {member.name}")
                user_name = member.name
        user = self.redmine.user_mgr.find(user_name)
        if not user:
            await ctx.respond(f"User {ctx.user.name} not mapped to redmine. Use `/scn add [redmine-user]` to create the mapping.")
            return

        ticket = self.redmine.ticket_mgr.get(ticket_id)
        if ticket:
            updated = self.redmine.ticket_mgr.progress_ticket(ticket_id, user.login)
            ticket_link = self.bot.formatter.redmine_link(ticket)
            await ctx.respond(
                f"Updated {ticket_link}, owner: {updated.assigned}, status: {updated.status}",
                embed=self.bot.formatter.ticket_embed(ctx, updated))
        else:
            await ctx.respond(f"Ticket {ticket_id} not found.") # print error


    @ticket.command(description="Assign a ticket")
    @option("ticket_id", description="ticket ID", autocomplete=discord.utils.basic_autocomplete(default_ticket))
    @option("member", description="Discord member taking ownership", optional=True)
    async def assign(self, ctx: discord.ApplicationContext, ticket_id:int, member:discord.Member=None):
        # lookup the user
        user_name = ctx.user.name
        if member:
            if self.bot.is_admin(ctx.user):
                log.info(f"ADMIN: {ctx.user.name} invoked assign on behalf of {member.name}")
                user_name = member.name
        user = self.redmine.user_mgr.find(user_name)
        if not user:
            await ctx.respond(f"User {ctx.user.name} not mapped to redmine. Use `/scn add [redmine-user]` to create the mapping.")
            return

        ticket = self.redmine.ticket_mgr.get(ticket_id)
        if ticket:
            self.redmine.ticket_mgr.assign_ticket(ticket_id, user)
            await self.bot.formatter.print_ticket(self.redmine.ticket_mgr.get(ticket_id), ctx)
        else:
            await ctx.respond(f"Ticket {ticket_id} not found.") # print error


    # command disabled
    #@ticket.command(name="edit", description="Edit a ticket")
    #@option("ticket_id", description="ticket ID")
    # async def edit(self, ctx:discord.ApplicationContext, ticket_id: int):
    #     """Edit the fields of a ticket"""
    #     # check team? admin?, provide reasonable error msg.
    #     ticket = self.redmine.ticket_mgr.get(ticket_id)
    #     await ctx.respond(f"EDIT #{ticket.id}", view=EditView(self.bot))


    async def create_thread(self, ticket:Ticket, channel):
        if isinstance(channel, discord.Thread):
            log.debug(f"creating thread in parent channel {channel.parent.name}, for {ticket}")
            thread = await self.create_ticket_thread(ticket, channel.parent)
        elif isinstance(channel, discord.TextChannel):
            log.debug(f"creating thread in channel {channel.name}, for {ticket}")
            thread = await self.create_ticket_thread(ticket, channel)
        else:
            log.warning(f"Unrecognized channel type: {type(channel)}, {channel}")

        return thread

    @ticket.command(name="new", description="Create a new ticket")
    @option("title", description="Title of the new SCN ticket")
    async def create_new_ticket(self, ctx: discord.ApplicationContext, title:str):
        user = self.redmine.user_mgr.find(ctx.user.name)
        if not user:
            await ctx.respond(f"User {ctx.user.name} not mapped to redmine. Use `/scn add` to create the mapping.") # error
            return

        channel_name = ctx.channel.name
        text = f"Created by Discord user {ctx.user.name} in channel {channel_name}"
        message = Message(from_addr=user.mail, subject=title, to=channel_name)
        message.set_note(text)

        ticket_id = NetBot.parse_thread_title(channel_name)
        log.debug(f">>> {channel_name} --> ticket: {ticket_id}")
        if ticket_id:
            # check if it's an epic
            epic = self.redmine.ticket_mgr.get(ticket_id)
            if epic and epic.priority.name == "EPIC":
                log.debug(f">>> {ticket_id} is an EPIC!")
                ticket = self.redmine.ticket_mgr.create(user, message, parent_issue_id=ticket_id)
                await self.thread(ctx, ticket.id)
                return

        # not in ticket thread, try tracker
        tracker = self.bot.tracker_for_channel(channel_name)
        team = self.bot.team_for_tracker(tracker)
        role = self.bot.get_role_by_name(team.name)
        if tracker:
            log.debug(f"creating ticket in {channel_name} for tracker={tracker}, owner={team}")
            ticket = self.redmine.ticket_mgr.create(user, message, tracker_id=tracker.id, assigned_to_id=team.id)
            # create new ticket thread
            thread = await self.create_thread(ticket, ctx.channel)
            # use to send notification for team/role
            ticket_link = self.bot.formatter.redmine_link(ticket)
            alert_msg = f"New ticket created: {ticket_link}"
            if role:
                await thread.send(self.bot.formatter.format_roles_alert([role.id], alert_msg))
            else:
                log.warning(f"unable to load role by team name: {team.name}")
            await ctx.respond(alert_msg, embed=self.bot.formatter.ticket_embed(ctx, ticket))
        else:
            log.error(f"no tracker for {channel_name}")
            await ctx.respond(f"ERROR: No tracker for {channel_name}.")


    @ticket.command(name="notify", description="Notify collaborators on a ticket")
    @option("message", description="Message to send with notification")
    async def notify(self, ctx: discord.ApplicationContext, message:str = ""):
        ticket_id = NetBot.parse_thread_title(ctx.channel.name)
        ticket = self.redmine.ticket_mgr.get(ticket_id, include="watchers") # inclde the option watchers/collaborators field
        if ticket:
            # * notify owner and collaborators of *notable* (not all) status changes of a ticket
            # * user @reference for notify
            # * notification placed in ticket-thread

            # owner and watchers
            discord_ids = self.bot.extract_ids_from_ticket(ticket)
            thread = self.bot.find_ticket_thread(ticket.id)
            if not thread:
                await ctx.respond(f"ERROR: No thread for ticket ID: {ticket_id}, assign a fall-back") ## TODO
                return
            if message == "":
                message = f"Ticket {ticket.id} is about will expire soon."
            await thread.send(self.bot.formatter.format_ticket_alert(ticket, discord_ids, message))
            await ctx.respond("Alert sent.")
        else:
            await ctx.respond(f"ERROR: Unkown ticket ID: {ticket_id}") ## TODO format error message


    @ticket.command(description="Thread a Redmine ticket in Discord")
    @option("ticket_id", description="ID of ticket to create thread for")
    async def thread(self, ctx: discord.ApplicationContext, ticket_id:int):
        ticket = self.redmine.ticket_mgr.get(ticket_id)
        if ticket:
            ticket_link = self.bot.formatter.redmine_link(ticket)

            # check if sync data exists for a different channel
            synced = ticket.get_sync_record()
            if synced and synced.channel_id != ctx.channel.id:
                thread = self.bot.get_channel(synced.channel_id)
                if thread:
                    url = thread.jump_url
                    await ctx.respond(f"Ticket {ticket_link} already synced with {url}")
                    return # stop processing
                else:
                    log.info(f"Ticket {ticket_id} synced with unknown thread ID {synced.channel_id}. Recovering.")
                    # delete the sync record
                    self.redmine.ticket_mgr.remove_sync_record(synced)
                    # fall thru to create thread and sync

            # create the thread...
            thread = await self.create_thread(ticket, ctx.channel)

            # update the discord flag on tickets, add a note with url of thread; thread.jump_url
            name = thread.name
            note = f"Created Discord thread: {name}: {thread.jump_url}"
            user = self.redmine.user_mgr.find_discord_user(ctx.user.name)
            self.redmine.ticket_mgr.enable_discord_sync(ticket.id, user, note)

            # ticket-614: add ticket link to thread response
            log.info('CTX5 %s', vars(ctx))
            await ctx.respond(f"Created new thread {thread.jump_url} for ticket {ticket_link}")
        else:
            await ctx.respond(f"ERROR: Unkown ticket ID: {ticket_id}")


    @ticket.command(name="tracker", description="Update the tracker of a ticket")
    @option("ticket_id", description="ID of ticket to update", autocomplete=discord.utils.basic_autocomplete(default_ticket))
    @option("tracker", description="Tracker to assign to ticket", autocomplete=get_trackers)
    async def tracker(self, ctx: discord.ApplicationContext, ticket_id:int, tracker:str):
        user = self.redmine.user_mgr.find_discord_user(ctx.user.name)
        ticket = self.redmine.ticket_mgr.get(ticket_id)
        if ticket:
            ticket_link = self.bot.formatter.redmine_link(ticket)

            # look up the tracker string
            tracker_rec = self.bot.redmine.ticket_mgr.get_tracker(tracker)
            fields = {
                "tracker_id": tracker_rec.id,
            }
            updated = self.bot.redmine.ticket_mgr.update(ticket_id, fields, user.login)

            await ctx.respond(
                f"Updated tracker of {ticket_link}: {ticket.tracker} -> {updated.tracker}",
                embed=self.bot.formatter.ticket_embed(ctx, updated))
        else:
            await ctx.respond(f"ERROR: Unkown ticket ID: {ticket_id}")


    @ticket.command(name="status", description="Update the status of a ticket")
    @option("ticket_id", description="ID of ticket to update", autocomplete=discord.utils.basic_autocomplete(default_ticket))
    @option("status", description="Status to assign to ticket", autocomplete=get_statuses)
    async def status(self, ctx: discord.ApplicationContext, ticket_id:int, status:str):
        user = self.redmine.user_mgr.find_discord_user(ctx.user.name)
        ticket = self.redmine.ticket_mgr.get(ticket_id)
        if ticket:
            ticket_link = self.bot.formatter.redmine_link(ticket)

            # look up the tracker string
            status_rec = self.bot.redmine.ticket_mgr.get_status(status)
            fields = {
                "status_id": status_rec.id,
            }
            updated = self.bot.redmine.ticket_mgr.update(ticket_id, fields, user.login)

            await ctx.respond(
                f"Updated tracker of {ticket_link}: {ticket.tracker} -> {updated.tracker}",
                embed=self.bot.formatter.ticket_embed(ctx, updated))
        else:
            await ctx.respond(f"ERROR: Unkown ticket ID: {ticket_id}")


    @ticket.command(name="priority", description="Update the priority of a ticket")
    @option("ticket_id", description="ID of ticket to update", autocomplete=discord.utils.basic_autocomplete(default_ticket))
    @option("priority", description="Priority to assign to ticket", autocomplete=get_priorities)
    async def priority(self, ctx: discord.ApplicationContext, ticket_id:int, priority:str):
        user = self.redmine.user_mgr.find_discord_user(ctx.user.name)
        ticket = self.redmine.ticket_mgr.get(ticket_id)
        if ticket:
            # look up the priority
            pri = self.bot.redmine.ticket_mgr.get_priority(priority)
            if pri is None:
                log.error(f"Unknown priority: {priority}")
                await ctx.respond(f"Unknown priority: {priority}")
                return

            fields = {
                "priority_id": pri.id,
            }
            updated = self.bot.redmine.ticket_mgr.update(ticket_id, fields, user.login)

            ticket_link = self.bot.formatter.redmine_link(ticket)
            await ctx.respond(
                f"Updated priority of {ticket_link}: {ticket.priority} -> {updated.priority}",
                embed=self.bot.formatter.ticket_embed(ctx, updated))
        else:
            await ctx.respond(f"ERROR: Unkown ticket ID: {ticket_id}")


    @ticket.command(name="subject", description="Update the subject of a ticket")
    @option("ticket_id", description="ID of ticket to update", autocomplete=discord.utils.basic_autocomplete(default_ticket))
    @option("subject", description="Updated subject")
    async def subject(self, ctx: discord.ApplicationContext, ticket_id:int, subject:str):
        user = self.redmine.user_mgr.find_discord_user(ctx.user.name)
        if not user:
            await ctx.respond(f"ERROR: Discord user without redmine config: {ctx.user.name}. Create with `/scn add`")
            return

        ticket = self.redmine.ticket_mgr.get(ticket_id)
        if not ticket:
            await ctx.respond(f"ERROR: Unkown ticket ID: {ticket_id}")
            return

        fields = {
            "subject": subject,
        }
        updated = self.bot.redmine.ticket_mgr.update(ticket_id, fields, user.login)

        ticket_link = self.bot.formatter.redmine_link(ticket)
        await ctx.respond(
            f"Updated subject of {ticket_link} to: {updated.subject}",
            embed=self.bot.formatter.ticket_embed(ctx, updated))


    async def find_event_for_ticket(self, ctx: discord.ApplicationContext, ticket_id:int) -> ScheduledEvent:
        title_prefix = f"Ticket #{ticket_id}"
        for event in await ctx.guild.fetch_scheduled_events():
            if event.name.startswith(title_prefix):
                return event


    @staticmethod
    def parse_human_date(date_str: str) -> dt.date:
        # should the parser be cached?
        return dateparser.parse(date_str, settings={
                'RETURN_AS_TIMEZONE_AWARE': True,
                'PREFER_DATES_FROM': 'future',
                'REQUIRE_PARTS': ['day', 'month', 'year']})


    @ticket.command(name="due", description="Set a due date for the ticket")
    @option("date", description="Due date, in a supported format: 2024-11-01, 11/1/24, next week , 2 months, in 5 days")
    async def due(self, ctx: discord.ApplicationContext, date:str):
        # automatiuc date conversion?
        # get the ticket ID from the thread:
        ticket_id = NetBot.parse_thread_title(ctx.channel.name)
        if ticket_id:
            # got a valid ticket, update it
            # standard date string, date format, etc.
            due_date = TicketsCog.parse_human_date(date)
            if due_date:
                # format in redmine-expected format
                # API design note: update interface calls for a string, but string must
                # in redmine-expected format.
                due_str = synctime.date_str(due_date)
                ticket = self.redmine.ticket_mgr.update(ticket_id, {"due_date": due_str})
                if ticket:
                    # valid ticket, create an event
                    # check for time, default to 9am if 0
                    #if due_date.hour == 0:
                    #    due_date.hour = 9 # DEFAULT "meeting" time, 9am local time (for the bot)

                    event_name = f"Ticket #{ticket.id} Due"

                    # check for existing event
                    existing = await self.find_event_for_ticket(ctx, ticket.id)
                    if existing:
                        await existing.edit(
                            start_time = due_date,
                            end_time = due_date + dt.timedelta(hours=1)) # DEFAULT "meeting" length, one hour)
                        log.info(f"Updated existing DUE event: {existing.name}")
                        await ctx.respond(f"Updated due date on {ticket_id} to {synctime.date_str(due_date)}")
                    else:
                        await ctx.respond(f"Updated due date on ticket #{ticket_id} to {synctime.date_str(due_date)}, scheduling event.")
                        event = await ctx.guild.create_scheduled_event(
                            name = event_name,
                            description = ticket.subject,
                            start_time = due_date,
                            end_time = due_date + dt.timedelta(hours=1), # DEFAULT "meeting" length, one hour
                            location = ctx.channel.name)
                        log.info(f"created event {event} for ticket={ticket.id}")
                        await ctx.send(f"Scheduled due event for ticket #{ticket_id} on {synctime.date_str(due_date)}.")
                else:
                    await ctx.respond(f"Problem updating ticket {ticket_id}, unknown ticket ID.")
            else:
                await ctx.respond(f"Invalid date value entered. Unable to parse `{date}`")
        else:
            # no ticket available.
            await ctx.respond("Command only valid in ticket thread. No ticket info found in this thread.")


    # @ticket.command(name="description", description="Edit the description of a ticket")
    # async def edit_description(self, ctx: discord.ApplicationContext):
    #     # pop the the edit description embed
    #     ticket_id = NetBot.parse_thread_title(ctx.channel.name)
    #     ticket = self.redmine.ticket_mgr.get(ticket_id)
    #     if ticket:
    #         modal = EditDescriptionModal(self.redmine, ticket, title=f"Editing ticket #{ticket.id}")
    #         await ctx.send_modal(modal)
    #     else:
    #         await ctx.respond(f"Cannot find ticket for {ctx.channel}")

    @ticket.command(name="description", description="Edit the description of a ticket")
    async def edit_description(self, ctx: discord.ApplicationContext):
        from redaction_queue import RedactionQueue

        # Check PII admin permission
        if not self.is_pii_admin(ctx.user):
            await ctx.respond(
                "You don't have permission to edit ticket descriptions.",
                ephemeral=True
            )
            return

        # Get ticket from thread name
        ticket_id = NetBot.parse_thread_title(ctx.channel.name)
        if not ticket_id:
            await ctx.respond(
                "This command only works in ticket threads.",
                ephemeral=True
            )
            return

        # Check if ticket is locked
        queue = RedactionQueue()
        if queue.is_locked(ticket_id):
            await ctx.respond(
                "Ticket is currently being redacted. Please wait and try again in a few moments.",
                ephemeral=True
            )
            return

        # Get ticket
        ticket = self.redmine.ticket_mgr.get(ticket_id)
        if not ticket:
            await ctx.respond(f"Cannot find ticket #{ticket_id}", ephemeral=True)
            return

        # Show edit modal
        modal = EditDescriptionModal(self.redmine, ticket, self.bot, title=f"Editing ticket #{ticket.id}")
        await ctx.send_modal(modal)


    @ticket.command(name="parent", description="Set a parent ticket for ")
    @option("parent_ticket", description="The ID of the parent ticket")
    async def parent(self, ctx: discord.ApplicationContext, parent_ticket:int):
        # /ticket parent 234 <- Get *this* ticket and set the parent to 234.

        # get ticket Id from thread
        ticket_id = NetBot.parse_thread_title(ctx.channel.name)
        if not ticket_id:
             # error - no ticket ID
            await ctx.respond("Command only valid in ticket thread. No ticket info found in this thread.")
            return

        # validate user
        user = self.redmine.user_mgr.find_discord_user(ctx.user.name)
        if not user:
            await ctx.respond(f"ERROR: Discord user without redmine config: {ctx.user.name}. Create with `/scn add`")
            return

        # check that parent_ticket is valid
        parent = self.redmine.ticket_mgr.get(parent_ticket)
        if not parent:
            await ctx.respond(f"ERROR: Unknow ticket #: {parent_ticket}")
            return

        # update the ticket
        params = {
            "parent_issue_id": parent_ticket,
        }
        updated = self.redmine.ticket_mgr.update(ticket_id, params, user.login)
        ticket_link = self.bot.formatter.redmine_link(updated)
        parent_link = self.bot.formatter.redmine_link(parent)
        await ctx.respond(
            f"Updated parent of {ticket_link} -> {parent_link}",
            embed=self.bot.formatter.ticket_embed(ctx, updated))


    @ticket.command(name="help", description="Display help about ticket management")
    async def help(self, ctx: discord.ApplicationContext):
        await ctx.respond(embed=self.bot.formatter.help_embed(ctx))


    @discord.slash_command(name="hours", description="Record time against a program")
    @option("hours", description="Hours worked on the program: `3.5`")
    @option("program_id", choices=get_program_options(), description="Select the program or grant", required=True)
    @option("note", description="Optional: Additional comments")
    async def recordTime(self, ctx: discord.ApplicationContext, hours: float, program_id: int, note: str = ""):
        redmine: Client = ctx.bot.redmine

        user = redmine.user_mgr.find(ctx.user.name)
        if not user:
            await ctx.respond(f"User {ctx.user.name} not mapped to redmine. Use `/scn add` to create the mapping.") # error
            return

        autoresolve = False
        ticket_id = NetBot.parse_thread_title(ctx.channel.name)
        if ticket_id is None:
            # create a ticket and thread
            ticket_cog = ctx.bot.get_cog('TicketsCog')
            if ticket_cog:
                await ticket_cog.create_new_ticket(ctx, note)
                autoresolve = True

        redmine.ticket_mgr.record_time(ticket_id, user, hours, program_id, note)
        if autoresolve:
            redmine.ticket_mgr.resolve(ticket_id)
        program = ctx.bot.redmine.ticket_mgr.get_program_by_id(program_id)
        await ctx.respond(f"Recorded **{hours} hours** on **{program}** for *{user.discord}*")


    @discord.slash_command(name="status", description="Show open ticket digest for this team")
    async def status_digest(self, ctx: discord.ApplicationContext):
        await ctx.defer()   # Redmine call may take up to 5 s

        term = default_term(ctx)
        team = self.redmine.user_mgr.find(term) if term else None

        if team:
            tickets = self.redmine.ticket_mgr.tickets_for_team(team)
            title = f"{team.name} — Open Tickets"
        else:
            from redmine.tickets import DEFAULT_SORT
            tickets = self.redmine.ticket_mgr.tickets(
                status_id="open", sort=DEFAULT_SORT, limit=100
            )
            title = "All Open Tickets"

        truncated = len(tickets) >= 100
        if truncated:
            log.warning(f"/status: hit 100-ticket cap (channel={ctx.channel.name}, term={term})")

        buckets = self.redmine.ticket_mgr.bucket_tickets(tickets)
        total_pages = max(1, math.ceil(len(buckets["sorted_tickets"]) / 5))

        view = StatusView(self.bot, title, buckets, truncated)
        embed = self.bot.formatter.status_embed(title, buckets, 0, total_pages, truncated)

        await ctx.respond(embed=embed, view=view)


    ### Ticket autothreading and notification ###

    AUTOTHREAD_TRACKERS = ["Mutual-Aid-Action"]
    AUTONOTIFY_TRACKERS = ["Mutual-Aid-Action"]


    @tasks.loop(minutes=1.0)
    async def poll_new_tickets(self):
        log.debug("notify_new_tickets. this should be called every minute.")

        # check for new tickets
        for ticket in self.get_new_tickets():
            if ticket.tracker.name in self.AUTOTHREAD_TRACKERS:
                log.debug(f"auto-threading ticket {ticket.id} based on tracker: {ticket.tracker}")
                await self.sync_ticket(ticket)

            if ticket.tracker.name in self.AUTONOTIFY_TRACKERS:
                # no need to await the notification
                await self.notify_ticket(ticket)


    def get_new_tickets(self):
        log.debug("Checking for new tickets")
        # for now, tickets created in the last 5 minutes
        ## FIXME - track and manage queries, state in netbot for last query
        timestamp = synctime.now() - dt.timedelta(minutes=5)
        tickets = self.redmine.ticket_mgr.new_tickets_since(timestamp)
        return tickets


    ### returns true only when a discord thread is created.
    async def sync_ticket(self, ticket: Ticket) -> bool:
        # first, check if sync currently exists
        # possible TODO: cache of ticket id -> thread ids
        channel_id = ticket.channel_id
        if channel_id == 0:
            # find parent channel for thread
            parent = self.bot.channel_for_ticket(ticket)
            # create thread
            thread = await self.create_ticket_thread(ticket, parent)
            if thread:
                # create sync record
                sync_rec = synctime.SyncRecord(ticket.id, thread.id)
                self.redmine.ticket_mgr.update_sync_record(sync_rec)
                # sync
                complete = await self.bot.sync_thread(thread)
                return complete
            else:
                log.error(f"No update. Cannot find channel for {ticket}")
                return False
        else:
            thread = self.bot.channel_for_ticket(ticket)
            _ = await self.bot.sync_thread(thread)
            return False


    async def notify_ticket(self, ticket:Ticket) -> None:
        log.info(f"FIXME: Notify ticket: {ticket}")


    async def create_ticket_thread(self, ticket: Ticket, parent_channel: discord.TextChannel) -> discord.Thread:
        if parent_channel:
            log.info(f"creating a new thread for ticket #{ticket.id} in channel: {parent_channel}")
            thread_name = f"Ticket #{ticket.id}: {ticket.subject}"

            log.debug(f"creating thread in channel {parent_channel.name}, for {ticket}")
            thread = await parent_channel.create_thread(name=thread_name, type=discord.ChannelType.public_thread)

            # ticket-614: Creating new thread should post the ticket details to the new thread
            await thread.send(self.bot.formatter.format_ticket_details(ticket))

            return thread
        else:
            log.warning(f"Empty parent_channel provided for threading ticket {ticket}")
