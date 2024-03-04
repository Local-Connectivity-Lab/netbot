#!/usr/bin/env python3
"""redmine client"""

import os
import re
import json
import logging
import datetime as dt
from types import SimpleNamespace

import requests
from dotenv import load_dotenv

import synctime
from session import RedmineSession
from users import User, UserResult, UserManager
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


    ## FIXME user logic
    def lookup_user(self, username:str):
        """Get a user based on ID, directly from redmine"""
        if username is None or len(username) == 0:
            log.debug("Empty user ID")
            return None

        response = requests.get(f"{self.url}/users.json?name={username}",
                                headers=self.get_headers(), timeout=TIMEOUT)
        if response.ok:
            user_result = UserResult(**response.json())
            log.debug(f"lookup_user: {username} -> {user_result.users}")

            if user_result.total_count == 1:
                return user_result.users[0]
            elif user_result.total_count > 1:
                log.warning(f"Too many results for {username}: {user_result.users}")
                return user_result.users[0]
            else:
                log.debug(f"Unknown user: {username}")
                return None


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
        # todo url-encode term?
        # note: sort doesn't seem to be working for search
        query = f"/search.json?q={subject}&all_words=1&titles_only=1&open_issues=1&limit=100"

        response = self.query(query)

        if response:
            ids = []
            for result in response.results:
                ids.append(str(result.id))

            return self.get_tickets(ids)
        else:
            log.debug(f"subject matched nothing: {subject}")
            return []


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


    def join_team(self, username, teamname:str) -> None:
        user = self.user_mgr.get_by_name(username)
        self.user_mgr.join_team(user, teamname)


    def leave_team(self, username:int, teamname:str) -> None:
        # look up user ID
        user = self.user_mgr.get_by_name(username)
        if user is None:
            log.warning(f"Unknown user name: {username}")
            return None

        # map teamname to team
        #team = self.user_mgr.get_team_by_name(teamname)
        #if team is None:
        #    log.warning(f"Unknown team name: {teamname}")
        #    return None

        self.user_mgr.leave_team(user, teamname)


    def get_headers(self, impersonate_id:str=None):
        headers = {
            'User-Agent': 'netbot/0.0.1', # TODO update to project version, and add version management
            'Content-Type': 'application/json',
            'X-Redmine-API-Key': self.token,
        }
        # insert the impersonate_id to impersonate another user
        if impersonate_id:
            headers['X-Redmine-Switch-User'] = impersonate_id # Make sure the comment is noted by the correct user
            log.debug(f"setting redmine impersonation flag for user={impersonate_id}")
        return headers


    def query(self, query_str:str, user:str=None):
        """run a query against a redmine instance"""

        headers = self.get_headers(user)

        # TODO Detect and handle paged results

        try:
            r = requests.get(f"{self.url}{query_str}", headers=headers, timeout=TIMEOUT)

            # check 200 status code
            if r.ok:
                # return the parsed the JSON text
                return json.loads(r.text, object_hook=lambda x: SimpleNamespace(**x))
            else:
                log.error(f"Status code {r.status_code} for {r.request.url}, reqid={r.headers['X-Request-Id']}: {r}")
        except TimeoutError as toe:
            # ticket-509: Handle timeout gracefully
            log.warning(f"Timeout during {query_str}: {toe}")
        except Exception as ex:
            log.warning(f"Excetion during {query_str}: {ex}")

        return None


    def assign_ticket(self, ticket_id, target, user_id=None):
        user = self.user_mgr.get_by_name(target)
        if user:
            fields = {
                "assigned_to_id": user.id,
                #"status_id": "1", # New
            }
            if user_id is None:
                # use the user-id to self-assign
                user_id = user.login
            self.update_ticket(ticket_id, fields, user_id)
        else:
            log.error(f"unknow user: {target}")


    def progress_ticket(self, ticket_id, user_id=None): # TODO notes
        fields = {
            "assigned_to_id": "me",
            "status_id": "2", # "In Progress"
        }
        self.update_ticket(ticket_id, fields, user_id)


    def reject_ticket(self, ticket_id, user_id=None): # TODO notes
        fields = {
            "assigned_to_id": "",
            "status_id": "5", # "Reject"
        }
        self.update_ticket(ticket_id, fields, user_id)


    def unassign_ticket(self, ticket_id, user_id=None):
        fields = {
            "assigned_to_id": "", # FIXME this *should* be the team it was assigned to, but there's no way to calculate.
            "status_id": "1", # New
        }
        self.update_ticket(ticket_id, fields, user_id)


    def resolve_ticket(self, ticket_id, user_id=None):
        self.update_ticket(ticket_id, {"status_id": "3"}, user_id) # '3' is the status_id, it doesn't accept "Resolved"


    def get_team(self, teamname:str):
        return self.user_mgr.get_team_by_name(teamname) # FIXME consistent naming


    def get_sync_record(self, ticket, expected_channel: int) -> synctime.SyncRecord:
        # Parse custom_field into datetime
        # lookup field by name
        token = None
        try :
            for field in ticket.custom_fields:
                if field.name == SYNC_FIELD_NAME:
                    token = field.value
                    log.debug(f"found {field.name} => '{field.value}'")
                    break
        except AttributeError:
            # custom_fields not set, handle same as no sync field
            pass

        if token:
            record = synctime.SyncRecord.from_token(ticket.id, token)
            log.debug(f"created sync_rec from token: {record}")
            if record:
                # check channel
                if record.channel_id == 0:
                    # no valid channel set in sync data, assume lagacy
                    record.channel_id = expected_channel
                    # update the record in redmine after adding the channel info
                    self.update_sync_record(record)
                    return record
                elif record.channel_id != expected_channel:
                    log.debug(f"channel mismatch: rec={record.channel_id} =/= {expected_channel}, token={token}")
                    return None
                else:
                    return record
        else:
            # no token implies not-yet-initialized
            record = synctime.SyncRecord(ticket.id, expected_channel, synctime.epoch_datetime())
            # apply the new sync record back to redmine
            self.update_sync_record(record)
            return record


    def update_sync_record(self, record:synctime.SyncRecord):
        log.debug(f"Updating sync record in redmine: {record}")
        fields = {
            "custom_fields": [
                { "id": 4, "value": record.token_str() } # cf_4, custom field syncdata, #TODO search for it
            ]
        }
        self.update_ticket(record.ticket_id, fields)


    # NOTE: This implies that ticket should be a full object with methods.
    # Starting to move fields out to their own methods, to eventually move to
    # their own Ticket class.
    def get_field(self, ticket, fieldname):
        try:
            match fieldname:
                case "id":
                    return f"{ticket.id}"
                case "url":
                    return f"{self.url}/issues/{ticket.id}"
                case "link":
                    return f"[{ticket.id}]({self.url}/issues/{ticket.id})"
                case "priority":
                    return ticket.priority.name
                case "updated":
                    return ticket.updated_on # string, or dt?
                case "assigned":
                    return ticket.assigned_to.name
                case "status":
                    return ticket.status.name
                case "subject":
                    return ticket.subject
                case "title":
                    return ticket.title
                #case "age":
                #    updated = dt.datetime.fromisoformat(ticket.updated_on) ### UTC
                #    age = dt.datetime.now(dt.timezone.utc) - updated
                #    return humanize.naturaldelta(age)
                #case "sync":
                #    try:
                #        # Parse custom_field into datetime
                #        # FIXME: this is fragile: relies on specific index of custom field, add custom field lookup by name
                #        timestr = ticket.custom_fields[1].value
                #        return dt.datetime.fromisoformat(timestr) ### UTC
                #    except Exception as e:
                #        log.debug(f"sync tag not set")
                #        return None
        except AttributeError:
            return "" # or None?




if __name__ == '__main__':
    # load credentials
    load_dotenv()

    # construct the client and run the email check
    client = Client.fromenv()
    tickets = client.find_tickets()
    client.format_report(tickets)
