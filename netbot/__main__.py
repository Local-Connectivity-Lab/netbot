#!/usr/bin/env python3
"""main and logging for netbot"""

import sys
import logging
import argparse

from dotenv import load_dotenv

from redmine.redmine import Client
from netbot.netbot import NetBot


log = logging.getLogger(__name__)


def setup_logging(verbosity:int, syslog: bool):
    """set up logging for netbot"""
    if verbosity == 0:
        log_level = logging.ERROR
    elif verbosity == 1:
        log_level = logging.INFO
    else:
        log_level = logging.DEBUG

    handler = None
    if syslog:
        handler = [logging.handlers.SysLogHandler(address='/dev/log')]

    logging.basicConfig(level=log_level,
                        handlers=handler,
                        format="{asctime} {levelname:<8s} {name:<16} {message}",
                        style='{')

    if log_level < logging.WARNING:
        # quiet chatty loggers
        logging.getLogger("discord.gateway").setLevel(logging.WARNING)
        logging.getLogger("discord.http").setLevel(logging.WARNING)
        logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)
        logging.getLogger("discord.client").setLevel(logging.WARNING)
        logging.getLogger("discord.webhook.async_").setLevel(logging.WARNING)


# -c/--config <file> : config file for logging


def main():
    """netbot main function"""
    # check args and setup config
    parser = argparse.ArgumentParser(description='Netbot: Discord/Redmine Integration Service')

    parser.add_argument('--sync_off', help='Turn off automatic syncronization', required=False, default=False)
    parser.add_argument('--syslog', help='Send logs to syslog', required=False, default=False)
    parser.add_argument('-v', '--verbose', action='count', default=0, help='Verbosity')

    args = parser.parse_args()

    setup_logging(args.verbose, args.syslog)

    log.info(f"loading .env for {__name__}")
    load_dotenv()

    client = Client.fromenv()
    bot = NetBot(client)

    if args.sync_off:
        log.info("Disabling ticket sync, as per --sync_off param")
        bot.run_sync = False

    # register cogs
    bot.load_extension("netbot.cog_scn")
    bot.load_extension("netbot.cog_tickets")

    # sanity check!
    client.sanity_check()

    # run the bot
    bot.run_bot()
    sys.exit(0)


if __name__ == '__main__':
    main()
