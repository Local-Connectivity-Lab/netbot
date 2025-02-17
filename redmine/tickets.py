#!/usr/bin/env python3
"""redmine ticket handling"""

import datetime as dt
import logging
import re
import json
import urllib.parse

from redmine.model import TO_CC_FIELD_NAME, User, Message, NamedId, Team, Ticket, TicketNote, TicketsResult, SYNC_FIELD_NAME
from redmine.session import RedmineSession, RedmineException
from redmine import synctime


log = logging.getLogger(__name__)


ISSUES_RESOURCE="/issues.json"
ISSUE_RESOURCE="/issues/"
DEFAULT_SORT = "status:desc,priority:desc,updated_on:desc"
SCN_PROJECT_ID = 1 # could lookup scn in projects
INTAKE_TEAM = "ticket-intake"
INTAKE_TEAM_ID = 19 # FIXME
EPIC_PRIORITY_NAME = "EPIC"


TICKET_DUSTY_AGE = 7 # days
TICKET_MAX_AGE = 7 * 3 # 3 weeks; 21 days
#TICKET_EXPIRE_NOTIFY = TICKET_MAX_AGE - 1 # 20 days, one day shorter than MAX_AGE


class TicketManager():
    """manage redmine tickets"""
    def __init__(self, session: RedmineSession, default_project:int):
        self.session: RedmineSession = session
        self.priorities = {}
        self.trackers = {}
        self.custom_fields = {}
        self.default_project:int = default_project

        self.reindex()


    def reindex(self):
        self.priorities = self.load_priorities()
        self.trackers = self.load_trackers()
        self.custom_fields = self.load_custom_fields()


    def sanity_check(self) -> dict[str, bool]:
        subsystems: dict[str, bool] = {}

        subsystems['default_project'] = self.default_project > 0
        subsystems['priorities'] = self.get_priority(EPIC_PRIORITY_NAME) is not None
        # todo trackers
        # todo custom fields

        return subsystems


    def load_custom_fields(self) -> dict[str,NamedId]:
        # call redmine to get the ticket custom fields
        fields_response = self.session.get("/custom_fields.json")
        if fields_response and 'custom_fields' in fields_response:
            fields = {}
            for field in fields_response['custom_fields']:
                fields[field['name']] = NamedId(id=field['id'], name=field['name'])
            return fields
        else:
            log.error("No custom fields.")


    def get_custom_field(self, name:str) -> NamedId | None:
        return self.custom_fields.get(name, None)


    def load_priorities(self) -> dict[str,NamedId]:
        """load active priorities"""

        # Note: This relies on py3.7 insertion-ordered hashtables
        priorities: dict[str,NamedId] = {}

        resp = self.session.get("/enumerations/issue_priorities.json")
        for priority in reversed(resp['issue_priorities']):
            if priority.get('active', False):
                priorities[priority['name']] = NamedId(priority['id'], priority['name'])

        return priorities


    def get_priority(self, name:str) -> NamedId | None:
        return self.priorities.get(name, None)


    def get_priorities(self) -> dict[str,NamedId]:
        return self.priorities


    def load_trackers(self) -> dict[str,NamedId]:
        # call redmine to get the ticket trackers
        response = self.session.get("/trackers.json")
        if response:
            trackers = {}
            for item in response['trackers']:
                trackers[item['name']] = NamedId(id=item['id'], name=item['name'])
            return trackers
        else:
            log.warning("No trackers to load")


    def get_tracker(self, name:str) -> NamedId | None:
        return self.trackers.get(name, None)


    def get_trackers(self) -> dict[str,NamedId]:
        return self.trackers


    def create(self, user: User, message: Message, project_id: int = None, **params) -> Ticket:
        """create a redmine ticket"""
        # https://www.redmine.org/projects/redmine/wiki/Rest_Issues#Creating-an-issue
        # would need full param handling to pass that thru discord to get to this invocation
        # this would be resolved by a Ticket class to emcapsulate.

        # check default project
        if not project_id:
            project_id = self.default_project

        data = {
            'issue': {
                'project_id': project_id,
                'subject': message.subject,
                'description': message.note,
                # ticket-485: adding custom field for To//Cc headers.
                # where '//' is the separater.
                'custom_fields': [
                    {
                        'id': self.get_custom_field(TO_CC_FIELD_NAME).id,
                        'value': message.to_cc_str(),
                    }
                ]
            }
        }

        if params:
            data['issue'].update(params)
            log.debug(f"added params to new ticket, ticket={data['issue']}")

        if message.attachments and len(message.attachments) > 0:
            data['issue']['uploads'] = []
            for a in message.attachments:
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


    def update(self, ticket_id:int, fields:dict[str,str], user_login:str|None=None) -> Ticket|None:
        """update a redmine ticket"""
        # PUT a simple JSON structure
        data = {
            'issue': fields
        }

        self.session.put(f"{ISSUE_RESOURCE}{ticket_id}.json", json.dumps(data), user_login)
        return self.get(ticket_id)


    def append_message(self, ticket_id:int, user_login:str, note:str, attachments=None):
        """append a note to a ticket"""
        # PUT a simple JSON structure
        data:dict = {
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


    def get_by(self, user) -> list[Ticket]:
        # GET /issues.json?author_id=6
        response = self.session.get(f"/issues.json?author_id={user.id}")
        if response:
            result = TicketsResult(**response)
            return result.issues
        else:
            log.debug(f"Unknown user: {user}")
            return None

    def get(self, ticket_id:int, **params) -> Ticket|None:
        """get a ticket by ID"""
        if ticket_id is None or ticket_id == 0:
            #log.debug(f"Invalid ticket number: {ticket_id}")
            return None

        query = f"/issues/{ticket_id}.json?{urllib.parse.urlencode(params)}"
        log.debug(f"getting #{ticket_id} with {query}")

        response = self.session.get(query)
        if response:
            ticket = Ticket(**response['issue'])

            # check for special case: the SubTickets in the
            # response (if requested at all) don't container enough info
            # if there are children, make a seperate query for
            # "all the children of ticket X"
            # check to replace placeholder child tickets
            #if "include" in params and "children" in params["include"]:
            if ticket.children and len(ticket.children) > 0:
                children = self.tickets(parent_id=ticket.id, status_id="*")
                if children and len(children) > 0:
                    ticket.children = children

            return ticket
        else:
            log.debug(f"Unknown ticket number: {ticket_id}, params:{params}")
            return None


    #GET /issues.json?issue_id=1,2
    def get_tickets(self, ticket_ids: list[int], **params) -> list[Ticket]:
        """get several tickets based on a list of IDs"""
        if ticket_ids is None or len(ticket_ids) == 0:
            log.debug("No ticket numbers supplied to get_tickets.")
            return []

        # status_id=* is "get open and closed tickets"
        url_str = f"/issues.json?issue_id={','.join(map(str, ticket_ids))}&status_id=*&sort={DEFAULT_SORT}"
        if len(params) > 0:
            url_str += "&" + urllib.parse.urlencode(params)
        log.debug(f"QUERY: {url_str}")
        response = self.session.get(url_str)
        if response:
            result = TicketsResult(**response)
            if result.total_count > 0:
                return result.issues
            else:
                return []

        else:
            log.info(f"Unknown ticket numbers: {ticket_ids}")
            return []


    def get_epics(self) -> list[Ticket]:
        """Get all the open epics, organized by tracker"""
        # query tickets pri = epic
        epic_priority = self.get_priority(EPIC_PRIORITY_NAME)

        if not epic_priority:
            # very unexpected
            log.error(f"Cannot find expected {EPIC_PRIORITY_NAME} priority! Can't find epics!")
            log.debug(f"known priorities: {self.priorities}")
            return []

        epics = self.tickets(priority_id=epic_priority.id, limit=10, sort=DEFAULT_SORT)
        for epic in epics:
            # get the sub-tickets for the epic (both open and closed)
            children = self.tickets(parent_id=epic.id, status_id="*")
            if children and len(children) > 0:
                epic.children = children

        return epics


    def recycle(self, ticket:Ticket, team: Team):
        """Recycle a dusty ticket:
        - reassign to tracker-based team
        - set status to new
        - add note to owner and collaborators
        """
        # note: there's no way to get the owner's details (like discord ID)
        # without accessing user manager. "owner" only provide ID and "name" (not unique login str)
        # ID can be resolved to discord-id, but not without call in user manager.
        # Ideally, this would @ the owner and collaborators.
        fields = {
            "assigned_to_id": f"{team.id}",
            "status_id": "1", # New, TODO lookup using status lookup table.
            "notes": f"Ticket automatically recycled after {TICKET_MAX_AGE} days due to inactivity.",
        }
        log.info(f"Recycling ticket {ticket.id}, {ticket.age_str}")
        return self.update(ticket.id, fields)


    # def expiring_tickets(self) -> list[Ticket]:
    #     # tickets that are about to expire
    #     tickets = set()
    #     #tickets.update(self.older_than(TICKET_EXPIRE_NOTIFY))
    #     tickets.update(self.due()) ### FIXME REMOVE
    #     return tickets


    def dusty(self) -> set[Ticket]:
        # tickets that are older than 7

        # http://localhost/projects/scn/issues.json?v[status_id][]=2&op[updated_on]=%3Ct-&v[updated_on][]=7
        #"status_id": "2"
        #query = f"/issues.json?status_id=2&op[updated_on]=%3Ct-&v[updated_on][]=7&op[priority_id]=!&v[priority_id][]=14&include=children"
        query = "/issues.json?set_filter=1&sort=id%3Adesc&f[]=priority_id&op[priority_id]=!&v[priority_id][]=14&f[]=status_id&op[status_id]=%3D&v[status_id][]=2&f[]=updated_on&op[updated_on]=%3Ct-&v[updated_on][]=7&f[]=&c[]=tracker&c[]=status&c[]=priority&c[]=subject&c[]=assigned_to&c[]=updated_on&group_by=&t[]="
        response = self.session.get(query)
        if response:
            return TicketsResult(**response).issues
        else:
            return []


    def recyclable(self) -> set[Ticket]:
        # tickets that have expired: older that TICKET_MAX_AGE
        tickets = set()
        tickets.update(self.older_than(TICKET_MAX_AGE))
        return tickets


    def older_than(self, days_old: int) -> list[Ticket]:
        """Get all the open tickets that haven't been updated
        in day_old days.
        """
        # before a certain date (uncrypted filter is "<= 2012-03-07") :
        # GET /issues.json?created_on=%3C%3D2012-03-07

        since = synctime.now() - dt.timedelta(days=days_old) # day_ago to a timestamp
        # To fetch issues updated before a certain timestamp (uncrypted filter is "<=2014-01-02T08:12:32Z")
        query = f"/issues.json?updated_on=%3C%3D{synctime.zulu(since)}&include=children"
        response = self.session.get(query)
        if response:
            return TicketsResult(**response).issues
        else:
            return []


    def due(self) -> list[Ticket]:
        """Get all open tickets that are due today or earlier"""
        # To fetch issues updated before a certain timestamp (uncrypted filter is "<=2014-01-02T08:12:32Z")
        query = f"/issues.json?due_date=%3C%3D{synctime.zulu(synctime.now())}"
        log.info(f"QUERY due: {query}")
        response = self.session.get(query)
        return TicketsResult(**response).issues


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
            return []

        response = TicketsResult(**jresp)
        if response.total_count > 0:
            return response.issues
        else:
            log.info("No open ticket for me.")
            return []


    def tickets_for_team(self, team:Team|User) -> list[Ticket]:
        response = self.session.get(f"/issues.json?assigned_to_id={team.id}&status_id=open&sort={DEFAULT_SORT}&limit=100")

        if not response:
            return []

        result = TicketsResult(**response)
        if result.total_count > 0:
            return result.issues
        else:
            log.info(f"No open ticket for {team}: {result}")
            return []


    def tickets(self, **kwargs) -> list[Ticket]:
        response = self.session.get(f"/issues.json?{urllib.parse.urlencode(kwargs)}")
        if not response:
            return []

        result = TicketsResult(**response)
        if result.total_count > 0:
            return result.issues
        else:
            log.debug(f"Zero results for {kwargs}")
            return []


    def search(self, term) -> list[Ticket]:
        """search all text of open tickets for the supplied terms"""
        # todo url-encode term?
        # note: open_issues=1 is open issues only
        query = f"/search.json?q={term}&issues=1&open_issues=1&limit=100"

        response = self.session.get(query)
        if not response:
            log.debug(f"SEARCH FAILED for {query}, zero results")
            return None

        # the response has only IDs....
        ids = [result['id'] for result in response['results']]
        # but there's a call to get several tickets
        return self.get_tickets(ids, include="children") # get sub-ticket IDs when querying tickets


    def match_subject(self, subject) -> list[Ticket]:
        # todo url-encode term?
        # note: sort doesn't seem to be working for search
        query = f"/search.json?q={subject}&all_words=1&titles_only=1&limit=100" #&open_issues=1

        response = self.session.get(query)
        if not response:
            return None

        # the response has only IDs....
        ids = [result['id'] for result in response['results']]
        # but there's a call to get several tickets
        return self.get_tickets(ids)


    def get_notes_since(self, ticket_id:int, timestamp:dt.datetime=None) -> list[TicketNote]:
        # get the ticket, with journals
        ticket = self.get(ticket_id, include="journals")
        log.debug(f"got ticket {ticket_id} with {len(ticket.journals)} notes")
        return ticket.get_notes(since=timestamp)


    def enable_discord_sync(self, ticket_id, user, note):
        fields = {
            "note": note, #f"Created Discord thread: {thread.name}: {thread.jump_url}",
            "cf_1": "1", # TODO: lookup in self.get_field_id
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


    def collaborate(self, ticket_id, user:User, user_id:str=None):
        # assign watcher, see
        # https://www.redmine.org/projects/redmine/wiki/Rest_Issues#Adding-a-watcher
        fields = {
            "user_id": user.id,
        }

        if user_id is None:
            # use the user-id to self-assign
            user_id = user.login

        self.session.post(f"{ISSUE_RESOURCE}{ticket_id}/watchers.json" , json.dumps(fields))


    def progress_ticket(self, ticket_id, user_id=None) -> Ticket:
        fields = {
            "assigned_to_id": "me",
            "status_id": "2", # "In Progress"
        }
        return self.update(ticket_id, fields, user_id)


    def reject_ticket(self, ticket_id, user_id=None) -> Ticket:
        fields = {
            "assigned_to_id": "",
            "status_id": "5", # "Reject"
        }
        return self.update(ticket_id, fields, user_id)


    def unassign(self, ticket_id, user_id=None):
        fields = {
            "assigned_to_id": "",
            "status_id": "1", # New, TODO lookup in status table
        }
        self.update(ticket_id, fields, user_id)


    def resolve(self, ticket_id, user_id=None):
        return self.update(ticket_id, {"status_id": "3"}, user_id) # '3' is the status_id, it doesn't accept "Resolved"


    def update_sync_record(self, record:synctime.SyncRecord):
        log.debug(f"Updating sync record in redmine: {record}")
        fields = {
            "custom_fields": [
                { "id": 4, "value": record.token_str() } # cf_4, custom field syncdata, #TODO see below
            ]
        }
        self.update(record.ticket_id, fields)


    def remove_sync_record(self, record:synctime.SyncRecord):
        field = self.custom_fields[SYNC_FIELD_NAME]
        if field:
            log.debug(f"Removing sync record in redmine: {record}")
            fields = {
                "custom_fields": [
                    { "id": field.id, "value": "" }
                ]
            }
            self.update(record.ticket_id, fields)
            log.debug(f"Removed {SYNC_FIELD_NAME} from ticket {record.ticket_id}")
        else:
            log.error(f"Missing expected custom field: {SYNC_FIELD_NAME}")


    def get_updated_field(self, ticket) -> dt.datetime:
        return synctime.parse_str(ticket.updated_on)


    # NOTE: This implies that ticket should be a full object with methods.
    # Starting to move fields out to their own methods, to eventually move to
    # their own Ticket class.
    def get_field(self, ticket:Ticket, fieldname:str) -> str:
        try:
            match fieldname:
                case "url":
                    return f"{self.url}/issues/{ticket.id}"
                case "link":
                    return f"[{ticket.id}]({self.url}/issues/{ticket.id})"
                case "updated":
                    return str(ticket.updated_on) # formatted string, or dt?
                case _:
                    return str(ticket.get_field(fieldname))
        except AttributeError:
            return None
