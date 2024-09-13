#!/bin/bash

# This script exists to bootstrap the python venv for the cron job.
# If the cron job references the venv directly, and it doesn't exist, it will fail
# due to the missing env.
#
# */5 * * * * /home/scn/github/netbot/venv/bin/python3 /home/scn/github/netbot/threader.py | /usr/bin/logger -t threader

# Instead, this script is used with the following job:
#
# */5 * * * * /home/scn/github/netbot/threader_job.sh | /usr/bin/logger -t threader


project_dir="$(cd -P -- "$(dirname -- "$0")" && pwd -P)"
cd "$project_dir" || exit 1

VENV=.venv
PYTHON="$project_dir/$VENV/bin/python3"
PYTHON_VERSION="python3.11"

# make sure venv is installed
if [ ! -x "$PYTHON" ]; then
    if command -v $PYTHON_VERSION &> /dev/null
    then
        echo Building $VENV with $($PYTHON_VERSION --version)
        $PYTHON_VERSION -m venv $VENV
        $PYTHON -m pip install --upgrade pip
        $PYTHON -m pip install -r requirements.txt
    else
        echo "$PYTHON_VERSION could not be found"
        exit 1
    fi
fi

# run the threader
$PYTHON -m threader.threader
