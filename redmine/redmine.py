import json
import os
import re
import logging

from redmine.session import RedmineSession
from redmine.model import REDACTOR_FIELD_NAME, Message, Ticket, User, NamedId
from redmine.users import UserManager
from redmine.tickets import TicketManager, SCN_PROJECT_ID


log = logging.getLogger(__name__)


DEFAULT_SORT = "status:desc,priority:desc,updated_on:desc"
TIMEOUT = 10 # seconds
SYNC_FIELD_NAME = "syncdata"
BLOCKED_TEAM_NAME = "blocked"
STATUS_REJECT = 5
DEFAULT_TRACKER = "External-Comms-Intake"
TRACKER_REGEX = re.compile(r"\s*\[([\w-]+)\]\s*")


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

        self.validate_sanity() 

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

        default_project = int(os.getenv("DEFAULT_PROJECT_ID", default=str(SCN_PROJECT_ID)))

        return cls.from_session(RedmineSession(url, token), default_project)


    def reindex(self):
        self.ticket_mgr.reindex()
        self.user_mgr.reindex()


    def sanity_check(self) -> dict[str, bool]:
        sanity = self.ticket_mgr.sanity_check()
        return sanity


    def validate_sanity(self):
        for subsystem, good in self.sanity_check().items():
            log.info(f"- {subsystem}: {good}")
            if not good:
                raise RedmineException(f"Subsystem {subsystem} not loading correctly.")


    def find_tracker_in_message(self, message:Message) -> NamedId:
        tracker = self.find_tracker(message.subject)
        if tracker.name != DEFAULT_TRACKER:
            message.subject = TRACKER_REGEX.sub("", message.subject)
        return tracker


    def find_tracker(self, value:str) -> NamedId:
        tracker_name = DEFAULT_TRACKER
        match = TRACKER_REGEX.search(value)
        if match:
            tracker_name = match.group(1)

        tracker = self.ticket_mgr.get_tracker(tracker_name)
        if tracker:
            return tracker
        else:
            return self.ticket_mgr.get_tracker(DEFAULT_TRACKER)


    def get_default_tracker(self) -> NamedId:
        return self.ticket_mgr.get_tracker(DEFAULT_TRACKER)


    def create_ticket(self, user:User, message:Message) -> Ticket:
        """
        Create a ticket - NO redaction happens here
        Redaction is done in threader before calling this
        """
        project_id = SCN_PROJECT_ID
        tracker = self.find_tracker_in_message(message)

        log.info(f"Creating ticket with project={project_id} and tracker={tracker.id}")
        ticket = self.ticket_mgr.create(user, message, project_id=project_id, tracker_id=tracker.id)

        # check user status, reject the ticket if blocked
        if self.user_mgr.is_blocked(user):
            log.debug(f"Rejecting ticket #{ticket.id} based on blocked user {user.login}")
            ticket = self.ticket_mgr.reject_ticket(ticket.id)

        return ticket


    def unredact_ticket(self, ticket:Ticket) -> Ticket:
        """
        Return ticket with original (unredacted) description
        The description field already contains original text
        """
        # With new architecture:
        # - description = original (unredacted) 
        # - custom field "redacted" = redacted version for Discord
        # So unredact just returns the ticket as-is
        return ticket


    def find_ticket_from_str(self, string:str) -> Ticket:
        """parse a ticket number from a string and get the associated ticket"""
        match = re.search(r'#(\d+)', string)
        if match:
            ticket_num = int(match.group(1))
            return self.ticket_mgr.get(ticket_num)
        else:
            log.debug(f"Unable to match ticket number in: {string}")
            return []