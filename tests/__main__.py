"""tests module"""

import argparse
import logging
import unittest


log = logging.getLogger(__name__)


def setup_logging(verbosity:int):
    """set up logging for netbot"""
    if verbosity == 0:
        log_level = logging.ERROR
    elif verbosity == 1:
        log_level = logging.INFO
    else:
        log_level = logging.DEBUG

    logging.basicConfig(level=log_level,
                        format="{asctime} {levelname:<8s} {name:<16} {message}",
                        style='{')

    if log_level < logging.WARNING:
        # quiet chatty loggers
        logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)


def main():
    """netbot main function"""
    # check args and setup config
    parser = argparse.ArgumentParser(description='Netbot: Discord/Redmine Integration Service')
    parser.add_argument('-v', '--verbose', action='count', default=0, help='Verbosity')
    args = parser.parse_args()
    setup_logging(args.verbose)

    unittest.main(module=None)


if __name__ == '__main__':
    main()
