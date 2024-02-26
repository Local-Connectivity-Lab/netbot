# Netbot Operations

## Setup Checklist

1. Configure `.env` file with Redmine and Discord settings
   1. Generate the [Discord token](#discord-token)
   2. Generate the [Redmine token](#redmine-token)
2. Deploy `netbot` container with `docker compose`
3. Confirm operation with `docker logs`

To start, you will need the URL of the Redmine server you're integrating with, and admin access to that redmine instance.


## Cheatsheet

* To deploy the latest: `git pull; docker compose up --build -d`
* To shudown netbot: `docker cmopose down`
* To check for errors in the logs: `docker logs netbot | grep ERROR`


## Netbot Configuration: `.env` file

To mangage authorization, security tokens and other credentials are stored in a local `.env` file and read by the code. The following credentials are needed for `netbot.sh`:
* `REDMINE_TOKEN`: Secure Redmine API token
* `REDMINE_URL`: URL of Redmine service
* `DISCORD_TOKEN`: Secure Discord API token, see Discord Token below

These values will be loaded from a `.env` file in the same directory as `netbot.py` and `compose.yaml`.

To set the values, create (or append to) a `.env` file with valid entries for the IMAP configuration:
```
REDMINE_TOKEN=123-TOKEN-456
REDMINE_URL=http://localhost
DISCORD_TOKEN=ABC-ANOTHER-TOKEN-DEF
```

Once the `.env` file has been created, the container can be started


## Docker Compose

`netbot` uses standard Docker compose:

To run `netbot` using a standard container system:
```
cd netbox
git pull
sudo docker compose up --build -d
```

to stop:
```
sudo docker compose down
```
The SCN email threader collects new IMAP email messages to publish to Redmine as tickets. The functionality is implemented in `threader.py`, is designed to run periodically as a cron job.


## Discord Token
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


## Redmine Token

TODO: create admin user as part of Redmine deployment. Not yet implemented.

Each Redmine API token is associated with a specific user, so an specific "admin" user is created for bot API access.

### Create the `admin` user

If the `admin` user already exists and Administrator privlidges, skip this step.

An existing Redmine administrator must log into the Redmine instance to access REDMINE_URL/user to create a new user:
* Login to Redmine via REDMINE_URL
* Click **+ New User** (top right)
* Enter the follow values. Everything else can be left as is.
  * Login: `admin`
  * First name: `Admin`
  * Last name: `-`
  * Email: `root@example.com`
  * Administrator: (check the box)
  * Authentication mode: Internal
  * Password: (generate a new secure password)
  * Confirmation: (same new password)
* Click **Create**

### Get the REDMINE_TOKEN

Once the `admin` user has been created:
* Login as the admin user with the new password
* Click on "My Account" (top right, REDMINE_URL/my/account)
* In the right-hand column, look for **API access key**
* Click the related **Show** button
* Copy the revealed token to the `.env` file as `REDMINE_TOKEN`


## Netbot Logs: `docker logs`

As a container, the logs from `netbot` are avilabel using the stantard Docker logging facilities. To view netbot logs, use:

`docker logs netbot`

To search for specific keyword 'xyz', combine that with `grep`:

`docker logs netbot | grep xyz`

To display the netbot logs to the console as they occur, the Unix [`tail`](https://en.wikipedia.org/wiki/Tail_(Unix)) command is handy:

`docker logs netbot | tail -f`
