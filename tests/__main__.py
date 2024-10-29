"""tests module"""

import logging
import unittest
import sys


log = logging.getLogger(__name__)


def setup_logging(level):
    """Setup preferring logging for test runs."""
    logging.basicConfig(level=level, format="{asctime} {levelname:<8s} {name:<16} {message}", style='{')
    logging.getLogger().setLevel(level)
    # these chatty loggers get set to ERROR regardless
    logging.getLogger("urllib3.connectionpool").setLevel(logging.ERROR)
    logging.getLogger("asyncio").setLevel(logging.ERROR)


if __name__ == '__main__':
    if '-v' in sys.argv:
        setup_logging(logging.DEBUG)
    else:
        setup_logging(logging.ERROR)

    unittest.main(module=None)
