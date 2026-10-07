#!/usr/bin/env bash
# Publication guard for website/content/daily pages. Usage: publication.sh [page.md ...]
# No args: pages changed in the working tree or last commit (all pages if no diff is possible).
# Needs a passing check.json (.local/journal/DATE/check.json) when the private dir exists;
# in CI (no .local) a published page must carry a matching article_sha256 from publish_daily.py.
# Principal override: PRINCIPAL_OVERRIDE=<reason> or a "Principal-Override: <reason>" trailer on HEAD.
set -u
ROOT="${PUBLICATION_ROOT:-$(cd "$(dirname "$0")/../.." && pwd)}"
cd "$ROOT" || exit 2
# shellcheck source=lib/principal-override.sh
. "$ROOT/scripts/checks/lib/principal-override.sh"
principal_override publication "$(git log -1 --format=%B 2>/dev/null)" && exit 0
pages=("$@")
if [ ${#pages[@]} -eq 0 ]; then
  mapfile -t pages < <({ git diff --name-only HEAD; git diff --name-only HEAD~1 HEAD; } 2>/dev/null | grep -E '^website/content/daily/[0-9-]+\.md$' | sort -u)
  if ! git rev-parse -q --verify HEAD~1 >/dev/null 2>&1; then mapfile -t pages < <(ls website/content/daily/*.md 2>/dev/null); fi
fi
fail=0
bad() { echo "publication check failed: $1: $2" >&2; fail=1; }
for page in "${pages[@]}"; do
  [ -f "$page" ] || continue
  day=$(basename "$page" .md); meta="${page%.md}.json"
  stripped=$(sed -E 's/\]\([^)]*\)/]/g; s#https?://[^ )]*##g' "$page")
  echo "$stripped" | grep -Eq '(^|[^0-9a-zA-Z])([0-9a-f]{7,40})([^0-9a-zA-Z]|$)' && \
    echo "$stripped" | grep -Eo '(^|[^0-9a-zA-Z])[0-9a-f]{7,40}([^0-9a-zA-Z]|$)' | grep -Eq '[0-9]' && \
    echo "$stripped" | grep -Eo '(^|[^0-9a-zA-Z])[0-9a-f]{7,40}([^0-9a-zA-Z]|$)' | grep -Eq '[a-f]' && bad "$page" "commit hash in text"
  grep -Eq '/home/[a-z]|/Users/[a-z]|C:\\Users|\.local/' "$page" && bad "$page" "private path"
  grep -Eq '(sk-ant-|ghp_|github_pat_|sk-proj-|AKIA)[A-Za-z0-9_-]{12,}|-----BEGIN [A-Z ]*PRIVATE KEY|(api[_-]?key|token|secret|password)[a-z_]*[:=] *[A-Za-z0-9_/+-]{16,}' "$page" && bad "$page" "secret-looking string"
  grep -Eq '^#{1,6} +[^a-z]*[A-Z]{3,}[^a-z]*$' "$page" && bad "$page" "all-caps heading"
  grep -Eiq '^#{1,6} +(corrections?|errata|edition history|version history|changelog|what changed|updates?|next|about this (report|edition)|how this was written)$' "$page" && bad "$page" "forbidden section"
  grep -q '\*\*' "$page" && bad "$page" "bold text"
  priv=".local/journal/$day/check.json"
  if [ -d .local/journal ]; then
    if [ ! -f "$priv" ]; then bad "$page" "missing $priv"
    elif ! python3 -c 'import json,sys;sys.exit(0 if json.load(open(sys.argv[1])).get("verdict") in ("pass","fixed") else 1)' "$priv" 2>/dev/null; then bad "$page" "check.json verdict not pass/fixed"; fi
  elif [ -f "$meta" ] && grep -q '"published": true' "$meta"; then
    python3 - "$page" "$meta" <<'PY' || bad "$page" "published without matching article_sha256"
import hashlib,json,sys
m=json.load(open(sys.argv[2]));sys.exit(0 if m.get('article_sha256')==hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest() else 1)
PY
  fi
done
exit $fail
