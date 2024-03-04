#!/usr/bin/env python3
"""redmine client"""

import os
import re
import logging
import datetime as dt

from dotenv import load_dotenv

import synctime
from session import RedmineSession
from users import User, UserManager
from tickets import Ticket, TicketManager


log = logging.getLogger(__name__)


DEFAULT_SORT = "status:desc,priority:desc,updated_on:desc"
TIMEOUT = 10 # seconds
SYNC_FIELD_NAME = "syncdata"
DISCORD_ID_FIELD = "Discord ID"
BLOCKED_TEAM_NAME = "blocked"
SCN_PROJECT_ID = 1  # could lookup scn in projects
STATUS_REJECT = 5 # could to status lookup, based on "reject"


class RedmineException(Exception):
    """redmine exception"""
    def __init__(self, message: str, request_id: str) -> None:
        super().__init__(message + ", req_id=" + request_id)
        self.request_id = request_id


class Client(): ## redmine.Client
    """redmine client"""
    def __init__(self, url: str, token: str):
        self.url = url
        if self.url is None:
            raise RedmineException("Unable to load REDMINE_URL", "[n/a]")

        self.token = token
        if self.url is None:
            raise RedmineException("Unable to load REDMINE_TOKEN", "__init__")

        session:RedmineSession = RedmineSession(url, token)
        self.user_mgr:UserManager = UserManager(session)
        self.ticket_mgr:TicketManager = TicketManager(session)

        self.user_mgr.reindex() # build the cache when starting


    @classmethod
    def fromenv(cls):
        url = os.getenv('REDMINE_URL')
        token = os.getenv('REDMINE_TOKEN')
        return cls(url, token)


    def create_ticket(self, user, subject, body, attachments=None):
        return self.ticket_mgr.create(user, subject, body, attachments)


    def update_ticket(self, ticket_id:int, fields:dict, user_login:str=None):
        return self.ticket_mgr.update(ticket_id, fields, user_login)


    def append_message(self, ticket_id:int, user_login:str, note:str, attachments=None): # Could be TicketNote
        return self.ticket_mgr.append_message(ticket_id, user_login, note, attachments)


    def upload_file(self, user:User, data, filename, content_type) -> str:
        return self.ticket_mgr.upload_file(user, data, filename, content_type)


    def upload_attachments(self, user:User, attachments):
        self.ticket_mgr.upload_attachments(user, attachments)

    def get_tickets_by(self, user) -> list[Ticket]:
        return self.ticket_mgr.get_tickets_by(user)

    def get_ticket(self, ticket_id:int, include_journals:bool = False) -> Ticket:
        return self.ticket_mgr.get(ticket_id, include_journals)

    #GET /issues.xml?issue_id=1,2
    def get_tickets(self, ticket_ids) -> list[Ticket]:
        return self.ticket_mgr.get_tickets(ticket_ids)


    def find_ticket_from_str(self, string:str) -> Ticket:
        """parse a ticket number from a string and get the associated ticket"""
        # for now, this is a trivial REGEX to match '#nnn' in a string, and return ticket #nnn
        match = re.search(r'#(\d+)', string)
        if match:
            ticket_num = int(match.group(1))
            return self.get_ticket(ticket_num)
        else:
            log.debug(f"Unable to match ticket number in: {string}")
            return []


    def remove_ticket(self, ticket_id:int):
        self.ticket_mgr.remove(ticket_id)

    def most_recent_ticket_for(self, email: str) -> Ticket:
        return self.ticket_mgr.most_recent_ticket_for(email)

    def new_tickets_since(self, timestamp:dt.datetime) -> list[Ticket]:
        return self.ticket_mgr.new_tickets_since(timestamp)

    def find_tickets(self) -> list[Ticket]:
        return self.ticket_mgr.find_tickets()

    def my_tickets(self, user=None) -> list[Ticket]:
        return self.ticket_mgr.my_tickets(user)

    def tickets_for_team(self, team_str:str) -> list[Ticket]:
        return self.ticket_mgr.tickets_for_team(team_str)

    def search_tickets(self, term) -> list[Ticket]:
        return self.ticket_mgr.search(term)

    def match_subject(self, subject):
        return self.ticket_mgr.match_subject(subject)

    def get_notes_since(self, ticket_id, timestamp=None):
        return self.ticket_mgr.get_notes_since(ticket_id, timestamp)

    def enable_discord_sync(self, ticket_id, user, note):
        fields = {
            "note": note, #f"Created Discord thread: {thread.name}: {thread.jump_url}",
            "cf_1": "1",
        }

        self.update_ticket(ticket_id, fields, user.login)
        # currently doesn't return or throw anything
        # todo: better error reporting back to discord


    def assign_ticket(self, ticket_id, target, user_id=None):
        user = self.user_mgr.find(target)
        if user:
            self.ticket_mgr.assign_ticket(ticket_id, user, user_id)
        else:
            log.error(f"unknow user: {target}") # Exception?

    def progress_ticket(self, ticket_id, user_id=None): # TODO notes
        self.ticket_mgr.progress_ticket(ticket_id, user_id)

    def reject_ticket(self, ticket_id, user_id=None):
        self.ticket_mgr.reject_ticket(ticket_id, user_id)

    def unassign_ticket(self, ticket_id, user_id=None):
        self.ticket_mgr.unassign_ticket(ticket_id, user_id)

    def resolve_ticket(self, ticket_id, user_id=None):
        return self.ticket_mgr.resolve_ticket(ticket_id, user_id)

    def get_team(self, teamname:str):
        return self.user_mgr.get_team_by_name(teamname) # FIXME consistent naming

    def update_sync_record(self, record:synctime.SyncRecord):
        self.ticket_mgr.update_sync_record(record)

    # mostly for formatting
    def get_field(self, ticket:Ticket, fieldname:str) -> str:
        match fieldname:
            case "url":
                return f"{self.url}/issues/{ticket.id}"
            case "link":
                return f"[{ticket.id}]({self.url}/issues/{ticket.id})"
            case _:
                return ticket.get_field(fieldname)


if __name__ == '__main__':
    # load credentials
    load_dotenv()

    # construct the client and run the email check
    client = Client.fromenv()
    tickets = client.find_tickets()
    client.format_report(tickets)
