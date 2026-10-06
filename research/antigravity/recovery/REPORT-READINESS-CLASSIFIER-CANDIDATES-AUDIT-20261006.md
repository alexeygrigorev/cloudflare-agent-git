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

## 4. Proposed Bounded Recovery Strategy
To resolve this without violating the Rust build hold:
1. **Bounded Blocked-SLO Recovery in Python**:
   - In `scripts/supervision/service.py`, when a pending message is `blocked_beyond_slo` specifically due to `recipient composer has an unsubmitted draft in progress` matching the known composite status bar pattern, while Python's verified `composer(fresh_screen, tag) == 'empty'` confirms the composer is truly resting and empty:
   - Instead of retrying indefinitely 76 times, route the alert to the responsible principal/head directly via standard `aplexer message send` or escalate with a structured backoff.
2. **Preserve Exact Audit Records**:
   - Retain all delivery records, cursor persistence, and envelope IDs (`01a111b2-da7a...`).
   - Settle ownership across heads cleanly.
