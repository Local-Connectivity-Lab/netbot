#!/usr/bin/env python3

import os
import re
import json
import requests
import logging
import datetime as dt

import humanize

from dotenv import load_dotenv
from types import SimpleNamespace

log = logging.getLogger(__name__)

DEFAULT_SORT = "status:desc,priority:desc,updated_on:desc"
TIMEOUT = 2 # seconds

class RedmineException(Exception):
    def __init__(self, message: str, request_id: str) -> None:
        super().__init__(message + ", req_id=" + request_id)
        self.request_id = request_id
    

class Client(): ## redmine.Client()
    def __init__(self):
        self.url = os.getenv('REDMINE_URL')
        self.token = os.getenv('REDMINE_TOKEN')
        self.reindex()

    def create_ticket(self, user, subject, body, attachments=None):
        # https://www.redmine.org/projects/redmine/wiki/Rest_Issues#Creating-an-issue
        # tracker_id = 13 is test tracker.
        # would need full param handling to pass that thru discord to get to this invocation....

        data = {
            'issue': {
                'project_id': 1, #FIXME hard-coded project ID
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
            return root.issue
        else:
            raise RedmineException(f"create_ticket failed, status=[{response.status_code}] {response.reason}", response.headers['X-Request-Id'])
        

    def update_user(self, user, fields:dict):
        # PUT a simple JSON structure
        data = {}
        data['user'] = fields

        response = requests.put(
            url=f"{self.url}/users/{user.id}.json", 
            data=json.dumps(data),
            headers=self.get_headers()) # removed user.login impersonation header
        
        log.debug(f"update user: [{response.status_code}] {response.request.url}, fields: {fields}")
        
        # check status
        if response.ok:
            # TODO get and return the updated user?
            return user
        else:
            raise RedmineException(f"update_user failed, status=[{response.status_code}] {response.reason}", response.headers['X-Request-Id'])


    def update_ticket(self, ticket_id:str, fields:dict, user_login:str=None):
        # PUT a simple JSON structure
        data = {
            'issue': {}
        }

        data['issue'] = fields

        response = requests.put(
            url=f"{self.url}/issues/{ticket_id}.json", 
            data=json.dumps(data),
            headers=self.get_headers(user_login))
        
        log.debug(f"update ticket: [{response.status_code}] {response.request.url}, fields: {fields}")
                
        # check status
        if response.ok:
            # no body, so re-get the updated tickets?
            return self.get_ticket(ticket_id)
        else:
            raise RedmineException(f"update_ticket failed, status=[{response.status_code}] {response.reason}", response.headers['X-Request-Id'])


    def append_message(self, ticket_id:str, user_login:str, note:str, attachments=None):
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
        # uploads all the attachments, 
        # sets the upload token for each 
        for a in attachments:
            token = self.upload_file(user_id, a.payload, a.name, a.content_type)
            a.set_token(token)

    def find_team(self, name):
        response = self.query(f"/groups.json")
        for group in response.groups:
            if group.name == name:
                return group
        # not found
        return None
        
    def get_user(self, id:int):
        if id:
            return self.user_ids[id]
    
    def find_user(self, name):
        # check if name is int, raw user id. then look up in userids
        # check the indicies
        if name in self.user_emails:
            return self.get_user(self.user_emails[name])
        elif name in self.users:
            return self.get_user(self.users[name])
        elif name in self.discord_users:
            return self.get_user(self.discord_users[name])
        elif name in self.groups:
            return self.groups[name] #ugly. put groups in user collection?
        else:
            return None
        
    def find_discord_user(self, user_id):
        if user_id == None:
            return None
        
        if user_id in self.discord_users:
            id = self.discord_users[user_id]
            return self.user_ids[id]
        else:
            return None

    def get_ticket(self, ticket_id:int, include_journals:bool = False):
        if ticket_id is None or ticket_id == 0:
            log.warning(f"Invalid ticket number: {ticket_id}")
            return None

        query = f"/issues/{ticket_id}.json"
        if include_journals:
            query += "?include=journals" # as per https://www.redmine.org/projects/redmine/wiki/Rest_IssueJournals

        response = self.query(query)
        if response:
            return response.issue
        else:
            log.warning(f"Unknown ticket number: {ticket_id}")
            return None
        
    #GET /issues.xml?issue_id=1,2
    def get_tickets(self, ticket_ids):
        response = self.query(f"/issues.json?issue_id={','.join(ticket_ids)}&sort={DEFAULT_SORT}")
        if response != None and response.total_count > 0:
            return response.issues
        else:
            log.info(f"Unknown ticket numbers: {ticket_ids}")
            return []
    
    def find_ticket_from_str(self, str:str):
        # for now, this is a trivial REGEX to match '#nnn' in a string, and return ticket #nnn
        match = re.search(r'#(\d+)', str)
        if match:
            ticket_num = int(match.group(1))
            return self.get_ticket(ticket_num)
        else:
            log.debug(f"Unable to match ticket number in: {str}")
            return []
    
    
    def create_user(self, email:str, first:str, last:str):
        data = {
            'user': {
                'login': email,
                'firstname': first,
                'lastname': last,
                'mail': email,                
            }
        }
        # on create, assign watcher: sender?
        
        r = requests.post(
            url=f"{self.url}/users.json", 
            data=json.dumps(data), 
            headers=self.get_headers())
                
        # check status
        if r.status_code == 201:
            root = json.loads(r.text, object_hook= lambda x: SimpleNamespace(**x))
            user = root.user
            
            log.info(f"created user: {user.id} {user.login} {user.mail}")
            self.reindex_users() # new user!
            
            # add user to User group and SCN project
                        
            #self.join_project(user.login, "scn") ### scn project key
            #log.info("joined scn project")
            
            self.join_team(user.login, "users") ### FIXME move default team name to defaults somewhere
            log.info("joined users group")
            
            return user
        elif r.status_code == 403:
            # can't create existing user. log err, but return from cache
            user = self.find_user(email)
            log.error(f"Trying to create existing user email: email={email}, user={user}")
            return user
        else:
            log.error(f"create_user, status={r.status_code}: {r.reason}, req-id={r.headers['X-Request-Id']}")
            #TODO throw exception?
            return None
        

    # used only in testing
    def remove_user(self, user_id:int):
        # DELETE to /users/{user_id}.json
        r = requests.delete(
            url=f"{self.url}/users/{user_id}.json", 
            headers=self.get_headers())

        # check status
        if r.status_code != 204:
            log.error(f"Error removing user status={r.status_code}, url={r.request.url}")
            
        
    def most_recent_ticket_for(self, email):
        # get the user record for the email
        user = self.find_user(email)

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
        # "kanban" query: all ticket open or closed recently
        project=1
        tracker=4
        query = f"/issues.json?project_id={project}&tracker_id={tracker}&status_id=*&sort={DEFAULT_SORT}&limit=100"
        response = self.query(query)

        return response.issues

    def my_tickets(self, user=None):
        response = self.query(f"/issues.json?assigned_to_id=me&status_id=open&sort={DEFAULT_SORT}&limit=100", user)

        if response.total_count > 0:
            return response.issues
        else:
            log.info(f"No open ticket for me.")
            return None

    def tickets_for_team(self, team_str:str):
        # validate team?
        team = self.find_user(team_str) # find_user is dsigned to be broad

        query = f"/issues.json?assigned_to_id={team.id}&status_id=open&sort={DEFAULT_SORT}&limit=100"
        response = self.query(query)

        if response.total_count > 0:
            return response.issues
        else:
            log.info(f"No open ticket found for: {team}")
            return None

    def search_tickets(self, term):
        # todo url-encode term?
        # note: sort doesn't seem to be working for search
        query = f"/search.json?q={term}&titles_only=1&open_issues=1&limit=100"

        response = self.query(query)

        ids = []
        for result in response.results:
            ids.append(str(result.id))

        return self.get_tickets(ids)

    # get the 
    def get_notes_since(self, ticket_id, timestamp=None):
        notes = []

        ticket = self.get_ticket(ticket_id, include_journals=True)
        log.debug(f"got ticket {ticket_id} with {len(ticket.journals)} notes")

        #try:
        for note in ticket.journals:
            # note.notes is a text field with notes, or empty. if there are no notes, ignore the journal
            if note.notes and timestamp:
                #log.debug(f"### get_notes_since - fromisoformat: {note.created_on}")
                created = dt.datetime.fromisoformat(note.created_on) ## creates UTC
                #log.debug(f"note {note.id} created {created} {age(created)} <--> {timestamp} {age(timestamp)}")
                if created > timestamp:
                    notes.append(note)
            elif note.notes:
                notes.append(note) # append all notes when there's no timestamp
        #except Exception as e:
        #    log.error(f"oops: {e}")

        return notes
    

    def discord_tickets(self):
        # todo: check updated field and track what's changed
        threaded_issue_query = "/issues.json?status_id=open&cf_1=1&sort=updated_on:desc"
        response = self.redmine.query(threaded_issue_query)

        if response.total_count > 0:
            return response.issues
        else:
            log.info(f"No open tickets found for: {response.request.url}")
            return None

    def enable_discord_sync(self, ticket_id, user, note):
        fields = {
            "note": note, #f"Created Discord thread: {thread.name}: {thread.jump_url}",
            "cf_1": "1",
        }
        
        self.update_ticket(ticket_id, fields, user.login)
        # currently doesn't return or throw anything
        # todo: better error reporting back to discord

    def update_syncdata(self, ticket_id:int, timestamp:dt.datetime):
        log.debug(f"Setting ticket {ticket_id} update_syncdata to: {timestamp} {age(timestamp)}")
        # 2023-11-19T20:42:09Z
        timestr = timestamp.strftime("%Y-%m-%dT%H:%M:%SZ") # timestamp.isoformat()
        fields = {
            "custom_fields": [
                { "id": 4, "value": timestr } # cf_4, custom field syncdata, #TODO search for it
            ]
        }
        self.update_ticket(ticket_id, fields)

    def create_discord_mapping(self, redmine_login:str, discord_name:str):
        user = self.find_user(redmine_login)

        field_id = 2 ## "Discord ID"search for me in cached custom fields
        fields = {
            "custom_fields": [
                { "id": field_id, "value": discord_name } # cf_4, custom field syncdata
            ]
        }
        self.update_user(user, fields)

    def join_project(self, username, project:str):
        # look up user ID
        user = self.find_user(username)
        if user == None:
            log.warning(f"Unknown user name: {username}")
            return None
        
        # check project name? just assume for now

        # POST /projects/{project}/memberships.json
        data = {
            "membership": {
                "user_id": user.id,
                "role_ids": [ 5 ], # this is the "User" role. need a mapping table, could be default for param    
            }
        }

        r = requests.post(
            url=f"{self.url}/projects/{project}/memberships.json", 
            data=json.dumps(data), 
            headers=self.get_headers())
        
        # check status
        if r.status_code == 204:
            log.info(f"joined project {username}, {project}, {r.request.url}, data={data}")
        else:
            resp = json.loads(r.text, object_hook=lambda x: SimpleNamespace(**x))
            log.error(f"Error joining group: {resp.errors}, status={r.status_code}: {r.request.url}, data={data}")
            

    def join_team(self, username, teamname:str):
        # look up user ID
        user = self.find_user(username)
        if user == None:
            log.warning(f"Unknown user name: {username}")
            return None
        
        # map teamname to team
        team = self.find_team(teamname)
        if team == None:
            log.warning(f"Unknown team name: {teamname}")
            return None
        
        # POST to /group/ID/users.json
        data = {
            "user_id": user.id
        }

        r = requests.post(
            url=f"{self.url}/groups/{team.id}/users.json", 
            data=json.dumps(data), 
            headers=self.get_headers())
        
        log.info(f"join_team {username}, {teamname}, {r}")

        # check status
        if r.status_code != 204:
            log.error(f"Error joining group. status={r.status_code}: {r.request.url}, data={data}")
            

    def leave_team(self, username:int, teamname:str):
        # look up user ID
        user = self.find_user(username)
        if user == None:
            log.warning(f"Unknown user name: {username}")
            return None
        
        # map teamname to team
        team = self.find_team(teamname)
        if team == None:
            log.warning(f"Unknown team name: {teamname}")
            return None

        # DELETE to /groups/{team-id}/users/{user_id}.json
        r = requests.delete(
            url=f"{self.url}/groups/{team.id}/users/{user.id}.json", 
            headers=self.get_headers())

        # check status
        if r.status_code != 204:
            log.error(f"Error removing user from group status={r.status_code}, url={r.request.url}")
            return None

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

        r = requests.get(f"{self.url}{query_str}", headers=headers, timeout=TIMEOUT)

        # check 200 status code
        if r.status_code == 200:
            return json.loads(r.text, object_hook=lambda x: SimpleNamespace(**x))
        else:
            log.error(f"{r.status_code}: {r.request.url}")
            return None
    

    def assign_ticket(self, id, target, user_id=None):
        user = self.find_user(target)
        if user:
            fields = {
                "assigned_to_id": user.id,
                "status_id": "1", # New
            }
            self.update_ticket(id, fields, user_id)
        else:
            log.error(f"unknow user: {target}")
    

    def progress_ticket(self, id, user_id=None): # TODO notes
        fields = {
            "assigned_to_id": "me",
            "status_id": "2", # "In Progress"
        }
        self.update_ticket(id, fields, user_id)


    def unassign_ticket(self, id, user_id=None):
        fields = {
            "assigned_to_id": "", # FIXME this *should* be the team it was assigned to, but there's no way to calculate.
            "status_id": "1", # New
        }
        self.update_ticket(id, fields, user_id)


    def resolve_ticket(self, ticket_id, user_id=None):
        self.update_ticket(ticket_id, {"status_id": "3"}, user_id) # '3' is the status_id, it doesn't accept "Resolved"


    def get_team(self, teamname:str):
        team = self.find_team(teamname)
        if team is None:
            log.debug(f"Unknown team name: {teamname}")
            return None
        
        # as per https://www.redmine.org/projects/redmine/wiki/Rest_Groups#GET-2
        # GET /groups/20.json?include=users
        response = self.query(f"/groups/{team.id}.json?include=users")
        if response:
            return response.group
        else:
            #TODO exception?
            return None

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
                case "age":
                    #log.debug(f"### fromisoformat: {ticket.updated_on}")
                    updated = dt.datetime.fromisoformat(ticket.updated_on) ###
                    age = dt.datetime.now(dt.timezone.utc) - updated
                    return humanize.naturaldelta(age)  
                case "sync":
                    try:
                        # Parse custom_field into datetime
                        # FIXME: this is fragile, add custom field lookup
                        timestr = ticket.custom_fields[1].value 
                        #log.debug(f"### fromisoformat: {timestr}")
                        return dt.datetime.fromisoformat(timestr) ### UTC
                    except Exception as e:
                        log.info(f"no sync tag available, {e}")
                        return None
        except AttributeError:
            return "" # or None?
    
    def get_discord_id(self, user):
        if user:
            for field in user.custom_fields:
                    if field.name == "Discord ID":
                        return field.value
        return None

    def is_user_or_group(self, user:str) -> bool:
        if user in self.users:
            return True
        elif user in self.groups:
            return True
        else:
            return False

    # python method sync?
    def reindex_users(self):
        # reset the indices
        self.users = {}
        self.user_ids = {}
        self.user_emails = {}
        self.discord_users = {}

        # rebuild the indicies
        response = self.query(f"/users.json?limit=1000") ## fixme max limit? paging?
        if response.users:
            for user in response.users:
                self.users[user.login] = user.id
                self.user_ids[user.id] = user
                self.user_emails[user.mail] = user.id

                discord_id = self.get_discord_id(user)
                if discord_id:
                    self.discord_users[discord_id] = user.id
            log.info(f"indexed {len(self.users)} users")
        else:
            log.error(f"No users: {response}")


    def get_teams(self):
        return self.groups.keys()

    def reindex_groups(self):
        # reset the indices
        self.groups = {}

        # rebuild the indicies
        response = self.query(f"/groups.json?limit=1000") ## FIXME max limit? paging?
        for group in response.groups:
            self.groups[group.name] = group

        log.info(f"indexed {len(self.groups)} groups")


    def is_user_in_team(self, username:str, teamname:str) -> bool:
        user_id = self.find_user(username).id
        team = self.get_team(teamname) # requires an API call, could be cashed? only used for testing

        if team:
            for user in team.users:
                if user.id == user_id:
                    return True
        return False


    def reindex(self):
        log.info("reindixing")
        self.reindex_users()
        self.reindex_groups()

def age(time:dt.datetime):
    #updated = dt.datetime.fromisoformat(time).astimezone(dt.timezone.utc)
    now = dt.datetime.now().astimezone(dt.timezone.utc)
    
    #log.debug(f"### now tz: {now.tzinfo}, time tz: {time.tzinfo}")

    age = now - time
    return humanize.naturaldelta(age)  

if __name__ == '__main__':
    # load credentials 
    load_dotenv()

    # construct the client and run the email check
    client = Client()
    tickets = client.find_tickets()
    client.format_report(tickets)