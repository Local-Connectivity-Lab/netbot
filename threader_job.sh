#!/bin/bash

# This script exists to bootstrap the python venv for the cron job.
# If the cron job references the venv directly, and it doesn't exist, it will fail
# due to the missing env.
#
# */5 * * * * /home/scn/github/netbot/venv/bin/python3 /home/scn/github/netbot/threader.py | /usr/bin/logger -t threader

# Instead, this script is used with the following job:
#
# */5 * * * * /home/scn/github/netbot/threader_job.sh | /usr/bin/logger -t threader


name=$(basename "$0")
project_dir="$(cd -P -- "$(dirname -- "$0")" && pwd -P)"
cd "$project_dir" || exit 1

env="venv"
PYTHON="$project_dir/venv/bin/python3"

if [ ! -x "$PYTHON" ]; then
    echo Building $env
    python3 -m venv venv
    $PYTHON -m pip install --upgrade pip
    $PYTHON -m pip install -r requirements.txt
fi

$PYTHON "$project_dir/threader.py"
