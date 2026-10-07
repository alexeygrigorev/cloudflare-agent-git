#!/bin/sh
# Shared helpers for scripts/checks/*.sh (sourced, not run; deliberately not executable).
#
# Scope selected by environment, set by scripts/checks/run-all.sh:
#   CHECK_MODE=staged (default)  files in the index          (pre-commit)
#   CHECK_MODE=range             files in $CHECK_RANGE, e.g. A..B  (pre-push, CI)
#   CHECK_MODE=all               every tracked file          (audit; reports legacy violations)
# A check script also treats a literal `--all` argument as CHECK_MODE=all.

check_parse_args() {
  for a in "$@"; do
    [ "$a" = "--all" ] && CHECK_MODE=all
  done
  CHECK_MODE=${CHECK_MODE:-staged}
}

# Paths ADDED or renamed-to in scope (all tracked files in `all` mode), one per line.
check_added_files() {
  case "${CHECK_MODE:-staged}" in
    all)    git ls-files ;;
    range)  git diff --name-only --diff-filter=AR "$CHECK_RANGE" -- ;;
    *)      git diff --cached --name-only --diff-filter=AR -- ;;
  esac
}

# Paths added, modified or renamed in scope (for checks that scan content).
check_touched_files() {
  case "${CHECK_MODE:-staged}" in
    all)    git ls-files ;;
    range)  git diff --name-only --diff-filter=AMR "$CHECK_RANGE" -- ;;
    *)      git diff --cached --name-only --diff-filter=AMR -- ;;
  esac
}
