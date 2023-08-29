#!/usr/bin/env python3


import os
import logging

import discord

import redmine
import netbox

from discord.commands import option
from dotenv import load_dotenv

from discord.ext import commands

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

log.info('initializing bot')

class NetBot(commands.Bot):
    def __init__(self):
        log.info(f'initializing {self}')
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


netbox_client = netbox.Client()
redmine_client = redmine.Client()
bot = NetBot()


async def complete_sites(ctx: discord.AutocompleteContext):
    """Returns a list of sites that begin with the characters entered so far."""
    names = netbox_client.site_names
    return [site for site in names if site.startswith(ctx.value.lower())]


@bot.slash_command(name="site") 
@option("site", description="pick a site", autocomplete=complete_sites)
async def site_command(ctx: discord.ApplicationContext, site="all"):
    msg = ""
    if site == 'all':
        msg = netbox_client.format_sites()
    else:
        msg = netbox_client.format_site(netbox_client.site(site))
        
    await ctx.respond(msg)


@bot.slash_command(name="tickets")
async def tickets_command(ctx: discord.ApplicationContext):
    # query issues
    msg = redmine_client.format_issues()
    await ctx.respond(msg)


# run the bot
bot.run()
