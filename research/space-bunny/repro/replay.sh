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

# GUARD OVERRIDE, LOUD BY DESIGN. Some negative tests must reach a DEEPER check, which means
# disabling a shallower guard. Deleting or regexing a guard out of the script is how this
# harness already broke twice, so instead a test sets REPLAY_GUARDS_OFF=1 and the run
# prints a banner. A guard-disabled run is therefore never silent, and it is greppable in
# any transcript. Default is 0: fail-closed.
REPLAY_GUARDS_OFF="${REPLAY_GUARDS_OFF:-0}"

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

# Fail closed if we cannot get our own private scratch. Never derive it from a payload dir.
SCRATCH_ROOT="$(mktemp -d /tmp/g3repro.XXXXXX)" || { echo "FATAL: cannot create scratch" >&2; exit 3; }
case "$SCRATCH_ROOT" in /tmp/g3repro.*) ;; *) echo "FATAL: scratch outside expected prefix: $SCRATCH_ROOT" >&2; exit 3 ;; esac
cleanup() { [ "${KEEP:-0}" = "1" ] || rm -rf "$SCRATCH_ROOT"; }
trap cleanup EXIT

# Expected case labels, verified after the run. Duplicates or gaps are a failure.
EXPECTED_CASES=(f1-base f1-A f1-B f1-AB f2-base f2-A f2-B f2-AB)

# LABEL -> OVERLAY BINDING. Muse (01a0ff9d) found that a case label is just a string: pointing
# `f1-A` at the wrong same-fixture overlay still reported PASS for all eight and exited 0.
# The overlay directory name therefore cannot be the only identity. Each overlay carries a
# `.head` file recording the executor commit that produced it, so we bind label -> recorded
# head and require the overlay actually used to match the head the label is supposed to mean.

fails=0
rows=()
seen=()

# EXPECTED_HEAD <label> -> the executor SHA that label must mean, read from the CANONICAL
# packet for that overlay dir. Derived from the label's own fixture/role, not from the overlay
# argument, so passing the wrong overlay is detectable.
EXPECTED_HEAD() {
  case "$1" in
    f1-A) cat "$HERE/arm1-signposted/A/.head" 2>/dev/null ;;
    f1-B) cat "$HERE/arm1-signposted/B/.head" 2>/dev/null ;;
    f2-A) cat "$HERE/arm2-signposted/A/.head" 2>/dev/null ;;
    f2-B) cat "$HERE/arm2-signposted/B/.head" 2>/dev/null ;;
    *) echo "" ;;
  esac
}

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

  # LABEL/HEAD BINDING (Muse 01a0ff9d): the overlay actually used must carry the executor head
  # the label is supposed to mean. Catches a swapped overlay that the fixture guard allows
  # because both overlays belong to the same fixture.
  local want_head got_head
  want_head="$( EXPECTED_HEAD "$label" )"
  if [ -n "$want_head" ] && [ "$REPLAY_GUARDS_OFF" = "0" ]; then
    got_head="$(cat "$overlay/.head" 2>/dev/null)"
    if [ "$got_head" != "$want_head" ]; then
      echo "LABEL/OVERLAY MISMATCH: $label expects head ${want_head:0:12} but $overlay carries ${got_head:0:12}" >&2
      return 2
    fi
  fi

  # Byte-identity assertion: every overlaid file must equal the published source byte for byte.
  if [ "$overlay" != "-" ]; then
    local f rel
    for f in "$overlay"/*; do
      rel="$(basename "$f")"
      [ "$rel" = ".head" ] && continue
      cmp -s "$f" "$dir/$rel" || { echo "OVERLAY MISMATCH: $rel" >&2; return 2; }
    done
  fi

  local out rc last
  # Capture the status DIRECTLY. `if ! cmd; then rc=$?` is wrong: `!` negates the
  # status, so $? inside the block is 0 and a real failure or timeout is mislabelled.
  out="$( cd "$dir" && timeout "$ORACLE_TIMEOUT" python3 -B oracle.py 2>&1 )"; rc=$?
  if [ "$rc" -ne 0 ]; then
    if [ "$rc" -eq 124 ]; then
      printf '%-14s TIMEOUT after %ss\n' "$label" "$ORACLE_TIMEOUT" >&2
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
  local WORK_PROV="$dir/.prov"
  local composed="$WORK_PROV"
  mkdir -p "$WORK_PROV" 2>/dev/null || true
  [ -d "$seed" ] && [ -d "$oa" ] && [ -d "$ob" ] \
    && [ -f "protected-oracle/$oracle" ] \
    || { echo "MISSING INPUT for $label" >&2; return 2; }
  # BOTH overlay arguments must match the seed's fixture. Checking only one of them
  # misses a wrong A paired with a valid B.
  if [ "$REPLAY_GUARDS_OFF" = "0" ]; then
  case "$seed" in
    seed-arm1) case "$oa" in arm1*) ;; *) echo "FIXTURE MISMATCH (A): $seed with $oa" >&2; return 2 ;; esac
              case "$ob" in arm1*) ;; *) echo "FIXTURE MISMATCH (B): $seed with $ob" >&2; return 2 ;; esac ;;
    seed-arm2) case "$oa" in arm2*) ;; *) echo "FIXTURE MISMATCH (A): $seed with $oa" >&2; return 2 ;; esac
              case "$ob" in arm2*) ;; *) echo "FIXTURE MISMATCH (B): $seed with $ob" >&2; return 2 ;; esac ;;
    *) echo "UNKNOWN SEED FIXTURE: $seed" >&2; return 2 ;;
  esac
  fi
  local f rel
  mkdir -p "$dir"                                          || { echo "MKDIR FAILED: $label" >&2; return 2; }
  cp -a "$seed"/. "$dir"/                                   || { echo "SEED COPY FAILED: $label" >&2; return 2; }
  cp -a "$oa"/. "$dir"/                                     || { echo "A COPY FAILED: $oa" >&2; return 2; }
  for f in "$ob"/*; do
    rel="$(basename "$f")"
    # .head is a provenance label, not part of the executable packet.
    [ "$rel" = ".head" ] && continue
    cp -a "$f" "$dir/$rel" || { echo "B COPY FAILED: $rel" >&2; return 2; }
  done
  cp "protected-oracle/$oracle" "$dir/oracle.py"            || { echo "ORACLE COPY FAILED: $label" >&2; return 2; }

  local want_a got_a want_b got_b
  want_a="$( EXPECTED_HEAD "$label" | head -1 )"
  case "$label" in
    f1-AB) want_a="$(cat "$HERE/arm1-signposted/A/.head" 2>/dev/null)"; want_b="$(cat "$HERE/arm1-signposted/B/.head" 2>/dev/null)" ;;
    f2-AB) want_a="$(cat "$HERE/arm2-signposted/A/.head" 2>/dev/null)"; want_b="$(cat "$HERE/arm2-signposted/B/.head" 2>/dev/null)" ;;
  esac
  got_a="$(cat "$oa/.head" 2>/dev/null)"; got_b="$(cat "$ob/.head" 2>/dev/null)"
  if [ "$REPLAY_GUARDS_OFF" = "0" ] && [ -n "$want_a" ] && [ "$got_a" != "$want_a" ]; then
    echo "LABEL/OVERLAY MISMATCH (A): $label expects ${want_a:0:12} but $oa carries ${got_a:0:12}" >&2; return 2
  fi
  if [ "$REPLAY_GUARDS_OFF" = "0" ] && [ -n "$want_b" ] && [ "$got_b" != "$want_b" ]; then
    echo "LABEL/OVERLAY MISMATCH (B): $label expects ${want_b:0:12} but $ob carries ${got_b:0:12}" >&2; return 2
  fi

  local ok=1
  for src in "$oa" "$ob"; do
    for f in "$src"/*; do
      rel="$(basename "$f")"
      cmp -s "$f" "$dir/$rel" || { echo "COMPOSE MISMATCH: $rel" >&2; ok=0; }
    done
  done
  [ "$ok" -eq 1 ] || return 2

  # PROVENANCE MUST BE FIXTURE-AWARE, not just a filename set.
  #
  # Muse (01a0ff64) showed a cross-fixture A overlay builds a "franken tree" that still
  # PASSES the oracle, so the oracle cannot detect contamination and a row-count gate is
  # too weak. A filename-set check alone is ALSO insufficient, and I verified that: when
  # the foreign overlay is the one we were told to use, its filenames are legitimately
  # "allowed", so the set check passes while the tree is still wrong.
  #
  # The rule that does hold: every file in the composed tree must be provided by some
  # source belonging to the SEED's fixture. A file only obtainable from a foreign fixture
  # is unaccounted provenance, whatever the oracle says.
  local seed_fixture src_fixture
  case "$seed" in
    seed-arm1) seed_fixture=arm1 ;;
    seed-arm2) seed_fixture=arm2 ;;
    *) echo "UNKNOWN SEED FIXTURE: $seed" >&2; return 2 ;;
  esac
  # Enumerate what actually landed in the composed tree, excluding our own scratch.
  ( cd "$dir" && find . -type f ! -name '.head' ! -path './.prov/*' -printf '%P\n' | sort ) \
    > "$composed/actual" || { echo "PROVENANCE SCAN FAILED (actual) in $label" >&2; return 2; }
  : > "$composed/allowed"
  local src
  for src in "$seed" "$oa" "$ob"; do
    case "$src" in
      *"$seed_fixture"*) ;;
      *) continue ;;   # foreign fixture: its names are not allowed into this tree
    esac
    ( cd "$src" && find . -type f ! -name '.head' -printf '%P\n' ) >> "$composed/allowed" \
      || { echo "PROVENANCE SCAN FAILED for $src in $label" >&2; return 2; }
  done
  echo "oracle.py" >> "$composed/allowed"
  sort -u -o "$composed/allowed" "$composed/allowed"
  present="$( comm -23 "$composed/actual" "$composed/allowed" )"
  if [ -n "$present" ]; then
    echo "UNACCOUNTED PROVENANCE in $label:" >&2
    printf '  %s\n' "$present" >&2
    return 2
  fi

  local out rc last
  out="$( cd "$dir" && timeout "$ORACLE_TIMEOUT" python3 -B oracle.py 2>&1 )"; rc=$?
  if [ "$rc" -ne 0 ]; then
    if [ "$rc" -eq 124 ]; then
      printf '%-14s TIMEOUT after %ss\n' "$label" "$ORACLE_TIMEOUT" >&2
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

if [ "$REPLAY_GUARDS_OFF" != "0" ]; then
  echo "!! REPLAY_GUARDS_OFF=$REPLAY_GUARDS_OFF - FIXTURE AND LABEL GUARDS ARE DISABLED IN THIS RUN !!" >&2
  echo "!! valid only for negative tests that must reach a deeper check; never a real result !!" >&2
fi

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
