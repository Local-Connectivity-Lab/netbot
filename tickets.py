#!/usr/bin/env python3
"""redmine ticket handling"""

import datetime as dt
import logging
import re
import json

from dataclasses import dataclass

from session import RedmineSession, RedmineException
from users import CustomField, User, Team, NamedId
import synctime


log = logging.getLogger(__name__)


ISSUES_RESOURCE="/issues.json"
ISSUE_RESOURCE="/issues/"
DEFAULT_SORT = "status:desc,priority:desc,updated_on:desc"
SCN_PROJECT_ID = 1  # could lookup scn in projects
SYNC_FIELD_NAME = "syncdata"


@dataclass
class TicketStatus():
    """status of a ticket"""
    id: int
    name: str
    is_closed: bool


@dataclass
class PropertyChange(): # https://www.redmine.org/projects/redmine/wiki/Rest_IssueJournals
    """a documented change in a single property"""
    property: str
    name: str
    old_value: str
    new_value: str


@dataclass
class TicketNote(): # https://www.redmine.org/projects/redmine/wiki/Rest_IssueJournals
    """a message sent to a ticket"""
    id: int
    user: NamedId
    notes: str
    created_on: dt.datetime
    private_notes: bool
    details: list[PropertyChange]

    def __post_init__(self):
        self.user = NamedId(**self.user)
        self.created_on = synctime.parse_str(self.created_on)
        if self.details:
            self.details = [PropertyChange(**change) for change in self.details]


@dataclass
class Ticket():
    """Encapsulates a redmine ticket"""
    id: int
    project: NamedId
    tracker: NamedId
    status: TicketStatus
    priority: NamedId
    author: NamedId
    subject: str
    description: str
    done_ratio: float
    is_private: bool
    estimated_hours: float
    total_estimated_hours: float
    start_date: dt.date
    due_date: dt.date
    created_on: dt.datetime
    updated_on: dt.datetime
    closed_on: dt.datetime
    spent_hours: float = 0.0
    total_spent_hours: float = 0.0
    assigned_to: NamedId = None
    custom_fields: list[CustomField] = None
    journals: list[TicketNote] = None

    def __post_init__(self):
        self.status = TicketStatus(**self.status)
        self.author = NamedId(**self.author)
        if self.created_on:
            self.created_on = synctime.parse_str(self.created_on)
        if self.updated_on:
            self.updated_on = synctime.parse_str(self.updated_on)
        if self.closed_on:
            self.closed_on = synctime.parse_str(self.closed_on)
        if self.start_date:
            self.start_date = synctime.parse_str(self.start_date)
        if self.due_date:
            self.due_date = synctime.parse_str(self.due_date)
        if self.custom_fields:
            self.custom_fields = [CustomField(**field) for field in self.custom_fields]
        if self.journals:
            self.journals = [TicketNote(**note) for note in self.journals]

    def get_custom_field(self, name: str) -> str:
        if self.custom_fields:
            for field in self.custom_fields:
                if field.name == name:
                    return field.value
        return None

    def get_sync_record(self, expected_channel: int) -> synctime.SyncRecord:
        # Parse custom_field into datetime
        # lookup field by name
        token = self.get_custom_field(SYNC_FIELD_NAME)
        #log.info(f"### found '{token}' for #{self.id}:{SYNC_FIELD_NAME}")
        #log.info(f"### custom field: {self.custom_fields}")
        if token:
            record = synctime.SyncRecord.from_token(self.id, token)
            log.debug(f"created sync_rec from token: {record}")
            if record:
                # check channel
                if record.channel_id == 0:
                    # no valid channel set in sync data, assume lagacy
                    record.channel_id = expected_channel
                    # update the record in redmine after adding the channel info
                    # self.update_sync_record(record) REALLY needed? should be handled when token created
                    return record
                elif record.channel_id != expected_channel:
                    log.debug(f"channel mismatch: rec={record.channel_id} =/= {expected_channel}, token={token}")
                    return None
                else:
                    return record
        else:
            # no token implies not-yet-initialized
            record = synctime.SyncRecord(self.id, expected_channel, synctime.epoch_datetime())
            # apply the new sync record back to redmine
            # self.update_sync_record(record) same REALLY as above ^^^^
            log.debug(f"created new sync record, none found: {record}")
            return record


    def get_notes(self, since:dt.datetime=None) -> list[TicketNote]:
        notes = []

        for note in self.journals:
            # note.notes is a text field with notes, or empty. if there are no notes, ignore the journal
            if note.notes:
                if not since or since < note.created_on:
                    notes.append(note)

        return notes

    def get_field(self, fieldname):
        return getattr(self, fieldname)



@dataclass
class TicketsResult:
    """Encapsulates a set of tickets"""
    total_count: int
    limit: int
    offset: int
    issues: list[Ticket]


    def __post_init__(self):
        if self.issues:
            self.issues = [Ticket(**ticket) for ticket in self.issues]


class TicketManager():
    """manage redmine tickets"""
    def __init__(self, session: RedmineSession):
        self.session: RedmineSession = session


    def create(self, user:User, subject, body, attachments=None) -> Ticket:
        """create a redmine ticket"""
        # https://www.redmine.org/projects/redmine/wiki/Rest_Issues#Creating-an-issue
        # would need full param handling to pass that thru discord to get to this invocation
        # this would be resolved by a Ticket class to emcapsulate.

        data = {
            'issue': {
                'project_id': SCN_PROJECT_ID, #FIXME hard-coded project ID MOVE project ID to API
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

        response = self.session.post(ISSUES_RESOURCE, json.dumps(data), user.login)

        # check status
        if response:
            return Ticket(**response['issue'])
        else:
            raise RedmineException(
                f"create_ticket failed, status=[{response.status_code}] {response.reason}",
                response.headers['X-Request-Id'])


    def update(self, ticket_id:str, fields:dict, user_login:str=None) -> Ticket:
        """update a redmine ticket"""
        # PUT a simple JSON structure
        data = {
            'issue': {}
        }

        data['issue'] = fields

        response = self.session.put(f"{ISSUE_RESOURCE}{ticket_id}.json", json.dumps(data), user_login)
        if response:
            # no body, so re-get the updated tickets?
            return self.get(ticket_id)


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

        self.session.put(f"{ISSUE_RESOURCE}{ticket_id}.json", json.dumps(data), user_login)
        # no return, excepion thrown in case of failure


    def upload_file(self, user:User, data, filename:str, content_type) -> str:
        """Upload a file to redmine"""
        return self.session.upload_file(user.login, data, filename, content_type)


    def upload_attachments(self, user:User, attachments):
        """Upload a list of attachments"""
        # uploads all the attachments,
        # sets the upload token for each
        for a in attachments:
            token = self.upload_file(user, a.payload, a.name, a.content_type)
            a.set_token(token)


    def get_tickets_by(self, user) -> list[Ticket]:
        # GET /issues.json?author_id=6
        response = self.session.get(f"/issues.json?author_id={user.id}")
        if response:
            result = TicketsResult(**response)
            return result.issues
        else:
            log.debug(f"Unknown user: {user}")
            return None


    def get(self, ticket_id:int, include_journals:bool = False) -> Ticket:
        """get a ticket by ID"""
        if ticket_id is None or ticket_id == 0:
            #log.debug(f"Invalid ticket number: {ticket_id}")
            return None

        query = f"/issues/{ticket_id}.json"
        if include_journals:
            query += "?include=journals" # as per https://www.redmine.org/projects/redmine/wiki/Rest_IssueJournals

        response = self.session.get(query)
        if response:
            return Ticket(**response['issue'])
        else:
            log.debug(f"Unknown ticket number: {ticket_id}")
            return None


    #GET /issues.json?issue_id=1,2
    def get_tickets(self, ticket_ids: list[int]) -> list[Ticket]:
        """get several tickets based on a list of IDs"""
        if ticket_ids is None or len(ticket_ids) == 0:
            log.debug("No ticket numbers supplied to get_tickets.")
            return []

        response = self.session.get(f"/issues.json?issue_id={','.join(map(str, ticket_ids))}&status_id=*&sort={DEFAULT_SORT}")
        log.debug(f"query response: {response}")
        if response:
            result = TicketsResult(**response)
            if result.total_count > 0:
                return result.issues
            else:
                return []

        else:
            log.info(f"Unknown ticket numbers: {ticket_ids}")
            return []

    def find_ticket_from_str(self, string:str):
        """parse a ticket number from a string and get the associated ticket"""
        # for now, this is a trivial REGEX to match '#nnn' in a string, and return ticket #nnn
        match = re.search(r'#(\d+)', string)
        if match:
            ticket_num = int(match.group(1))
            return self.get(ticket_num)
        else:
            log.debug(f"Unable to match ticket number in: {string}")
            return []


    def remove(self, ticket_id:int) -> None:
        """delete a ticket in redmine. used for testing"""
        # DELETE to /issues/{ticket_id}.json
        self.session.delete(f"/issues/{ticket_id}.json")


    def most_recent_ticket_for(self, user:User) -> Ticket:
        """get the most recent ticket for the user with the given email"""
        # get the user record for the email
        if not user:
            return None

        # query open tickets created by user, sorted by most recently updated, limit 1
        response = self.session.get(f"/issues.json?author_id={user.id}&status_id=open&sort=updated_on:desc&limit=1")
        if response:
            return TicketsResult(**response)
        else:
            log.info(f"No recent open ticket found for: {user}")
            return None


    def new_tickets_since(self, timestamp:dt.datetime):
        """get new tickets since provided timestamp"""
        # query for new tickets since date
        # To fetch issues created after a certain timestamp (uncrypted filter is ">=2014-01-02T08:12:32Z") :
        # GET /issues.xml?created_on=%3E%3D2014-01-02T08:12:32Z
        timestr = dt.datetime.isoformat(timestamp) # time-format.
        query = f"/issues.json?created_on=%3E%3D{timestr}&sort={DEFAULT_SORT}&limit=100"
        response = self.session.get(query)

        if response.total_count > 0:
            return response.issues
        else:
            log.debug(f"No tickets created since {timestamp}")
            return None


    def find_tickets(self) -> list[Ticket]:
        """default ticket query"""
        # "kanban" query: all ticket open or closed recently
        project=1
        tracker=4
        query = f"/issues.json?project_id={project}&tracker_id={tracker}&status_id=*&sort={DEFAULT_SORT}&limit=100"
        response = self.session.get(query)
        return TicketsResult(**response).issues


    def my_tickets(self, user=None) -> list[Ticket]:
        """get my tickets"""
        jresp = self.session.get(f"/issues.json?assigned_to_id=me&status_id=open&sort={DEFAULT_SORT}&limit=100", user)

        if not jresp:
            return None

        response = TicketsResult(**jresp)
        if response.total_count > 0:
            return response.issues
        else:
            log.info("No open ticket for me.")
            return None


    def tickets_for_team(self, team:Team) -> list[Ticket]:
        # validate team?
        #team = self.user_mgr.get_by_name(team_str) # find_user is dsigned to be broad
        response = self.session.get(f"/issues.json?assigned_to_id={team.id}&status_id=open&sort={DEFAULT_SORT}&limit=100")

        if not response:
            return None

        result = TicketsResult(**response)
        if result.total_count > 0:
            return result.issues
        else:
            log.info("No open ticket for me.")
            return None


    def search(self, term) -> list[Ticket]:
        """search all text of all tickets (not just open) for the supplied terms"""
        # todo url-encode term?
        # note: sort doesn't seem to be working for search
        query = f"/search.json?q={term}&issues=1&limit=100&sort={DEFAULT_SORT}"

        response = self.session.get(query)
        if not response:
            return None

        # the response has only IDs....
        log.debug(f"SEARCH {response}")
        ids = [result['id'] for result in response['results']]
        # but there's a call to get several tickets
        return self.get_tickets(ids)


    def match_subject(self, subject):
        # todo url-encode term?
        # note: sort doesn't seem to be working for search
        query = f"/search.json?q={subject}&all_words=1&titles_only=1&open_issues=1&limit=100"

        response = self.session.get(query)
        if not response:
            return None

        # the response has only IDs....
        ids = [result['id'] for result in response['results']]
        # but there's a call to get several tickets
        return self.get_tickets(ids)


    def get_notes_since(self, ticket_id:int, timestamp:dt.datetime=None) -> list[TicketNote]:
        # get the ticket, with journals
        ticket = self.get(ticket_id, include_journals=True)
        log.debug(f"got ticket {ticket_id} with {len(ticket.journals)} notes")
        return ticket.get_notes(since=timestamp)


    def enable_discord_sync(self, ticket_id, user, note):
        fields = {
            "note": note, #f"Created Discord thread: {thread.name}: {thread.jump_url}",
            "cf_1": "1",
        }

        self.update(ticket_id, fields, user.login)
        # currently doesn't return or throw anything
        # todo: better error reporting back to discord


    def assign_ticket(self, ticket_id, user:User, user_id=None):
        fields = {
            "assigned_to_id": user.id,
            #"status_id": "1", # New
        }
        if user_id is None:
            # use the user-id to self-assign
            user_id = user.login
        self.update(ticket_id, fields, user_id)


    def progress_ticket(self, ticket_id, user_id=None): # TODO notes
        fields = {
            "assigned_to_id": "me",
            "status_id": "2", # "In Progress"
        }
        self.update(ticket_id, fields, user_id)


    def reject_ticket(self, ticket_id, user_id=None): # TODO notes
        fields = {
            "assigned_to_id": "",
            "status_id": "5", # "Reject"
        }
        self.update(ticket_id, fields, user_id)


    def unassign_ticket(self, ticket_id, user_id=None):
        fields = {
            "assigned_to_id": "", # FIXME this *should* be the team it was assigned to, but there's no way to calculate.
            "status_id": "1", # New
        }
        self.update(ticket_id, fields, user_id)


    def resolve_ticket(self, ticket_id, user_id=None):
        self.update(ticket_id, {"status_id": "3"}, user_id) # '3' is the status_id, it doesn't accept "Resolved"


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
        self.update(record.ticket_id, fields)


    def get_updated_field(self, ticket) -> dt.datetime:
        return synctime.parse_str(ticket.updated_on)


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
