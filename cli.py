#!/usr/bin/env python3

import io
import logging
import datetime as dt


import hashlib
import click

from dotenv import load_dotenv

import redmine

### reimplementing  "tickets" command using click.  https://pypi.org/project/click/

# using https://pypi.org/project/rich/ for terminal formatting
from rich.console import Console
from rich.table import Table
from rich import box


log = logging.getLogger(__name__)

# redmine client
# load creds into env, and init the redmine client
load_dotenv()
redmine_client = redmine.Client.fromenv()

# figure out what the term refers to
# better way?
# REMOVE still needed?
def resolve_query_term(term):
    # special cases: ticket num and team name
    try:
        id = int(term)
        ticket = redmine_client.get_ticket(id)
        return [ticket]
    except ValueError:
        # not a numeric id, check team
        if redmine_client.is_user_or_group(term):
            return redmine_client.tickets_for_team(term)
        else:
            # assume a search term
            return redmine_client.search_tickets(term)

# the 'rich' version
def print_tickets(tickets, fields=["link","status","priority","age","assigned","subject"]):
    if not tickets:
        print("no tickets found")
        return
    elif len(tickets) == 1:
        print_ticket(tickets[0])
        return

    console = Console()

    table = Table(show_header=True, box=box.SIMPLE_HEAD, collapse_padding=True, header_style="bold magenta")
    for field in fields:
        #table.add_column("Date", style="dim", width=12)
        table.add_column(field)

    for ticket in tickets:
        row = []
        for field in fields:
            row.append(get_formatted_field(ticket, field))
        table.add_row(*row)

    console.print(table)

def print_tickets_md(tickets, fields=["link","status","priority","age","assigned","subject"]):
    if not tickets:
        print("no tickets found")
        return
    elif len(tickets) == 1:
        print_ticket(tickets[0])
        return

    print(f"found {len(tickets)} tickets")
    console = Console(file=io.StringIO(), color_system=None)

    table = Table(show_header=True, box=box.SIMPLE_HEAD, collapse_padding=True, header_style="bold magenta")
    for field in fields:
        #table.add_column("Date", style="dim", width=12)
        table.add_column(field)

    for ticket in tickets:
        row = []
        for field in fields:
            row.append(redmine_client.get_field(ticket, field))
        table.add_row(*row)

    console.print(table)

    buffer = io.StringIO(console.file.getvalue())

    for line in buffer:
        print(f"{line.strip()}")


def print_team(team):
    console = Console()
    table = Table(show_header=True, box=box.SIMPLE_HEAD, collapse_padding=True, header_style="bold magenta")
    table.add_column(team.name)
    for user in team.users:
        table.add_row(user.name)

    console.print(table)


def print_teams(teams):
    if not teams:
        print("no teams found")
    else:
        for teamname in teams:
            team = redmine_client.get_team(teamname)
            print_team(team)


color_map = {
    "Low": "dim",
    "Normal": "green",
    "High": "yellow",
    "Urgent": "orange",
    "Immediate": "red",

    "New": "hot_pink",
    "In Progress": "green",
    "Feedback": "yellow",
    "Resolved": "dark_green",
    "Closed": "dim",
    "Rejected/Spam": "dim",
}

def lookup_color(term:str):
    return color_map.get(term, None)

def hash_color(value):
    # consistently-hash the value into a color
    # hash_val = hash(value) <-- this does it inconsistantly (for security reasons)
    hash_val = int(hashlib.md5(value.encode('utf-8')).hexdigest(), 16)
    r = (hash_val & 0xFF0000) >> 16
    g = (hash_val & 0x00FF00) >> 8
    b = hash_val & 0x0000FF
    return f"rgb({r},{g},{b})"

def get_formatted_field(ticket, field):
    value = redmine_client.get_field(ticket, field)

    match field:
        case "link":
            url = redmine_client.get_field(ticket, "url")
            return f"[link={url}]{ticket.id}[/link]"
        case "subject":
            url = redmine_client.get_field(ticket, "url")
            return f"[link={url}]{value}[/link]"
        case "url":
            url = redmine_client.get_field(ticket, "url")
            return f"[link={url}]{value}[/link]"
        case "priority":
            color = lookup_color(value)
            return f"[{color}]{value}[/{color}]"
        case "age":
            updated = dt.datetime.fromisoformat(ticket.updated_on)
            age = dt.datetime.now(dt.timezone.utc) - updated

            color = None
            if age.days == 0:
                color = "green"
            elif age.days > 0 and age.days <= 2:
                pass # no color
            elif age.days > 2 and age.days <= 7:
                color = "bright_yellow"
            elif age.days > 7 and age.days <= 15:
                color = "dark_orange"
            else:
                color = "red"
            if color:
                return f"[{color}]{value}[/{color}]"
            else:
                return value
        case "status":
            color = lookup_color(value)
            return f"[{color}]{value}[/{color}]"
        case "assigned":
            color = hash_color(value)
            return f"[{color}]{value}[/{color}]"
    return value

def print_ticket(ticket):
    # print details for a single ticket
    console = Console()
    url = redmine_client.get_field(ticket, "url")

    console.print(f"[link={url}]{ticket.tracker.name} #{ticket.id}[/link]")
    console.print(f"Added by {ticket.author.name}")

    assigned_to = ""
    if hasattr(ticket, 'assigned_to'):
        assigned_to = ticket.assigned_to.name

    table = Table(show_header=False, box=box.SIMPLE_HEAD)
    table.add_column("key1", justify="right", style="dim")
    table.add_column("value1", justify="left")
    table.add_column("key2", justify="right", style="dim")
    table.add_column("value2", justify="left")
    table.add_row("Status:", ticket.status.name, "Start date:", ticket.created_on)
    table.add_row("Priority:", ticket.priority.name, "Due date:", ticket.due_date)
    table.add_row("Assignee:", assigned_to, "% Done:", f"{ticket.done_ratio}%")
    table.add_row("Category:", ticket.category.name, "Estimated time:", ticket.estimated_hours)
    console.print(table)

    console.print(ticket.description, width=80)

"""
id: 93
project: namespace(id=1, name='Seattle Community Network')
tracker: namespace(id=4, name='Software Dev Task')
status: namespace(id=2, name='In Progress', is_closed=False)
priority: namespace(id=2, name='Normal')
author: namespace(id=15, name='Fred Example')
assigned_to: namespace(id=5, name='Paul Philion')
category: namespace(id=4, name='feature request')
subject: Threading with Emails
description: Issue threading does not currently work when tickr
start_date: 2023-10-16
due_date: None
done_ratio: 50
is_private: False
estimated_hours: None
total_estimated_hours: 0.0
spent_hours: 14.0
total_spent_hours: 16.0
custom_fields:
created_on: 2023-10-10T02:38:33Z
updated_on: 2023-11-15T04:36:39Z
closed_on: None
"""

def format_tickets(tickets, fields=["link","priority","updated","assigned","subject"]):
        if len(tickets) == 1:
            format_ticket_details(tickets[0])
        else:
            for ticket in tickets:
                print(format_ticket(ticket, fields))


def format_ticket(ticket, fields=["link","priority","updated","assigned", "subject"]):
    url = f"FIXME/issues/{ticket.id}"
    try: # hack to get around missing key
        assigned_to = ticket.assigned_to.name
    except AttributeError:
        assigned_to = ""

    section = ""
    for field in fields:
        match field:
            case "id":
                section += f"{ticket.id}"
            case "url":
                section += url
            case "link":
                section += f"[{ticket.id}]({url})"
            case "priority":
                section += f"{ticket.priority.name}"
            case "updated":
                section += f"{ticket.updated_on[:10]}" # just the date, strip time
            case "assigned":
                section += f"{assigned_to}"
            case "status":
                section += f"{ticket.status.name}"
            case "subject":
                section += f"{ticket.subject}"
        section += " " # spacer, one space
    return section.strip() # remove trailing whitespace


def format_ticket_details(ticket):
    print(ticket)


@click.group()
def cli():
    """This script showcases different terminal UI helpers in Click."""
    pass


@cli.command()
@click.argument("query", default="")
def tickets(query):
    """Query open tickets"""
    if query:
        print_tickets(resolve_query_term(query))
    else:
        print_tickets(redmine_client.my_tickets())


@cli.command()
@click.argument("id", type=int)
def resolve(id:int):
    """Reslove ticket"""
    # case "resolve":
    redmine_client.resolve_ticket(id)
    print_ticket(redmine_client.get_ticket(id))


@cli.command()
@click.argument("id", type=int)
def progress(id:int):
    """Mark ticket in-progress"""
    #case "progress":
    redmine_client.progress_ticket(id)
    print_ticket(redmine_client.get_ticket(id))


@cli.command()
@click.argument("id", type=int)
@click.argument("asignee", type=str)
def assign(id:int, asignee:str):
    """Assign ticket to user"""
    # case assign
    redmine_client.assign_ticket(id, asignee)
    print_ticket(redmine_client.get_ticket(id))


@cli.command()
@click.argument("id", type=int)
def unassign(id:int):
    """Unassign ticket"""
    # case "unassign":
    redmine_client.unassign_ticket(id)
    print_ticket(redmine_client.get_ticket(id))


@cli.command()
def teams():
    """List teams"""
    print_teams(redmine_client.get_teams())


@cli.command()
@click.argument("team", type=str)
def team(team:str):
    """List team members"""
    print_team(redmine_client.get_team(team))


@cli.command()
@click.argument("user", type=str)
@click.argument("team", type=str)
def join(user:str, team:str):
    """Join a team"""
    redmine_client.join_team(user, team)
    print_team(redmine_client.get_team(team))


@cli.command()
@click.argument("user", type=str)
@click.argument("team", type=str)
def leave(user:str, team:str):
    """Leave a team"""
    redmine_client.leave_team(user, team)
    print_team(redmine_client.get_team(team))


if __name__ == '__main__':
    cli()
