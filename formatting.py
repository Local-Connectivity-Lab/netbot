#!/usr/bin/env python3

"""Formatting Discord messages"""

import logging

import discord

from model import Ticket, User, NamedId
import synctime

log = logging.getLogger(__name__)


MAX_MESSAGE_LEN = 2000


EMOJI = {
    'Resolved': '✅',
    'Reject': '❌',
    'Spam': '❌',
    'New': '🟡',
    'In Progress': '🔷',
    'Low': '🔽',
    'Normal': '⏺️',
    'High': '🔼',
    'Urgent': '⚠️',
    'Immediate': '❗',
    'EPIC': '🎇',
}


COLOR = {
    'Resolved': discord.Color.dark_green(),
    'Reject': discord.Color.dark_orange(),
    'Spam': discord.Color.orange(),
    'New': discord.Color.yellow(),
    'In Progress': discord.Color.blue(),
    'Low': discord.Color.teal(),
    'Normal': discord.Color.blue(),
    'High': discord.Color.gold(),
    'Urgent': discord.Color.dark_gold(),
    'Immediate': discord.Color.red(),
    'EPIC': discord.Color.dark_gray(),
}


class DiscordFormatter():
    """
    Format tickets and user information for Discord
    """
    def __init__(self, url: str):
        self.base_url = url


    async def print_tickets(self, title:str, tickets:list[Ticket], ctx:discord.ApplicationContext):
        if len(tickets) == 1:
            await self.print_ticket(tickets[0], ctx)
        else:
            msg = self.format_tickets(title, tickets)

            if len(msg) > MAX_MESSAGE_LEN:
                log.warning(f"message over {MAX_MESSAGE_LEN} chars. truncing.")
                msg = msg[:MAX_MESSAGE_LEN]
            await ctx.respond(msg)


    async def print_ticket(self, ticket, ctx:discord.ApplicationContext):
        await ctx.respond(embed=self.ticket_embed(ctx, ticket))
        #msg = self.format_ticket_details(ticket)
        #if len(msg) > MAX_MESSAGE_LEN:
        #    log.warning("message over {MAX_MESSAGE_LEN} chars. truncing.")
        #    msg = msg[:MAX_MESSAGE_LEN]
        #await ctx.respond(msg)


    def format_registered_users(self, users: list[User]) -> str:
        msg = ""
        for user in users:
            msg = msg + f"{user.discord_id} -> {user.login} {user.name}, {user.mail}\n"
        msg = msg.strip()

        if len(msg) > MAX_MESSAGE_LEN:
            log.warning("message over {MAX_MESSAGE_LEN} chars. truncing.")
            msg = msg[:MAX_MESSAGE_LEN]

        return msg


    def build_legend(self, tickets:list[Ticket]) -> dict[str,str]:
        # builds an icon-based legend from the status and
        # priorities of a list of tickets

        legend = {}

        # TODO: Ordering?
        for ticket in tickets:
            # track which symbols are used for status and priority
            if ticket.status.name not in legend:
                legend[ticket.status.name] = EMOJI[ticket.status.name]
            if ticket.priority.name not in legend:
                legend[ticket.priority.name] = EMOJI[ticket.priority.name]

        return legend


    def format_tickets(self, title:str, tickets:list[Ticket], max_len=MAX_MESSAGE_LEN) -> str:
        if tickets is None:
            return "No tickets found."

        legend = self.build_legend(tickets)
        legend_row = "`  "
        for name, icon in legend.items():
            legend_row += icon + name + " "
        legend_row = legend_row[:-1] + '`' # remove the last space

        section = "**" + title + "**\n"
        for ticket in tickets:
            ticket_line = self.format_ticket_row(ticket)
            if len(section) + len(ticket_line) + len(legend_row) + 1 < max_len:
                # make sure the lenght is less that the max
                section += ticket_line + "\n" # append each ticket
            else:
                break # max_len hit

        section += legend_row # add the legend
        return section.strip()


    # noting for future: https://docs.python.org/3/library/string.html#string.Template

    def format_link(self, ticket:Ticket) -> str: ## to Ticket.link(base_url)?
        return f"[`#{ticket.id}`]({self.base_url}/issues/{ticket.id})"


    def format_ticket_row(self, ticket:Ticket) -> str:
        link = self.format_link(ticket)
        # link is mostly hidden, so we can't use the length to format.
        # but the length of the ticket id can be used
        link_padding = ' ' * (5 - len(str(ticket.id))) # field width = 6
        status = EMOJI[ticket.status.name]
        priority = EMOJI[ticket.priority.name]
        age = synctime.age_str(ticket.updated_on)
        assigned = ticket.assigned_to.name if ticket.assigned_to else ""
        return f"`{link_padding}`{link}` {status} {priority}  {age:<10} {assigned:<18} `{ticket.subject[:60]}"


    def format_discord_note(self, note) -> str:
        """Format a note for Discord"""
        age = synctime.age_str(note.created_on)
        return f"> **{note.user}** *{age} ago*\n> {note.notes}"[:MAX_MESSAGE_LEN]


    def format_ticket(self, ticket:Ticket) -> str:
        link = self.format_link(ticket)
        status = f"{EMOJI[ticket.status.name]} {ticket.status.name}"
        priority = f"{EMOJI[ticket.priority.name]} {ticket.priority.name}"
        assigned = ticket.assigned_to.name if ticket.assigned_to else ""
        return " ".join([link, priority, status, ticket.tracker.name, assigned, ticket.subject])


    def format_ticket_details(self, ticket:Ticket) -> str:
        link = self.format_link(ticket)
        # link is mostly hidden, so we can't use the length to format.
        # but the length of the ticket id can be used
        # layout, based on redmine:
        # # Tracker #id
        # ## **Subject**
        # Added by author (created-ago). Updated (updated ago).
        # Status:   status             Start date:     date
        # Priority: priority           Due date:       date|blank
        # Assignee: assignee           % Done:         ...
        # Category: category           Estimated time: ...
        # ### Description
        # description text
        #link_padding = ' ' * (5 - len(str(ticket.id))) # field width = 6
        status = f"{EMOJI[ticket.status.name]} {ticket.status}"
        priority = f"{EMOJI[ticket.priority.name]} {ticket.priority}"
        created_age = synctime.age_str(ticket.created_on)
        updated_age = synctime.age_str(ticket.updated_on)
        assigned = ticket.assigned_to.name if ticket.assigned_to else ""

        details =  f"# {ticket.tracker} {link}\n"
        details += f"## {ticket.subject}\n"
        details += f"Added by {ticket.author} {created_age} ago. Updated {updated_age} ago.\n"
        details += f"**Status:**  {status}\n"
        details += f"**Priority:**  {priority}\n"
        details += f"**Assignee:**  {assigned}\n"
        details += f"**Category:**  {ticket.category}\n"
        if ticket.to or ticket.cc:
            details += f"**To:** {', '.join(ticket.to)}  **Cc:** {', '.join(ticket.cc)}\n"

        details += f"### Description\n{ticket.description}"
        return details


    def format_expiration_notification(self, ticket:Ticket, discord_ids: list[str]):
        # format an alert.
        # https://discord.com/developers/docs/interactions/message-components#action-rows
        # action row with what options?
        # :warning:
        # ⚠️
        # [icon] **Alert** [Ticket x](link) will expire in x hours, as xyz.
        ids_str = ["@" + id for id in discord_ids]
        return f"ALERT: Expiring ticket: {self.format_link(ticket)} {' '.join(ids_str)}"


    def format_ticket_alert(self, ticket: Ticket, discord_ids: list[str], msg: str) -> str:
        ids_str = ["@" + id for id in discord_ids]
        return f"ALERT #{self.format_link(ticket)} {' '.join(ids_str)}: {msg}"


    def format_epic(self, name: str, epic: list[Ticket]) -> str:
        buff = f"**{name}**\n"
        for ticket in epic:
            buff += self.format_ticket_row(ticket)
        return buff


    def format_epics(self, epics: dict[str,list[Ticket]]) -> str:
        buff = ""
        for name, epic in epics.items():
            buff += self.format_epic(name, epic) + '\n'
        return buff[:MAX_MESSAGE_LEN] # truncate!


    def ticket_color(self, ticket:Ticket) -> discord.Color:
        """Get the default color associtated with a priority"""
        if ticket.status.is_closed:
            # return the status color:
            return COLOR[ticket.status.name]
        else:
            return COLOR[ticket.priority.name]


    def lookup_discord_user(self, ctx: discord.ApplicationContext, name:str) -> discord.Member:
        for user in ctx.bot.get_all_members():
            if user.name == name or user.nick == name:
                return user
        return None


    def get_user_id(self, ctx: discord.ApplicationContext, ticket:Ticket) -> str:
        if ticket is None or ticket.assigned_to is None:
            return ""

        user = ctx.bot.redmine.user_mgr.get(ticket.assigned_to.id)
        if user and user.discord_id:
            member = self.lookup_discord_user(ctx, user.discord_id)
            return f"<@!{member.id}>"
        else:
            return ticket.assigned


    def ticket_embed(self, ctx: discord.ApplicationContext, ticket:Ticket) -> discord.Embed:
        """Build an embed panel with full ticket details"""
        embed = discord.Embed(
            title=ticket.subject,
            description=ticket.description,
            colour=self.ticket_color(ticket)
        )

        embed.add_field(name="Status", value=ticket.status)
        embed.add_field(name="Priority", value=ticket.priority)
        embed.add_field(name="Tracker", value=ticket.tracker)
        if ticket.category:
            embed.add_field(name="Category", value=ticket.category)

        if ticket.assigned_to:
            embed.add_field(name="Owner", value=self.get_user_id(ctx, ticket))

        # thread & redmine links
        thread = ctx.bot.find_ticket_thread(ticket.id)
        if thread:
            embed.add_field(name="Thread", value=thread.jump_url)
        embed.add_field(name="Redmine", value=self.format_link(ticket))

        return embed


    def help_embed(self, ctx: discord.ApplicationContext) -> discord.Embed:
        """Build an embed panel with help"""
        embed = discord.Embed(
            title="Ticket Help",
            description="Tickets are used to manage SCN work items. Discord commands are provided to:\n" +
            "* Register with the ticket system\n"
            "* Find tickets\n" +
            "* Create new tickets\n"+
            "* Work on tickets",
        )

        embed.add_field(
            name="Register to work on tickets",
            value="* **`/scn add <redmine-login>`** Register your Discord account with a new Redmine account *<redmine-login>*. " +
            "A new account will be created on the ticket system, for approval by administrators.",
            inline=False)

        embed.add_field(
            name="Find tickets to work on",
            value="* **`/ticket query me`** to find tickets assigned to you.\n" +
            "* **`/ticket query <term>`** to find tickets associated with a specific *<term>*\n" +
            "* **`/ticket details <id>`** to get detailed information about ticket *<id>*\n" +
            "* **`/ticket epics`** to list the large projects",
            inline=False)

        embed.add_field(
            name="Create a new ticket",
            value="* **`/ticket create <subject>`** Create a new ticket with the subject *<subject>*.",
            inline=False)

        embed.add_field(
            name="Work on a ticket",
            value="* **`/ticket progress <id>`** to take ownership of ticket *<id>* and mark it In Progress\n" +
            "* **`/ticket subject <id> <new subject>`** to change the subject of a ticket\n" +
            "* **`/ticket priority <id> <new priority>`** to change the priority of a ticket\n" +
            "* **`/ticket tracker <id> <new tracker>`** to change the tracker of a ticket\n" +
            "* **`/ticket resolve <id>`** to mark the ticket complete\n" +
            "Each ticket has an associated Discord thread (see `/ticket details`). Any comments in that thread will be synced with the ticket system.",
            inline=False)

        embed.add_field(
            name="Typical workflow",
            value="*Pre-conditions:* Discord member has registered with **`/scn add`** and been approved.\n" +
            "1. Create a new ticket to track a problem:\n" +
            "   - **`/ticket new Replace lightbulb 27b`**\n" +
            "2. Take ownership of the new ticket and mark it in-progress:\n" +
            "   - **`/ticket progress 42`**\n" +
            "3. *Actually get an new lightbulb and replace the burned out bulb at location 27b.*\n" +
            "4. Comment on the ticket-thread: *Replaced that bulb.*\n" +
            "5. Update the ticket to make it complete:\n" +
            "   - **`/ticket resolve 42`**\n" +
            "*Post-conditions:* Task has been completed, ticket is resolved. Ready for the next task!",
            inline=False)

        return embed


def main():
    pass
    #redmine = Client.fromenv()

    # construct the formatter
    #formatter = DiscordFormatter(redmine)

    #tickets = ticket_manager.search("test")
    #output = formatter.format_tickets("Test Tickets", tickets)
    #print (output)

if __name__ == '__main__':
    main()
