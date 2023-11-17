#!/usr/bin/env python3

import os
import logging
from pathlib import Path
import datetime as dt
from dotenv import load_dotenv

import imap
import disclient


# configure logging
#logpath = Path("logs")
#logpath.mkdir(parents=True, exist_ok=True)
#logfile = logpath.joinpath("threader-" + dt.datetime.now().strftime('%Y%m%d-%H%M') + ".log")
#logging.basicConfig(filename=logfile, filemode='a',
#    format="{asctime} {levelname:<8s} {name:<16} {message}", style='{',
#    level=logging.INFO) # TODO Add cmdline switch for log level.
logging.basicConfig(level=logging.DEBUG)

log = logging.getLogger(__name__)
log.info(f"starting threader")

# load credentials 
load_dotenv()

# load some threading services
services = {
    "imap": imap.Client(),
    "discord": disclient.Client(),
}

for name, service in services.items():
    log.info(f"synchronizing {name}")
    service.synchronize()

