#!/usr/bin/env python3

"""Formatting Discord messages"""

import logging
import discord

from redmine.model import NamedId, Ticket, User
from redmine import synctime

log = logging.getLogger(__name__)

MAX_MESSAGE_LEN = 2000
EMBED_TITLE_LEN = 256 # title, field name, author
EMBED_DESC_LEN = 4096
EMBED_VALUE_LEN = 1024
EMBED_FOOTER_LEN = 2048
EMBED_MAX_LEN = 6000

# Note: Up to 10 embeds per response, 25 fields each

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
    '?': '❓',
}

def get_emoji(key:str) -> str:
    return EMOJI.get(key, "")


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

#EPIC_TAG = "[EPIC] "
#def strip_epic_tag(subject:str) -> str:
#     return subject[len(EPIC_TAG):] if subject.startswith(EPIC_TAG) else subject


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

        #TODO: Ordering?
        for ticket in tickets:
            # track which symbols are used for status and priority
            if ticket.status.name not in legend:
                legend[ticket.status.name] = get_emoji(ticket.status.name)
            if ticket.priority.name not in legend:
                legend[ticket.priority.name] = get_emoji(ticket.priority.name)

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


    def redmine_link(self, ticket:Ticket) -> str:
        return f"[`#{ticket.id}`]({self.base_url}/issues/{ticket.id})"


    def discord_link(self, ctx: discord.ApplicationContext, ticket:Ticket) -> str:
        thread = ctx.bot.find_ticket_thread(ticket.id)
        if thread:
            return thread.jump_url


    def format_tracker(self, tracker:NamedId|None) -> str:
        if tracker:
            return f"{get_emoji(tracker.name)} {tracker.name}"
        else:
            return ""


    def format_icon(self, value:NamedId|None) -> str:
        if value and value.name:
            emoji = get_emoji(value.name)
            if len(emoji) > 0:
                return f"{get_emoji(value.name)} {value.name}"
            else:
                return value.name
        elif value:
            return str(value.id)
        else:
            return ""


    def format_ticket_row(self, ticket:Ticket) -> str:
        link = self.redmine_link(ticket)
        # link is mostly hidden, so we can't use the length to format.
        # but the length of the ticket id can be used
        link_padding = ' ' * (5 - len(str(ticket.id))) # field width = 6

        status = get_emoji(ticket.status.name) if ticket.status else get_emoji('?')
        priority = get_emoji(ticket.priority.name) if ticket.priority else get_emoji('?')
        age = synctime.age_str(ticket.updated_on)
        assigned = ticket.assigned_to.name if ticket.assigned_to else ""
        return f"`{link_padding}`{link}` {status} {priority}  {age:<10} {assigned:<18} `{ticket.subject[:60]}"


    def format_subticket(self, ctx: discord.ApplicationContext, ticket:Ticket) -> str:
        if ticket.status and ticket.status.is_closed:
            # if the ticket is closed, remove the link and add strikeout
            return f"~~{ticket.id} - {ticket.subject}~~"
        else:
            thread_url = self.discord_link(ctx, ticket)
            if thread_url:
                return thread_url
            else:
                log.info(f"No Discord thread for {ticket}")
                return f"[{ticket.id}]({self.base_url}/issues/{ticket.id}) - {ticket.subject}"



    def format_discord_note(self, note) -> str:
        """Format a note for Discord"""
        age = synctime.age_str(note.created_on)
        return f"> **{note.user}** *{age} ago*\n> {note.notes}"[:MAX_MESSAGE_LEN]


    def format_ticket(self, ticket:Ticket) -> str:
        link = self.redmine_link(ticket)
        status = f"{get_emoji(ticket.status.name)} {ticket.status.name}"
        priority = f"{get_emoji(ticket.priority.name)} {ticket.priority.name}"
        assigned = ticket.assigned_to.name if ticket.assigned_to else ""
        return " ".join([link, priority, status, ticket.tracker.name, assigned, ticket.subject])


    def format_ticket_details(self, ticket:Ticket) -> str:
        link = self.redmine_link(ticket)
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
        status = self.format_icon(ticket.status)
        priority = self.format_icon(ticket.priority)
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
        return f"ALERT: Expiring ticket: {self.redmine_link(ticket)} {' '.join(ids_str)}"


    def format_ticket_alert(self, ticket: Ticket, discord_ids: list[str], msg: str) -> str:
        ids_str = ["@" + id for id in discord_ids]
        return f"ALERT #{self.redmine_link(ticket)} {' '.join(ids_str)}: {msg}"


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
            if member:
                return f"<@!{member.id}>"

        return ticket.assigned


    def ticket_embed(self, ctx: discord.ApplicationContext, ticket:Ticket) -> discord.Embed:
        """Build an embed panel with full ticket details"""
        subject = f"{get_emoji(ticket.priority.name)} {ticket.subject[:EMBED_TITLE_LEN-8]} (#{ticket.id})"
        embed = discord.Embed(
            title=subject,
            description=ticket.description[:EMBED_DESC_LEN],
            colour=self.ticket_color(ticket)
        )

        # noting, assuming all these values are less than
        #         status = self.format_icon(ticket.status)
        #priority = self.format_icon(ticket.priority)
        embed.add_field(name="Status", value=self.format_icon(ticket.status))
        embed.add_field(name="Priority", value=self.format_icon(ticket.priority))
        embed.add_field(name="Tracker", value=self.format_icon(ticket.tracker))
        if ticket.category:
            embed.add_field(name="Category", value=ticket.category)

        if ticket.assigned_to:
            embed.add_field(name="Owner", value=self.get_user_id(ctx, ticket))

        # list the sub-tickets
        if ticket.children:
            buff = ""
            for child in ticket.children:
                buff += "- " + self.format_subticket(ctx, child) + "\n"
            embed.add_field(name="Tickets", value=buff, inline=False)

        # thread & redmine links
        jump_url = self.discord_link(ctx, ticket)
        if jump_url:
            embed.add_field(name="Thread", value=jump_url)
        else:
            embed.add_field(name="Redmine", value=self.redmine_link(ticket))

        return embed


    def epics_embed(self, ctx: discord.ApplicationContext, epics: list[Ticket]) -> list[discord.Embed]:
        """Build an array of embeds, one for each epic"""
        embeds = []
        total_len = 0

        for epic in epics:
            title = f"{ get_emoji(epic.priority.name) } {epic.subject[:EMBED_TITLE_LEN-8]} (#{epic.id})"
            embed = discord.Embed(
                title=title,
                description=epic.description[:EMBED_DESC_LEN],
                color=discord.Color.blurple() # based on tracker?
            )

            # noting, assuming all these values are less than
            if epic.assigned_to:
                embed.add_field(name="Owner", value=self.get_user_id(ctx, epic))
            embed.add_field(name="Tracker", value=self.format_tracker(epic.tracker))
            embed.add_field(name="Age", value=epic.age_str)

            if epic.children:
                buff = ""
                for child in epic.children:
                    buff += "- " + self.format_subticket(ctx, child) + "\n"
                embed.add_field(name="", value=buff, inline=False)

            # thread & redmine links
            jump_url = self.discord_link(ctx, epic)
            if jump_url:
                embed.add_field(name="Thread", value=jump_url)
            else:
                embed.add_field(name="Redmine", value=self.redmine_link(epic))

            # truncing approach:
            # 1 message, 10 embeds, 6000 chars max
            # if the embed is > 600, clip the description so the overall length == 600
            # this effectively removes descriptions from epics with a lot of tickets.
            # it also leaves a lot of wasted overhead, when the other embeds in the message
            # are less than 600, about 10% on current samples.
            embed_len = len(embed)
            if embed_len > 600: # 6000/10
                overage = embed_len - 600
                embed.description = embed.description[:-overage]
                #log.info(f"EMBED: orig={embed_len}, desc={len(embed.description)}, over={overage}")

            # add embed to the set
            total_len += len(embed)
            embeds.append(embed)

        return embeds


    def help_embed(self, _: discord.ApplicationContext) -> discord.Embed:
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
