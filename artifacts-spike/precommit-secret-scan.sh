#!/bin/sh
# precommit-secret-scan.sh — secret-pattern gate over staged changes (artifacts-spike).
#
# Scans ADDED lines of `git diff --cached` for the same token shapes redact.py
# redacts (keep the two in sync; redact.py is the reference implementation):
#   1. Artifacts repo-token family:  art_v[0-9]_x?_?[0-9a-f]{20,}
#      (art_v1_<40 hex> per docs, art_v2_x_<40 hex> per the real service;
#      optionally followed by ?expires=<epoch>)
#   2. Bearer-like runs: 40+ base64url/alnum characters, EXCLUDING runs that are
#      exactly 40 lowercase hex chars — those are git SHA-1s (commit/tree hashes)
#      and are legitimate commit metadata (bunny-art-review §2). Longer hex runs
#      (e.g. sha256 content hashes) DO trip this check by design; refine the
#      exclusion only with evidence, never silently.
#   3. Credential URLs:  user:<password>@host  ([A-Za-z0-9_-]+:[A-Za-z0-9_%.-]+@)
#
# If CLOUDFLARE_API_TOKEN is already set in the hook's environment, the literal
# value is also matched (catches a live token that evades the generic patterns).
# The script never prints a full match — reports are masked to 10 chars.
#
# NOTE: the fetched docs/ snapshots (official Cloudflare pages) contain synthetic
# example tokens (art_v1_ + 0123456789abcdef…). A hit there is expected to be a
# docs example — verify, don't blanket-allow.
#
# Install as this worktree's pre-commit hook (this repo is a linked worktree; a
# plain .git/hooks/pre-commit lands in the SHARED main-repo hooks dir and would
# fire in every worktree, so scope it to this checkout instead). The
# .githooks/pre-commit wrapper committed with this script already execs it:
#
#   git config extensions.worktreeConfig true          # once per repo (safe)
#   git config --worktree core.hooksPath "$PWD/.githooks"
#
# For a normal (non-worktree) clone the plain form works:
#
#   cp artifacts-spike/precommit-secret-scan.sh .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit

set -u

diff_adds=$(git diff --cached --unified=0 2>/dev/null | grep '^+' | grep -v '^+++' || true)
if [ -z "$diff_adds" ]; then
    exit 0
fi

fail=0

# report <label> <extracted matches>
report() {
    label=$1
    echo "precommit-secret-scan: FAIL — $label (masked, first 10 chars):" >&2
    printf '%s\n' "$2" | sort -u | cut -c1-10 | sed 's/$/…/' >&2
    echo "precommit-secret-scan: locate with: git diff --cached | grep -nE <pattern> (see script header)" >&2
}

# 1. Artifacts repo-token family
m=$(printf '%s\n' "$diff_adds" | grep -oE 'art_v[0-9]_x?_?[0-9a-f]{20,}' || true)
if [ -n "$m" ]; then
    report "Artifacts repo-token pattern (art_v*_<hex>)" "$m"
    fail=1
fi

# 2. Bearer-like 40+ base62 runs, pure 40-char lowercase hex (git SHAs) allowed
m=$(printf '%s\n' "$diff_adds" | grep -oE '[A-Za-z0-9]{40,}' | grep -vE '^[0-9a-f]{40}$' || true)
if [ -n "$m" ]; then
    report "bearer-like 40+ char run" "$m"
    fail=1
fi

# 3. Credential URLs (user:<password>@host)
m=$(printf '%s\n' "$diff_adds" | grep -oE '[A-Za-z0-9_-]+:[A-Za-z0-9_%.-]+@' || true)
if [ -n "$m" ]; then
    report "credential URL (user:<password>@)" "$m"
    fail=1
fi

# 0. Literal live API token, only when the hook env already has it (no sourcing here)
if [ -n "${CLOUDFLARE_API_TOKEN:-}" ]; then
    if printf '%s\n' "$diff_adds" | grep -qF -- "$CLOUDFLARE_API_TOKEN"; then
        echo "precommit-secret-scan: FAIL — staged diff contains the live CLOUDFLARE_API_TOKEN value" >&2
        fail=1
    fi
fi

if [ "$fail" -ne 0 ]; then
    echo "precommit-secret-scan: commit blocked — redact staged content (artifacts-spike/redact.py) and re-stage." >&2
fi
exit "$fail"
