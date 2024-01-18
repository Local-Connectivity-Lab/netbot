# netbot

[![Python application](https://github.com/philion/netbot/actions/workflows/python-app.yml/badge.svg?branch=main)](https://github.com/philion/netbot/actions/workflows/python-app.yml)

Testing currently requires VPN access, so automanted tests are skipped for now. To test manually, run `python -m unittest` from the commandline with a valid `.env` file.

community **NET**work discord **BOT**, for integrating network management functions

## Deploy netbot
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


## Discord Token & Invite Bot
To enable netbot on your Discord server, you need to generate a valid `DISCORD_TOKEN` and then invite the bot to your Discord instance.

1. Go to https://discord.com/developers/applications and login.
2. Create a **New Application** (top-right button).
2. Fill in the *Name* and click the Terms of Service.
3. Add a Description on the General Information page and save changes. 
3. In the "Bot" settings, *unset* the **Public Bot** switch.
3. One the OAuth2/General settings, copy the Client ID to a safe location.
3. *Reset* the Client Secret and copy it. This is the DISCORD_TOKEN.
3. Create a `.env` file containing: `DISCORD_TOKEN=your-token-contents`
4. In the OAuth2/URL Generator setion, generate a URL for a **bot** with **Administrator** permissions.
5. That URL will look something like:
    https://discord.com/api/oauth2/authorize?client_id=[client-id]&permissions=8&scope=bot
6. Open a browser with that URL and and login.
7. You'll be presented with a window to add your bot to any server you have admin permissions for.
8. Select your server and click OK.

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

## Deploy threader
The threader functionality, managed by `threader.py`, needs to be registered as a cron job to run every 5 minutes.

```
sudo crontab -e
```

and add the following entry to the bottom:
```
*/5 * * * * /home/scn/github/netbot/threader_job.sh | /usr/bin/logger -t threader
```

This cron job uses the Python venv to execute, and captures std and err output to syslog (tagged "threader").

Logs from the runs are stored in `/home/scn/github/netbot/logs` folder, one per cron jon with timestamps.


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

## CLI

A command-line interface version of the `tickets` Discord bot command provides the same capablities as the bot on Discord. This CLI was developed to help testing, which the asynchonous nature of Discord interactions adds a layer of complexity to.

```
cli.py                   - List the new tickets assigned to me or teams I'm on
cli.py [user]            - List the tickets assigned to user
cli.py [#]               - List details for ticket #
cli.py [query]           - Search for tickets containing the term [query]
cli.py [#] assign [user] - Assign ticket # to the specified user
cli.py [#] unassign      - Mark ticket # new and unassigned.
cli.py [#] progress      - Assign ticket # to yourself and set it yourself.
cli.py [#] resolve       - Mark ticket number # resolved.
```

### CLI Configuration

To configure the API key needed for `cli.py` to access the Redmine server, create a API key as per: https://www.redmine.org/projects/redmine/wiki/Rest_api#Authentication, notably:

> You can find your API key on your account page ( /my/account ) when logged in, on the right-hand pane of the default layout.

Once you have you API key, create a file in the local directoy named `.env`.

In the new file, create entries for:

    REDMINE_TOKEN=[your redmine api token]
    REDMINE_URL=http://your.redmine.server

Now you should be able to see a list of interesting tickets, specifically for the user with the supplied API key.

    ./cli.py


## Build and Test

A `Makefile` is provided with the following targets:
- `venv`     : build a Python virtual environment ("venv") in `.venv`
- `test`     : run the unit test suite
- `coverage` : run the unit tests and generate a minimal coverage report
- `htmlcov`  : run the unit tests and generate a full report in htmlcov/
