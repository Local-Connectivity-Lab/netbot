#!/usr/bin/env python3
"""main and logging for netbot"""

import logging
import argparse

from dotenv import load_dotenv

from threader import imap


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
        logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)


def main():
    """netbot main function"""
    # check args and setup config
    parser = argparse.ArgumentParser(description='Threader: Email/Redmine Integration Service')

    parser.add_argument('--syslog', help='Send logs to syslog', required=False, default=False)
    parser.add_argument('-v', '--verbose', action='count', default=0, help='Verbosity')

    args = parser.parse_args()

    setup_logging(args.verbose, args.syslog)

    log.info(f"loading .env for {__name__}")
    load_dotenv()


    # load some threading services
    services = {
        "imap": imap.Client(),
    }

    for name, service in services.items():
        log.info(f"starting synchronize for {name}")
        service.synchronize()


if __name__ == '__main__':
    main()
