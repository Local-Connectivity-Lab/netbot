#!/usr/bin/env python3

import os
import logging

import discord

import redmine
import netbox

from dotenv import load_dotenv

import asyncio


logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

log.info('initializing environment')

# load security creds from the `.env` file
load_dotenv()

redmineClient = redmine.Client()
discordClient = discord.Client()

# query "open tickets with discord-thread=Yes modified in the last N minutes"
threaded_issue_query = "/issues.json?status_id=open&discord_thread=yes&sort=category:desc,updated_on"

for issue in redmineClient.query(threaded_issue_query):
    # * if thread does not exist, create it
    threadName = f"TICKET-#{issue.id}"

    assigned = None
    if hasattr(issue, 'assigned_to'):
       assigned = issue.assigned_to.name

    print(f"#{issue.id}: assigned to {assigned} {issue.subject} - {issue.priority.name}")

    
# * get discord comments from last N minutes and post as note to ticket

# * get comments from ticket from last N minutes and post to discord thread


#discord = "?" # HOW?
#channel = discord.channel("some-channel-name") # HOW?


async def send_message_to_specific_channel(message: str, id: int):
  channel = discordClient.get_channel(id)
  await channel.send(message)


# setup the async to send the message
#asyncio.run_coroutine_threadsafe(send_message_to_specific_channel('abc',123), discordClient.loop)

