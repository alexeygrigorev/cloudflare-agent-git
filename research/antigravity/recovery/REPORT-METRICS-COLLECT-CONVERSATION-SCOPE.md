# REPORT-METRICS-COLLECT-CONVERSATION-SCOPE

**Author:** `metrics-collect-worker` (native-harness subagent `fd6f993c-e2b0-45d6-8656-247d90e24427`)  
**Parent:** `antigravity-head` (`46fdb644-9b58-4e2f-aab3-9be5e1e33337`)  
**Directives:** Desktop Root and Codex Principal C1735 / C1736 / C1764  
**Workspace:** `/home/alexey/git/cloudflare-agent-git`  
**Scratch Root:** `/home/alexey/git/cloudflare-agent-git/.local/scratch/metrics-collect-fix/` (mode `0700`, 4 KB ≤ 512 MB, zero `/tmp` growth)  
**Target File:** `scripts/metrics/collect.py`  
**Test Suite:** `tests/test_collect_conversation_scope.py`  
**Verification Date:** 2026-10-04  

---

## 1. Executive Summary & Defect Audit

### 1.1 Defect Audit in `scripts/metrics/collect.py`
Prior to this implementation, `scripts/metrics/collect.py` lines 194–200 scanned `.local/metrics/usage-events.jsonl` using naive tag-and-team matching:

```python
# scripts/metrics/collect.py (prior implementation):
events = STORE / 'usage-events.jsonl'; found = None
if events.exists() and events.stat().st_size <= 16 * 1024 * 1024:
    for line in events.open():
        try: entry = json.loads(line)
        except ValueError: continue
        if entry.get('tag') == item.get('tag') and entry.get('team_id') == team_id and (found is None or entry.get('total_tokens', 0) > found.get('total_tokens', 0)):
            found = entry
    if found:
        usage = {**found, 'source': 'owner-metadata-' + found.get('provider', 'unknown') + '-' + found.get('model', 'unknown'), 'scope': 'Exact owner-registered cumulative counters, not independent telemetry verification'}
```

#### Defect Mechanisms:
1. **Omission of Conversation ID Isolation:** Line 199 matched only on `(entry.tag == item.tag and entry.team_id == team_id)`. It completely ignored `entry.get('conversation_id')` and the active agent session's authentic conversation identifier.
2. **Greedy Maximization Cross-Contamination (`max(total_tokens)`):** When an agent tag was reused across distinct runs or sessions (e.g. `worker-alpha`, `zcode-recovery-test`, `sdk-distribution-reviewer`), `collect.py` selected the record with the maximum token count across all recorded conversations. Consequently, a newer, smaller run using that tag was erroneously attributed the cumulative token total of a prior, larger run.
3. **Dictionary Key Overwrite in Session Selection:** At lines 142–147, `config` mapped `item.get('tag') -> (team_id, item)`. When multiple agents or subagents shared a tag (or when an agent tag was declared for multiple tasks), the dictionary key collided, dropping prior agent declarations from observation.

---

## 2. Conversation-Aware Implementation

### 2.1 Authentic Conversation ID Resolution (`authentic_conversation_id`)
A robust multi-source resolver was introduced to determine the agent's authentic conversation UUID:

```python
def authentic_conversation_id(s, item):
    """Determine the session's authentic conversation ID.
    Checks:
    1. item.get('harness_conversation_id')
    2. s.get('engine_session_id')
    3. s.get('conversation_id')
    4. Disk session binding (transcript.json or session record on disk)
    5. item.get('conversation_id') or item telemetry conversation_id
    """
```
- **Harness Subagents:** Checks `item.get('harness_conversation_id')` (e.g. native Gemini harness subagents registered in `TEAM-REGISTRY.json`).
- **Engine Sessions:** Checks `s.get('engine_session_id')` and `s.get('conversation_id')`.
- **Disk Session Bindings:** Checks `APLEXER_STATE/<session_id>/transcript.json` (`engine_session_id` / `conversation_id`) and disk records (`session.json` / `session_record.json`).
- **Telemetry Fallbacks:** Checks `item.get('conversation_id')` and `item.get('telemetry', {}).get('conversation_id')`.

### 2.2 Strict Conversation Scope Matching (`match_usage_event`)
The matching routine enforces conversation isolation with deterministic reconciliation:

```python
def match_usage_event(events_path, tag, team_id, session_cid=None):
    """Match usage event from usage-events.jsonl.
    - If session_cid is known: require entry.conversation_id == session_cid. Mismatched IDs NEVER bind.
    - If session_cid is None and event has no conversation_id: legacy fallback to (tag, team_id).
    - If multiple events match: deterministically reconcile by timestamp to select latest cumulative record.
    Returns (found_entry, is_fallback).
    """
```

- **Exact Conversation Match:** When `session_cid` is known, an event matches **only** if `entry.get('conversation_id') == session_cid`. Mismatched conversation IDs NEVER bind, even if `tag` and `team_id` are identical.
- **Negative Rejection:** Events with a `conversation_id` will never bind to a session lacking a conversation ID, and events without a `conversation_id` will never bind to a session with a known conversation ID.
- **Truthful Legacy Fallback:** When neither session nor event has a `conversation_id`, the system falls back to `(tag, team_id)` matching, but explicitly labels the observation scope:
  `'Fallback tag-matched owner counters without conversation binding, not independent telemetry verification'`
- **Deterministic Reconciliation:** When multiple snapshots exist for the same conversation, records are sorted by normalized timestamp (`parse_entry_timestamp`) and cumulative total (`total_tokens`) to deterministically select the latest snapshot.

### 2.3 Preserving Distinct Agent Declarations in `_collect()`
Lines 142–148 were updated from a lossy tag-keyed dictionary to an append-only declared list:
- All agents in `teams[...].agents` are preserved in `declared` without tag-collision overwrites.
- Top-level `agents` are appended only if their tag was not already declared in a team, eliminating redundant top-level mirror duplicates (such as `journal-opus-writer-0930`) while preserving independent services and principals.

---

## 3. Unit Test Suite Verification (`tests/test_collect_conversation_scope.py`)

A comprehensive unit test suite was implemented in `tests/test_collect_conversation_scope.py` covering all core behaviors, edge cases, and end-to-end `collect.collect()` integrations:

| Test Identifier | Description | Result |
| :--- | :--- | :--- |
| `test_01_exact_conversation_match` | Session with conversation ID `C1` matches event `C1`, completely ignores event `C2` despite identical `(tag, team_id)`. | **PASS** |
| `test_02_tag_reused_negative_check` | Two distinct conversations `C1` (150 tokens) and `C2` (900 tokens) for tag `worker-alpha` / team `a16`. Verifies `C1` gets 150, `C2` gets 900; neither gets `max(C1, C2)`. | **PASS** |
| `test_02_tag_reused_end_to_end_collect` | End-to-end `collect.collect()` with mocked aplexer and registry. Confirms distinct session attribution and aggregate `known_conversation_tokens` = 1050 (150 + 900). | **PASS** |
| `test_03_legacy_fallback` | Session and event without conversation ID fall back to tag match; events with conversation ID rejected when session has none. | **PASS** |
| `test_03_legacy_fallback_scope_labeling_in_collect` | End-to-end verification of truthful fallback scope string vs exact owner scope string. | **PASS** |
| `test_04_deterministic_reconciliation` | Multiple snapshots for same conversation written out-of-order in JSONL; correctly selects latest snapshot by timestamp. | **PASS** |
| `test_04_deterministic_reconciliation_observed_at_and_numeric_ts` | Reconciliation across `observed_at`, `timestamp`, ISO strings, and epoch numeric timestamps. | **PASS** |
| `test_authentic_conversation_id_sources` | Tests all 5 authentic conversation ID discovery paths (harness, engine_session_id, conversation_id, transcript disk binding, session disk binding, telemetry). | **PASS** |

### Execution Commands & Output:
```bash
$ python3 -m unittest -v tests/test_collect_conversation_scope.py
test_01_exact_conversation_match (tests.test_collect_conversation_scope.TestCollectConversationScope.test_01_exact_conversation_match) ... ok
test_02_tag_reused_end_to_end_collect (tests.test_collect_conversation_scope.TestCollectConversationScope.test_02_tag_reused_end_to_end_collect) ... ok
test_02_tag_reused_negative_check (tests.test_collect_conversation_scope.TestCollectConversationScope.test_02_tag_reused_negative_check) ... ok
test_03_legacy_fallback (tests.test_collect_conversation_scope.TestCollectConversationScope.test_03_legacy_fallback) ... ok
test_03_legacy_fallback_scope_labeling_in_collect (tests.test_collect_conversation_scope.TestCollectConversationScope.test_03_legacy_fallback_scope_labeling_in_collect) ... ok
test_04_deterministic_reconciliation (tests.test_collect_conversation_scope.TestCollectConversationScope.test_04_deterministic_reconciliation) ... ok
test_04_deterministic_reconciliation_observed_at_and_numeric_ts (tests.test_collect_conversation_scope.TestCollectConversationScope.test_04_deterministic_reconciliation_observed_at_and_numeric_ts) ... ok
test_authentic_conversation_id_sources (tests.test_collect_conversation_scope.TestCollectConversationScope.test_authentic_conversation_id_sources) ... ok

----------------------------------------------------------------------
Ran 8 tests in 0.013s

OK
```

### Full Repository Regression Verification:
- `tests/test_*.py`: 59 tests passed (100%).
- `scripts/metrics/test_*.py`: 43 tests passed (100%).
- Total suite: 102 tests passed, 0 failures, 0 regressions.

---

## 4. Invariants, Hygiene & Resource Footprint

1. **`record_usage.py` Untouched:** Zero edits to `scripts/metrics/record_usage.py` (explicit coordination required; untouched in `git status`).
2. **No Daemons or Scrapers:** Zero new daemons, loops, or background scrapers launched.
3. **OpenCode & Codex Baseline Preservation:** All native Codex cumulative, rollout parsing, and OpenCode per-message SQLite/JSON integrations remain completely intact.
4. **Zero Gemini Emission Before Mapping:** In strict compliance with directives, zero derived Gemini counters were emitted to `.local/metrics/usage-events.jsonl`.
5. **Storage & Scratch Containment:**
   - Scratch directory: `.local/scratch/metrics-collect-fix/` (mode `0700`).
   - Scratch usage: 4.0 KB (strictly within the 512 MB boundary).
   - `/tmp` growth: 0 bytes written to `/tmp`.
6. **Publication Guard Verification:**
   The publication guard script was executed against this report deliverable:
   ```bash
   $ python3 research/antigravity/tooling/publication_guard.py research/antigravity/recovery/REPORT-METRICS-COLLECT-CONVERSATION-SCOPE.md
   ```
   Result: **0 violations detected, exit code 0**.

---

*Report submitted by `metrics-collect-worker` (`fd6f993c-e2b0-45d6-8656-247d90e24427`) to `antigravity-head` (`46fdb644-9b58-4e2f-aab3-9be5e1e33337`). Subagent does not commit per invariant; handoff to parent ready.*
