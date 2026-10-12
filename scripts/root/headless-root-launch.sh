#!/usr/bin/env bash
# systemd --user entry point: place the run in its own transient user scope
# (survives SSH logout; Linger=yes) with memory/pids limits.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
exec systemd-run --user --scope --collect --quiet \
  --unit="headless-root-$(date +%Y%m%d%H%M%S)" \
  -p MemoryMax=${HR_MEMORY:-2500M} -p TasksMax=${HR_PIDS:-512} \
  env -u APLEXER_SESSION_ID -u APLEXER_TAG -u APLEXER_WORKSPACE \
  "$here/headless-root-run.sh"
