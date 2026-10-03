#!/usr/bin/env bash
# NEGATIVE TESTS for replay.sh - Codex principal delegated these (01a0ff5f).
#
# Each mutation MUST make replay.sh exit nonzero, and MUST surface a reason. No agents,
# no network, no credentials. Every mutation is applied to a COPY of replay.sh and to
# payload files that are restored afterwards; payload integrity is re-verified at the end.
#
# Usage: ./negative-tests.sh     (exit 0 means every negative test behaved correctly)
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"
pass=0; fail=0
chk(){ # name expected_nonzero actual_code
  if [ "$2" = "yes" ] && [ "$3" -ne 0 ]; then echo "  OK   $1 -> exit $3 (nonzero as required)"; pass=$((pass+1))
  elif [ "$2" = "no" ] && [ "$3" -eq 0 ]; then echo "  OK   $1 -> exit 0 (happy path)"; pass=$((pass+1))
  else echo "  BAD  $1 -> exit $3 (wanted nonzero=$2)"; fail=$((fail+1)); fi
}
WORK="$(mktemp -d /tmp/g3neg.XXXXXX)"
cleanup(){ rm -f ./neg.sh; rm -rf "$WORK"; }
trap cleanup EXIT
mut(){ cp replay.sh "$WORK/neg.sh"; chmod +x "$WORK/neg.sh"; cp "$WORK/neg.sh" ./neg.sh; }
run(){ ./neg.sh >"$WORK/out" 2>&1; echo $?; }
grep_out(){ grep -m1 "$1" "$WORK/out"; }

echo "N1 missing overlay dir (must be nonzero)"
mut; sed -i 's|run_case f2-B     seed-arm2 arm2-signposted/B|run_case f2-B     seed-arm2 NOPE|' neg.sh; c=$(run)
chk "missing input" yes "$c"; grep -q "MISSING OVERLAY DIR\|STRUCTURE FAILURE" $WORK/out && echo "       reason surfaced: $(grep -m1 'MISSING OVERLAY DIR\|STRUCTURE FAILURE' $WORK/out)"

echo "N2 cross-fixture overlay (must be nonzero)"
mut; sed -i 's|run_case f2-A     seed-arm2 arm2-signposted/A|run_case f2-A     seed-arm2 arm1-signposted/A|' neg.sh; c=$(run)
chk "cross-fixture" yes "$c"; grep -q "FIXTURE MISMATCH" $WORK/out && echo "       reason surfaced: $(grep -m1 FIXTURE $WORK/out)"

echo "N3 cross-fixture in compose (must be nonzero)"
mut; sed -i 's|compose_case f2-AB seed-arm2 arm2-signposted/A arm2-signposted/B|compose_case f2-AB seed-arm2 arm2-signposted/A arm1-signposted/B|' neg.sh; c=$(run)
chk "cross-fixture compose" yes "$c"

echo "N4 tampered payload / copy failure (must be nonzero)"
mut; cp arm1-signposted/A/cache.py $WORK/cache.keep
printf '\n# tampered\n' >> arm1-signposted/A/cache.py; c=$(run)
chk "tampered payload" yes "$c"; grep -q "MANIFEST FAILED" $WORK/out && echo "       reason surfaced: MANIFEST FAILED"
cp $WORK/cache.keep arm1-signposted/A/cache.py

echo "N5 unreadable overlay (copy failure path, must be nonzero)"
mut; cp -r arm1-signposted/A $WORK/Akeep; chmod 000 arm1-signposted/A/cache.py
c=$(run); chmod 644 arm1-signposted/A/cache.py
chk "unreadable overlay" yes "$c"

echo "N6 oracle timeout (must be nonzero, bounded)"
mut; cp protected-oracle/oracle-arm1.py $WORK/o.keep
printf '\nimport time\ntime.sleep(600)\n' >> protected-oracle/oracle-arm1.py
c=$(ORACLE_TIMEOUT=3 timeout 120 bash ./neg.sh >$WORK/out 2>&1; echo $?)
chk "oracle timeout" yes "$c"; grep -q "TIMEOUT" $WORK/out && echo "       reason surfaced: $(grep -m1 TIMEOUT $WORK/out)"
cp $WORK/o.keep protected-oracle/oracle-arm1.py

echo "N7 happy path still zero"
mut; c=$(run); chk "clean run" no "$c"
rm -f neg.sh
echo; echo "negative tests: $pass passed, $fail bad"
sha256sum -c MANIFEST.sha256 >/dev/null 2>&1 && echo "payload restored: 21/21 OK"
exit $fail
