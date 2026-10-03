# A01 frozen BASE known-good preflight — VERDICT

- Reviewer: zcode-independent (aplexer session 64049aa2, native zcodex), non-author of fixture
- Date: 2026-10-03 (UTC timestamps in hash log)
- Fixture: `.local/protected/a01-ground-truth/` per antigravity-head note 01a1009b-ad36; manifest `CHECKSUMS.json` sha256 `c631f8d9468da858ec659c0c0648be0ef9482ea80438f8c7660166048352d87a` (hash at verification time; log's earlier copy `7b929fbf…` predates a 09:36 rewrite); grader pin `af751299…` verified present
- Method: read-only. Tests and grader executed only on a temp copy; fixture re-hashed post-run, byte-identical.

## Result: PASS with one manifest metadata defect

1. **Content identity 9/9 VERIFIED** — every pinned sha256 matches the on-disk file (`ok=9 mismatch=0 missing=0`).
2. **Manifest byte-count defect** — 5/9 `bytes` fields are wrong (all five `base_event_store` files; deltas +60/+227/+67/+67/+91 B). Ruled out: CRLF accounting (zero CR bytes in any file) and UTF-8 char-count vs byte-count (chars != declared). The hash fields are correct; only the size metadata is stale — generator bug, content unaffected. **Recommendation to owner (antigravity-head): regenerate `bytes` from `os.path.getsize` or drop the field; sha256 is the load-bearing pin.** No content re-freeze required.
3. **Fixture functionality** — base tests pass on temp copy: producer emit/flush roundtrip (1 passed); consumer `test_process_stream_interface` is interface-presence only (`hasattr`), passes against the `NotImplementedError` stub. Baseline tests are deliberately smoke-level; the real verification load sits in the grader.
4. **Frozen grader vs frozen BASE** — `test_integration_stream.py` v2.2.0 run twice against base copy: exit 1 both runs, identical error `NotImplementedError: process_stream must be implemented per Ticket ENG-402`; DETERMINISTIC. This is the documented FAIL path and the correct known-good baseline for A01 pairs.

## Preflight gate status

Frozen BASE is verified known-good; A01 pairs may proceed against this pin. A01 pair arms must re-verify hashes before run (script: hash log in `.local/producer-check-z/a01-base-preflight-hashlog.txt`).

**Concurrency observation:** the manifest file was rewritten at 09:36:14+02:00, between my 09:34 hash run and verdict time, while the five byte-count defects persisted unchanged — verified against the `c631f8d9…` state. Ask the owner to freeze the manifest (no rewrites) once A01 pairs start, or repin and notify checkers.

Raw evidence: `.local/producer-check-z/a01-base-preflight-hashlog.txt` (private side, uncommitted hashes of full manifest).
