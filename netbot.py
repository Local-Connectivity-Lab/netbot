#!/usr/bin/env python3


import os
import logging

import requests
import discord
import pynetbox
import json
import humanize
import datetime as dt


from discord.commands import option
from dotenv import load_dotenv

from discord.ext import commands

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

log.debug('initializing bot')

# load security creds from the `.env` file
# not used in container
#load_dotenv()


class NetBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(
            command_prefix=commands.when_mentioned_or("!"), intents=intents
        )

    def run(self):
        log.info(f"starting {self}")
        super().run(os.getenv('DISCORD_TOKEN'))

    async def on_ready(self):
        log.info(f"Logged in as {self.user} (ID: {self.user.id})")


class Netbox():
    def __init__(self):
        # build the client and initalze the constructs
        self.client = Netbox.build_client(url=os.getenv('NETBOX_URL'), token=os.getenv('NETBOX_TOKEN'))
        self.reload()

    # load any data that needs to be loaded
    def reload(self):
        """Load the data and cache locally, to avoid a lot of slow network calls"""
        log.info("Loading sites")
        self.sites = self.load_sites()
        self.site_names = list(self.sites)
        log.info(f"Loaded: {self.site_names}")

    # build a client for communicating with an instance of netbox
    def build_client(url:str, token:str):
        """Given a secure token, build a client to communicate with a netbox instance"""
        client = pynetbox.api(url, token)

        # create a custom session to disable SSL validation, as per
        # https://pynetbox.readthedocs.io/en/latest/advanced.html#ssl-verification
        # FIXME This should be removed as soon as real certs are in place.
        session = requests.Session()
        session.verify = False
        client.http_session = session
        
        return client

    def site(self, slug:str):
        return self.sites[slug]

    def load_sites(self):
        """Load the list of sites from the netbox client"""
        sites = {}
        for site in self.client.dcim.sites.all():
            sites[site.slug] = site
            
        return sites
    
    def format_site(self, site):
        #return f"**({site.url})[{site.slug}]** {site.name} {site.last_updated}"
        url = site.url.replace('/api', '') # strip the /api from the url
        return f"**[{site.slug}]({url})** - {site.name}"
    
    def format_sites(self):
        msg = ""
        for site in self.sites.values():
            msg += self.format_site(site) + '\n'
        return msg


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
        return f"**[#{issue['id']}]({self.url}/issues/{issue['id']})** {issue['subject']} - {issue['priority']['Name']} {age} old"
    
    def format_issues(self):
        msg = ""
        for issue in self.load_issues():
            msg += self.format_issue(issue) + '\n'
        return msg

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




netbox = Netbox()
redmine = Redmine()
bot = NetBot()


## Left as example code, for now
#async def color_searcher(ctx: discord.AutocompleteContext):
#    """
#    Returns a list of matching colors from the LOTS_OF_COLORS list.
#
#   In this example, we've added logic to only display any results in the
#    returned list if the user's ID exists in the BASIC_ALLOWED list.
#
#    This is to demonstrate passing a callback in the discord.utils.basic_autocomplete function.
#    """
#
#    return [
#        color for color in LOTS_OF_COLORS if ctx.interaction.user.id in BASIC_ALLOWED
#    ]


#def build_netbox_client(url, token):
#    """Given a secure token, build a client to communicate with a netbox instance"""
#    client = pynetbox.api(url, token)
#
    # create a custom session to disable SSL validation, as per
    # https://pynetbox.readthedocs.io/en/latest/advanced.html#ssl-verification
    # FIXME This should be removed as soon as real certs are in place.
#    session = requests.Session()
#    session.verify = False
#    client.http_session = session
#
#    return client


async def complete_sites(ctx: discord.AutocompleteContext):
    """Returns a list of sites that begin with the characters entered so far."""
    names = netbox.site_names
    return [site for site in names if site.startswith(ctx.value.lower())]


#@bot.slash_command(name="sites", description="list all the active sites")
#async def sites(ctx):
#    msg = ""
#    for site in netbox.sites():
#        msg += format(site) + '\n'
#    await ctx.respond(msg)


@bot.slash_command(name="site") 
@option("site", description="pick a site", autocomplete=complete_sites)
async def site_command(ctx: discord.ApplicationContext, site="all"):
    msg = ""
    if site == 'all':
        msg = netbox.format_sites()
    else:
        msg = netbox.format_site(netbox.site(site))
        
    await ctx.respond(msg)


@bot.slash_command(name="tickets")
async def tickets_command(ctx: discord.ApplicationContext):
    # query issues
    site_msg = redmine.format_issues()

    # to disable embeds
    flags = discord.MessageFlags(suppress_embeds=True).value

    await ctx.respond(site_msg, flags=flags)


# run the bot
bot.run()
