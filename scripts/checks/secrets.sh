#!/usr/bin/env bash
# secrets.sh - repo-wide secret and private-data scan (public repo guard).
#
# Policy: _docs/03-way-of-working.md section 13. Secrets, keys, tokens, host
# addresses, private paths and personal data never go into the repo.
#
# Modes (default: --staged)
#   --staged        added lines of the staged diff (pre-commit)
#   --pushed        added lines of upstream..HEAD, falling back to origin/main..HEAD (pre-push, CI)
#   --range <rev>   added lines of an arbitrary git diff range, e.g. origin/main...HEAD
#   --all           every tracked text file (full audit)
#
# Output never contains the matched value: only "path:line: kind". Exit 1 on any finding.
#
# Allowlist: scripts/checks/secrets.allowlist, one rule per line:
#     <kind> <path-glob>   # mandatory reason
# kind is one of the kinds printed below or "*"; path-glob uses shell patterns
# (case syntax, so * crosses slashes). A single line can also carry the marker
# "secrets-allow: <reason>" to be skipped. Every exception needs a reason.
#
# Principal override: PRINCIPAL_OVERRIDE=<reason> in the environment, or a
# "Principal-Override: <reason>" trailer on a commit in the --pushed/--range
# commits, lets the check pass. Findings are still listed and the reason is
# logged to stderr and appended to .local/principal-overrides.log.
#
# Private hostnames, personal emails and other host-specific terms are not
# listed in this public file. Put extra extended regexes, one per line, in
# git-ignored .local/secrets-extra-patterns (kind: private-term), or in the
# SECRETS_EXTRA_PATTERNS environment variable (newline separated).
set -u

root=$(git rev-parse --show-toplevel 2>/dev/null) || { echo "secrets: not in a git repo" >&2; exit 2; }
cd "$root" || exit 2
allowfile="scripts/checks/secrets.allowlist"

mode=staged; range=""
while [ $# -gt 0 ]; do
  case $1 in
    --staged) mode=staged ;;
    --pushed) mode=pushed ;;
    --all) mode=all ;;
    --range) mode=range; range=${2:-}; shift ;;
    -h|--help) sed -n '2,31p' "$0"; exit 0 ;;
    *) echo "secrets: unknown argument $1" >&2; exit 2 ;;
  esac
  shift
done

tmp=$(mktemp -d "${TMPDIR:-/tmp}/secrets.XXXXXX") || exit 2
trap 'rm -rf "$tmp"' EXIT
lines="$tmp/lines.tsv"   # path <TAB> lineno <TAB> content
paths="$tmp/paths"       # paths considered (for file-name rules)

parse_diff() {
  awk '
    /^\+\+\+ /   { p = $0; sub(/^\+\+\+ (b\/)?/, "", p); if (p == "/dev/null") p = ""; if (p != "") print p > P; next }
    /^@@ /       { s = $3; sub(/^\+/, "", s); split(s, a, ","); n = a[1] + 0; next }
    /^\+/        { if (p != "") printf "%s\t%d\t%s\n", p, n, substr($0, 2); n++ }
  ' P="$paths"
}

case $mode in
  staged) git diff --cached --unified=0 --no-color --no-ext-diff --diff-filter=ACMR | parse_diff > "$lines" ;;
  range)  [ -n "$range" ] || { echo "secrets: --range needs a revision range" >&2; exit 2; }
          git diff --unified=0 --no-color --no-ext-diff --diff-filter=ACMR "$range" | parse_diff > "$lines" || exit 2 ;;
  pushed) if up=$(git rev-parse --abbrev-ref '@{upstream}' 2>/dev/null); then base=$up; else base=origin/main; fi
          git diff --unified=0 --no-color --no-ext-diff --diff-filter=ACMR "$base...HEAD" | parse_diff > "$lines" || exit 2 ;;
  all)    git ls-files > "$paths"
          git grep -InE -e '' -- . 2>/dev/null | awk '{ i = index($0, ":"); path = substr($0, 1, i - 1); r = substr($0, i + 1); j = index(r, ":"); printf "%s\t%s\t%s\n", path, substr(r, 1, j - 1), substr(r, j + 1) }' > "$lines" ;;
esac
touch "$paths"

# kind<TAB>ERE. Keep in sync with docs; add providers here.
patterns() {
  cat <<'P'
anthropic-key	sk-ant-[A-Za-z0-9_-]{20,}
openai-key	sk-(proj-|svcacct-)?[A-Za-z0-9_-]{32,}
github-token	(gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{40,})
aws-key	(AKIA|ASIA|AGPA|AIDA|AROA)[0-9A-Z]{16}([^0-9A-Z]|$)
google-key	(AIza[0-9A-Za-z_-]{35}|ya29\.[0-9A-Za-z_-]{30,})
telegram-bot-token	(^|[^0-9])[0-9]{8,10}:AA[A-Za-z0-9_-]{33}
slack-token	xox[abprs]-[A-Za-z0-9-]{10,}
private-key-block	-----BEGIN ([A-Z0-9]+ )*PRIVATE KEY( BLOCK)?-----
cloudflare-token	(CLOUDFLARE|CF)_[A-Z0-9_]*(TOKEN|API_KEY|SECRET|GLOBAL_KEY)[A-Z0-9_]*["' ]*[=:]["' ]*[A-Za-z0-9_-]{37,}
artifacts-token	art_v[0-9]_x?_?[0-9a-f]{20,}
bearer-token	[Bb]earer +[A-Za-z0-9._~+/=-]{24,}
generic-secret-assignment	(api[_-]?key|secret|token|passw(or)?d)["']?[ ]*[=:][ ]*["'][A-Za-z0-9/+_=.-]{24,}["']
credential-url	[a-z][a-z0-9+.-]*://[^/ :@$<{(]+:[^/ :@$<{(]+@[A-Za-z0-9.-]+
private-home-path	(/home/alexey|/Users/alexey|[Cc]:[\\/]+Users[\\/]+alexey|~alexey)
private-email	alexey\.s\.grigoriev@
P
}

findings="$tmp/findings"; : > "$findings"
while IFS="$(printf '\t')" read -r kind re; do
  [ -n "$kind" ] || continue
  LC_ALL=C grep -E -e "$re" "$lines" | grep -v 'secrets-allow:' | cut -f1,2 | sed "s/\$/	$kind/" >> "$findings"
done <<EOF2
$(patterns)
EOF2

# optional host-private terms (hostnames, personal emails, IPs) kept out of the public tree
{ [ -f .local/secrets-extra-patterns ] && cat .local/secrets-extra-patterns; printf '%s\n' "${SECRETS_EXTRA_PATTERNS:-}"; } | while IFS= read -r re; do
  case $re in ''|'#'*) continue ;; esac
  LC_ALL=C grep -E -e "$re" "$lines" | grep -v 'secrets-allow:' | cut -f1,2 | sed "s/\$/	private-term/" >> "$findings"
done

# credential-bearing file names
while IFS= read -r f; do
  b=${f##*/}
  case $b in
    .env.example|.env.sample|.env.template|*.example|*.sample|*.template) continue ;;
    .env|.env.*|*.env|.dev.vars|.netrc|.npmrc|.pgpass|credentials|credentials.json|*.pem|*.key|*.p12|*.pfx|*.jks|id_rsa|id_dsa|id_ecdsa|id_ed25519|*.kdbx)
      printf '%s\t0\tcredential-file\n' "$f" >> "$findings" ;;
  esac
done < "$paths"

allowed() { # path kind
  [ -f "$allowfile" ] || return 1
  while read -r ak ag _; do
    case $ak in ''|'#'*) continue ;; esac
    case $ag in '#'*|'') continue ;; esac
    if [ "$ak" = "*" ] || [ "$ak" = "$2" ]; then
      # shellcheck disable=SC2254
      case $1 in $ag) return 0 ;; esac
    fi
  done < "$allowfile"
  return 1
}

fail=0
sort -u "$findings" | while IFS="$(printf '\t')" read -r p n k; do
  allowed "$p" "$k" && continue
  echo "$p:$n: $k"
done > "$tmp/out"
if [ -s "$tmp/out" ]; then
  reason=${PRINCIPAL_OVERRIDE:-}
  if [ -z "$reason" ]; then
    case $mode in
      range) rr=$range ;;
      pushed) rr="${base:-origin/main}..HEAD" ;;
      *) rr="" ;;
    esac
    [ -n "$rr" ] && reason=$(git log --format='%(trailers:key=Principal-Override,valueonly,unfold)' "$rr" 2>/dev/null | grep -v '^$' | head -1)
  fi
  if [ -n "$reason" ]; then
    sed 's/^/secrets: overridden: /' "$tmp/out" >&2
    echo "secrets: PRINCIPAL OVERRIDE honoured, reason: $reason" >&2
    mkdir -p .local 2>/dev/null && printf '%s\tsecrets\t%s findings\t%s\n' "$(date -u +%FT%TZ)" "$(wc -l < "$tmp/out")" "$reason" >> .local/principal-overrides.log
    exit 0
  fi
  cat "$tmp/out" >&2
  echo "secrets: $(wc -l < "$tmp/out") finding(s). Remove the data (public repo: _docs/03-way-of-working.md section 13)," >&2
  echo "secrets: or add a justified rule to $allowfile. Values are never printed." >&2
  exit 1
fi
exit $fail
