"""
contains all the dataclass and models for redmine
"""

import logging
import dataclasses
from dataclasses import dataclass
import datetime as dt
import re
import json

from redmine import synctime

log = logging.getLogger(__name__)


# Parsing compound forwarded emails messages is more complex than expected, so
# Message will represent everything needed for creating and updating tickets,
# including attachments.
class Attachment():
    """email attachment"""
    def __init__(self, name:str, content_type:str, payload):
        self.name = name
        self.content_type = content_type
        self.payload = payload
        self.token = None

    def upload(self, client, user):
        # FIXME This is messy, move to caller.
        self.token = client.ticket_mgr.upload_file(user, self.payload, self.name, self.content_type)

    def set_token(self, token):
        self.token = token


class Message():
    """email message"""
    from_address: str
    to: str
    cc: str
    subject:str
    attachments: list[Attachment]
    note: str

    def __init__(self, from_addr:str, subject:str, to:str = None, cc:str = None):
        self.from_address = from_addr
        self.subject = subject
        self.to = to
        self.cc = cc
        self.attachments = []
        self.note = ""

    # Note: note containts the text of the message, the body of the email
    def set_note(self, note:str):
        self.note = note

    def add_attachment(self, attachment:Attachment):
        self.attachments.append(attachment)

    def subject_cleaned(self) -> str:
        # strip any re: and forwarded from a subject line
        # from: https://stackoverflow.com/questions/9153629/regex-code-for-removing-fwd-re-etc-from-email-subject
        p = re.compile(r'^([\[\(] *)?(RE?S?|FYI|RIF|I|FS|VB|RV|ENC|ODP|PD|YNT|ILT|SV|VS|VL|AW|WG|ΑΠ|ΣΧΕΤ|ΠΡΘ|תגובה|הועבר|主题|转发|FWD?) *([-:;)\]][ :;\])-]*|$)|\]+ *$', re.IGNORECASE)
        return p.sub('', self.subject).strip()

    def __str__(self):
        return f"from:{self.from_address}, subject:{self.subject}, attached:{len(self.attachments)}; {self.note[0:20]}"

    def to_cc_str(self) -> str | None:
        if not self.cc:
            return self.to
        elif not self.to:
            return self.cc
        else:
            return '//'.join([self.to, self.cc])


@dataclass
class PropertyChange(): # https://www.redmine.org/projects/redmine/wiki/Rest_IssueJournals
    """a documented change in a single property"""
    property: str
    name: str
    old_value: str
    new_value: str

    def __str__(self):
        return f"{self.name}/{self.property} {self.old_value} -> {self.new_value}"


@dataclass
class NamedId():
    '''named ID in redmine'''
    id: int
    name: str | None

    def __str__(self) -> str:
        if self.name:
            return self.name #+ ":" + str(self.id)
        else:
            return str(self.id)

    def as_token(self) -> str:
        return f"{self.id}|{self.name}"

    @classmethod
    def from_token(cls, token: str):
        vals = token.split("|")
        discord_id = int(vals[0])
        name = vals[1]
        return cls(id=discord_id, name=name)


@dataclass
class TicketStatus(NamedId):
    """status of a ticket"""
    id: int
    name: str
    is_closed: bool
    description: str | None = None

    def __str__(self):
        return self.name


@dataclass
class TicketNote(): # https://www.redmine.org/projects/redmine/wiki/Rest_IssueJournals
    """a message sent to a ticket"""
    id: int
    notes: str
    created_on: dt.datetime
    updated_on: dt.datetime
    private_notes: bool
    details: list[PropertyChange]
    user: NamedId | None = None
    updated_by: NamedId | None = None

    def __post_init__(self):
        self.user = NamedId(**self.user)
        self.created_on = synctime.parse_str(self.created_on)
        if self.details:
            self.details = [PropertyChange(**change) for change in self.details]
        if self.updated_by:
            self.updated_by = NamedId(**self.updated_by)

    def __str__(self):
        return f"#{self.id} - {self.user}: {self.notes}"


@dataclass
class CustomField():
    """A redmine custom field"""
    id: int
    name: str
    value: str

    def __str__(self) -> str:
        return f"field-{self.id}:{self.name}={self.value}"


@dataclass
class Team:
    """Encapsulates a team"""
    id: int
    name: str
    users: list[NamedId] = None

    def __post_init__(self):
        if self.users:
            self.users = [NamedId(**name) for name in self.users]

    def __str__(self) -> str:
        return self.name

    def add_user(self, named:NamedId):
        if not self.users:
            self.users = []
        self.users.append(named)


class TeamSet:
    _teams: dict[str,Team] = {}

    def __str__(self) -> str:
        return str(self._teams)

    def get(self, name: str) -> Team:
        self._teams.get(name, None)


    def in_team(self, username:str, teamname:str) -> bool:
        if username is None or teamname is None:
            return False

        team = self.get(teamname)
        if team:
            for team_user in team.users:
                if team_user.name == username:
                    return True

        return False


    def add_user(self, teamname:str, username:str, userid:int) -> None:
        team = self.get(teamname)
        if not team:
            team = Team(id=-1, name=teamname)
            team.users = []
            self._teams[teamname] = team
        # TODO check if user already in team before adding: set behavior.
        team.add_user(NamedId(userid, username))


DISCORD_ID_FIELD = "Discord ID"


@dataclass
class User():
    """Encapsulates a redmine user"""
    id: int
    login: str
    mail: str
    custom_fields: dict
    admin: bool
    firstname: str
    lastname: str
    mail: str
    created_on: dt.datetime
    updated_on: dt.datetime
    last_login_on: dt.datetime
    passwd_changed_on: dt.datetime
    twofa_scheme: str
    api_key: str = ""
    status: int = 0
    custom_fields: list[CustomField]


    def __post_init__(self):
        self.custom_fields = [CustomField(**field) for field in self.custom_fields]
        self.discord_id = self.parse_discord_custom_field()


    def get_custom_field(self, name: str) -> str:
        for field in self.custom_fields:
            if field.name == name:
                return field.value

        return None


    def set_custom_field(self, field_id: int, name: str, value: str) -> str:
        for field in self.custom_fields:
            if field.name == name:
                old = field.value # old value
                field.value = value
                return old
        # not found, add new
        self.custom_fields.append(CustomField(field_id, name, value))
        return None


    def parse_discord_custom_field(self) -> NamedId:
        id_str = self.get_custom_field(DISCORD_ID_FIELD)
        if id_str and len(id_str) > 0:
            if '|' in id_str:
                try:
                    return NamedId.from_token(id_str)
                except Exception:
                    log.error(f"Unable to parse custom field for discord ID: {id_str}")
            else:
                # no id. assume old style
                return NamedId(0, id_str)
        else:
            return None


    @property
    def discord(self) -> str:
        if self.discord_id:
            return self.discord_id.name

    @property
    def name(self) -> str:
        if self.firstname is None or len(self.firstname) < 2:
            return self.lastname
        if self.lastname is None or len(self.lastname) < 2:
            return self.firstname
        return self.firstname + " " + self.lastname

    def __str__(self):
        return f"#{self.id} {self.name} login={self.login} discord={self.discord_id}"

    def set_field(self, fieldname:str, value):
        setattr(self, fieldname, value)
        log.debug(f"@{self.login}: {fieldname} <= {value}")

    def asdict(self):
        return dataclasses.asdict(self)

    @property
    def json(self):
        return json.dumps(self.asdict(), indent=4, default=vars)


@dataclass
class UserResult:
    """Encapsulates a set of users"""
    users: list[User]
    total_count: int
    limit: int
    offset: int

    def __post_init__(self):
        self.users = [User(**user) for user in self.users]

    def __str__(self):
        return f"users:({[u.login + ',' for u in self.users]}), total={self.total_count}, {self.limit}/{self.offset}"


@dataclass
class SubTicket:
    """Minimal ticket metadata included when include=children"""
    id: int
    tracker: NamedId
    subject: str

    def __post_init__(self, **kwargs):
        #if self.tracker:
        #    self.tracker = NamedId(**self.tracker)
        pass


@dataclass
class ParentTicket:
    """Parent ticket metadata"""
    id: int
    subject: str|None = None


SYNC_FIELD_NAME = "syncdata"
TO_CC_FIELD_NAME = "To/CC"


@dataclass
class Ticket():
    """Encapsulates a redmine ticket"""
    id: int
    subject: str
    description: str
    created_on: dt.datetime
    updated_on: dt.datetime
    done_ratio: float = 0.0
    estimated_hours: float = 0.0
    total_estimated_hours: float = 0.0
    start_date: dt.date|None = None
    due_date: dt.date|None = None
    is_private: bool = False
    closed_on: dt.datetime|None = None
    project: NamedId|None = None
    tracker: NamedId|None = None
    priority: NamedId|None = None
    author: NamedId|None = None
    status: TicketStatus|None = None
    parent: ParentTicket|None = None
    spent_hours: float = 0.0
    total_spent_hours: float = 0.0
    category: NamedId|None = None
    assigned_to: NamedId|None = None
    custom_fields: list[CustomField]|None = None
    journals: list[TicketNote]|None = None
    children: list|None = None
    watchers: list[NamedId]|None = None


    def __post_init__(self):
        self.status = TicketStatus(**self.status)
        self.author = NamedId(**self.author)
        self.priority = NamedId(**self.priority)
        self.project =  NamedId(**self.project)
        self.tracker = NamedId(**self.tracker)

        if self.parent and isinstance(self.parent, dict):
            self.parent = ParentTicket(**self.parent)
        if self.assigned_to and isinstance(self.assigned_to, dict):
            self.assigned_to = NamedId(**self.assigned_to)
        if self.created_on and isinstance(self.created_on, str):
            self.created_on = synctime.parse_str(self.created_on)
        if self.updated_on and isinstance(self.updated_on, str):
            self.updated_on = synctime.parse_str(self.updated_on)
        if self.closed_on and isinstance(self.closed_on, str):
            self.closed_on = synctime.parse_str(self.closed_on)
        if self.start_date and isinstance(self.start_date, str):
            self.start_date = synctime.parse_str(self.start_date)
        if self.due_date and isinstance(self.due_date, str):
            self.due_date = synctime.parse_str(self.due_date)
        if self.custom_fields and len(self.custom_fields) > 0 and isinstance(self.custom_fields[0], dict):
            self.custom_fields = [CustomField(**field) for field in self.custom_fields]
        if self.journals and len(self.journals) > 0 and isinstance(self.journals[0], dict):
            self.journals = [TicketNote(**note) for note in self.journals]
        if self.category and isinstance(self.category, dict):
            self.category = NamedId(**self.category)
        if self.children and len(self.children) > 0 and isinstance(self.children[0], dict):
            self.children = [SubTicket(**child) for child in self.children]

        if self.watchers:
            self.watchers = [NamedId(**named) for named in self.watchers]


    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.id == other.id

    def __hash__(self):
        return hash(self.id)

    def __repr__(self):
        return f'<Ticket {self.id}>'


    def get_custom_field(self, name: str) -> str | None:
        if self.custom_fields:
            for field in self.custom_fields:
                if field.name == name:
                    return field.value

        log.debug(f"missing expected custom field: {name}")
        return None

    def set_custom_field(self, field_id: int, name: str, value: str) -> str | None:
        """
        Set the value of a custom field on a ticket. If
        """
        if self.custom_fields:
            for field in self.custom_fields:
                if field.id == field_id and field.name == name:
                    old_value = field.value
                    field.value = value
                    return old_value
        else:
            # adding new value to empty list, initialize
            self.custom_fields = []

        # there is no matching custom field, add one
        cf = CustomField(id=id, name=name, value=value)
        self.custom_fields.append(cf)
        log.debug(f"added new custom field to ticket #{self.id}: {cf}")
        return None

    def asdict(self):
        return dataclasses.asdict(self)

    @property
    def json(self):
        return json.dumps(self.asdict(), indent=4, default=vars)

    @property
    def to(self) -> list[str]:
        val = self.get_custom_field(TO_CC_FIELD_NAME)
        if val:
            if '//' in val:
                # string contains to,to//cc,cc
                to_str, _ = val.split('//')
            else:
                to_str = val
            return [to.strip() for to in to_str.split(',')]

    @property
    def cc(self) -> list[str]:
        val = self.get_custom_field(TO_CC_FIELD_NAME)
        if val:
            if '//' in val:
               # string contains to,to//cc,cc
                _, cc_str = val.split('//')
            else:
                cc_str = val
            return [to.strip() for to in cc_str.split(',')]


    @property
    def assigned(self) -> str:
        if self.assigned_to:
            return self.assigned_to.name
        else:
            return ""


    @property
    def age_str(self) -> str:
        return synctime.age_str(self.updated_on)


    def __str__(self):
        return f"#{self.id:04d}  {self.status.name:<11}  {self.priority.name:<6}  {self.assigned:<20}  {self.subject}"


    def get_sync_record(self) -> synctime.SyncRecord | None:
        # Parse custom_field into datetime
        # lookup field by name
        token = self.get_custom_field(SYNC_FIELD_NAME)
        if token:
            record = synctime.SyncRecord.from_token(self.id, token)
            log.debug(f"created sync_rec from token: {record}")
            return record


    def validate_sync_record(self, expected_channel: int = 0) -> synctime.SyncRecord | None:
        # Parse custom_field into datetime
        # lookup field by name
        record = self.get_sync_record()
        if record:
            # check channel
            if record.channel_id == 0:
                # no valid channel set in sync data, assume lagacy
                record.channel_id = expected_channel
                # update the record in redmine after adding the channel info
                return record
            elif record.channel_id != expected_channel:
                log.debug(f"channel mismatch: rec={record.channel_id} =/= {expected_channel}")
                return None
            else:
                return record
        else:
            # no token implies not-yet-initialized
            record = synctime.SyncRecord(self.id, expected_channel, synctime.epoch_datetime())
            log.debug(f"created new sync record, none found: {record}")
            return record


    def get_notes(self, since:dt.datetime|None=None) -> list[TicketNote]:
        notes = []

        for note in self.journals:
            # note.notes is a text field with notes, or empty. if there are no notes, ignore the journal
            if note.notes:
                if not since or since < note.created_on:
                    notes.append(note)

        return notes

    def get_field(self, fieldname:str):
        val = getattr(self, fieldname)
        return val


    def set_field(self, fieldname:str, value):
        setattr(self, fieldname, value)
        log.debug(f"ticket-{self.id} {fieldname} <= {value}")




@dataclass
class TicketsResult:
    """Encapsulates a set of tickets"""
    total_count: int
    limit: int
    offset: int
    issues: list[Ticket]

    def __post_init__(self):
        if self.issues and len(self.issues) > 0 and isinstance(self.issues[0], dict):
            self.issues = [Ticket(**ticket) for ticket in self.issues]

    def asdict(self):
        return dataclasses.asdict(self)

    @property
    def json(self):
        return json.dumps(self.asdict(), indent=4, default=vars)
