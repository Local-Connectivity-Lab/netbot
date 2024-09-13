#!/usr/bin/env python3
"""email threading module"""
import logging
from dotenv import load_dotenv

from threader import imap

# configure logging
logging.basicConfig(level=logging.INFO,
                    format="{asctime} {levelname:<8s} {name:<16} {message}", style='{')
logging.getLogger("urllib3.connectionpool").setLevel(logging.ERROR)
logging.getLogger("asyncio").setLevel(logging.ERROR)


log = logging.getLogger(__name__)


def main():
    log.info("starting threader")
    # load credentials
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
