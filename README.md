# netbot
community **NET**work discord **BOT**, for integrating network management functions

## Deploy
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

#TODO: netbot should be containerized and run as a standard container (with heartbeat, etc) in the typical SCN setup.

## Development Log

### 2023-08-24
Today's goals:
* DONE Get Dockerfile in place
* DONE Get compose.yaml in place
* DONE Test full deploy on azure
* DONE Update docs to match
* Get simple redmine calls in place.

Dockerfile and compose.yaml in place and working.

Deployed and working in azure on redmine host.


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