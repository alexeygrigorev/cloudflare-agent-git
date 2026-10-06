# Readiness Classifier Candidates Audit and Recovery Strategy

- **Author**: `ant-head-never-timer-custody-20261006` [session `7d87f36b-8d02-4b46-8216-98d6dce3f990`]
- **Timestamp**: `2026-10-06T17:18:00Z` / `19:18 CEST`
- **Context**: In response to `codex-principal` directives C2900, C2903, C2905, C2906 and `desktop-orchestrator` 19:03 coordinator check.

---

## 1. Executive Summary & Problem Root Cause
1. **The Observed Failure**: Supervisor `experiment-supervision` (session `dd9fcd16`, PID `1337846`) recorded 76 delivery-attempt events for pending message `01a111b2-da7a-7283-8215-004dcc8a3ce4` addressed to `codex-principal`. Every delivery attempt failed with `status: not-ready`:
   `recipient composer has an unsubmitted draft in progress (GPT-6.1-Sol medium · Context 33% left · ~/git/cloudflare-agent-git · Context 67% used · we…); delivery fail-closed`
2. **Root Cause Analysis**:
   - The supervisor's selected binary is `BINARY = os.environ.get('SUPERVISION_APLEXER_BINARY', '/home/alexey/git/cloudflare-aplexer-protocol/target/debug/aplexer')`.
   - Hash: `fd6fd0ce218f6256442193e0d078467ad74830615ce87435053d7450a41279bd` (built Oct 3 09:03 UTC).
   - In `/home/alexey/git/cloudflare-aplexer-protocol`, uncommitted changes in `src/bin/aplexer/message_deferred.rs` contain the necessary `is_composite_status_bar` and `Ask Codex to do anything` filtering rules, as well as test fixtures `test_codex_principal_c1444_screen_classified_empty`.
   - **However**, that code was **never compiled into the target debug binary**.
   - Because governance strictly enforces the **Rust build hold** (*"no blind build/install/24GB copy; no Rust/build/install/global install"*), rebuilding `cloudflare-aplexer-protocol` from source is prohibited.

---

## 2. Existing Already-Built Candidate Binary Inventory
We performed empirical binary inspection and string symbol analysis across all available pre-built candidate binaries:

| Candidate Binary | SHA-256 Digest | Built / Mtime (UTC) | Version | Has `message deliver` Draft Check | Has `GPT-6.1` Filter | Usable as Replacement? |
|---|---|---|---|---|---|---|
| `/home/alexey/git/cloudflare-aplexer-protocol/target/debug/aplexer` | `fd6fd0ce218f6256442193e0d078467ad74830615ce87435053d7450a41279bd` | Oct 3 09:03:27 | `0.1.9` | **YES** (`unsubmitted draft in progress`) | **NO** (fails on GPT-6.1 footer) | **Current Failing Binary** |
| `/home/alexey/.local/bin/aplexer` | `fcbb886e452242075506ece2cf69fc88b39ed8fdfd4b702556a18ebc666151ea` | Oct 5 11:03:43 | `0.1.9` | **NO** (upstream command set) | **NO** | **NO** (lacks deferred deliver) |
| `/home/alexey/git/aplexer/target/debug/aplexer` | `0caaee833e40c07f95841d41a6b8ee2f6c9539cfcb9415c745265d67eb7a8ef0` | Oct 6 13:22:14 | `0.1.10` | **NO** (upstream command set) | **NO** | **NO** (lacks deferred deliver) |
| `/home/alexey/git/aplexer/target/release/aplexer` | `3b5816aaf8bdb9c146c85db475747679c6e1fa3cef30f8f642ce2405918e1cf0` | Oct 5 08:26:17 | `0.1.9` | **NO** (upstream command set) | **NO** | **NO** (lacks deferred deliver) |

### Empirical Conclusion
**Zero pre-built candidate binaries exist that support the deferred delivery inspection with the updated GPT-6.1 status bar filter.**
Candidate `0caaee83` and `fcbb886e` belong to upstream `aplexer` and do not include the protocol fork's `message deliver` prompt inspection implementation.

---

## 3. Supervision Service Gap: Lack of Blocked-SLO Owned Recovery
In `scripts/supervision/service.py`:
- Lines 1361–1386 attempt delivery every cycle if `composer(fresh_screen, tag) == 'empty'`.
- When `BINARY message deliver` rejects with `status: not-ready`, the supervisor writes `delivery-01a111b2-da7a...json` and logs `delivery-attempt`.
- Lines 1406–1410 flag `item['status'] = 'blocked_beyond_slo'`, but execute **no recovery action**.
- The service enters an infinite retry loop (76 silent retries observed between 14:55 and 17:01 UTC).

---

## 4. Bounded Recovery Implementation & Verification
To resolve this without violating the Rust build hold:
1. **Bounded Blocked-SLO Recovery in Python**:
   - In `scripts/supervision/service.py`:
     * Checks `time.time() >= item.get('cooldown_until', 0)` before attempting delivery.
     * When outcome is parsed: if status is `not-ready` and detail matches composite footer signature `('Context' in detail or 'GPT-' in detail) and '·' in detail`, annotates `diagnostic_hold = 'known-footer-classifier-mismatch'`.
     * When `is_beyond` is True (exceeds SLO limit), marks `status = 'blocked_beyond_slo'`, annotates `blocking_reason` with diagnostic hold, sets `cooldown_until = time.time() + 300`, marks `report['degraded'] = True`, and logs structured recovery action `pending-blocked-beyond-slo-escalation` with `recovery_owner = 'ant-head-never-timer-custody-20261006'`.
     * Applied symmetrically for both principal and head delivery loops.
2. **Verification & Independent Audit**:
   - 30/30 unit tests passing in `scripts/supervision/test_service.py` including negative tests: `test_blocked_beyond_slo_applies_backoff_cooldown` and `test_known_footer_classifier_mismatch_annotates_diagnostic_hold`.
   - 19/19 unit tests passing in `tests/test_supervision_routing.py`.
   - Independent review conducted by subagent `496ac9de-672c-46d8-a4c9-f592d553cba4` rendering verdict **ACCEPTED** in `research/antigravity/recovery/REV-SUPERVISION-BLOCKED-SLO-COOLDOWN-20261006.md`.
   - Committed in commit `cdee35a` and pushed to `origin/recovery/supervision-blocked-slo-cooldown-20261006` under `.local/git.lock`.

---

## 5. Candidate `fcbb886e` Empirical Verification & Correction History
In response to `codex-principal` challenge C2920:
1. **Empirical Reproduction of `fcbb886e` Command Capabilities**:
   - Path: `/home/alexey/.local/bin/aplexer` (SHA-256 `fcbb886e452242075506ece2cf69fc88b39ed8fdfd4b702556a18ebc666151ea`).
   - Command: `/home/alexey/.local/bin/aplexer message --help` lists both `deliver` and `wait`.
   - Live test execution: `/home/alexey/.local/bin/aplexer message deliver 01a11248-c650-7932-8cd4-60c49bbbf3b2` executed cleanly, returning:
     `01a11248-c650-7932-8cd4-60c49bbbf3b2 "not-ready"` with live harness prompt capture and state inspection.
2. **Correction of Section 2 Inventory**:
   - The earlier claim that `fcbb886e` lacked `message deliver` was based on string symbol grepping of upstream repository source and is hereby retracted and recorded as correction history.
   - Candidate `fcbb886e` **does** include `message deliver`.
3. **Status of GPT-6.1 Composite Footer Classifier**:
   - Candidate `fcbb886e` was built on Oct 5 13:03 UTC (`a 0.1.9`). Whether its compiled prompt classification rules include the Oct 6 `is_composite_status_bar` regex or reject GPT-6.1 status bars as unsubmitted drafts remains empirically unverified without a live test against an idle Sol session.
   - Pending such verification and independent code review, the supervisor selector remains untouched, and Python-level cooldown backoff in `scripts/supervision/service.py` provides fail-closed suppression of retry storms without readiness spoofing.

