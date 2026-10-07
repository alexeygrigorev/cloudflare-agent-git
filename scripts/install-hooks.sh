#!/bin/sh
# Enable the repo's git hooks: point core.hooksPath at .githooks, make the hooks executable and
# print what is active. Safe to run any number of times.
set -e
root=$(git rev-parse --show-toplevel)
cd "$root"
git config core.hooksPath .githooks
for h in .githooks/*; do
  [ -f "$h" ] && chmod +x "$h"
done
echo "core.hooksPath=$(git config core.hooksPath)"
echo "Active hooks:"
for h in .githooks/*; do
  [ -f "$h" ] && echo "  $(basename "$h")"
done
echo "Checks run by hooks and CI: scripts/checks/run-all.sh"
