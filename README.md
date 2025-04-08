# netbot

## community **NET**work discord **BOT**, for integrating network management functions

[![Python application](https://github.com/philion/netbot/actions/workflows/python-app.yml/badge.svg?branch=main)](https://github.com/philion/netbot/actions/workflows/python-app.yml)


A collection of Seattle Community Network ([SCN](https://seattlecommunitynetwork.org/)) tools, including:
* **`threader`**: SCN's email threading service to collect and categorize SCN messages.
* **`netbot`**: SCN's Discord bot to manage Redmine tickets from Discord.
* **`redmine`**: A Redmine client written in Python, designed for SCN use cases.

This code base currently supports several different services due to the reliance on the Redmine client code. (In the future, this should be split into several projects, and redmine.py cleaned up and submitted to PyPI.)


## threader

The email threader functionality is implemented in `threader.py`, is designed to run periodically as a cron job.

For design and implementation details, see [Design](docs/design.md).

For deployment and operational details, see [Threader Operation](docs/threader.md).


## netbot

The netbot functionality is implemented in `netbot.py` (and supporting `cog_*.py` implementations), is designed to run in as a container using a standard `compose.yaml` file.

For design and implementation details, see [Design](docs/design.md).

For deployment and operational details, see [Netbot Operation](docs/netbot.md).


## Development

`netbot` has been updated to run with standard [`uv`](https://docs.astral.sh/uv/) commands.

To set up a development envrionment, after installing [`uv`](https://docs.astral.sh/uv/getting-started/installation/):
```sh
git clone https://github.com/Local-Connectivity-Lab/netbot
cd netbot
uv run tests
```

Specific commands have been added for uv:
- `uv run netbot` : run `netbot`
- `uv run threader` : run the email `threader`
- `uv run tests` : run the test suite

The email threader can be run from a system crontab job with:
```sh
uv run --project /home/scn/netbot threader
```

```
sudo crontab -e

# add the following line
*/5 * * * * uv run --project /home/scn/netbot threader | /usr/bin/logger -t threader
```

### Old (but still supported)
A `Makefile` is provided with the following targets:
- `venv`     : build a Python virtual environment ("venv")
- `run`      : run netbot
- `test`     : run the unit test suite
- `coverage` : run the unit tests and generate a minimal coverage report
- `htmlcov`  : run the unit tests and generate a full report in htmlcov/

Testing and coverage requires standing up a local testbed. For details, see [Design](docs/design.md).
