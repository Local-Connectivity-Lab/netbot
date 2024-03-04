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
from users import UserResult, UserManager
from tickets import TicketManager


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

    def DELETE_create_ticket(self, user, subject, body, attachments=None):
        """create a redmine ticket"""
        # https://www.redmine.org/projects/redmine/wiki/Rest_Issues#Creating-an-issue
        # would need full param handling to pass that thru discord to get to this invocation
        # this would be resolved by a Ticket class to emcapsulate.

        data = {
            'issue': {
                'project_id': SCN_PROJECT_ID, #FIXME hard-coded project ID
                'subject': subject,
                'description': body,
            }
        }

        if attachments and len(attachments) > 0:
            data['issue']['uploads'] = []
            for a in attachments:
                data['issue']['uploads'].append({
                    "token": a.token,
                    "filename": a.name,
                    "content_type": a.content_type,
                })

        response = requests.post(
            url=f"{self.url}/issues.json",
            data=json.dumps(data),
            headers=self.get_headers(user.login),
            timeout=TIMEOUT)

        # check status
        if response.ok:
            root = json.loads(response.text, object_hook= lambda x: SimpleNamespace(**x))
            ticket = root.issue

            # ticket 484 - http://10.10.0.218/issues/484
            # if the user is blocked, "reject" the new ticket
            if self.user_mgr.is_blocked(user):
                log.debug(f"Rejecting ticket #{ticket.id} based on blocked user {user.login}")
                self.reject_ticket(ticket.id)
                return self.get_ticket(ticket.id) # refresh the ticket?
            else:
                return ticket
        else:
            raise RedmineException(
                f"create_ticket failed, status=[{response.status_code}] {response.reason}",
                response.headers['X-Request-Id'])


    def update_ticket(self, ticket_id:str, fields:dict, user_login:str=None):
        """update a redmine ticket"""
        # PUT a simple JSON structure
        data = {
            'issue': {}
        }

        data['issue'] = fields

        response = requests.put(
            url=f"{self.url}/issues/{ticket_id}.json",
            timeout=TIMEOUT,
            data=json.dumps(data),
            headers=self.get_headers(user_login))

        # ASIDE: this is a great example of lint standards that just make the code more difficult
        # to read. There are no good answers for string-too-long.
        log.debug(
            f"update ticket: [{response.status_code}] {response.request.url}, fields: {fields}")

        # check status
        if response.ok:
            # no body, so re-get the updated tickets?
            return self.get_ticket(ticket_id)
        else:
            raise RedmineException(
                f"update_ticket failed, status=[{response.status_code}] {response.reason}",
                response.headers['X-Request-Id'])


    def append_message(self, ticket_id:int, user_login:str, note:str, attachments=None):
        """append a note to a ticket"""
        # PUT a simple JSON structure
        data = {
            'issue': {
                'notes': note,
            }
        }

        # add the attachments
        if attachments and len(attachments) > 0:
            data['issue']['uploads'] = []
            for a in attachments:
                data['issue']['uploads'].append({
                    "token": a.token,
                    "filename": a.name,
                    "content_type": a.content_type,
                })

        r = requests.put(
            url=f"{self.url}/issues/{ticket_id}.json",
            timeout=TIMEOUT,
            data=json.dumps(data),
            headers=self.get_headers(user_login))

        # check status
        if r.status_code == 204:
            # all good
            pass
        elif r.status_code == 403:
            # no access
            #print(f"#### {vars(r)}")
            log.error(f"{user_login} has no access to add note to ticket #{ticket_id}, req-id={r.headers['X-Request-Id']}")
        else:
            log.error(f"append_message, status={r.status_code}: {r.reason}, req-id={r.headers['X-Request-Id']}")
            #TODO throw exception to show update failed, and why


    def upload_file(self, user_id, data, filename, content_type):
        """Upload a file to redmine"""
        # POST /uploads.json?filename=image.png
        # Content-Type: application/octet-stream
        # (request body is the file content)

        headers = {
            'User-Agent': 'netbot/0.0.1', # TODO update to project version, and add version management
            'Content-Type': 'application/octet-stream', # <-- VERY IMPORTANT
            'X-Redmine-API-Key': self.token,
            'X-Redmine-Switch-User': user_id, # Make sure the comment is noted by the correct user
        }

        r = requests.post(
            url=f"{self.url}/uploads.json?filename={filename}",
            timeout=TIMEOUT,
            files={ 'upload_file': (filename, data, content_type) },
            headers=headers)

        # 201 response: {"upload":{"token":"7167.ed1ccdb093229ca1bd0b043618d88743"}}
        if r.status_code == 201:
            # all good, get token
            root = json.loads(r.text, object_hook= lambda x: SimpleNamespace(**x))
            token = root.upload.token
            log.info(f"Uploaded {filename} {content_type}, got token={token}")
            return token
        else:
            #print(vars(r))
            log.error(f"upload_file, file={filename} {content_type}, status={r.status_code}: {r.reason}, req-id={r.headers['X-Request-Id']}")
            # todo throw exception
            #TODO throw exception to show upload failed, and why

    def upload_attachments(self, user_id, attachments):
        """Upload a list of attachments"""
        # uploads all the attachments,
        # sets the upload token for each
        for a in attachments:
            token = self.upload_file(user_id, a.payload, a.name, a.content_type)
            a.set_token(token)




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


    def get_tickets_by(self, user):
        # GET /issues.json?author_id=6
        response = self.query(f"/issues.json?author_id={user.id}")
        if response:
            return response.issues
        else:
            log.debug(f"Unknown user: {user}")
            return None


    def get_ticket(self, ticket_id:int, include_journals:bool = False):
        return self.ticket_mgr.get(ticket_id, include_journals)

    def DELETE_get_ticket(self, ticket_id:int, include_journals:bool = False):
        """get a ticket by ID"""
        if ticket_id is None or ticket_id == 0:
            #log.debug(f"Invalid ticket number: {ticket_id}")
            return None

        query = f"/issues/{ticket_id}.json"
        if include_journals:
            query += "?include=journals" # as per https://www.redmine.org/projects/redmine/wiki/Rest_IssueJournals

        response = self.query(query)
        if response:
            return response.issue
        else:
            log.debug(f"Unknown ticket number: {ticket_id}")
            return None

    #GET /issues.xml?issue_id=1,2
    def get_tickets(self, ticket_ids):
        """get several tickets based on a list of IDs"""
        if ticket_ids is None or len(ticket_ids) == 0:
            log.debug("No ticket numbers supplied to get_tickets.")
            return []

        response = self.query(f"/issues.json?issue_id={','.join(ticket_ids)}&status_id=*&sort={DEFAULT_SORT}")
        log.debug(f"query response: {response}")
        if response is not None and response.total_count > 0:
            return response.issues
        else:
            log.info(f"Unknown ticket numbers: {ticket_ids}")
            return []

    def find_ticket_from_str(self, string:str):
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
        """delete a ticket in redmine. used for testing"""
        # DELETE to /issues/{ticket_id}.json
        response = requests.delete(
            url=f"{self.url}/issues/{ticket_id}.json",
            timeout=TIMEOUT,
            headers=self.get_headers())

        if response.ok:
            log.info(f"remove_ticket {ticket_id}")
        else:
            raise RedmineException(f"remove_ticket failed, status=[{response.status_code}] {response.reason}", response.headers['X-Request-Id'])


    def most_recent_ticket_for(self, email):
        """get the most recent ticket for the user with the given email"""
        # get the user record for the email
        user = self.user_mgr.get_by_name(email)

        if user:
            # query open tickets created by user, sorted by most recently updated, limit 1
            response = self.query(f"/issues.json?author_id={user.id}&status_id=open&sort=updated_on:desc&limit=1")

            if response.total_count > 0:
                return response.issues[0]
            else:
                log.info(f"No recent open ticket found for: {user}")
                return None
        else:
            log.warning(f"Unknown email: {email}")
            return None

    def new_tickets_since(self, timestamp:dt.datetime):
        """get new tickets since provided timestamp"""
        # query for new tickets since date
        # To fetch issues created after a certain timestamp (uncrypted filter is ">=2014-01-02T08:12:32Z") :
        # GET /issues.xml?created_on=%3E%3D2014-01-02T08:12:32Z
        timestr = dt.datetime.isoformat(timestamp) # time-format.
        query = f"/issues.json?created_on=%3E%3D{timestr}&sort={DEFAULT_SORT}&limit=100"
        response = self.query(query)

        if response.total_count > 0:
            return response.issues
        else:
            log.debug(f"No tickets created since {timestamp}")
            return None


    def find_tickets(self):
        """default ticket query"""
        # "kanban" query: all ticket open or closed recently
        project=1
        tracker=4
        query = f"/issues.json?project_id={project}&tracker_id={tracker}&status_id=*&sort={DEFAULT_SORT}&limit=100"
        response = self.query(query)

        return response.issues

    def my_tickets(self, user=None):
        """get my tickets"""
        response = self.query(f"/issues.json?assigned_to_id=me&status_id=open&sort={DEFAULT_SORT}&limit=100", user)

        if response.total_count > 0:
            return response.issues
        else:
            log.info("No open ticket for me.")
            return None

    def tickets_for_team(self, team_str:str):
        # validate team?
        team = self.user_mgr.get_by_name(team_str) # find_user is dsigned to be broad

        query = f"/issues.json?assigned_to_id={team.id}&status_id=open&sort={DEFAULT_SORT}&limit=100"
        response = self.query(query)

        if response.total_count > 0:
            return response.issues
        else:
            log.info(f"No open ticket found for: {team}")
            return None

    def search_tickets(self, term):
        """search all text of all tickets (not just open) for the supplied terms"""
        # todo url-encode term?
        # note: sort doesn't seem to be working for search
        query = f"/search.json?q={term}&issues=1&limit=100&sort={DEFAULT_SORT}"

        response = self.query(query)

        ids = []
        for result in response.results:
            ids.append(str(result.id))

        return self.get_tickets(ids)

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

    def DELETE_get_notes_since(self, ticket_id, timestamp=None):
        notes = []

        ticket = self.get_ticket(ticket_id, include_journals=True)
        log.debug(f"got ticket {ticket_id} with {len(ticket.journals)} notes")

        for note in ticket.journals:
            # note.notes is a text field with notes, or empty. if there are no notes, ignore the journal
            if note.notes and timestamp:
                created = synctime.parse_str(note.created_on)
                if created > timestamp:
                    notes.append(note)
            elif note.notes:
                notes.append(note) # append all notes when there's no timestamp

        return notes


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
