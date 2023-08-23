# netbot
community **NET**work discord **BOT**, for integrating network management functions

## Deploy
To mangage authorization, security tokens and other credentials are stored in a local `.env` file and read by the code. The following credentials are needed for full integrarion:
```
DISCORD_TOKEN=someToken1234
NETBOX_TOKEN=anotherToken5678
```

To run `netbot` using a standard python venv setup:
```
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
./netbot.py
```

#TODO: netbot should be containerized and run as a standard container (with heartbeat, etc) in the typical SCN setup.

## Development Log

### 2023-08-23
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
