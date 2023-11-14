#!/usr/bin/env python3

import os
import re
import json
import requests
import logging
import datetime as dt
#import humanize

from dotenv import load_dotenv
from types import SimpleNamespace


#from typing import TypedDict # see https://peps.python.org/pep-0589/
#from dataclasses import dataclass

#logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)


class Client(): ## redmine.Client()
    def __init__(self):
        self.url = os.getenv('REDMINE_URL')
        self.token = os.getenv('REDMINE_TOKEN')
        self.reindex()

    def create_ticket(self, user_id, subject, body):
        # https://www.redmine.org/projects/redmine/wiki/Rest_Issues#Creating-an-issue

        headers = { # TODO DRY headers
            'User-Agent': 'netbot/0.0.1', # TODO update to project version, and add version management
            'Content-Type': 'application/json',
            'X-Redmine-API-Key': self.token,
            'X-Redmine-Switch-User': user_id, # Make sure the comment is noted by the correct user
        }

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
            headers=headers)
        
        print(f"create_ticket response: {r}")
        
        # check status
        #if r.status_code != 201:
        # check 201 status
        #root = json.loads(r.text, object_hook= lambda x: SimpleNamespace(**x))
        #ticket = root.ticket[0]
        #return ticket

    def append_message(self, ticket_id:str, user_id:str, note:str, attachments):
        headers = { # TODO DRY headers
            'User-Agent': 'netbot/0.0.1', # TODO update to project version, and add version management
            'Content-Type': 'application/json',
            'X-Redmine-API-Key': self.token,
            'X-Redmine-Switch-User': user_id, # Make sure the comment is noted by the correct user
        }

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
            headers=headers)
        
        # check status
        if r.status_code != 204:
            root = json.loads(r.text, object_hook= lambda x: SimpleNamespace(**x))
            log.error(f"append_message, status={r.status_code}: {root}")
            # throw exception?


    def upload_file(self, user_id, data, filename, content_type):
        # POST /uploads.json?filename=image.png
        # Content-Type: application/octet-stream
        # (request body is the file content)
        
        headers = { # TODO DRY headers
            'User-Agent': 'netbot/0.0.1', # TODO update to project version, and add version management
            'Content-Type': 'application/octet-stream',
            'X-Redmine-API-Key': self.token,
            'X-Redmine-Switch-User': user_id, # Make sure the comment is noted by the correct user
        }

        r = requests.post(
            url=f"{self.url}/uploads.json?filename={filename}", 
            files={ 'upload_file': (filename, data, content_type) },
            headers=headers
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

    ### OLD REMOVE
    def xxx_append_attachment(self, ticket_id, user_id, data, filename, content_type):
        # upload the data as a new file
        upload_token = self.upload_file(user_id, data, filename, content_type)

        # then PUT the upload to the issue API
        headers = { # TODO DRY headers
            'User-Agent': 'netbot/0.0.1', # TODO update to project version, and add version management
            'Content-Type': 'application/json',
            'X-Redmine-API-Key': self.token,
            'X-Redmine-Switch-User': user_id, # Make sure the comment is noted by the correct user
        }

        # PUT a simple JSON structure with the uploaded file info
        data = {
            'issue': {
                'notes': f"Uploading attachment {filename} to ticket #{ticket_id}.",
                'uploads': [
                    { 
                        "token": upload_token, 
                        "filename": filename,
                        "content_type": content_type,
                    }
                ]
            }
        }

        r = requests.put(
            url=f"{self.url}/issues/{ticket_id}.json", 
            data=json.dumps(data),
            headers=headers)

        print(f"append_attachment response: {r}")

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
            return self.users[id]
        else:
            return None
        
    def get_ticket(self, ticket_num:int):
        response = self.query(f"/issues.json?issue_id={ticket_num}")
        if response.total_count > 0:
            return response.issues[0]
        else:
            log.warning(f"Unknown ticket number: {ticket_num}")
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
        
    # project_id=1&tracker_id=4&sort=priority:desc,updated_on:desc,id:desc
    def find_tickets(self):
        # "kanban" query: all ticket open or closed recently
        project=1
        tracker=4
        response = self.query(f"/issues.json?project_id={project}&tracker_id={tracker}\
                              &status_id=*&sort=priority:desc,updated_on:desc,id:desc&limit=100")

        return response.issues

    def tickets_for_team(self, team_str:str):
        # validate team?
        team = self.find_user(team_str) # find_user is dsigned to be broad

        query = f"/issues.json?assigned_to_id={team.id}&status_id=open&sort=priority:desc,updated_on:desc,id:desc&limit=100"
        response = self.query(query)

        if response.total_count > 0:
            return response.issues
        else:
            log.info(f"No open ticket found for: {team}")
            return None

    def search_tickets(self, term):
        # todo url-encode term?
        # GET /search.json?q=issue_keyword wiki_keyword&issues=1&wiki_pages=1
        query = f"/search.json?q={term}&status_id=open&sort=updated_on:desc&limit=1"
        response = self.query(query)

        if response.total_count > 0:
            return response.issues[0]
        else:
            log.info(f"No tickets found for: {term}")
            return None

    def query(self, query_str:str, user_id:str=None):
        """run a query against a redmine instance"""
        headers = {
            'User-Agent': 'netbot/0.0.1', # TODO update to project version, and add version management
            'Content-Type': 'application/json',
            'X-Redmine-API-Key': self.token,
        }
        if user_id:
            headers['X-Redmine-Switch-User'] = user_id # Make sure the comment is noted by the correct user
        
        # run the query with the 
        r = requests.get(f"{self.url}{query_str}", headers=headers)

        # check 200 status code
        if r.status_code == 200:
            return json.loads(r.text, object_hook= lambda x: SimpleNamespace(**x))
        else:
            log.error(f"{r.status_code}: {r.request.url}")
            return None
    
    def assign_ticket(self, id, target):
        pass
    
    def progress_ticket(self, id, target):
        pass

    def unassign_ticket(self, id):
        pass

    def resolve_ticket(self, id):
        pass 

    def format_report(self, tickets):
        # 3 passes: new, in progress, closed
        
        print(len(self.format_section(tickets, "New")))
        print(self.format_section(tickets, "In Progress"))
        print(self.format_section(tickets, "Resolved"))

    def format_section(self, tickets, status):
        section = ""
        section += f"> {status}\n"
        for ticket in tickets:
            if ticket.status.name == status:
                url = f"{self.url}/issues/{ticket.id}"
                try: # hack to get around missing key
                    assigned_to = ticket.assigned_to.name
                except AttributeError:
                    assigned_to = ""
                section += f"[**`{ticket.id:>4}`**]({url})`  {ticket.priority.name:<6}  {ticket.updated_on[:10]}  {assigned_to[:20]:<20}  {ticket.subject}`\n"
        return section
    
    def format_tickets(self, tickets, fields=["link","priority","updated","assigned", "subject"]):
        section = ""
        for ticket in tickets:
            section += self.format_ticket(ticket, fields) + "\n" # append each ticket
        return section.strip()

    def format_ticket(self, ticket, fields):
        url = f"{self.url}/issues/{ticket.id}"
        try: # hack to get around missing key
            assigned_to = ticket.assigned_to.name
        except AttributeError:
            assigned_to = ""

        section = ""
        for field in fields:
            match field:
                case "id":
                    section += f"{ticket.id}"
                case "url":
                    section += url
                case "link":
                    section += f"[{ticket.id}]({url})"
                case "priority":
                    section += f"{ticket.priority.name}"
                case "updated":
                    section += f"{ticket.updated_on[:10]}" # just the date, strip time
                case "assigned":
                    section += f"{assigned_to}"
                case "status":
                    section += f"{ticket.status.name}"
                case "subject":
                    section += f"{ticket.subject}"
            section += " " # spacer, one space
        return section.strip() # remove trailing whitespace

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
        for user in response.users:
            self.users[user.login] = user.id
            self.user_ids[user.id] = user
            self.user_emails[user.mail] = user.id

            discord_id = self.get_discord_id(user)
            if discord_id:
                self.discord_users[discord_id] = user.id
        log.info(f"indexed {len(self.users)} users")

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