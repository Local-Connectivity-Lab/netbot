#!/usr/bin/env python3


import os
import logging

import requests
import discord
import pynetbox


from discord.commands import option
from dotenv import load_dotenv

from discord.ext import commands

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

log.debug('initializing bot')

# load security creds from the `.env` file
load_dotenv()


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
        self.site_names = self.sites.keys()
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
    
    def site_names(self):
        return self.site_names

    def site(self, slug:str):
        return self.sites[slug]

    def load_sites(self):
        """Load the list of sites from the netbox client"""
        sites = {}
        for site in self.client.dcim.sites.all():
            sites[site.slug] = site
            
        return sites



# utility stuff for formatting
def format_site(site):
    #return f"**({site.url})[{site.slug}]** {site.name} {site.last_updated}"
    url = site.url.replace('/api', '') # strip the /api from the url
    return f"**[{site.slug}]({url})** - {site.name}"


netbox = Netbox()
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
    names = netbox.site_names()
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
        for _site in netbox.sites.values():
            msg += format_site(_site) + '\n'
    else:
        msg = format_site(netbox.site(site))
        
    await ctx.respond(msg)


#@bot.slash_command(name="site")
#@option(
#    "site",
#    description="Pick a site",
#    autocomplete=discord.utils.basic_autocomplete(SITES),
#    # Demonstrates passing a static iterable discord.utils.basic_autocomplete
#)
#async def autocomplete_site(ctx: discord.ApplicationContext, site_str: str):
#    # query site details
#    #site = netbox_client.dcim.sites.get(slug=site_str)
#    site_msg = format_site(NETBOX, site_str)
#    await ctx.respond(site_msg)



# run the bot
bot.run()
