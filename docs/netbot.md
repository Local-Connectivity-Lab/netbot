# Netbot Operation

To mangage authorization, security tokens and other credentials are stored in a local `.env` file and read by the code. The following credentials are needed for full integrarion:
```
DISCORD_TOKEN=ABC
REDMINE_TOKEN=123
REDMINE_URL=http://do/re/mi

IMAP_HOST=imap.example.com
IMAP_USER=redmine@example.org
IMAP_PASSWORD=u&me
```

`netbot` uses standard Docker compose:

To run `netbot` using a standard container system:
```
git clone https://github.com/philion/netbot
cd netbox
cp ~/.env ./.env
sudo docker compose up -d
```

to stop:
```
sudo docker compose down
```
The SCN email threader collects new IMAP email messages to publish to Redmine as tickets. The functionality is implemented in `threader.py`, is designed to run periodically as a cron job.


## Discord Token & Invite Bot
To enable netbot on your Discord server, you need to generate a valid `DISCORD_TOKEN` and then invite the bot to your Discord instance.

1. Go to https://discord.com/developers/applications and login.
2. Create a **New Application** (top-right button).
2. Fill in the *Name* and click the Terms of Service.
3. Add a Description on the General Information page and save changes.
4. In the OAuth2/URL Generator section, generate a URL for a **bot** with **Administrator** permissions.
5. That URL will look something like:
    https://discord.com/api/oauth2/authorize?client_id=[client-id]&permissions=8&scope=bot
6. Open a browser with that URL and login.
7. You'll be presented with a window to add your bot to any server you have admin permissions for.
8. Select your server and click OK.
4. Back in the bot setup, in the "Bot" section, under "Build-A-Bot", **Copy** the Token. This is the DISCORD_TOKEN
3. On the same page, a little lower, *unset* the **Public Bot** switch.
4. Under "Privlidged Gateway Intents", enable "Message Content Intent".
5. Create an `.env` file in the `netbot` directory containing:
     `DISCORD_TOKEN=your-token-contents`

Note: Not all admin permissions are needed. If you want a very targeted bot, select:
* Manage Server
* Manage Roles
* Manage Channels
* Manage Expressions
* Read Messages/View Channels
* Send Messages
* Create Pubilc Threads
* Create Private Threads
* Send Messages in Threads
* Manage Messages
* Manage Threads
* Embed Links
* Attach Files
* Read Message History
* Use Slash Commands


## Discord Usage
The following Discord commands are implemented:

```
/scn add [login]    - Map current discord userid to redmine [login]
/scn join [team]    - discord user joins [team] (and maps user id)
/scn leave [team]   - discord user leaves [team]
/scn reindex        - rebuild the bot's index of users, teams and other metadata.
                      Use after adding new users and teams to Redmine.

/tickets me         - (default) tickets assigned to me or my teams
/tickets [team]     - tickets assigned to team [team]
/tickets [user]     - tickets assigned to a specific [user]
/tickets [query]    - tickets that match the term [query]

/ticket # show      - (default) show ticket info for ticket #
/ticket # details   - show ticket # with all notes (in a decent format)

/ticket # assign    - Assign ticket n to the specified user - not yet implemented
/ticket # unassign  - Mark ticket n new and unassigned.
/ticket # progress  - Assign the ticket to yourself and set it yourself.
/ticket # resolve   - Mark the ticket resolved.

/new [title]        - Create a new ticket with the title [title]
```


FIXME

## Setup Checklist

1. Configure `.env` file with IMAP settings
2. Deploy email threader with `crontab`
3. Confirm operation with logging


## Threader Configuration: `.env` file

`threader.sh` relies on the following environment settings:
* `IMAP_HOST`: The IMAP server
* `IMAP_USER`: The IMAP username
* `IMAP_PASSWORD` : Password for the IMAP user.

These values will be loaded from a `.env` file in the same directory as `threader.py`.

To set the values, create (or append to) a `.env` file with valid entries for the IMAP configuration:
```
IMAP_HOST=imap.example.com
IMAP_USER=redmine@example.org
IMAP_PASSWORD=tHePa$Sw0rd
```

Once the `.env` file has been created, the `cron` settings can be configured.


## Threader Deployment: `cron`

[`cron`](https://en.wikipedia.org/wiki/Cron) is a standard *nix tool for scheduling periodic jobs. `threader.py` uses `cron` to run as a stand-alone job every 5 minutes.

To create a new entry for the threader job, use `crontab`:
```
sudo crontab -e
```

and add the following entry to the bottom, to run the threader_job.sh every 5 minutes, and direct the output to system logging with the tag `threader`:
```
*/5 * * * * /home/scn/netbot/threader_job.sh | /usr/bin/logger -t threader
```

Replace `/home/scn/netbot` above with the actual full path to the `threader_job.sh` script on the system.

The `threader_job.sh` exists to make sure the `.env` file and the `venv` Python virtual environment are loaded to execute the `threader.py` code.

All output to stdout and stderr captured and logged to syslog with the tag "threader".


## Threader Logs: `/var/log/syslog`

Logs from executing the `threader` are set to [`syslog`](https://en.wikipedia.org/wiki/Syslog), which is typically logged to the file `/var/log/syslog`.

To see the threader logs in syslog, `grep` is very useful. For example:

`grep threader /var/log/syslog`

Would result in something like:
```
Feb 26 18:20:01 hostname CRON[438320]: (root) CMD (/home/scn/netbot/threader_job.sh 2>&1 | /usr/bin/logger -t threader)
Feb 26 18:20:01 hostname threader: 2024-02-26 18:20:01,596 INFO     __main__         starting threader
Feb 26 18:20:01 hostname threader: 2024-02-26 18:20:01,888 INFO     __main__         starting synchronize for imap
Feb 26 18:20:02 hostname threader: 2024-02-26 18:20:02,290 INFO     imap             logged into imap imap.example.com
Feb 26 18:20:02 hostname threader: 2024-02-26 18:20:02,350 INFO     imap             processing 0 new messages from imap.example.com
Feb 26 18:20:02 hostname threader: 2024-02-26 18:20:02,350 INFO     imap             done. processed 0 messages
```

To filter the logs further, to a specific keyword, timestamp or request-id, pipe through another grep:

`grep threader /var/log/syslog | grep '2024-02-26 18:20'`

In the above case, "match logs that occur in the minute of 6:20pm UTC on Feb 26th" (by matching that specific string in the log timestamp).

Note that logs are typically configured for UTC, and this might make them seem a few hours off.

To watch the threader logs as they are happening (the above log segment occurs every 5 minutes, based on the cron configuration), the Unix [`tail`](https://en.wikipedia.org/wiki/Tail_(Unix)) command is handy:

`tail -f /var/log/syslog | grep threader`

will display the latest logs to the console as they occur, and is a convient way to check if the cron is operating at expected. This is where any access or authtentication errors would be displayed.