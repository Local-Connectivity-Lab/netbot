.PHONY: all run clean

# Simple makefile to help with repetitive Python tasks
# Targets are:
# - test     : run the unit test suite
# - lint     | run ruff
# - coverage : run the unit tests and generate a minimal coverage report
# - htmlcov  : run the unit tests and generate a full report in htmlcov/

all:

run:
	uv run -m netbot.netbot debug sync-off

test:
	uv run -m tests

coverage:
	uvx coverage run -m tests
	uvx coverage report

htmlcov:
	uvx coverage run -m tests
	uvx coverage html

lint:
	uvx ruff check .

clean:
	rm -rf __pycache__
	rm -rf $(VENV)
	rm -rf htmlcov
	rm -f discord.log
	rm -f dpytest_*.dat
	find . -type f -name ‘*.pyc’ -delete