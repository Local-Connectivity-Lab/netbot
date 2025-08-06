#!/bin/bash

# This script exists to bootstrap the python venv for the cron job.
# If the cron job references the venv directly, and it doesn't exist, it will fail
# due to the missing env.
#
# */5 * * * * /home/scn/github/netbot/venv/bin/python3 /home/scn/github/netbot/threader.py | /usr/bin/logger -t threader

# Instead, this script is used with the following job:
#
# */5 * * * * /home/scn/github/netbot/threader_job.sh | /usr/bin/logger -t threader

# Add the uv directory to PATH
export PATH=$HOME/.local/bin:$PATH

project_dir="$(cd -P -- "$(dirname -- "$0")" && pwd -P)"
cd "$project_dir" || exit 1


# run the threader with uv
uv sync
uv run -m threader.threader
