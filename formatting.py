#!/usr/bin/env python3

"""Formatting Discord messages"""

import logging

import discord

from model import Ticket
from tickets import TicketManager
from session import RedmineSession
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

class DiscordFormatter():
    """
    Format tickets and user information for Discord
    """
    def __init__(self, url: str):
        self.base_url = url


    async def print_tickets(self, title:str, tickets:list[Ticket], ctx:discord.ApplicationContext):
        msg = self.format_tickets(title, tickets)
        if len(msg) > MAX_MESSAGE_LEN:
            log.warning(f"message over {MAX_MESSAGE_LEN} chars. truncing.")
            msg = msg[:MAX_MESSAGE_LEN]
        await ctx.respond(msg)


    async def print_ticket(self, ticket, ctx):
        msg = self.format_ticket_details(ticket)
        if len(msg) > MAX_MESSAGE_LEN:
            log.warning("message over {MAX_MESSAGE_LEN} chars. truncing.")
            msg = msg[:MAX_MESSAGE_LEN]
        await ctx.respond(msg)

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
        log.info(f"### {note} {age} {note.user}")
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


def main():
    ticket_manager = TicketManager(RedmineSession.fromenvfile(), "1")

    # construct the formatter
    formatter = DiscordFormatter(ticket_manager.session.url)

    tickets = ticket_manager.search("test")
    output = formatter.format_tickets("Test Tickets", tickets)
    print (output)

if __name__ == '__main__':
    main()
