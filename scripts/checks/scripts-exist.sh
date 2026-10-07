#!/usr/bin/env bash
# Every scripts/ path that the docs name as installed must exist, and a script
# must be executable. Executable contract (platform-independent):
#   - data files (.service .timer .md .json .yml .yaml .txt .toml) are exempt;
#   - a tracked script is executable when its git index mode is 100755
#     (`git ls-files -s`), because the filesystem bit is unreliable on MSYS/NTFS;
#   - an untracked script falls back to the filesystem bit;
#   - a tracked symlink (mode 120000) passes when its target is executable by
#     the same rules;
#   - a shebang is not required for scripts run through an interpreter. When
#     the docs invoke a non-.sh script directly (as the command itself) and it
#     has no shebang, the check prints a WARNING with the doc location; it
#     does not fail.
# Gaps that are known and tracked go in KNOWN_GAPS with an issue number; they are
# reported on every run, never skipped silently. A gap that has been fixed must be
# removed from the list (the check fails on stale entries).
set -u
root=$(cd "$(dirname "$0")/../.." && pwd)
cd "$root" || exit 2

# path|issue
KNOWN_GAPS=(
  "scripts/recover-agent|102"
  "scripts/supervision/service.py|104"
)

fail=0
docs=$(grep -rhoE 'scripts/[A-Za-z0-9_.-]+(/[A-Za-z0-9_.-]+)*' _docs AGENTS.md 2>/dev/null \
  | sed -E 's/[.,;:)]+$//' | sort -u)

gap_issue() {
  local g
  for g in "${KNOWN_GAPS[@]}"; do
    [ "${g%%|*}" = "$1" ] && { echo "${g##*|}"; return 0; }
  done
  return 1
}

is_data() {
  case "$1" in
    *.service|*.timer|*.md|*.json|*.yml|*.yaml|*.txt|*.toml) return 0;;
  esac
  return 1
}

is_exec() {
  local mode t
  # Mode is read from the git index (not the working tree), so it is the same on every platform.
  mode=$(git ls-files -s -- "$1" 2>/dev/null | awk 'NR==1{print $1}')
  if [ "$mode" = "120000" ]; then
    t=$(readlink -f -- "$1") || return 1
    case "$t" in
      "$root"/*) is_exec "${t#"$root"/}";;
      *) [ -x "$t" ];;
    esac
  elif [ -n "$mode" ]; then [ "$mode" = "100755" ]
  else [ -x "$1" ]
  fi
}

# Doc locations (file:line) where $1 is used as the command itself: at the start
# of a line or code span, after `$ `, `./`, `&&`, `;` or `|`, and not after an
# interpreter such as `bash` or `python3`.
direct_locs() {
  local esc line prefix
  esc=$(printf '%s' "$1" | sed 's/[.]/\\./g')
  grep -rnoE ".{0,12}${esc}([^A-Za-z0-9_./-]|$)" _docs AGENTS.md 2>/dev/null | while IFS= read -r line; do
    prefix=${line#*:}; prefix=${prefix#*:}      # drop file and line number
    prefix=${prefix%%"$1"*}
    prefix=${prefix%./}
    case "$prefix" in
      ""|*'`'|*'$ '|*'&& '|*'; '|*'| ') echo "${line%%:*}:$(cut -d: -f2 <<<"$line")";;
    esac
  done | sort -u
}

has_shebang() { [ "$(head -c2 -- "$1" 2>/dev/null)" = "#!" ]; }

for p in $docs; do
  [ -d "$p" ] && continue          # directory references are not scripts
  case "$(basename "$p")" in test_*) continue;; esac  # tests are run, not installed
  if issue=$(gap_issue "$p"); then
    if [ -e "$p" ] && { is_data "$p" || is_exec "$p"; }; then
      echo "STALE ALLOWLIST: $p now exists and is executable; remove it from KNOWN_GAPS (issue $issue)"; fail=1
    else
      echo "KNOWN GAP: $p is advertised but missing or not executable (issue $issue)"
    fi
    continue
  fi
  if [ ! -e "$p" ]; then echo "MISSING: $p is named in the docs but does not exist"; fail=1
  elif is_data "$p"; then :
  elif ! is_exec "$p"; then echo "NOT EXECUTABLE: $p"; fail=1
  elif [[ "$p" != *.sh ]] && ! has_shebang "$p"; then
    locs=$(direct_locs "$p" | paste -sd, -)
    [ -n "$locs" ] && echo "WARNING: $p has no shebang but is invoked directly at $locs"
  fi
done

for g in "${KNOWN_GAPS[@]}"; do
  grep -qxF -- "${g%%|*}" <<<"$docs" || { echo "STALE ALLOWLIST: ${g%%|*} is no longer named in the docs"; fail=1; }
done
exit $fail
