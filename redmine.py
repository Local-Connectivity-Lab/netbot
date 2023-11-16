#!/usr/bin/env python3

import os
import re
import json
import requests
import logging
import datetime as dt

from dotenv import load_dotenv
from types import SimpleNamespace

#logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)

DEFAULT_SORT = "status:desc,priority:desc,updated_on:desc"

class Client(): ## redmine.Client()
    def __init__(self):
        self.url = os.getenv('REDMINE_URL')
        self.token = os.getenv('REDMINE_TOKEN')
        self.reindex()

    def create_ticket(self, user_id, subject, body):
        # https://www.redmine.org/projects/redmine/wiki/Rest_Issues#Creating-an-issue

        data = {
            'issue': {
                'project_id': 1,
                'subject': subject,
                'description': body,
            }
        }

        r = requests.post(
            url=f"{self.url}/issues.json", 
            data=json.dumps(data), 
            headers=self.get_headers(user_id))
        
        print(f"create_ticket response: {r}")
        
        # check status
        #if r.status_code != 201:
        # check 201 status
        #root = json.loads(r.text, object_hook= lambda x: SimpleNamespace(**x))
        #ticket = root.ticket[0]
        #return ticket

    def update_ticket(self, ticket_id:str, fields:dict, user_id:str=None):
        # PUT a simple JSON structure
        data = {
            'issue': {}
        }

        data['issue'] = fields

        r = requests.put(
            url=f"{self.url}/issues/{ticket_id}.json", 
            data=json.dumps(data),
            headers=self.get_headers(user_id))
                
        # check status
        if r.status_code != 204:
            root = json.loads(r.text, object_hook= lambda x: SimpleNamespace(**x))
            log.error(f"append_message, status={r.status_code}: {root}")
            # throw exception?


    def append_message(self, ticket_id:str, user_id:str, note:str, attachments):
        # PUT a simple JSON structure
        data = {
            'issue': {
                'notes': note,
                'uploads': []
            }
        }

        # add the attachments
        if len(attachments) > 0:
            for a in attachments:
                data['issue']['uploads'].append({
                    "token": a.token, 
                    "filename": a.name,
                    "content_type": a.content_type,
                })

        r = requests.put(
            url=f"{self.url}/issues/{ticket_id}.json", 
            data=json.dumps(data),
            headers=self.get_headers(user_id))
        
        # check status
        if r.status_code != 204:
            root = json.loads(r.text, object_hook= lambda x: SimpleNamespace(**x))
            log.error(f"append_message, status={r.status_code}: {root}")
            # throw exception?


    def upload_file(self, user_id, data, filename, content_type):
        # POST /uploads.json?filename=image.png
        # Content-Type: application/octet-stream
        # (request body is the file content)
        r = requests.post(
            url=f"{self.url}/uploads.json?filename={filename}", 
            files={ 'upload_file': (filename, data, content_type) },
            headers=self.get_headers(user_id)
        )
        
        # 201 response: {"upload":{"token":"7167.ed1ccdb093229ca1bd0b043618d88743"}}
        if r.status_code == 201:
            # all good, get token
            root = json.loads(r.text, object_hook= lambda x: SimpleNamespace(**x))
            token = root.upload.token
            log.info(f"Uploaded {filename} {content_type}, got token={token}")
            return token
        else:
            #print(vars(r))
            log.error(f"Error uploading {filename} {content_type} - response:{r}")
            # todo throw exception

    def upload_attachments(self, user_id, attachments):
        # uploads all the attachments, 
        # sets the upload token for each 
        for a in attachments:
            token = self.upload_file(user_id, a.payload, a.name, a.content_type)
            a.set_token(token)

    def find_group(self, name):
        response = self.query(f"/groups.json")
        for group in response.groups:
            if group.name == name:
                return group
        # not found
        return None
        
    def find_user(self, name):
        # check the indicies
        if name in self.user_emails:
            id = self.user_emails[name]
            return self.user_ids[id]
        elif name in self.users:
            id = self.users[name]
            return self.user_ids[id]
        elif name in self.discord_users:
            id = self.discord_users[name]
            return self.user_ids[id]
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
        
    def get_ticket(self, ticket_num:int):
        response = self.query(f"/issues.json?issue_id={ticket_num}")
        if response.total_count > 0:
            return response.issues[0]
        else:
            log.warning(f"Unknown ticket number: {ticket_num}")
            return None
        
    #GET /issues.xml?issue_id=1,2
    def get_tickets(self, ticket_ids):
        response = self.query(f"/issues.json?issue_id={','.join(ticket_ids)}&sort={DEFAULT_SORT}")
        if response != None and response.total_count > 0:
            return response.issues
        else:
            log.info(f"Unknown ticket numbers: {ticket_ids}")
            return None
    
    def find_ticket_from_str(self, str:str):
        # for now, this is a trivial REGEX to match '#nnn' in a string, and return ticket #nnn
        match = re.search(r'#(\d+)', str)
        if match:
            ticket_num = int(match.group(1))
            return self.get_ticket(ticket_num)
        else:
            log.warning(f"Unable to match ticket number in: {str}")
            return None
    
    def create_user(self, email, first, last):
        user = {
            'login': email,
            'firstname': 'test-first',
            'lastname': 'test-last',
            'mail': email,
        }
        # on create, assign watcher: sender.

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
        
    def find_tickets(self):
        # "kanban" query: all ticket open or closed recently
        project=1
        tracker=4
        query = f"/issues.json?project_id={project}&tracker_id={tracker}&status_id=*&sort={DEFAULT_SORT}&limit=100"
        response = self.query(query)

        return response.issues

    def my_tickets(self, user):
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

    def get_headers(self, impersonate_id:str=None):
        headers = {
            'User-Agent': 'netbot/0.0.1', # TODO update to project version, and add version management
            'Content-Type': 'application/json',
            'X-Redmine-API-Key': self.token,
        }
        # insert the impersonate_id to impersonate another user
        if impersonate_id:
            headers['X-Redmine-Switch-User'] = impersonate_id # Make sure the comment is noted by the correct user
        return headers

    def query(self, query_str:str, user:str=None):
        """run a query against a redmine instance"""

        headers = self.get_headers(user)

        r = requests.get(f"{self.url}{query_str}", headers=headers)

        # check 200 status code
        if r.status_code == 200:
            return json.loads(r.text, object_hook=lambda x: SimpleNamespace(**x))
        else:
            log.error(f"{r.status_code}: {r.request.url}")
            return None
    
    def assign_ticket(self, id, target):
        user = self.find_user(target)
        if user:
            self.update_ticket(id, {"assigned_to_id": user.id})
        else:
            log.error(f"unknow user: {target}")
    
    def progress_ticket(self, id): # TODO notes
        fields = {
            "assigned_to_id": "me",
            "status_id": "2", # "In Progress"
        }
        self.update_ticket(id, fields)

    def unassign_ticket(self, id):
        fields = {
            "assigned_to_id": "",
            "status_id": "1", # New
        }
        self.update_ticket(id, fields)

    def resolve_ticket(self, id):
        self.update_ticket(id, {"status_id": "Resolved"}) 

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
                        return ticket.updated_on
                    case "assigned":
                        return ticket.assigned_to.name
                    case "status":
                        return ticket.status.name
                    case "subject":
                        return ticket.subject
                    case "title":
                        return ticket.title
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

    def reindex_groups(self):
        # reset the indices
        self.groups = {}

        # rebuild the indicies
        response = self.query(f"/groups.json?limit=1000") ## fixme max limit? paging?
        for group in response.groups:
            self.groups[group.name] = group

        log.info(f"indexed {len(self.groups)} groups")


    def reindex(self):
        log.info("reindixing")
        self.reindex_users()
        self.reindex_groups()


if __name__ == '__main__':
    # load credentials 
    load_dotenv()

    # construct the client and run the email check
    client = Client()
    tickets = client.find_tickets()
    client.format_report(tickets)