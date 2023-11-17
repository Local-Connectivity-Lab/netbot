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

### Configuration

To configure the API key needed for `tickets.py` to access the Redmine server, create a API key as per: https://www.redmine.org/projects/redmine/wiki/Rest_api#Authentication, notably:

> You can find your API key on your account page ( /my/account ) when logged in, on the right-hand pane of the default layout.

Once you have you API key, create a file in the local directoy named `.env`.

In the new file, create entries for:

    REDMINE_TOKEN=[your redmine api token]
    REDMINE_URL=http://your.redmine.server

Now you should be able to see a list of interesting tickets, specifically for the user with the supplied API key.

    ./tickets.py
	

## Development Log

### 2023-08-29
After the ticket workflow discussions, I've been thinking about how to better integrate the "issue source of truth" (was osticket, becomming redmine) with the tools that *humans* use for discussion and issue resolution (Discord). Esther suggested an integration that tracked ticket discussion in specific threads, which was similar to slack-thread-per-issue in a few startups. 

The state of this thread tracking can be managed in redmine, using a custom boolean field attached to the issue. When this flag is enabled (for an open ticket), an external cron script can sync comments on a Discord thread with comments on the redmine ticket.

As the netbot.py code is getting complex, it's time to start partitioning the support code into modules:
* DONE First is all the redmine and netbox specific code into their own files.
* Then rebuilding netbot to use the new encapsulated classes. - TODO Test in PROD
* Then adding a job to encapsulate "reqularly manage issue threads":
  * A cron job every N minutes to query "open tickets with discord-thread=Yes modified in the last N minutes"
  * For each:
    * if thread does not exist, create it
    * get discord comments from last N minutes and post as note to ticket
    * get comments from ticket from last N minutes and post to discord thread

Side note about user ids and impersonation: https://www.redmine.org/projects/redmine/wiki/rest_api#User-Impersonation

It looks like it is possible to set a header to impersonate a user:

    X-Redmine-Switch-User: jsmith

This can be used to map Discord users to redmine users. (we'll see how it goes)

### 2023-08-28

Simplified file format, based on authentication needs:

```
redmine:
  command_name:
    query: <url-of-query>
	format: <python str.format string to markdown-ify the query results>
  tickets:
	query: "/issues.json?status_id=open&sort=category:desc,updated_on"
	format: "**[#{issue['id']}](<{self.url}/issues/{issue['id']}>)** {issue['subject']} - {issue['priority']['name']} - {age} old"
	# note: requires {age}, which is generated in the function
```


### 2023-08-27

#### Ticket Workflow
Paul's description of a potential workflow for incoming issues.

1. User has a problem, question, or concern.
2. Sends email to expected address with issue. (currently redmine@seattlecommunitynetwork.org)
3. ticket-system collects new email (currently, an every-5-minute cron task)
4. ticket-system creates and categorizes new ticket from email
    1. ticket-system can also read attributes directly from email (TODO: test)
5. new ticket notification is sent based on data available in ticket (or not)
    1. if there are certain fields filled in (assigned-to, role, etc). a specific notification can be sent.
    2. if not, a more general notification is sent to an "incoming ticket" channel to notify that the system can't automatically route the ticket.
6. Assuming general notification, a person-in-a-specific role for unhandled incoming tickets sets the role/necessary attrs for the ticket.
    2. and the standard notifications to the roles/sites are sent

#### Alternate Flows
* specific vs new generic emails.
* wrong email, wrong address, wrong system (scn.org)
* timeouts on notifications - time-since-last-update crosses a threshold for open tickets results in new notifications.

#### Workflow Notes
* What attributes are required
* There will always be a human involved, so design that from the start.
* But design the system low volume, so the messages stand out and are important.

#### Design Options
* multiple incoming email addresses, one for each site or "area of concern"
* test capabilities of attributes in incoming email.


### 2023-08-25
Deeper design discussion about data, caching, commands and abstractions.

Basic idea -> command -> autocomplete-options -> command+params -> url/request -> response (json) -> parse to dict -> apply filter -> discord

* command
  * options + autocomplete (interface with file-based impl is superclass?)
	* url (with {} substitution tags)
	* filter, perhaps several or iterating-filters, as per (details vs summary)
	

- commands:
  - my tickets:
		- url: 
		- filter:
	- my [user,identity]:
		- url:
		- filter:
	- sites
		- url:
		- filter:
	- site [sitename]
	- tickets [filter, default=open]
	- ticket [number]

TODO: track down SCN guild/team info and add bot restriction.

### 2023-08-24
Today's goals:
* DONE Get Dockerfile in place
* DONE Get compose.yaml in place
* DONE Test full deploy on azure
* DONE Update docs to match
* DONE Get simple redmine calls in place.

Dockerfile and compose.yaml in place and working.

Deployed and working in azure on redmine host.

Turning to....
#### redmine
* for JSON content, it must be set to Content-Type: application/json
* token passed in as a "X-Redmine-API-Key" HTTP header
* https://www.redmine.org/projects/redmine/wiki/Rest_Issues
* https://www.redmine.org/projects/redmine/wiki/Rest_api


GET /issues.json?status_id=open&sort=category:desc,updated_on

Also adding "humize" to manage dates and timedeltas.

```
pip install humanize
pip freeze > requirements.txt
```

Got simple query working, with links, but... the embeds were screwing everything up.

Got on the pycord discord....

```
you can suppress the embeds by wrapping each url in <>
for example:
<https://google.com>
```

Added that to the formatting in the bot, and volia!

Deployed and working on temp instance in azure.

### 2023-08-23
* DONE Start with a *basic* Discord command, written in python. Get the example working end to end.
* DONE Add a command to query netbox.
* DONE Add netbox API call and get auth working.

#### pycord
Starting work on a new bot, from scratch, based on https://github.com/Pycord-Development/pycord

https://github.com/Pycord-Development/pycord/blob/master/examples/app_commands/slash_autocomplete.py

Adding initial requirement.txt and setting up `venv`:

```
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install py-cord
pip freeze > requirements.txt
```

Simple example runs but fails auth. How is auth handled? Sending a token in the bot run command.

* https://docs.pycord.dev/en/master/api/data_classes.html#discord.Intents.message_content
* https://support-dev.discord.com/hc/en-us/articles/4404772028055

Using `.env` file for auth, with a var named `DISCORD_TOKEN`

```
pip install python-dotenv
pip freeze > requirements.txt
```

Example bot working. 

#### netbox
Moving on to netbox integration.

* code: https://github.com/netbox-community/pynetbox
* docs: https://pynetbox.readthedocs.io/en/latest/

```
pip install pynetbox
pip freeze > requirements.txt
```

The inital command will be getting a list of `sites`.

Code failing due to `ssl.SSLCertVerificationError: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: self-signed certificate (_ssl.c:1002)`

Looks like self-signed certs fail validation, so it needs to be disabled:

    nb.http_session.verify = False

https://pynetbox.readthedocs.io/en/latest/advanced.html#ssl-verification:
```
>>> import pynetbox
>>> import requests
>>> session = requests.Session()
>>> session.verify = False
>>> nb = pynetbox.api(
...     'http://localhost:8000',
...     token='d6f4e314a5b5fefd164995169f28ae32d987704f'
... )
>>> nb.http_session = session
```

After much tinkering, got a `/site` command working in a reliable way.
