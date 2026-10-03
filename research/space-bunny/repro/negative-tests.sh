#!/usr/bin/env bash
# Negative tests for replay.sh - Codex principal delegated these (01a0ff5f, 01a0ff61).
#
# Each case works on a DISPOSABLE COPY of the whole packet. The canonical payload in
# this directory is never mutated: an earlier version edited payload files and restored
# them, which is fragile under a signal or interleaving. Here, only a scratch copy is
# ever touched, and only scratch is removed.
#
# Every case requires a NONZERO exit AND a surfaced reason, and must exercise the RUNTIME
# guarded path rather than being preempted by the manifest check.
#
# Usage: ./negative-tests.sh     (exit 0 means every negative test behaved correctly)
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK="$(mktemp -d /tmp/g3neg.XXXXXX)" || { echo "FATAL: no scratch" >&2; exit 3; }
cleanup(){ rm -rf "$WORK"; }
trap cleanup EXIT

pass=0; bad=0

# fresh_packet: a full disposable copy of the packet, with its own replay.sh
fresh_packet(){
  local name="$1"
  local d="$WORK/$name"
  mkdir -p "$d"
  # Copy the CONTENTS of this directory. `cp -a "$HERE"/* "$d"/` rather than
  # `cp -a "$HERE"/. "$d"/`: with a trailing "/." the copy silently produced an empty
  # tree in my first attempt, and every case then "passed" for the wrong reason.
  cp -a "$HERE"/. "$d"/ || return 1
  cp -a "$HERE"/*.py "$d"/ 2>/dev/null || true
  for sub in seed-arm1 seed-arm2 arm1-signposted arm2-signposted protected-oracle repro; do
    [ -e "$HERE/$sub" ] && cp -a "$HERE/$sub" "$d/"
  done
  cp "$HERE/replay.sh" "$HERE/MANIFEST.sha256" "$d"/
  rm -f "$d/negative-tests.sh"   # avoid recursion in the copy
  # Prove the copy is usable before any case depends on it.
  [ -x "$d/replay.sh" ] || { chmod +x "$d/replay.sh" 2>/dev/null; }
  [ -f "$d/replay.sh" ] || { echo "FATAL: fresh_packet produced no replay.sh" >&2; return 1; }
  [ -d "$d/protected-oracle" ] || { echo "FATAL: fresh_packet produced no payload" >&2; return 1; }
  printf '%s' "$d"
}

# skip_manifest: neuter the integrity gate inside a COPY so the RUNTIME guarded path is
# genuinely exercised. Without this, deleting or editing a payload file is preempted by
# the manifest check and the runtime guard is never reached - which is exactly what
# Codex caught in my earlier "hanging oracle" test.
skip_manifest(){ sed -i 's|^sha256sum -c MANIFEST.sha256 .*|echo "(manifest check skipped by negative test)"|' "$1/replay.sh"; }

# check <name> <packet> <expected_exit_may_be_zero:yes|no> <reason-regex>
check(){
  local name="$1" pkt="$2" want_zero="$3" reason="$4"
  local out code
  out="$( cd "$pkt" && timeout 120 ./replay.sh 2>&1 )"; code=$?
  if [ "$want_zero" = "no" ] && [ "$code" -ne 0 ] && printf '%s' "$out" | grep -qE "$reason"; then
    printf '  OK   %-34s exit=%-3s reason=%s\n' "$name" "$code" "$(printf '%s' "$out" | grep -oE "$reason" | head -1)"
    pass=$((pass+1))
  elif [ "$want_zero" = "yes" ] && [ "$code" -eq 0 ]; then
    printf '  OK   %-34s exit=0 (happy path)\n' "$name"
    pass=$((pass+1))
  else
    printf '  BAD  %-34s exit=%-3s wanted_zero=%s reason=/%s/\n' "$name" "$code" "$want_zero" "$reason"
    bad=$((bad+1))
  fi
}

echo "N1  missing overlay dir              (runtime guard, not integrity)"
p="$(fresh_packet n1)"; sed -i 's|run_case f2-B     seed-arm2 arm2-signposted/B|run_case f2-B     seed-arm2 NOPE|' "$p/replay.sh"
check "missing overlay dir" "$p" no 'MISSING OVERLAY DIR'

echo "N2  missing oracle FILE             (manifest skipped, runtime guard)"
p="$(fresh_packet n2)"; rm -f "$p/protected-oracle/oracle-arm2.py"
skip_manifest "$p"
check "missing oracle file" "$p" no 'MISSING ORACLE FILE'

echo "N3  cross-fixture overlay, single A  (runtime guard)"
p="$(fresh_packet n3)"; sed -i 's|run_case f2-A     seed-arm2 arm2-signposted/A|run_case f2-A     seed-arm2 arm1-signposted/A|' "$p/replay.sh"
check "cross-fixture single A" "$p" no 'FIXTURE MISMATCH'

echo "N4  cross-fixture compose, wrong A only (regression: guard must check A too)"
p="$(fresh_packet n4)"; sed -i 's|compose_case f2-AB seed-arm2 arm2-signposted/A arm2-signposted/B|compose_case f2-AB seed-arm2 arm1-signposted/A arm2-signposted/B|' "$p/replay.sh"
check "cross-fixture compose wrong A" "$p" no 'FIXTURE MISMATCH \(A\)'

echo "N5  cross-fixture compose, wrong B only"
p="$(fresh_packet n5)"; sed -i 's|compose_case f2-AB seed-arm2 arm2-signposted/A arm2-signposted/B|compose_case f2-AB seed-arm2 arm2-signposted/A arm1-signposted/B|' "$p/replay.sh"
check "cross-fixture compose wrong B" "$p" no 'FIXTURE MISMATCH \(B\)'

echo "N6  unreadable overlay file          (copy-failure guard, manifest skipped)"
p="$(fresh_packet n6)"; skip_manifest "$p"; chmod 000 "$p/arm1-signposted/A/cache.py"
check "unreadable overlay" "$p" no 'OVERLAY COPY FAILED'
chmod 644 "$p/arm1-signposted/A/cache.py" 2>/dev/null

echo "N7  hanging oracle -> real TIMEOUT   (manifest skipped, guard reached)"
p="$(fresh_packet n7)"; skip_manifest "$p"
printf '\nimport time\ntime.sleep(600)\n' >> "$p/protected-oracle/oracle-arm1.py"
out="$( cd "$p" && ORACLE_TIMEOUT=3 timeout 180 ./replay.sh 2>&1 )"; code=$?
if [ "$code" -ne 0 ] && printf '%s' "$out" | grep -q 'TIMEOUT'; then
  printf '  OK   %-34s exit=%-3s reason=%s\n' "hanging oracle" "$code" "$(printf '%s' "$out" | grep -oE 'TIMEOUT' | head -1)"
  pass=$((pass+1))
else
  printf '  BAD  %-34s exit=%-3s (expected nonzero + TIMEOUT)\n' "hanging oracle" "$code"; bad=$((bad+1))
fi

echo "N8  failing oracle -> real rc        (not TIMEOUT, not rc=0)"
p="$(fresh_packet n8)"; skip_manifest "$p"
printf '\nraise SystemExit(3)\n' >> "$p/protected-oracle/oracle-arm1.py"
out="$( cd "$p" && ORACLE_TIMEOUT=20 timeout 180 ./replay.sh 2>&1 )"; code=$?
if [ "$code" -ne 0 ] && printf '%s' "$out" | grep -qE 'FAIL\(rc=3\)'; then
  printf '  OK   %-34s exit=%-3s reason=%s\n' "failing oracle" "$code" "$(printf '%s' "$out" | grep -oE 'FAIL\(rc=3\)' | head -1)"
  pass=$((pass+1))
else
  printf '  BAD  %-34s exit=%-3s (expected nonzero + FAIL(rc=3); rc must NOT be 0)\n' "failing oracle" "$code"; bad=$((bad+1))
fi

echo "N9  tampered payload, manifest NOT resealed (integrity gate, expected)"
p="$(fresh_packet n9)"; printf '\n# tampered\n' >> "$p/arm1-signposted/A/cache.py"
check "tampered payload" "$p" no 'MANIFEST FAILED'

echo "N9b cross-fixture franken tree (Muse 01a0ff64) - oracle CANNOT catch it"
# Reproduce Muse's case exactly: the oa/ob guard is REMOVED, so a cross-fixture A
# overlay builds a tree the oracle accepts. The provenance-by-file-set check must
# still refuse it, because the oracle cannot detect contamination.
# Disable BOTH guards, not just the fixture one: the label/head binding would otherwise
# fire first and the provenance check under test would never be reached.
p="$(fresh_packet n9b)"; skip_manifest "$p"
# No script surgery: REPLAY_GUARDS_OFF=1 disables the shallower guards so the DEEPER check
# under test is actually reached, and replay.sh prints a loud banner when it is set.
sed -i 's|compose_case f2-AB seed-arm2 arm2-signposted/A arm2-signposted/B|compose_case f2-AB seed-arm2 arm1-signposted/A arm2-signposted/B|' "$p/replay.sh"
export REPLAY_GUARDS_OFF=1
check "unaccounted provenance" "$p" no 'UNACCOUNTED PROVENANCE'

unset REPLAY_GUARDS_OFF

echo "N9c extra file smuggled into a case"
p="$(fresh_packet n9c)"; skip_manifest "$p"
sed -i 's|  cp "protected-oracle/$oracle" "$dir/oracle.py" .. { echo "ORACLE COPY FAILED: $oracle" >&2; return 2; }|&|' "$p/replay.sh" 2>/dev/null || true
python3 - "$p/replay.sh" <<'PY3'
import pathlib, sys
p = pathlib.Path(sys.argv[1]); t = p.read_text()
# inject a stray file right after the seed copy in compose_case
t = t.replace('  cp -a "$ob"/. "$dir"/'.replace('"ob"/.', '"$ob"/.'),
              '  cp -a "$ob"/. "$dir"/', 1)
t = t.replace('  for f in "$ob"/*; do',
              '  echo "smuggled" > "$dir/EXTRA-STOWAWAY.txt"   # injected foreign file\n  for f in "$ob"/*; do', 1)
p.write_text(t)
PY3
check "extra foreign file" "$p" no 'UNACCOUNTED PROVENANCE'

echo "N9d label/overlay swap (Muse 01a0ff9d) - same fixture, wrong overlay"
# A case LABEL is just a string. Pointing f1-A at f1-B's overlay satisfies the fixture
# guard (both are arm1) and used to report PASS for all eight with exit 0.
p="$(fresh_packet n9d)"; skip_manifest "$p"
sed -i 's|run_case f1-A     seed-arm1 arm1-signposted/A|run_case f1-A     seed-arm1 arm1-signposted/B|' "$p/replay.sh"
check "label/overlay swap" "$p" no 'LABEL/OVERLAY MISMATCH'

echo "N9e compose label/overlay swap (A side)"
p="$(fresh_packet n9e)"; skip_manifest "$p"
sed -i 's|compose_case f1-AB seed-arm1 arm1-signposted/A arm1-signposted/B|compose_case f1-AB seed-arm1 arm1-signposted/B arm1-signposted/B|' "$p/replay.sh"
check "compose label swap (A)" "$p" no 'LABEL/OVERLAY MISMATCH \(A\)'

echo "N10 happy path control"
p="$(fresh_packet n10)"
check "clean run" "$p" yes ''

echo
echo "negative tests: $pass passed, $bad bad"
[ "$bad" -eq 0 ] || exit 1
exit 0
