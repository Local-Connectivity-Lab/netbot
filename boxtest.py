#!/usr/bin/env python3

import os
import pynetbox
import requests
import json
import humanize
import datetime as dt

from dotenv import load_dotenv


def build_netbox_client(url, token):
    """Given a secure token, build a client to communicate with a netbox instance"""
    client = pynetbox.api(url, token)

    # create a custom session to disable SSL validation, as per
    # https://pynetbox.readthedocs.io/en/latest/advanced.html#ssl-verification
    session = requests.Session()
    session.verify = False
    client.http_session = session

    return client

def load_sites(netbox):
    """Load the list of sites from the netbox client"""
    # filtering?
    return netbox.dcim.sites.all()

def format_site(netbox, site_str):
    site = netbox.dcim.sites.get(slug=site_str)
    url = site.url.replace('/api', '') # strip the /api from the url
    #print(vars(site))
    return f"**[{site.slug}]({url})** {site.name} {site.last_updated}"


class Redmine():
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

    def format_issue(self, issue):
        # parse the "updated_on" field to create a datetime
        last_updated = dt.datetime.strptime(issue['updated_on'], '%Y-%m-%dT%H:%M:%SZ')
        # create a human-readable time difference
        age = humanize.naturaldelta(dt.datetime.now() - last_updated)
        # format everything for 
        return f"**[\#{issue['id']}]({self.url}/issues/{issue['id']})** {issue['subject']} {age}"
    
    def format_issues(self):
        msg = ""
        for issue in self.load_issues():
            msg += self.format_issue(issue) + '\n'
        return msg

load_dotenv()
print(Redmine().format_issues())

# 'id': 8, 'url': 'https://netbox.westus2.cloudapp.azure.com:8089/api/dcim/sites/8/', 'display': 'Westin Building', 
# 'name': 'Westin Building', 'slug': 'wbx', 'status': Active, 'region': Seattle, 'group': Transit Sites, 'tenant': None, 'facility': 
# 'Westin Exchange Building', 'time_zone': 'America/Los_Angeles', 'description': '', 'physical_address': '', 'shipping_address': '', 
# 'latitude': None, 'longitude': None, 'comments': '', 'asns': [AS54429, AS395823 (6.2607)], 'tags': [], 'custom_fields': {}, 
# 'created': '2023-03-01T02:16:58.531844Z', 'last_updated': '2023-03-22T01:05:08.302835Z', 'circuit_count': 0, 'device_count': 3, 
# 'prefix_count': 2, 'rack_count': 1, 'virtualmachine_count': 0, 'vlan_count': 0