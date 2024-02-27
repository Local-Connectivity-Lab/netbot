# Netbot Design and Implementation

## netbot


### Discord User Mapping
To maintain accurate attribution in Redmine when comments are made in Discord, a mapping is setup between Discord users and Redmine users.

This mapping is stored in a custom field, "Discord ID", in the Redmine user data.


## Email Threader

cron job

script to encapsulate loadin python environment

processes each new IMAP message:
- extracts sender from From header
- creates account for sender if one does not exist, based on email
- extracts 'content' of email
  - if content is HTML, it is converted to text (quick and dirty, this could be better)
- searches for a ticket with the same Subject as the new email
- if a matching ticket is found, the content is appended to that ticket, attributed to the account
- if not, a new Redmine ticket is created with the email subject and content, attributed to the account
- if the user is blocked (see below), the ticket is created as above, and will immediately be put in a `Reject` state.


## Block system

A "block" system allows messages from certain users be recorded as rejected tickets when processing.

This in initiated when the user is added to a `blocked` team in Redmine. New tickets from users in the `blocked` team are automatically rejected. Updates (new messages using the same subject) from blocked users are still append to rejected ticket, but doesn't change the status of the ticket.

When the `/scn block <email>` command is issued, the user is added to the `blocked` team, then all tickets created by the user are put in a `Reject`ed state. If a user is moved to the `blocked` team without using the Discord command, reject post-action will not trigger (currently). `/scn block` is designed to be idempotent, and multiple calls for the same email should result in the same outcome: user in blocked team and all authored tickets rejected.

The user can be "unblocked" by removing them from the `blocked` team or issuing `/scn unblock <email>`. None of the `Reject`ed tickets will be updated, but new tickets will be created and not rejected.


## Build and Test
A `Makefile` is provided with the following targets:
- `venv`     : build a Python virtual environment ("venv") in `.venv`
- `test`     : run the unit test suite
- `coverage` : run the unit tests and generate a minimal coverage report
- `htmlcov`  : run the unit tests and generate a full report in htmlcov/
- `lint`     : generate a pylint report, based on settings in `pylintrc`

All the [`make`](https://en.wikipedia.org/wiki/Make_(software)) targets depend on `venv`, which builds a [standard Python virtual environment](https://docs.python.org/3/library/venv.html).

### Constructing a Virtual Environment

Creating the virtual environment with `make`:
```
make venv
```

If you prefer to do so by hand:
```
python3.11 -m venv .venv
./.venv/bin/pip install --upgrade pip
./.venv/bin/pip install -r requirements.txt
```

`python3.11` is used specificlly as a widely available version. That version can be managed in the `Makefile`.

Any builds targeted with `make` will used the `venv` automatically (and generate it, if it's not already there). Users operating Python from the command line will need to [load their environment](https://docs.python.org/3/library/venv.html#how-venvs-work).

For example, `bash` and `zsh` users would:
```
$ source .venv/bin/activate
```

### Testing

This is a Python project, and tests can be run using Python unittest:
```
python -m unittest
```
or
```
make test
```

Each `test_*.py` file can be run independantly, which targets the specific sub-system and turns on DEBUG logging.

Full integration testing requires standing up a local testbed with the [SCN Redmine](https://github.com/Local-Connectivity-Lab/scn-redmine) container composition. Tests that cannot be run without access to Redmine will skip when the `.env` file is absent.

Automated testing using Github Actions is disabled without valid `.env` settings. *When/if SCN releases public containers*, Github Actions could be updated to run the full integration suite with an `.env` configured for an ephemeral test instance built from the public container.


### Deploying a Redmine Testbed

All the services rely on redmine for testing.

To setup a test instance, follow https://github.com/Local-Connectivity-Lab/scn-redmine/blob/main/README.md

* Deploy scn_redmine
* add custom fields and admin user - covered in Initial Setup (or will be)
* Setup access token in .env as per [redmine](./redmine.md)
