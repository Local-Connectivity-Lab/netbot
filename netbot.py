#!/usr/bin/env python3

## --log=DEBUG

import os
import logging

import requests
import discord
import pynetbox


from discord.commands import option
from dotenv import load_dotenv

log = logging.getLogger(__name__)
NETBOX = None

log.debug('initializing bot')
bot = discord.Bot()

# from https://drive.google.com/drive/u/1/folders/1zfSaL_Whbi8esFZk8tb8EKsdcUhGNDDo
#SITES = [
#    "filipino-community-village",
#    "katharines-place",
#    "lihi-southend-village",
#    "nickelsville-cd",
#    "nickelsville-northlake",
#    "progressive-skyway-village",
#]

SITES = []

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


def build_netbox_client(url, token):
    """Given a secure token, build a client to communicate with a netbox instance"""
    client = pynetbox.api(url, token)

    # create a custom session to disable SSL validation, as per
    # https://pynetbox.readthedocs.io/en/latest/advanced.html#ssl-verification
    # FIXME This should be removed as soon as real certs are in place.
    session = requests.Session()
    session.verify = False
    client.http_session = session

    return client


def load_sites(netbox):
    """Load the list of sites from the netbox client"""
    sites = {}
    for site in netbox.dcim.sites.all():
        #sites.append(site.slug) # just grabbing the 'slug', or url short name.
        sites[site.slug] = site.id
    return sites


async def get_sites(ctx: discord.AutocompleteContext):
    """Returns a list of colors that begin with the characters entered so far."""
    return [site for site in SITES if site.startswith(ctx.value.lower())]

@bot.slash_command(name="list")
async def sites(ctx: discord.AutocompleteContext):
    msg = ""
    for site in NETBOX.dcim.sites.all():
        msg += format(site) + '\n'

    log.warn
    await ctx.respond(msg)


def format_site(netbox, site_str):
    return format(netbox.dcim.sites.get(slug=site_str))


def format(site):
    #return f"**({site.url})[{site.slug}]** {site.name} {site.last_updated}"
    return f"({site.url})[{site.name}]"


@bot.slash_command(name="site") 
@option("site", description="pick a site", autocomplete=get_sites)
#@option("animal", description="Pick an animal!", autocomplete=get_animals)
async def autocomplete_example(
    ctx: discord.ApplicationContext,
    site_slug: str,
):
    site_msg = format_site(NETBOX, site_slug) ### FIXME: global NETBOX defination
    await ctx.respond(site_msg)


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


# load security creds from the `.env` file
load_dotenv()
discord_token = os.getenv('DISCORD_TOKEN')
netbox_token = os.getenv('NETBOX_TOKEN')
netbox_url = os.getenv('NETBOX_URL')

# load some cached settings from netbox
# TODO: need a hook to refresh this cache: command in the bot (eventually)
log.info("loading sites from netbox")
NETBOX = build_netbox_client(netbox_url, netbox_token)
SITES.extend(load_sites(NETBOX))
log.debug(SITES)

# run the bot, main thread
log.info("starting bot")
bot.run(discord_token)
