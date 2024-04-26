#!/usr/bin/env python3
"""redmine client"""

import os
import re
import logging
import datetime as dt

from dotenv import load_dotenv

import synctime
from session import RedmineSession
from model import Message, Ticket, User
from users import UserManager
from tickets import TicketManager, SCN_PROJECT_ID


log = logging.getLogger(__name__)


DEFAULT_SORT = "status:desc,priority:desc,updated_on:desc"
TIMEOUT = 10 # seconds
SYNC_FIELD_NAME = "syncdata"
DISCORD_ID_FIELD = "Discord ID"
BLOCKED_TEAM_NAME = "blocked"
STATUS_REJECT = 5 # could to status lookup, based on "reject"


class RedmineException(Exception):
    """redmine exception"""
    def __init__(self, message: str, request_id: str = "-") -> None:
        super().__init__(message + ", req_id=" + request_id)
        self.request_id = request_id


class Client():
    """redmine client"""
    def __init__(self, session:RedmineSession, default_project: int):
        self.url = session.url
        self.user_mgr:UserManager = UserManager(session)
        self.ticket_mgr:TicketManager = TicketManager(session, default_project=default_project)

        self.user_mgr.reindex() # build the cache when starting


    @classmethod
    def fromenv(cls):
        url = os.getenv('REDMINE_URL')
        if url is None:
            raise RedmineException("Unable to load REDMINE_URL")

        token = os.getenv('REDMINE_TOKEN')
        if token is None:
            raise RedmineException("Unable to load REDMINE_TOKEN")

        default_project = os.getenv("DEFAULT_PROJECT_ID", default=SCN_PROJECT_ID)
        return cls(RedmineSession(url, token), default_project)


    def create_ticket(self, user:User, message:Message) -> Ticket:
        ticket = self.ticket_mgr.create(user, message)
        # check user status, reject the ticket if blocked
        if self.user_mgr.is_blocked(user):
            log.debug(f"Rejecting ticket #{ticket.id} based on blocked user {user.login}")
            ticket = self.ticket_mgr.reject_ticket(ticket.id)
        return ticket


    def update_ticket(self, ticket_id:int, fields:dict, user_login:str|None=None):
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
            "cf_1": "1", # TODO: read from custom fields via
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
        log.debug(f"Updating sync record in redmine: {record}")
        fields = {
            "custom_fields": [
                { "id": 4, "value": record.token_str() } # cf_4, custom field syncdata,
                #TODO search for custom field ID with TicketManager.get_field_id
            ]
        }
        self.update_ticket(record.ticket_id, fields)

    def get_updated_field(self, ticket) -> dt.datetime:
        return synctime.parse_str(ticket.updated_on)


    # NOTE: This implies that ticket should be a full object with methods.
    # Starting to move fields out to their own methods, to eventually move to
    # their own Ticket class.
    def get_field(self, ticket, fieldname):
        return self.ticket_mgr.get_field(ticket, fieldname)


    def get_discord_id(self, user):
        if user:
            for field in user.custom_fields:
                if field.name == "Discord ID":
                    return field.value
        return None

    def is_user_or_group(self, user:str) -> bool:
        return self.user_mgr.is_user_or_group(user)


if __name__ == '__main__':
    # load credentials
    load_dotenv()

    # construct the client and run the email check
    client = Client.fromenv()
    tickets = client.find_tickets()
    client.format_report(tickets)
