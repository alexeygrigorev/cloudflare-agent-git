#!/usr/bin/env bash
# Replay all eight G3 composition cases from published files only.
#
# Provenance: space-bunny-head. Reviewed as docs-only work; it starts NO agents, touches
# NO network, needs NO credentials, and writes ONLY inside its own mktemp scratch
# directories. It never writes to the payload directories, which are read-only inputs.
#
# Design constraints this script exists to satisfy, each after a real defect:
#   1. Unique scratch per case, via mktemp -d. Never a path derived from a payload dir.
#   2. Seed copied FIRST, agent overlay SECOND. The reverse silently leaves the seed's
#      copy of a file the agent also changed.
#   3. Overlay fixture MUST match the seed fixture. No "|| true" fallbacks.
#   4. Source-byte identity asserted with cmp against the published overlay, not grep.
#   5. Every case records an explicit oracle exit status.
#   6. Scratch is cleaned on exit, and only scratch.
#
# Usage:  ./replay.sh            run all eight cases, print a table
#         KEEP=1 ./replay.sh     keep scratch dirs and list them (for inspection)
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

SCRATCH_ROOT="$(mktemp -d /tmp/g3repro.XXXXXX)"
cleanup() { [ "${KEEP:-0}" = "1" ] || rm -rf "$SCRATCH_ROOT"; }
trap cleanup EXIT

fails=0
rows=()

# run_case <label> <seed-dir> <overlay-dir|-> <oracle-file>
run_case() {
  local label="$1" seed="$2" overlay="$3" oracle="$4"
  local dir="$SCRATCH_ROOT/$label"

  # Refuse to run if any input is missing, rather than silently doing something else.
  # Oracle is a FILE, so it is tested with -f; seed and overlay are dirs (-d).
  [ -d "$seed" ]        || { echo "MISSING SEED DIR: $seed" >&2; return 2; }
  [ -f "protected-oracle/$oracle" ] || { echo "MISSING ORACLE FILE: protected-oracle/$oracle" >&2; return 2; }
  [ "$overlay" = "-" ] || [ -d "$overlay" ] || { echo "MISSING OVERLAY DIR: $overlay" >&2; return 2; }
  # An overlay from the other fixture is a configuration error, not a fallback.
  case "$seed:$overlay" in
    seed-arm1:arm2*|seed-arm2:arm1*) echo "FIXTURE MISMATCH: $seed with $overlay" >&2; return 2 ;;
  esac

  mkdir -p "$dir"
  cp -a "$seed"/. "$dir"/                       # seed FIRST
  if [ "$overlay" != "-" ]; then
    cp -a "$overlay"/. "$dir"/                   # overlay SECOND (overwrites)
  fi
  cp "protected-oracle/$oracle" "$dir/oracle.py"

  # Byte-identity assertion: every overlaid file must equal the published source byte for byte.
  if [ "$overlay" != "-" ]; then
    local f rel
    for f in "$overlay"/*; do
      rel="$(basename "$f")"
      cmp -s "$f" "$dir/$rel" || { echo "OVERLAY MISMATCH: $rel" >&2; return 2; }
    done
  fi

  local out rc
  out="$( cd "$dir" && python3 -B oracle.py 2>&1 )"; rc=$?
  local last; last="$(printf '%s' "$out" | tail -n 1)"
  printf '%-14s rc=%-3s %s\n' "$label" "$rc" "$last" >&2
  rows+=("$(printf '%-14s %s' "$label" "$( [ "$rc" -eq 0 ] && echo PASS || echo "FAIL(rc=$rc)" )")")
  [ "$rc" -eq 0 ] || fails=$((fails + 1))
  return 0
}

# compose_case <label> <seed> <overlayA> <overlayB> <oracle>
# Starts from A, then copies ONLY B's files. Never copies B over A wholesale.
compose_case() {
  local label="$1" seed="$2" oa="$3" ob="$4" oracle="$5"
  local dir="$SCRATCH_ROOT/$label"
  [ -d "$seed" ] && [ -d "$oa" ] && [ -d "$ob" ] \
    && [ -f "protected-oracle/$oracle" ] \
    || { echo "MISSING INPUT for $label" >&2; return 2; }
  case "$seed:$oa:$ob" in
    seed-arm1:*:arm2*|seed-arm2:*:arm1*) echo "FIXTURE MISMATCH for $label" >&2; return 2 ;;
  esac
  mkdir -p "$dir"
  cp -a "$seed"/. "$dir"/
  cp -a "$oa"/. "$dir"/
  local f rel
  for f in "$ob"/*; do rel="$(basename "$f")"; cp -a "$f" "$dir/$rel"; done
  cp "protected-oracle/$oracle" "$dir/oracle.py"

  local ok=1
  for src in "$oa" "$ob"; do
    for f in "$src"/*; do
      rel="$(basename "$f")"
      cmp -s "$f" "$dir/$rel" || { echo "COMPOSE MISMATCH: $rel" >&2; ok=0; }
    done
  done
  [ "$ok" -eq 1 ] || return 2

  local out rc
  out="$( cd "$dir" && python3 -B oracle.py 2>&1 )"; rc=$?
  local last; last="$(printf '%s' "$out" | tail -n 1)"
  printf '%-14s rc=%-3s %s\n' "$label" "$rc" "$last" >&2
  rows+=("$(printf '%-14s %s' "$label" "$( [ "$rc" -eq 0 ] && echo PASS || echo "FAIL(rc=$rc)" )")")
  [ "$rc" -eq 0 ] || fails=$((fails + 1))
  return 0
}

echo "== payload integrity =="
sha256sum -c MANIFEST.sha256 || { echo "MANIFEST FAILED"; exit 2; }
echo

echo "== eight cases (stderr shows per-case oracle output) =="
run_case f1-base  seed-arm1 -                 oracle-arm1.py
run_case f1-A     seed-arm1 arm1-signposted/A oracle-arm1.py
run_case f1-B     seed-arm1 arm1-signposted/B oracle-arm1.py
compose_case f1-AB seed-arm1 arm1-signposted/A arm1-signposted/B oracle-arm1.py

run_case f2-base  seed-arm2 -                 oracle-arm2.py
run_case f2-A     seed-arm2 arm2-signposted/A oracle-arm2.py
run_case f2-B     seed-arm2 arm2-signposted/B oracle-arm2.py
compose_case f2-AB seed-arm2 arm2-signposted/A arm2-signposted/B oracle-arm2.py

echo
echo "== summary =="
printf '%s\n' "${rows[@]}"
echo "cases failing: $fails"
[ "${KEEP:-0}" = "1" ] && echo "scratch kept: $SCRATCH_ROOT"
echo "expected: all eight PASS (base/A/B/A+B for both fixtures)"
exit "$fails"
