.PHONY: all run clean

# Simple makefile to help with repetitive Python tasks
# Targets are:
# - venv     : build a venv in ./.venv
# - test     : run the unit test suite
# - coverage : run the unit tests and generate a minimal coverage report
# - htmlcov  : run the unit tests and generate a full report in htmlcov/

VENV = .venv
PYTHON = $(VENV)/bin/python3
PIP = $(VENV)/bin/pip

all: venv

run: venv
	$(PYTHON) -m netbot.netbot debug sync-off

venv: $(VENV)/bin/activate

$(VENV)/bin/activate: requirements.txt
	python3.11 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

test: $(VENV)/bin/activate
	$(PYTHON) -m unittest

coverage: $(VENV)/bin/activate
	$(PYTHON) -m coverage run -m unittest tests/test_*.py
	$(PYTHON) -m coverage report

htmlcov: $(VENV)/bin/activate
	$(PYTHON) -m coverage run -m unittest
	$(PYTHON) -m coverage html

lint: $(VENV)/bin/activate
	$(PYTHON) -m pylint */*.py

clean:
	rm -rf __pycache__
	rm -rf $(VENV)
	rm -rf htmlcov
	rm -f discord.log
	rm -f dpytest_*.dat
	find . -type f -name ‘*.pyc’ -delete