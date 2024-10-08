#!/usr/bin/env python3
"""redmine client"""

import os
import re
import logging

from redmine.session import RedmineSession
from redmine.model import Message, Ticket, User
from redmine.users import UserManager
from redmine.tickets import TicketManager, SCN_PROJECT_ID


log = logging.getLogger(__name__)


DEFAULT_SORT = "status:desc,priority:desc,updated_on:desc"
TIMEOUT = 10 # seconds
SYNC_FIELD_NAME = "syncdata"
BLOCKED_TEAM_NAME = "blocked"
STATUS_REJECT = 5 # could to status lookup, based on "reject"


class RedmineException(Exception):
    """redmine exception"""
    def __init__(self, message: str, request_id: str = "-") -> None:
        super().__init__(message + ", req_id=" + request_id)
        self.request_id = request_id


class Client():
    """redmine client"""
    def __init__(self, session:RedmineSession, user_mgr:UserManager, ticket_mgr:TicketManager):
        self.url = session.url
        self.session = session
        self.user_mgr = user_mgr
        self.ticket_mgr = ticket_mgr


    @classmethod
    def from_session(cls, session:RedmineSession, default_project:int):
        user_mgr = UserManager(session)
        ticket_mgr = TicketManager(session, default_project=default_project)

        return cls(session, user_mgr, ticket_mgr)


    @classmethod
    def fromenv(cls):
        url = os.getenv('REDMINE_URL')
        if url is None:
            raise RedmineException("Unable to load REDMINE_URL")

        token = os.getenv('REDMINE_TOKEN')
        if token is None:
            raise RedmineException("Unable to load REDMINE_TOKEN")

        default_project = os.getenv("DEFAULT_PROJECT_ID", default=SCN_PROJECT_ID)

        return cls.from_session(RedmineSession(url, token), default_project)


    def reindex(self):
        self.ticket_mgr.reindex() # re-load enumerations (priority, tracker, etc)
        self.user_mgr.reindex() # rebuild the user cache


    def create_ticket(self, user:User, message:Message) -> Ticket:
        # NOTE to self re "projects": TicketManager.create supports a project ID
        # Need to find a way to pass it in.
        ticket = self.ticket_mgr.create(user, message)
        # check user status, reject the ticket if blocked
        if self.user_mgr.is_blocked(user):
            log.debug(f"Rejecting ticket #{ticket.id} based on blocked user {user.login}")
            ticket = self.ticket_mgr.reject_ticket(ticket.id)
        return ticket

    def find_ticket_from_str(self, string:str) -> Ticket:
        """parse a ticket number from a string and get the associated ticket"""
        # for now, this is a trivial REGEX to match '#nnn' in a string, and return ticket #nnn
        match = re.search(r'#(\d+)', string)
        if match:
            ticket_num = int(match.group(1))
            return self.ticket_mgr.get(ticket_num)
        else:
            log.debug(f"Unable to match ticket number in: {string}")
            return []


    def enable_discord_sync(self, ticket_id, user, note):
        fields = {
            "note": note, #f"Created Discord thread: {thread.name}: {thread.jump_url}",
            "cf_1": "1", # TODO: read from custom fields via
        }

        self.ticket_mgr.update(ticket_id, fields, user.login)
        # currently doesn't return or throw anything
        # todo: better error reporting back to discord
