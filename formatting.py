#!/usr/bin/env python3

"""Formatting Discord messages"""

import logging

import discord

from tickets import Ticket, TicketManager
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
    'Low': '⬇️',
    'Normal': ' ',
    'High': '⬆️',
    'Urgent': '⚠️',
    'Immediate': '❗',
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
        msg = self.format_ticket_row(ticket)
        if len(msg) > MAX_MESSAGE_LEN:
            log.warning("message over {MAX_MESSAGE_LEN} chars. truncing.")
            msg = msg[:MAX_MESSAGE_LEN]
        await ctx.respond(msg)


    def format_tickets(self, title:str, tickets:list[Ticket], fields=None, max_len=MAX_MESSAGE_LEN):
        if tickets is None:
            return "No tickets found."

        if fields is None:
            fields = ["link","priority","updated_on","assigned_to","subject"]

        section = "**" + title + "**\n"
        for ticket in tickets:
            ticket_line = self.format_ticket_row(ticket)
            if len(section) + len(ticket_line) + 1 < max_len:
                # make sure the lenght is less that the max
                section += ticket_line + "\n" # append each ticket
            else:
                break # max_len hit

        return section.strip()


    # noting for future: https://docs.python.org/3/library/string.html#string.Template

    def format_link(self, ticket:Ticket) -> str: ## to Ticket.link(base_url)?
        return f"[`#{ticket.id}`]({self.base_url}/issues/{ticket.id})"


    def format_ticket_row(self, ticket:Ticket):
        link = self.format_link(ticket)
        # link is mostly hidden, so we can't use the length to format.
        # but the length of the ticket id can be used
        link_padding = ' ' * (5 - len(str(ticket.id))) # field width = 6
        status = EMOJI[ticket.status.name]
        priority = EMOJI[ticket.priority.name]
        age = synctime.age_str(ticket.updated_on)
        assigned = ticket.assigned_to.name if ticket.assigned_to else ""
        return f"`{link_padding}`{link}` {status} {priority} {age:>10} {assigned:>18}: `{ticket.subject[:60]}"


    def format_discord_note(self, note):
        """Format a note for Discord"""
        age = synctime.age_str(note.created_on)
        log.info(f"### {note} {age} {note.user}")
        message = f"> **{note.user}** *{age} ago*\n> {note.notes}"[:MAX_MESSAGE_LEN]
        return message

def main():
    ticket_manager = TicketManager(RedmineSession.fromenvfile())

    # construct the formatter
    formatter = DiscordFormatter(ticket_manager.session.url)

    tickets = ticket_manager.search("test")
    output = formatter.format_tickets("Test Tickets", tickets)
    print (output)

if __name__ == '__main__':
    main()
