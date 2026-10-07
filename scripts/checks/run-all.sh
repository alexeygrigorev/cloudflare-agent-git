#!/bin/bash
# Run every executable scripts/checks/*.sh (except itself). One check per script: exit nonzero =
# fail, print what is wrong. Usage:
#   run-all.sh [staged | range <A..B> | all]
# Add a check by dropping an executable *.sh here; the hooks and CI pick it up automatically.
#
# Scope reaches a check as env CHECK_MODE (staged|range|all), CHECK_RANGE and COMMIT_MSG_FILE (see
# lib.sh). secrets.sh and journal.sh have their own flags and are given --range/--all here; every
# other check is self-scoped and runs with no arguments.
#
# Principal override, the one shared override: trailer `Principal-Override: <reason>` (staged: in
# $COMMIT_MSG_FILE; range: on any commit in the range) or env PRINCIPAL_OVERRIDE=<reason>.
# The reason is exported to every check, logged, and the runner exits 0 even if checks fail.
# In GitHub Actions an override is also emitted as a ::warning:: annotation.
set -u
root=$(git rev-parse --show-toplevel) || exit 2
cd "$root" || exit 2
. scripts/checks/lib/principal-override.sh
mode=${1:-staged}
case "$mode" in
  staged) CHECK_MODE=staged ;;
  range)  CHECK_MODE=range; CHECK_RANGE=${2:?range needs A..B} ;;
  all)    CHECK_MODE=all ;;
  *) echo "usage: run-all.sh [staged | range A..B | all]" >&2; exit 2 ;;
esac
export CHECK_MODE CHECK_RANGE COMMIT_MSG_FILE

text=""
case "$mode" in
  staged) [ -n "${COMMIT_MSG_FILE:-}" ] && [ -f "$COMMIT_MSG_FILE" ] && text=$(cat "$COMMIT_MSG_FILE") ;;
  range)  text=$(git log --format=%B "$CHECK_RANGE" 2>/dev/null) ;;
esac
override=""
if principal_override run-all "$text"; then
  override=${PRINCIPAL_OVERRIDE:-$(printf '%s\n' "$text" | sed -n 's/^Principal-Override:[[:space:]]*//p' | sed -n '1p')}
  export PRINCIPAL_OVERRIDE=$override
  [ -n "${GITHUB_ACTIONS:-}" ] && echo "::warning title=Principal override::${override}"
fi

fail=0
for c in scripts/checks/*.sh; do
  case "$c" in */run-all.sh|*/lib.sh) continue ;; esac
  [ -x "$c" ] || continue
  args=()
  case "$(basename "$c")" in
    secrets.sh|journal.sh)
      case "$mode" in
        range)  args=(--range "$CHECK_RANGE") ;;
        all)    args=(--all) ;;
        staged) [ "$(basename "$c")" = journal.sh ] && [ -n "${COMMIT_MSG_FILE:-}" ] && args=(--message-file "$COMMIT_MSG_FILE") ;;
      esac ;;
  esac
  if ! "$c" ${args[@]+"${args[@]}"}; then
    echo "FAILED: $c" >&2
    fail=1
  fi
done
if [ $fail -eq 1 ] && [ -n "$override" ]; then
  echo "run-all: checks failed but the principal overrode them: $override"
  exit 0
fi
exit $fail
