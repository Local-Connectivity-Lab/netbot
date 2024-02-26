# Netbot Command Line Interface (CLI)

`cli.py` provides command-line interface version of the `netbot` capablities.


## Configuration: `.env` file

`cli.py` relies on the following environment settings:
* `REDMINE_TOKEN`: Secure Redmine API token
* `REDMINE_URL`: URL of Redmine service

To configure the API key needed for `cli.py` to access the Redmine server, create a API key as per: https://www.redmine.org/projects/redmine/wiki/Rest_api#Authentication, notably:

> You can find your API key on your account page (/my/account) when logged in, on the right-hand pane of the default layout.

Once you have you API key, create a file in the local directoy named `.env`.

In the new file, create entries for:

```
REDMINE_TOKEN=[your redmine api token]
REDMINE_URL=http://your.redmine.server
```

Once the `.env` file has been created, the `cli.py` should "just work".


## CLI Usage

```
cli.py                   - List the new tickets assigned to me or teams I'm on
cli.py [user]            - List the tickets assigned to user
cli.py [#]               - List details for ticket #
cli.py [query]           - Search for tickets containing the term [query]
cli.py [#] assign [user] - Assign ticket # to the specified user
cli.py [#] unassign      - Mark ticket # new and unassigned.
cli.py [#] progress      - Assign ticket # to yourself and set it yourself.
cli.py [#] resolve       - Mark ticket number # resolved.
```


## Logging

All CLI logs are output to the console, and can be redirected using standard Unix tools.