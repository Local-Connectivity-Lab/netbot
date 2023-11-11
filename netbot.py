#!/usr/bin/env python3


import os
import logging

import discord

import redmine
#import netbox

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


log.info(f"initializing {__name__}")
load_dotenv()
#netbox_client = netbox.Client()
client = redmine.Client()
bot = NetBot()


#async def complete_sites(ctx: discord.AutocompleteContext):
#    """Returns a list of sites that begin with the characters entered so far."""
#    names = netbox_client.site_names
#    return [site for site in names if site.startswith(ctx.value.lower())]


#@bot.slash_command(name="site") 
#@option("site", description="pick a site", autocomplete=complete_sites)
#async def site_command(ctx: discord.ApplicationContext, site="all"):
#    msg = ""
#    if site == 'all':
#        msg = netbox_client.format_sites()
#    else:
#        msg = netbox_client.format_site(netbox_client.site(site))
#        
#    await ctx.respond(msg)


@bot.slash_command(name="tickets")
async def tickets_command(ctx: discord.ApplicationContext):
    # query issues
    tickets = client.find_tickets()
    log.info(f"found {len(tickets)} tickets")

    for status in ["New", "In Progress", "Resolved"]:
        msg = client.format_section(tickets, status)
        if len(msg) > 2000:
            log.warning("message over 2000 chars. truncing.")
            msg = msg[:2000]
        await ctx.respond(msg)

@bot.slash_command(name="intake")
async def intake(ctx: discord.ApplicationContext):
    # query intake issues: new, assigned to the groups ticket-intake.
    # looking up "ticket-intake", to make sure the ID is correct
    team = client.find_group("ticket-intake")

    response = client.query(f"/issues.json?status=New&assigned_to_id={team.id}&sort=priority:desc,updated_on:desc,id:desc&limit=100")
    tickets = response.issues
    log.debug(f"found {len(tickets)} intake tickets")

    print(f"author={ctx.author}, name={ctx.author.name}, display={ctx.author.display_name}")
    user = client.find_discord_user(ctx.author.name)
    print(f"user={user}")

    msg = client.format_section(tickets, "New") # FIXME
    if len(msg) > 2000:
        log.warning("message over 2000 chars. truncing.")
        msg = msg[:2000]
    await ctx.respond(msg)

# run the bot
bot.run()


# namespace(id=1, name='New', is_closed=False)
# There is no way to


# http://10.0.1.20/projects/scn/issues?
# c[]=tracker&c[]=status&c[]=priority&c[]=subject&c[]=assigned_to&c[]=updated_on&
# f[]=status_id&f[]=assigned_to_id&f[]=&
# group_by=
# &op[assigned_to_id]==&op[status_id]==
# &set_filter=1
# &sort=updated_on:desc,priority:desc,id:desc&t[]=
# &utf8=✓&
# v[assigned_to_id][]=19&v[status_id][]=1


# {'id': 126, 'project': namespace(id=1, name='Seattle Community Network'), 
# 'tracker': namespace(id=6, name='Software Maintenance'), 
# 'status': namespace(id=3, name='Resolved', is_closed=True), 
# 'priority': namespace(id=4, name='Urgent'), 
# 'author': namespace(id=7, name='Dan B'), 
# 'assigned_to': namespace(id=7, name='Dan B'), 
# 'category': namespace(id=6, name='tech-research'), 
# 'subject': 'Investigate Log Activity on Jumpbox', 'description': 'Researching suspicious log activity reported by Kent on the weekend of 10.22.2023. ', 'start_date': '2023-10-23', 'due_date': None, 'done_ratio': 100, 'is_private': False, 'estimated_hours': 3.0, 'total_estimated_hours': 3.0, 'spent_hours': 3.0, 'total_spent_hours': 3.0, 'custom_fields': [namespace(id=1, name='Discord Thread', value='0')], 'created_on': '2023-10-23T20:42:03Z', 'updated_on': '2023-10-25T03:00:41Z', 'closed_on': '2023-10-25T03:00:41Z'}