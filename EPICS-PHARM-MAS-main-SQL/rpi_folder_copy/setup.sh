#!/bin/sh
# Prepare dependencies only. Never overwrite API source or start actuators implicitly.
set -eu
TASK_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
python3 -m venv "$TASK_DIR/.venv"
"$TASK_DIR/.venv/bin/python" -m pip install -r "$TASK_DIR/requirements.txt"
printf '%s\n' 'Environment prepared. Read docs/RUNNING.md before configuring the service.'
