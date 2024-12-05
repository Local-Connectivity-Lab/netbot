#!/usr/bin/env python3
"""github issues as tickets"""

import os
import logging
import urllib.parse

from dotenv import load_dotenv

from redmine.session import RedmineSession, RedmineException
from redmine.model import Ticket


log = logging.getLogger(__name__)


class GithubSession(RedmineSession):
    """docstring"""
    @classmethod
    def fromenv(cls):
        url = 'https://api.github.com'
        token = os.getenv('GITHUB_TOKEN')
        if token is None:
            raise RedmineException("Unable to load GITHUB_TOKEN", "__init__")

        return cls(url, token)


    @classmethod
    def fromenvfile(cls):
        load_dotenv()
        return cls.fromenv()


    def get_headers(self, impersonate_id:str|None=None):
        headers = {
            'User-Agent': 'netbot/0.0.1', # TODO update to project version, and add version management
            'Accept': 'application/vnd.github+json',
            'Authorization': 'Bearer ' + self.token,
            'X-GitHub-Api-Version': '2022-11-28',
        }

        return headers


class GithubTicketManager():
    """manage redmine tickets"""
    def __init__(self, sess: GithubSession, project:str):
        self.session = sess
        # project is assumed to br org/repo
        self.project = project # NOTE could be org/project and skip org
        self.ticket_url = f"/{self.project}/issues/"

    def unmarshal(self, response) -> Ticket:
        ticket_id = response['number']
        title = response['title']
        desc = response['description']
        created_on = response['created_on']
        updated_on = response['updated_on']
        return Ticket(ticket_id, title, desc, created_on, updated_on)

    def get(self, ticket_id:int, **params) -> Ticket|None:
        """get a ticket by ID"""
        if ticket_id is None or ticket_id == 0:
            #log.debug(f"Invalid ticket number: {ticket_id}")
            return None

        query = f"{self.ticket_url}{ticket_id}?{urllib.parse.urlencode(params)}"
        log.debug(f"getting #{ticket_id} with {query}")

        response = self.session.get(query)
        if response:
            return self.unmarshal(response['issue'])
        else:
            log.debug(f"Unknown ticket number: {ticket_id}, params:{params}")
            return None



if __name__ == '__main__':
    # load session
    load_dotenv()
    session = GithubSession.fromenv()
    ticket_mgr = GithubTicketManager(session, "Local-Connectivity-Lab/ccn-coverage-vis")
    ticket = ticket_mgr.get(40)
    print(ticket)
