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
set -euo pipefail

# Bounded oracle runtime. A hung oracle must fail the case, not the reviewer's session.
ORACLE_TIMEOUT="${ORACLE_TIMEOUT:-30}"

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

# Fail closed if we cannot get our own private scratch. Never derive it from a payload dir.
SCRATCH_ROOT="$(mktemp -d /tmp/g3repro.XXXXXX)" || { echo "FATAL: cannot create scratch" >&2; exit 3; }
case "$SCRATCH_ROOT" in /tmp/g3repro.*) ;; *) echo "FATAL: scratch outside expected prefix: $SCRATCH_ROOT" >&2; exit 3 ;; esac
cleanup() { [ "${KEEP:-0}" = "1" ] || rm -rf "$SCRATCH_ROOT"; }
trap cleanup EXIT

# Expected case labels, verified after the run. Duplicates or gaps are a failure.
EXPECTED_CASES=(f1-base f1-A f1-B f1-AB f2-base f2-A f2-B f2-AB)

fails=0
rows=()
seen=()

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

  # Every filesystem step fails closed: no step may be silently skipped.
  mkdir -p "$dir"            || { echo "MKDIR FAILED: $dir" >&2; return 2; }
  cp -a "$seed"/. "$dir"/     || { echo "SEED COPY FAILED: $seed" >&2; return 2; }
  if [ "$overlay" != "-" ]; then
    cp -a "$overlay"/. "$dir"/ || { echo "OVERLAY COPY FAILED: $overlay" >&2; return 2; }
  fi
  cp "protected-oracle/$oracle" "$dir/oracle.py" || { echo "ORACLE COPY FAILED: $oracle" >&2; return 2; }

  # Byte-identity assertion: every overlaid file must equal the published source byte for byte.
  if [ "$overlay" != "-" ]; then
    local f rel
    for f in "$overlay"/*; do
      rel="$(basename "$f")"
      cmp -s "$f" "$dir/$rel" || { echo "OVERLAY MISMATCH: $rel" >&2; return 2; }
    done
  fi

  local out rc last
  if ! out="$( cd "$dir" && timeout "$ORACLE_TIMEOUT" python3 -B oracle.py 2>&1 )"; then
    rc=$?
    # 124 is timeout's own code; distinguish it from a genuine test failure.
    if [ "$rc" -eq 124 ]; then
      last="TIMEOUT after ${ORACLE_TIMEOUT}s"
      printf '%-14s TIMEOUT\n' "$label" >&2
      seen+=("$label"); rows+=("$(printf '%-14s %s' "$label" "TIMEOUT")")
      fails=$((fails + 1)); return 0
    fi
    last="$(printf '%s' "$out" | tail -n 1)"
    printf '%-14s rc=%-3s %s\n' "$label" "$rc" "$last" >&2
    seen+=("$label"); rows+=("$(printf '%-14s %s' "$label" "FAIL(rc=$rc)")")
    fails=$((fails + 1)); return 0
  fi
  last="$(printf '%s' "$out" | tail -n 1)"
  printf '%-14s rc=0   %s\n' "$label" "$last" >&2
  seen+=("$label"); rows+=("$(printf '%-14s %s' "$label" "PASS")")
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
  local f rel
  mkdir -p "$dir"                                          || { echo "MKDIR FAILED: $label" >&2; return 2; }
  cp -a "$seed"/. "$dir"/                                   || { echo "SEED COPY FAILED: $label" >&2; return 2; }
  cp -a "$oa"/. "$dir"/                                     || { echo "A COPY FAILED: $oa" >&2; return 2; }
  for f in "$ob"/*; do rel="$(basename "$f")"; cp -a "$f" "$dir/$rel" || { echo "B COPY FAILED: $rel" >&2; return 2; }; done
  cp "protected-oracle/$oracle" "$dir/oracle.py"            || { echo "ORACLE COPY FAILED: $label" >&2; return 2; }

  local ok=1
  for src in "$oa" "$ob"; do
    for f in "$src"/*; do
      rel="$(basename "$f")"
      cmp -s "$f" "$dir/$rel" || { echo "COMPOSE MISMATCH: $rel" >&2; ok=0; }
    done
  done
  [ "$ok" -eq 1 ] || return 2

  local out rc last
  if ! out="$( cd "$dir" && timeout "$ORACLE_TIMEOUT" python3 -B oracle.py 2>&1 )"; then
    rc=$?
    if [ "$rc" -eq 124 ]; then
      printf '%-14s TIMEOUT\n' "$label" >&2
      seen+=("$label"); rows+=("$(printf '%-14s %s' "$label" "TIMEOUT")"); fails=$((fails + 1)); return 0
    fi
    last="$(printf '%s' "$out" | tail -n 1)"
    printf '%-14s rc=%-3s %s\n' "$label" "$rc" "$last" >&2
    seen+=("$label"); rows+=("$(printf '%-14s %s' "$label" "FAIL(rc=$rc)")"); fails=$((fails + 1)); return 0
  fi
  last="$(printf '%s' "$out" | tail -n 1)"
  printf '%-14s rc=0   %s\n' "$label" "$last" >&2
  seen+=("$label"); rows+=("$(printf '%-14s %s' "$label" "PASS")")
  return 0
}

echo "== payload integrity =="
sha256sum -c MANIFEST.sha256 || { echo "MANIFEST FAILED"; exit 2; }
echo

echo "== eight cases (stderr shows per-case oracle output) =="

# Every caller failure is CAPTURED. A case that aborts on missing input, a bad copy or a
# guard is a run failure, not a silent skip. Note the explicit `|| rc=$?` on each call.
setup_err=0

rc=0; run_case f1-base  seed-arm1 -                      oracle-arm1.py || rc=$?
[ "$rc" -eq 0 ] || { echo "SETUP FAILURE in f1-base (rc=$rc)" >&2; setup_err=1; }

rc=0; run_case f1-A     seed-arm1 arm1-signposted/A      oracle-arm1.py || rc=$?
[ "$rc" -eq 0 ] || { echo "SETUP FAILURE in f1-A (rc=$rc)" >&2; setup_err=1; }

rc=0; run_case f1-B     seed-arm1 arm1-signposted/B      oracle-arm1.py || rc=$?
[ "$rc" -eq 0 ] || { echo "SETUP FAILURE in f1-B (rc=$rc)" >&2; setup_err=1; }

rc=0; compose_case f1-AB seed-arm1 arm1-signposted/A arm1-signposted/B oracle-arm1.py || rc=$?
[ "$rc" -eq 0 ] || { echo "SETUP FAILURE in f1-AB (rc=$rc)" >&2; setup_err=1; }

rc=0; run_case f2-base  seed-arm2 -                      oracle-arm2.py || rc=$?
[ "$rc" -eq 0 ] || { echo "SETUP FAILURE in f2-base (rc=$rc)" >&2; setup_err=1; }

rc=0; run_case f2-A     seed-arm2 arm2-signposted/A      oracle-arm2.py || rc=$?
[ "$rc" -eq 0 ] || { echo "SETUP FAILURE in f2-A (rc=$rc)" >&2; setup_err=1; }

rc=0; run_case f2-B     seed-arm2 arm2-signposted/B      oracle-arm2.py || rc=$?
[ "$rc" -eq 0 ] || { echo "SETUP FAILURE in f2-B (rc=$rc)" >&2; setup_err=1; }

rc=0; compose_case f2-AB seed-arm2 arm2-signposted/A arm2-signposted/B oracle-arm2.py || rc=$?
[ "$rc" -eq 0 ] || { echo "SETUP FAILURE in f2-AB (rc=$rc)" >&2; setup_err=1; }

echo
echo "== summary =="
printf '%s\n' "${rows[@]}"

# Exactly eight rows, exactly the expected labels, no duplicates, no gaps.
nseen=${#seen[@]}
if [ "$nseen" -ne "${#EXPECTED_CASES[@]}" ]; then
  echo "STRUCTURE FAILURE: recorded $nseen case rows, expected ${#EXPECTED_CASES[@]}" >&2
  setup_err=1
fi
for want in "${EXPECTED_CASES[@]}"; do
  hit=0
  for got in "${seen[@]}"; do [ "$got" = "$want" ] && hit=1; done
  [ "$hit" -eq 1 ] || { echo "STRUCTURE FAILURE: missing case row '$want'" >&2; setup_err=1; }
done
dupes=$(printf '%s\n' "${seen[@]}" | sort | uniq -d)
[ -z "$dupes" ] || { echo "STRUCTURE FAILURE: duplicate case rows: $dupes" >&2; setup_err=1; }

echo "cases failing (oracle/timeout): $fails"
echo "setup/structure failures:       $setup_err"
echo "expected: all eight PASS (base/A/B/A+B for both fixtures)"
[ "${KEEP:-0}" = "1" ] && echo "scratch kept: $SCRATCH_ROOT"

if [ "$setup_err" -ne 0 ]; then exit 3; fi
exit "$fails"
