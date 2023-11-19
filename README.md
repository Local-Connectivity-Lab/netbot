# netbot

community **NET**work discord **BOT**, for integrating network management functions

## Deploy netbot
To mangage authorization, security tokens and other credentials are stored in a local `.env` file and read by the code. The following credentials are needed for full integrarion:
```
DISCORD_TOKEN=someToken1234
NETBOX_TOKEN=anotherToken5678
NETBOX_URL=https://netbox.example.com/
REDMINE_TOKEN=yoToken9012
REDMINE_URL=https://redmine.example.com/
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
`netbot` provides the following commands in Discord:

```
scn add [login]    - Map current discord userid to redmine [login]
scn sync           - manually sychs the current Discord thread (assuming you're in one), or replies with warning 
scn join [team]    - discord user joins [team] (and maps user id)
scn leave [team]   - discord user leaves [team] 
scn reindex        - rebuild the bot's index of users, teams and other metadata. Use when adding new users and teams to Redmine.

tickets me         - (default) tickets assigned to me or my teams
tickets [team]     - tickets assigned to team [team]
tickets [user]     - tickets assigned to a specific [user]
tickets [query]    - tickets that match the term [query]

ticket new [title] - create a new ticket with the title [title]

ticket # show      - (default) show ticket info for ticket #
ticket # details   - show ticket # with all notes (in a decent format)

ticket # assign    - Assign ticket n to the specified user
ticket # unassign  - Mark ticket n new and unassigned.
ticket # progress  - Assign the ticket to yourself and set it yourself.
ticket # resolve   - Mark the ticket resolved.
ticket # note      - Add a note to the specific ticket. same as commenting in the ticket thread (if there is a ticket-thread, works without)
ticket # thread    - Creates new synced thread for ticket in the current text channel, or errors
```

## CLI

A command-line interface version of the `tickets` Discord bot command provides the same capablities as the bot on Discord. This CLI was developed to help testing, which the asynchonous nature of Discord interactions adds a layer of complexity to.

```
tickets.py                   - List the new tickets assigned to me or teams I'm on
tickets.py [user]            - List the tickets assigned to user
tickets.py [n]               - List details for ticket n
tickets.py [query]           - Search for tickets containing this term
tickets.py [n] assign [user] - Assign ticket n to the specified user
tickets.py [n] unassign      - Mark ticket n new and unassigned.
tickets.py [n] progress      - Assign the ticket to yourself and set it yourself.
tickets.py [n] resolve       - Mark the ticket resolved.
```

### CLI Configuration

To configure the API key needed for `tickets.py` to access the Redmine server, create a API key as per: https://www.redmine.org/projects/redmine/wiki/Rest_api#Authentication, notably:

> You can find your API key on your account page ( /my/account ) when logged in, on the right-hand pane of the default layout.

Once you have you API key, create a file in the local directoy named `.env`.

In the new file, create entries for:

    REDMINE_TOKEN=[your redmine api token]
    REDMINE_URL=http://your.redmine.server

Now you should be able to see a list of interesting tickets, specifically for the user with the supplied API key.

    ./tickets.py
	
