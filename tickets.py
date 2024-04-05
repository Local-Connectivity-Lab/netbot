#!/usr/bin/env python3
"""redmine ticket handling"""

import datetime as dt
import logging
import re
import json
import urllib.parse



from model import TO_CC_FIELD_NAME, User, Message, NamedId, Team, Ticket, TicketNote, TicketsResult
from session import RedmineSession, RedmineException
import synctime


log = logging.getLogger(__name__)


ISSUES_RESOURCE="/issues.json"
ISSUE_RESOURCE="/issues/"
DEFAULT_SORT = "status:desc,priority:desc,updated_on:desc"
SCN_PROJECT_ID = 1  # could lookup scn in projects
INTAKE_TEAM = "ticket-intake"
INTAKE_TEAM_ID = 19 # FIXME


TICKET_MAX_AGE = 4 * 7 # 4 weeks; 28 days
TICKET_EXPIRE_NOTIFY = TICKET_MAX_AGE - 1 # 27 days, one day shorter than MAX_AGE


class TicketManager():
    """manage redmine tickets"""
    def __init__(self, session: RedmineSession):
        self.session: RedmineSession = session
        self.custom_fields = self.load_custom_fields()


    def load_custom_fields(self) -> dict[str,NamedId]:
        # call redmine to get the ticket custom fields
        fields_response = self.session.get("/custom_fields.json")
        if fields_response and 'custom_fields' in fields_response:
            fields = {}
            for field in fields_response['custom_fields']:
                fields[field['name']] = NamedId(id=field['id'], name=field['name'])
            return fields
        else:
            log.warning("No custom fields to load")


    def load_trackers(self) -> dict[str,NamedId]:
        # call redmine to get the ticket trackers
        response = self.session.get("/trackers.json")
        if response:
            trackers = {}
            for item in response['trackers']:
                #print(f"##### {item}")
                trackers[item['name']] = NamedId(id=item['id'], name=item['name'])
            return trackers
        else:
            log.warning("No custom fields to load")


    def get_field_id(self, name:str) -> int | None:
        if name in self.custom_fields:
            return self.custom_fields[name].id
        return None


    def create(self, user: User, message: Message) -> Ticket:
        """create a redmine ticket"""
        # https://www.redmine.org/projects/redmine/wiki/Rest_Issues#Creating-an-issue
        # would need full param handling to pass that thru discord to get to this invocation
        # this would be resolved by a Ticket class to emcapsulate.

        data = {
            'issue': {
                'project_id': SCN_PROJECT_ID, #FIXME hard-coded project ID MOVE project ID to API
                'subject': message.subject,
                'description': message.note,
                # ticket-485: adding custom field for To//Cc headers.
                # where '//' is the separater.
                'custom_fields': [
                    {
                        'id': self.get_field_id(TO_CC_FIELD_NAME),
                        'value': message.to_cc_str(),
                    }
                ]
            }
        }

        if message.attachments and len(message.attachments) > 0:
            data['issue']['uploads'] = []
            for a in message.attachments:
                data['issue']['uploads'].append({
                    "token": a.token,
                    "filename": a.name,
                    "content_type": a.content_type,
                })

        #log.debug(f"POST data: {data}")
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


    def get_tickets_by(self, user) -> list[Ticket]:
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
            return Ticket(**response['issue'])
        else:
            log.debug(f"Unknown ticket number: {ticket_id}, params:{params}")
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


    def expire(self, ticket:Ticket):
        """Expire a ticket:
        - reassign to intake
        - set status to new
        - add note to owner and collaborators
        """
        # note: there's no way to get the owner's details (like discord ID)
        # without accessing user manager. "owner" only provide ID and "name" (not unique login str)
        # ID can be resolved to discord-id, but not without call in user manager.
        # Ideally, this would @ the owner and collaborators.
        fields = {
            "assigned_to_id": INTAKE_TEAM_ID,
            "status_id": "1", # New
            "notes": f"Ticket automatically expired after {TICKET_MAX_AGE} days due to inactivity.",
        }
        self.update(ticket.id, fields)
        log.info(f"Expired ticket {ticket.id}, {ticket.age_str}")


    def expiring_tickets(self) -> list[Ticket]:
        # tickets that are about to expire
        tickets = set()
        tickets.update(self.older_than(TICKET_EXPIRE_NOTIFY))
        tickets.update(self.due()) ### FIXME REMOVE
        return tickets


    def expired_tickets(self) -> set[Ticket]:
        # tickets that have expired: older that TICKET_MAX_AGE
        tickets = set()
        tickets.update(self.older_than(TICKET_MAX_AGE))
        tickets.update(self.due()) ### FIXME REMOVE
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
            return None

        #log.debug(f"### json: {jresp}")
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


    def match_subject(self, subject) -> list[Ticket]:
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
        ticket = self.get(ticket_id, include="journals")
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


    def progress_ticket(self, ticket_id, user_id=None):
        fields = {
            "assigned_to_id": "me",
            "status_id": "2", # "In Progress"
        }
        self.update(ticket_id, fields, user_id)


    def reject_ticket(self, ticket_id, user_id=None) -> Ticket:
        fields = {
            "assigned_to_id": "",
            "status_id": "5", # "Reject"
        }
        return self.update(ticket_id, fields, user_id)


    def unassign_ticket(self, ticket_id, user_id=None):
        fields = {
            "assigned_to_id": INTAKE_TEAM_ID,
            "status_id": "1", # New
        }
        self.update(ticket_id, fields, user_id)


    def resolve_ticket(self, ticket_id, user_id=None):
        self.update(ticket_id, {"status_id": "3"}, user_id) # '3' is the status_id, it doesn't accept "Resolved"


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



def main():
    ticket_mgr = TicketManager(RedmineSession.fromenv())

    #ticket_mgr.expire_expired_tickets()
    #for ticket in ticket_mgr.older_than(7): #ticket_mgr.expired_tickets():
    #    print(synctime.age_str(ticket.updated_on), ticket)
    #print(ticket_mgr.get(105, include_children=True).json_str())
    #print(json.dumps(ticket_mgr.load_custom_fields(), indent=4, default=vars))

    print(ticket_mgr.due())

# for testing the redmine
if __name__ == '__main__':
    # load credentials
    from dotenv import load_dotenv
    load_dotenv()
    logging.basicConfig(level=logging.DEBUG, format="{asctime} {levelname:<8s} {name:<16} {message}", style='{')
    logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)

    main()
