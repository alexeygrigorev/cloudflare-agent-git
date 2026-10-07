#!/usr/bin/env bash
# Founder journal rules (_docs/03-way-of-working.md): day files are YYYY-MM-DD.md,
# append-only, entries start with "## HH:MM" (Europe/Berlin) and are not in the
# future. Duplicate HH:MM headings are legal. An out-of-order timestamp is only a
# warning (late reconstructed intake must not be blocked). failures.md is free-form.
#
#   journal.sh [--staged]        staged diff (pre-commit; default)
#   journal.sh --range A..B      every non-merge commit in a pushed range (CI)
#   journal.sh --all             whole-file rules on every day file
#   --message-file F             (staged) commit message to scan for the trailer
#
# The principal can override: trailer "Principal-Override: <reason>" in the commit
# message, or env PRINCIPAL_OVERRIDE=<reason>. An override skips the append-only
# and entry rules (file naming is still reported only without override too).
# Only violations on lines a commit adds fail it; --all reports all of them.
# Test hook: JOURNAL_NOW="YYYY-MM-DD HH:MM" replaces the Berlin clock.
set -u
DIR="_docs/founder-journal"
mode=staged; range=""; msgfile=""
while [ $# -gt 0 ]; do
  case "$1" in
    --staged) mode=staged ;;
    --all) mode=all ;;
    --range) mode=range; range="${2:-}"; shift ;;
    --message-file) msgfile="${2:-}"; shift ;;
    *) echo "usage: journal.sh [--staged|--all|--range A..B] [--message-file F]" >&2; exit 2 ;;
  esac
  shift
done
cd "$(git rev-parse --show-toplevel)" || exit 2
NOW="${JOURNAL_NOW:-$(TZ=Europe/Berlin date '+%F %H:%M')}"
fail=0
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
say() {
  case "$1" in
    *"warning: "*) echo "journal: $1" >&2 ;;
    *) echo "journal: $1" >&2; fail=1 ;;
  esac
}

day_name_ok() {
  local b="$1" d
  [ "$b" = failures.md ] && return 0
  [[ "$b" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}\.md$ ]] || return 1
  d="${b%.md}"; [ "$(date -d "$d" +%F 2>/dev/null)" = "$d" ]
}

# entry_rules FILE DATE -> "line<TAB>message" per violation
entry_rules() {
  awk -v date="$2" -v now="$NOW" '
    /^## / {
      if ($0 !~ /^## ([01][0-9]|2[0-3]):[0-5][0-9]$/) { printf "%d\tentry heading must be \"## HH:MM\": %s\n", NR, $0; next }
      t = substr($0, 4, 5)
      if (prev != "" && t < prev) printf "%d\twarning: timestamp %s is earlier than previous %s (allowed for late intake)\n", NR, t, prev
      if (date " " t > now) printf "%d\ttimestamp %s %s is in the future (now %s)\n", NR, date, t, now
      prev = t; next
    }
  ' "$1"
}

has_override() { git interpret-trailers --parse | grep -qi '^Principal-Override:[[:space:]]*[^[:space:]]'; }

# Globals set by the caller: LABEL, OVERRIDE, SHOW (command prefix), DIFFC (array).
examine() {
  local st path b
  while IFS=$'\t' read -r st path; do
    [ -n "$path" ] || continue
    [ "$OVERRIDE" = 1 ] && continue
    b=$(basename "$path")
    if [ "$st" = D ]; then say "$LABEL: $path deleted (needs Principal-Override)"; continue; fi
    if ! day_name_ok "$b"; then say "$LABEL: $path must be named YYYY-MM-DD.md (or failures.md)"; continue; fi
    [ "$b" = failures.md ] && continue
    if [ "$st" = M ] && "${DIFFC[@]}" -- "$path" | grep -q '^-\([^-]\|$\)'; then
      say "$LABEL: $path removes or modifies existing lines (journal is append-only; needs Principal-Override)"
    fi
    ${SHOW}"$path" > "$tmp/new" 2>/dev/null || continue
    "${DIFFC[@]}" -U0 -- "$path" | awk '/^@@/ { split($3, a, ","); s = substr(a[1], 2) + 0; n = (a[2] == "" ? 1 : a[2] + 0); for (i = 0; i < n; i++) print s + i }' > "$tmp/added"
    entry_rules "$tmp/new" "${b%.md}" | while IFS=$'\t' read -r ln msg; do
      grep -qx "$ln" "$tmp/added" && echo "$path:$ln: $msg"
    done > "$tmp/viol"
    if [ -s "$tmp/viol" ]; then while read -r l; do say "$LABEL: $l"; done < "$tmp/viol"; fi
  done
}

case "$mode" in
  all)
    for f in "$DIR"/*.md; do
      [ -e "$f" ] || continue
      b=$(basename "$f")
      day_name_ok "$b" || { say "$f must be named YYYY-MM-DD.md (or failures.md)"; continue; }
      [ "$b" = failures.md ] && continue
      entry_rules "$f" "${b%.md}" > "$tmp/all"
      if [ -s "$tmp/all" ]; then
        while IFS=$'\t' read -r ln msg; do say "$f:$ln: $msg"; done < "$tmp/all"
      fi
    done ;;
  staged)
    LABEL=staged; OVERRIDE=0; SHOW="git show :"; DIFFC=(git diff --cached --no-renames)
    [ -n "${PRINCIPAL_OVERRIDE:-}" ] && OVERRIDE=1
    [ -n "$msgfile" ] && [ -f "$msgfile" ] && has_override < "$msgfile" && OVERRIDE=1
    examine < <(git diff --cached --no-renames --name-status --diff-filter=ADM -- "$DIR") ;;
  range)
    [ -n "$range" ] || { echo "journal: --range needs A..B" >&2; exit 2; }
    for c in $(git rev-list --reverse --no-merges "$range"); do
      OVERRIDE=0; [ -n "${PRINCIPAL_OVERRIDE:-}" ] && OVERRIDE=1
      git log -1 --format=%B "$c" | has_override && OVERRIDE=1
      p="$c^"; git rev-parse -q --verify "$p" >/dev/null || p=$(git hash-object -t tree /dev/null)
      LABEL="${c:0:7}"; SHOW="git show $c:"; DIFFC=(git diff --no-renames "$p" "$c")
      examine < <(git diff --no-renames --name-status --diff-filter=ADM "$p" "$c" -- "$DIR")
    done ;;
esac
exit "$fail"
