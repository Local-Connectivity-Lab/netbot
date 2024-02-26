# Netbot Design and Implementation

FIXME - design details

## netbot

### user mapping

## threader

## block system


## Building and Testing
A `Makefile` is provided with the following targets:
- `venv`     : build a Python virtual environment ("venv") in `.venv`
- `test`     : run the unit test suite
- `coverage` : run the unit tests and generate a minimal coverage report
- `htmlcov`  : run the unit tests and generate a full report in htmlcov/


## Testing

Testing requires standing up a local testbed with the [SCN Redmine](https://github.com/Local-Connectivity-Lab/scn-redmine) container composition. Automated testing using Git Actions have been disabled without valid `.env` settings. To test manually, run `python -m unittest` from the commandline with a valid `.env` file. See [Development](docs/development.md) for further details.


## Deploying a Redmine Testbed

All the services rely on redmine for testing....

* DEploy scn_redmine
* add custom fields and users...
* setup access tockets, as per...