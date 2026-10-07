#!/bin/sh
# Point this clone at the tracked hooks in .githooks/.
set -e
cd "$(git rev-parse --show-toplevel)"
git config core.hooksPath .githooks
echo "core.hooksPath set to .githooks"
