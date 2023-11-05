#!/usr/bin/env python3

import logging
import discord
import redmine
from dotenv import load_dotenv

import asyncio


logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

## note: these could go in a 'discord' module
def get_channel(name: str) -> discord.TextChannel:
    return discord.utils.get(discordClient.get_all_channels(), name=name)

def find_thread(channel, name: str) -> discord.Thread:
    ch = get_channel(channel)
    for thread in ch.threads:
        if name == thread.name:
            return thread

async def send_message(message_str: str, channel_name: str) -> discord.Message:
    return await get_channel(channel_name).send(message_str)

async def create_thread(thread_name: str, message_str: str, channel_name: str) -> discord.Thread:
    # threads are started with a message
    message = send_message(message_str, channel_name)
    return await message.create_thread(name=thread_name)

async def propagate_comments(channel: str, issue):
    # * if thread does not exist, create it
    thread_name = f"TICKET-#{issue.id}" #TODO format string
    url = f"{redmineClient.url}/issues/{issue.id}"

    message = f"[#{issue.id} {issue.subject}](<{url}>) - {issue.priority.name} has just been created." #TODO another format str

    thread = find_thread(channel, thread_name)
    if thread == None:
        thread = await create_thread(thread_name, message, channel)

    # * get discord comments from last N minutes and post as note to ticket

    # * get comments from ticket from last N minutes and post to discord thread

async def check_flagged_issues(channel: str, query: str):
    for issue in redmineClient.query(query):
        propagate_comments(channel, issue)
        log.info(f"synchronized comments for {issue}")

rich_format = """
[{issue.tracker.name}] [{issue.priority.name}]
[{site.name}] [{site.zip}]
[{issue.due_date}]
[{issue.assigned_to.name}]
[{issue.status.name}] *
"""

# NOTE: No site associated with ticket as custom data. 
# Could attach as sub-project, and get zip from netbox or custom field on the sub-project.
# "Lead Person" vs "Assigned Team" -> redmine has "assigned to", which can work for team or person.
# but we need better description of what the requirements are. using just assigned to for now.

# ----

# load security creds from the `.env` file
load_dotenv()
log.info('initialized environment')

redmineClient = redmine.Client()
discordClient = discord.Client()

# query "open tickets with discord-thread=Yes modified in the last N minutes"
## 'cf_1' stands for "custom field #1", and true is 1.
threaded_issue_query = "/issues.json?status_id=open&cf_1=1&sort=category:desc,updated_on"
channel_name = "admin-team"

# setup the async to send the message
asyncio.run_coroutine_threadsafe(check_flagged_issues(channel_name, threaded_issue_query), discordClient.loop)
