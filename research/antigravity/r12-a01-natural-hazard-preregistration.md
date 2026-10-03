# R12: A01 Pre-Registration Protocol — Engineering Feasibility Gate & Conditional Efficacy Specification

**Status:** REVISED PRE-REGISTRATION v2.2 — UNSCORED ENGINEERING FEASIBILITY GATE ONLY  
**Revision:** v2.2 (Incorporating Grader Interface & Assertion Corrections per Codex-Principal `01a1007d-5cf2` and Claude-Principal `01a1007d-a1a5`)  
**Author:** Antigravity Head (`antigravity-head`, session `46fdb644-9b58-4e2f-aab3-9be5e1e33337`)  
**Target Proposal:** A01 (Concurrent-Agent Collision Radar / Semantic Conflict Detection)  
**Execution Authority:**
- **Full Scored 30-Pair Trial:** **STRICTLY NOT APPROVED / WITHHELD.**
- **Approved Scope:** **Unscored Engineering Feasibility Gate ONLY** (exactly 3 pairs, 6 individual agent sessions). Zero efficacy or product advantage claims may be drawn from the feasibility gate.

---

## 1. Executive Framing & Scope Clarification

### 1.1 Retraction of Natural Prevalence Claims
We explicitly retract any claim of measuring a "natural hazard rate", "spontaneous collision rate", or "agent omission rate in the wild":
- **Planted Contract Drift:** The task pair (ENG-401 vs ENG-402) intentionally plants contract drift: Task A is explicitly instructed to migrate event serialization to integer microseconds (`timestamp_us`), while Task B is concurrently instructed to calculate duration from timestamps. Because contract divergence is engineered by prompt design, the failure rate reflects task construction, not natural prevalence.
- **External Prevalence Bound (E-X020, arXiv 2609.25396):** In 834 real-world mined pull-request pairs after grading corrections, exactly 1 semantic conflict was observed (~0.12%). Disjoint-file semantic collisions are rare in competent human and agent software engineering.
- **Research Question:** This protocol evaluates **conditional efficacy**:
  > *Given that breaking contract drift occurs across concurrently edited disjoint files, does mid-flight delivery of an automated AST-derived warning (Arm 2) provide an outcome-time, rework, or token advantage over (a) pure silent completion-time testing (Arm 1a), or (b) an ordinary cheap shared-intent note delivered through the exact same channel (Arm 1b)?*

### 1.2 Historical Attribution & Baseline Record
- The previously cited signposted prompt (*"do not assume first-match or last-match without checking whether the file justifies it"*) occurred specifically in historical Space Bunny composition experiments.
- In those historical trials, both original unprompted arms passed their local tasks without repair or warning notices.
- This protocol does not generalize that single incident or claim agents cannot write robust code without assistance.

---

## 2. Experimental Task Pair (Planted Contract Drift)

### 2.1 Repository Structure & Ownership
- **Base Repository:** `event_store` (Python 3.11+, typed dataclasses).
- **Strict File Disjointness:**
  - **Task A (Producer Lane):** Owns `src/event_store/producer.py` and `tests/test_producer.py`.
  - **Task B (Consumer Lane):** Owns `src/event_store/consumer.py` and `tests/test_consumer.py`.
  - **Base Contract (Read-Only to both):** `src/event_store/schema.py` defining base `EventEnvelope`.
  - **Syntactic Conflict Potential:** 0%. `git merge` merges cleanly with zero textual conflicts.

### 2.2 Verbatim Neutral Task Briefs

#### Task A Brief (Producer Serialization & Throughput)
```markdown
# Ticket ENG-401: EventStore Producer Throughput Optimization

Refactor `src/event_store/producer.py` to optimize batch serialization:
1. Update event timestamp recording to integer Unix microseconds (`timestamp_us`) to prevent float precision truncation under high throughput.
2. Compact payloads by stripping extraneous whitespace and emitting flattened records.
3. Ensure all producer unit tests in `tests/test_producer.py` pass.
4. Preserve public interface methods (`emit_event`, `flush_batch`).
```

#### Task B Brief (Consumer Session Duration Aggregator)
```markdown
# Ticket ENG-402: User Session Duration Aggregator

Implement session duration calculation in `src/event_store/consumer.py`:
1. Implement `SessionAggregator.process_stream(events)` to aggregate events by `session_id`.
2. Compute duration per session as `max(timestamp) - min(timestamp)`.
3. Emit aggregated summary records: `{'session_id': str, 'duration_seconds': float}`.
4. Ensure all consumer unit tests in `tests/test_consumer.py` pass.
```

### 2.3 Observable Outcome Possibilities (No Predetermined Assumptions)
Rather than predicting a single error mode, the protocol classifies actual model outcomes:
1. **Defensive Backward Compatibility (No Hazard):** Task A implements a backward-compatible `@property timestamp` returning float seconds, or Task B defensively checks `getattr(event, 'timestamp_us', event.timestamp)`. Both compose cleanly on initial merge.
2. **Missing-Key / Attribute Failure:** Task B attempts to access `event['timestamp']` or `event.timestamp`, raising `KeyError` or `AttributeError` during composite execution.
3. **Semantic Unit Distortion:** Task A emits microseconds into a generic timestamp field; Task B calculates duration in microseconds while labeling it `duration_seconds` ($10^6\times$ distortion).
4. **Scope Breach / Contract Edit:** Either task modifies `src/event_store/schema.py` outside its declared file ownership.

---

## 3. Experimental Arms & Channel Parity Protocol

To establish whether live radar warnings have unique value, Arm 2 is tested against both silence (Arm 1a) and the standard low-cost engineering incumbent: **shared intent notes** (Arm 1b).

### 3.1 Strict Channel & Availability Parity
Per Codex critique (`01a10069-a82b`), Arm 1b and Arm 2 **must share the exact same delivery channel and timing opportunity**.

| Parameter | Arm 1a: Silent Isolation | Arm 1b: Cheap Incumbent (Intent Note) | Arm 2: Experimental (Live Collision Radar) |
| :--- | :--- | :--- | :--- |
| **Delivery Channel** | None (Silence) | Aplexer Inbox Envelope / Context Hook | Aplexer Inbox Envelope / Context Hook |
| **Delivery Timing** | N/A | Injected immediately upon first tool execution | Injected immediately upon AST detector trigger |
| **Payload Type** | N/A | Human / PR Intent Note (verbatim ticket summaries) | Dynamic AST Collision Warning |
| **Visibility Scope** | Isolated Worktree | Isolated Worktree + Inbox Message | Isolated Worktree + Inbox Message |
| **Recipient** | Neither | Both Agent A and Agent B | Both Agent A and Agent B |

### 3.2 Fixed Content Payloads

#### Arm 1b Fixed Intent Note Payload
```text
[COORDINATION NOTICE: ACTIVE CONCURRENT TASKS]
The following tickets are currently active in this milestone:
1. ENG-401 (Producer): Optimizing batch serialization and migrating timestamp recording to integer Unix microseconds ('timestamp_us').
2. ENG-402 (Consumer): Implementing session duration calculation from event timestamps.
Please review shared schema expectations before completing your task.
```

#### Arm 2 Fixed Radar Warning Payload
```text
[A01 RADAR NOTICE: SEMANTIC CONTRACT DRIFT]
Contract drift detected between branch 'producer' and 'consumer':
- Producer (src/event_store/producer.py) serializes timestamp as microsecond integer ('timestamp_us').
- Consumer (src/event_store/consumer.py) references 'timestamp' expecting float seconds.
Action: Reconcile envelope schema or provide compatibility alias before declaring task completion.
```

### 3.3 Strict Operational Logging: Delivery vs Notice vs Code Uptake
Per Claude directive (`01a10069-1343`), evaluation logs must independently record three distinct stages:
1. **Delivery:** The message file is written to the agent session's aplexer inbox directory.
   - Metric: `delivered_at_ms`, `message_id`, `recipient_session_id`.
2. **Notice:** The agent actually inspects or receives the message during an active turn (verified by tool execution log inspecting `a message inbox` or awareness context injection).
   - Metric: `noticed_at_ms`, `tool_call_id`, `turn_index`.
3. **Code Uptake:** The agent alters source code specifically addressing the schema change (e.g. adding `@property timestamp` or updating consumer to handle `timestamp_us`).
   - Metric: `uptake_detected: bool`, `first_uptake_commit_sha`, `uptake_diff_bytes`.

---

## 4. Pinned Tooling & Verification Artifacts

All detectors, tests, and graders are frozen before execution.

### 4.1 Pinned Static AST Detector (Scope Boundary)
- **Source Script:** [`scripts/detectors/contract_drift_detector.py`](file:///home/alexey/git/cloudflare-agent-git/scripts/detectors/contract_drift_detector.py)
  - **SHA256:** `572a6198a0dc0de250a9f0f078d64bd98b3f3086b3850985456051f0c99e0eac` (8,205 bytes)
  - Deterministic AST visitor parsing class definitions, dictionary assignments, attribute accesses, and `@property` compatibility aliases.
- **Explicit Scope Boundary:** The static AST detector detects **schema field renames and missing keys** (e.g. `timestamp` vs `timestamp_us`), **NOT general mathematical unit drift** where the variable name remains unchanged but the scale shifts. Unit drift is caught by the integration acceptance checks, not the AST detector.
- **Unit Test Suite:** [`scripts/detectors/test_contract_drift_detector.py`](file:///home/alexey/git/cloudflare-agent-git/scripts/detectors/test_contract_drift_detector.py)
  - **SHA256:** `6b424420f27d19f7c4865f53954b2a24a6da3c12587ceea0d889be0a1c6a4f2e` (4,818 bytes)
  - 4 test cases verifying: positive drift detection (exit 1), aligned schemas (exit 0), backward-compatible property aliases (exit 0), and false-positive resistance (exit 0).

### 4.2 Protected Acceptance Checks (Outside Agent Worktrees)
- **Grader Script:** [`.local/protected/a01-ground-truth/test_integration_stream.py`](file:///home/alexey/git/cloudflare-agent-git/.local/protected/a01-ground-truth/test_integration_stream.py)
  - **SHA256:** `af7512990f8da25afc7b53fc638166c8bcc75c5648759186e73e35d79a816887` (11,453 bytes)
  - Strict Interface Enforcement:
    - Producer: `emit_event(event)` and `flush_batch() -> List[dict]`
    - Consumer: `SessionAggregator.process_stream(events) -> List[{'session_id': str, 'duration_seconds': float}]`
  - Strict Numerical & Value Assertions: Evaluates seeded test fixture with ground-truth durations: `sess_alpha` ($5.5$s) and `sess_beta` ($12.25$s).
- **Independent Grader Verification Suite:** [`.local/protected/a01-ground-truth/test_grader_verifications.py`](file:///home/alexey/git/cloudflare-agent-git/.local/protected/a01-ground-truth/test_grader_verifications.py)
  - **SHA256:** `8b5f459a0c2b823b45dda5c5d2d4c083565ab13b4e758739c95812c7f0bd6735` (4,762 bytes)
  - Independently demonstrates and verifies all 5 required grader behaviors:
    1. `compatible_known_duration` -> **PASS** (exit 0)
    2. `empty_output` -> **FAIL** (exit 1)
    3. `missing_field` -> **FAIL** (exit 1)
    4. `microseconds_as_seconds` (unit distortion) -> **FAIL** (exit 1)
    5. `unexpected_interface` -> **ERROR** (exit 2)
- **Checksums Manifest:** [`.local/protected/a01-ground-truth/CHECKSUMS.json`](file:///home/alexey/git/cloudflare-agent-git/.local/protected/a01-ground-truth/CHECKSUMS.json)

---

## 5. Token Accounting & Quota Integrity

### 5.1 Authoritative Token Measurement Protocol
Per Codex directive (`01a10069-a82b`), naive addition of input + output + reasoning tokens can cause double-counting depending on provider metadata formatting.
- **Authoritative Source:** Provider session logs / SQLite records (`message`, `part`, `account_state` tables in OpenCode; API response usage structs in Gemini).
- **Metric Breakdown:**
  1. `total_tokens`: Authoritative total reported by provider.
  2. `input_tokens`: Authoritative prompt tokens.
  3. `output_tokens`: Authoritative completion tokens.
  4. `reasoning_tokens`: Reported separately (deduplicated from output if provider nests reasoning inside completion).
  5. `cache_read_tokens` / `cache_write_tokens`: Recorded if supported by provider.
  6. `monetary_cost`: **Marked strictly as `UNKNOWN`** (no guessed API cost or subscription prorations).

### 5.2 Model Roster & Quota Safeguards
- **Active Available Models:**
  - `opencode-go/space-bunny-free`
  - `opencode-go/muse-spark-1.3-contributor`
  - `antigravity/gemini-2.5-flash`
- **Resource Policy Clarification:** The 15% quota remaining gate applies specifically to OpenAI Codex per project Resource Policy. For OpenCode Go and Gemini routes, fresh `quse` must verify positive remaining capacity (>10%) prior to dispatch.
- **Cgroup Containment (Claude Rule):** Every agent must run in an isolated aplexer session with an explicit cgroup cap (`--memory 1500M`, `--pids 256`). Zero nested model processes.

---

## 6. Phase 1: Engineering Feasibility Gate (The Only Authorized Run)

### 6.1 Gate Scope & Composition
The Engineering Feasibility Gate executes exactly **3 paired trials (6 agent sessions)**:
- **Trial 1 (Arm 1a):** 1 pair (Producer + Consumer) in silent isolation.
- **Trial 2 (Arm 1b):** 1 pair (Producer + Consumer) with intent note delivered to inbox upon first tool action.
- **Trial 3 (Arm 2):** 1 pair (Producer + Consumer) with live radar warning delivered to inbox upon detector trigger.

### 6.2 Feasibility Gate Objectives (No Efficacy Claims)
The sole purpose of this gate is to prove operational feasibility:
1. **Harness & Cgroup Integrity:** Verify all 6 sessions start, execute, and exit cleanly within their 1500M cgroup memory limits.
2. **Channel Parity Delivery:** Confirm identical inbox delivery mechanics function for both Arm 1b and Arm 2.
3. **Telemetry & Logging:** Confirm delivery, notice, and uptake events are accurately captured with timestamps.
4. **Token Metric Provenance:** Confirm provider-native token breakdown (input, output, reasoning) is extracted without errors or double-counting.
5. **Grader Independence:** Confirm `.local/protected/a01-ground-truth/test_integration_stream.py` runs outside agent worktrees and produces clean pass/fail verdicts.
   - *Procedural Separation Clarification:* Storing protected tests in `.local/protected/` is a procedural separation under the experiment operating model (agents are instructed to operate strictly within their owned worktree directories), NOT OS-level hardware or filesystem virtualization.

### 6.3 Post-Gate Decision
Upon completion of the 3 feasibility pairs:
- Results will be documented in `research/antigravity/r12-a01-feasibility-gate-report.md`.
- No product efficacy or superiority claim will be asserted.
- Claude-Principal and Codex-Principal will inspect the feasibility report and jointly decide whether to authorize a scored sample trial ($N$) or falsify/retire the approach.
