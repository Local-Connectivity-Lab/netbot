import os
import json
import requests
import datetime as dt
import humanize

from types import SimpleNamespace
#from collections import namedtuple


#from typing import TypedDict # see https://peps.python.org/pep-0589/
from dataclasses import dataclass

class Client(): ## redmine.Client()
    def __init__(self):
        self.url = os.getenv('REDMINE_URL')
        self.token = os.getenv('REDMINE_TOKEN')
        self.issue_query = "/issues.json?status_id=open&sort=category:desc,updated_on"
        # GET /issues.json?status_id=open&sort=category:desc,updated_on

    def load_issues(self):
        #TODO add query params and default query
        """load open issues from a redmine instance"""
        headers = {
            'User-Agent': 'netbot/0.0.1',
            'Content-Type': 'application/json',
            'X-Redmine-API-Key': self.token,
        }

        r = requests.get(f"{self.url}{self.issue_query}", headers=headers)
        # parse json response in `r.text`
        result = json.loads(r.text)
        # but there's an extra 'issues' wrapper
        return result['issues']

    def query(self, query_str: str):
        """run a query against a redmine instance"""
        headers = {
            'User-Agent': 'netbot/0.0.1', # TODO update to project version, and add version management
            'Content-Type': 'application/json',
            'X-Redmine-API-Key': self.token,
        }
        # run the query with the 
        r = requests.get(f"{self.url}{query_str}", headers=headers)

        root = json.loads(r.text, object_hook= lambda x: SimpleNamespace(**x))
        #root = json.loads(r.text, object_hook=lambda d: namedtuple('Issue', d.keys())(*d.values())) 

        return root.issues


    def format_issue(self, issue):
        # parse the "updated_on" field to create a datetime
        last_updated = dt.datetime.strptime(issue['updated_on'], '%Y-%m-%dT%H:%M:%SZ')
        # create a human-readable time difference
        age = humanize.naturaldelta(dt.datetime.now() - last_updated)
        # format everything for 
        return f"**[#{issue['id']}](<{self.url}/issues/{issue['id']}>)** {issue['subject']} - {issue['priority']['name']} - {age} old"
    
    def format_issues(self):
        msg = ""
        for issue in self.load_issues():
            msg += self.format_issue(issue) + '\n'
        return msg


# @dataclass
# class NamedId:
#     id: int
#     name: str

#     def __str__(self) -> str:
#         return self.name


# @dataclass
# class Issue:
#     id: int
#     project: NamedId
#     tracker: NamedId
#     status: NamedId
#     priority: NamedId
#     author: NamedId
#     assigned_to: NamedId
#     subject: str
#     description: str
#     start_date: dt.date
#     due_date: dt.date
#     done_ratio: float
#     is_private: bool
#     estimated_hours: float
#     total_estimated_hours: float
#     spent_hours: float
#     total_spent_hours: float
#     created_on: dt.datetime
#     updated_on: dt.datetime
#     closed_on: dt.datetime
#     custom_fields: dict
#     #url: str # TODO is there a formal URL type?


### issue fields ###
# issue url: http://40.65.85.252/issues/22 -> {base_url}/issues/{issue.id}
# {'id': 2, 'project': {'id': 1, 'name': 'Seattle Community Network'}, 
# 'tracker': {'id': 3, 'name': 'Support'}, 
# 'status': {'id': 1, 'name': 'New', 'is_closed': False}, 
# 'priority': {'id': 3, 'name': 'High'}, 
# 'author': {'id': 5, 'name': 'Paul Philion'}, 
# 'assigned_to': {'id': 6, 'name': 'Esther Jang'}, 
# 'subject': 'Testing email notification', 
# 'description': 'Is email getting sent?\r\n\r\nEsther will know.', 
# 'start_date': '2023-08-01', 
# 'due_date': None, 
# 'done_ratio': 0, 
# 'is_private': False, 
# 'estimated_hours': None, 
# 'total_estimated_hours': None, 
# 'spent_hours': 0.0, 
# 'total_spent_hours': 0.0, 
# 'created_on': '2023-08-01T00:21:07Z', 
# 'updated_on': '2023-08-04T16:34:24Z', 
# 'closed_on': None