#!/usr/bin/env python3

"""encapsulate Discord ticket functions"""

import logging

import discord

from discord.commands import option, SlashCommandGroup

from discord.ext import commands
from discord.enums import InputTextStyle
from discord.ui.item import Item, V

from model import Message, Ticket
from redmine import Client
from netbot import NetBot


log = logging.getLogger(__name__)


def setup(bot):
    bot.add_cog(TicketsCog(bot))
    log.info("initialized tickets cog")


def get_trackers(ctx: discord.AutocompleteContext):
    """Returns a list of trackers that begin with the characters entered so far."""
    trackers = ctx.bot.redmine.get_trackers() # this is expected to be cached
    # .lower() is used to make the autocomplete match case-insensitive
    return [tracker['name'] for tracker in trackers if tracker['name'].lower().startswith(ctx.value.lower())]


def get_priorities(ctx: discord.AutocompleteContext):
    """Returns a list of trackers that begin with the characters entered so far."""
    priorities = ctx.bot.redmine.get_priorities() # this is expected to be cached
    # .lower() is used to make the autocomplete match case-insensitive
    return [priority['name'] for priority in priorities if priority['name'].lower().startswith(ctx.value.lower())]


class PrioritySelect(discord.ui.Select):
    """Popup menu to select ticket priority"""
    def __init__(self, bot_: discord.Bot):
        # For example, you can use self.bot to retrieve a user or perform other functions in the callback.
        # Alternatively you can use Interaction.client, so you don't need to pass the bot instance.
        self.bot = bot_

        # Get the possible priorities
        options = []
        for priority in self.bot.redmine.get_priorities():
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
        for tracker in self.bot.redmine.get_trackers():
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


class SubjectEdit(discord.ui.InputText, Item[V]):
    """Popup menu to select ticket tracker"""
    def __init__(self, bot_: discord.Bot, ticket: Ticket):
        # For example, you can use self.bot to retrieve a user or perform other functions in the callback.
        # Alternatively you can use Interaction.client, so you don't need to pass the bot instance.
        self.bot = bot_
        self.ticket = ticket

        # Get the possible trackers
        options = []
        for tracker in self.bot.redmine.get_trackers():
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


class EditView(discord.ui.View):
    """View to allow ticket editing"""
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
    def __init__(self, bot_: discord.Bot, ticket: Ticket) -> None:
        self.bot = bot_
        super().__init__()

        # Adds the dropdown to our View object
        self.add_item(PrioritySelect(self.bot))
        #self.add_item(SubjectEdit(self.bot, ticket))
        self.add_item(TrackerSelect(self.bot))

        self.add_item(discord.ui.Button(label="Done", row=4))
        self.add_item(discord.ui.Button(label="Edit Subject & Description", row=4))
        #self.add_item(discord.ui.Button(label="Block email@address.com", row=4))

    async def select_callback(self, select, interaction): # the function called when the user is done selecting options
        await interaction.response.send_message(f"EditView.select_callback() selected: {select.values[0]}")

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"EditView.callback() {interaction.data}")


class TicketsCog(commands.Cog):
    """encapsulate Discord ticket functions"""
    def __init__(self, bot:NetBot):
        self.bot:NetBot = bot
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
        if not user:
            log.info(f"Unknown user name: {ctx.user.name}")
            # TODO make this a standard error.
            await ctx.respond(f"Discord member **{ctx.user.name}** is not provisioned in redmine. Use `/scn add [redmine-user]` to provision.")
            return

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



    @ticket.command(description="Collaborate on a ticket")
    @option("ticket_id", description="ticket ID")
    async def collaborate(self, ctx: discord.ApplicationContext, ticket_id:int):
        """Add yourself as a collaborator on a ticket"""
        # lookup the user
        user = self.redmine.user_mgr.find(ctx.user.name)
        if not user:
            await ctx.respond(f"User {ctx.user.name} not mapped to redmine. Use `/scn add [redmine-user]` to create the mapping.")
            return
        ticket = self.redmine.get_ticket(ticket_id)
        if ticket:
            self.redmine.ticket_mgr.collaborate(ticket_id, user)
            await self.bot.formatter.print_ticket(self.redmine.get_ticket(ticket_id), ctx)
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


    @ticket.command(name="edit", description="Edit a ticket")
    @option("ticket_id", description="ticket ID")
    async def edit(self, ctx:discord.ApplicationContext, ticket_id: int):
        """Edit the fields of a ticket"""
        # check team? admin?, provide reasonable error msg.
        ticket = self.redmine.ticket_mgr.get(ticket_id)
        await ctx.respond(f"EDIT #{ticket.id}", view=EditView(self.bot, ticket))


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


    @ticket.command(name="alert", description="Alert collaborators on a ticket")
    @option("ticket_id", description="ID of ticket to alert")
    async def alert_ticket(self, ctx: discord.ApplicationContext, ticket_id:int=0):
        if not ticket_id:
            # check thread for ticket id
            ticket_id = self.bot.parse_thread_title(ctx.channel.name)

        ticket = self.redmine.get_ticket(ticket_id, include="watchers") # inclde the option watchers/collaborators field
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
            msg = f"Ticket {ticket.id} is about will expire soon."
            await thread.send(self.bot.formatter.format_ticket_alert(ticket.id, discord_ids, msg))
            await ctx.respond("Alert sent.")
        else:
            await ctx.respond(f"ERROR: Unkown ticket ID: {ticket_id}") ## TODO format error message


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


    @ticket.command(name="tracker", description="Update the tracker of a ticket")
    @option("ticket_id", description="ID of ticket to update")
    @option("tracker", description="Track to assign to ticket", autocomplete=get_trackers)
    async def tracker(self, ctx: discord.ApplicationContext, ticket_id:int, tracker:str):
        user = self.redmine.user_mgr.find_discord_user(ctx.user.name)
        ticket = self.redmine.get_ticket(ticket_id)
        if ticket:
            ticket_link = self.bot.formatter.format_link(ticket)

            # look up the tracker string
            tracker_rec = self.bot.lookup_tracker(tracker)

            fields = {
                "tracker_id": tracker_rec.id,
            }
            updated = self.bot.redmine.ticket_mgr.update(ticket_id, fields, user.login)

            await ctx.respond(f"Updated {ticket_link} to tracker => {updated.tracker.name}")
        else:
            await ctx.respond(f"ERROR: Unkown ticket ID: {ticket_id}")


    @ticket.command(name="priority", description="Update the tracker of a ticket")
    @option("ticket_id", description="ID of ticket to update")
    @option("priority", description="Priority to assign to ticket", autocomplete=get_priorities)
    async def priority(self, ctx: discord.ApplicationContext, ticket_id:int, priority:str):
        user = self.redmine.user_mgr.find_discord_user(ctx.user.name)
        ticket = self.redmine.get_ticket(ticket_id)
        if ticket:
            ticket_link = self.bot.formatter.format_link(ticket)

            # look up the tracker string
            priority = self.bot.lookup_priority(priority)

            fields = {
                "priority_id": priority.id,
            }
            updated = self.bot.redmine.ticket_mgr.update(ticket_id, fields, user.login)

            await ctx.respond(f"Updated {ticket_link} to priority => {updated.priority.name}")
        else:
            await ctx.respond(f"ERROR: Unkown ticket ID: {ticket_id}")


    @ticket.command(name="subject", description="Update the subject of a ticket")
    @option("ticket_id", description="ID of ticket to update")
    @option("subject", description="Updated subject")
    async def subject(self, ctx: discord.ApplicationContext, ticket_id:int, subject:str):
        user = self.redmine.user_mgr.find_discord_user(ctx.user.name)
        if not user:
            await ctx.respond(f"ERROR: Discord user without redmine config: {ctx.user.name}. Create with `/scn add`")
            return

        ticket = self.redmine.get_ticket(ticket_id)
        if not ticket:
            await ctx.respond(f"ERROR: Unkown ticket ID: {ticket_id}")
            return

        ticket_link = self.bot.formatter.format_link(ticket)

        fields = {
            "subject": subject,
        }
        updated = self.bot.redmine.ticket_mgr.update(ticket_id, fields, user.login)

        await ctx.respond(f"Updated {ticket_link} with new subject => {updated.subject}") #TODO return ticket summary.
