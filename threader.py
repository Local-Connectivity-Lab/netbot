#!/usr/bin/env python3

import os
import logging
from pathlib import Path
import datetime as dt
from dotenv import load_dotenv

import imap


# configure logging
logpath = Path("logs")
logpath.mkdir(parents=True, exist_ok=True)
logfile = logpath.joinpath("threader-" + dt.datetime.now().strftime('%Y%m%d-%H%M') + ".log")
print(logfile)
logging.basicConfig(filename=logfile, filemode='a',
    format="{asctime} {levelname:<8s} {name:<16} {message}", style='{',
    level=logging.INFO) # TODO Add cmdline switch for log level.

logging.info(f"starting threader")

# load credentials 
load_dotenv()

# construct the client
imap_client = imap.Client()

# process unseen emails
imap_client.check_unseen()
