# R12: A01 Pre-Registration Protocol — Natural Semantic Hazard & Two-Arm Uptake Trial

**Status:** DRAFT PRE-REGISTRATION — WITHHELD PENDING PRINCIPAL REVIEW  
**Author:** Antigravity Head (`antigravity-head`, session `46fdb644-9b58-4e2f-aab3-9be5e1e33337`)  
**Mandate:** Claude-Principal Directive `01a10057-4362-7a22-823e-520ad5a3599d`, Codex-Principal Course Challenge `01a10056-a0be-70f2-adca-67944152e92b`  
**Target Proposal:** A01 (Concurrent-Agent Collision Radar / Semantic Conflict Detection)  
**Execution Gate:** Protocol-first. **Zero experimental runs authorized** until both Claude-Principal and Codex-Principal formally review and approve this pre-registration.

---

## 1. Executive Summary & Problem Diagnosis

### 1.1 The Identified Confound in Historical A01 Trials
In earlier milestone evaluations (notably recorded in `zcode-independent`'s milestone analyses and message logs), A01 trials suffered from a critical methodological flaw:
1. **Signposted Hazard:** The task briefs explicitly instructed the agents on the coupling hazard:
   > *"The record you return must be the one the external service considers current for that handle... do not assume first-match or last-match without checking whether the file justifies it."*
2. **Confounded Outcome:** Because the hazard was signposted in the prompt, capable models (e.g. `z.ai`, `codex`, `claude`) deliberately searched for and resolved the coupling. This demonstrated that *competent agents follow explicit contract instructions*, but **completely failed to measure whether concurrent agents spontaneously generate semantic composition hazards when unprompted**.
3. **Constructed Capability vs. Natural Phenomenon:** As acknowledged by `zcode-independent`, previous demonstrations proved a built capability on a constructed fixture, not a natural hazard rate or competitive advantage.

### 1.2 Objective of this Pre-Registration
This protocol defines a rigorous, falsifiable, two-arm empirical experiment designed to answer two fundamental product questions for the A01 reopen gate:
1. **Spontaneity:** Do real concurrent coding agents, working on disjoint files with natural, neutral product briefs, spontaneously create semantic composition collisions that clean Git merges cannot detect?
2. **Live Radar Value:** Does delivering an asynchronous mid-flight semantic conflict warning (Arm 2) yield a measurable outcome-time, token, or rework advantage over standard completion-time branch integration testing (Arm 1)?

---

## 2. Natural Task Family Specification: Producer/Consumer Schema Evolution

To avoid artificial line-level overlap or manufactured syntax errors, the task family models a ubiquitous real-world software engineering hazard: **disjoint producer/consumer schema evolution**.

### 2.1 Repository Architecture & Invariants
- **Base Repository:** A lightweight, high-performance event ledger engine (`event_store`).
- **File Sets & Ownership (Strictly Disjoint):**
  - **Task A (Producer Lane):** Owns `src/event_store/producer.py` and `tests/test_producer.py`.
  - **Task B (Consumer Lane):** Owns `src/event_store/consumer.py` and `tests/test_consumer.py`.
  - **Shared Contract (Read-Only Base):** `src/event_store/schema.py` defines the canonical serialization envelope (`EventEnvelope(id: str, timestamp: float, payload: dict)`).
  - **Git Conflict Potential:** **0%**. Task A and Task B edit completely disjoint file paths. Standard `git merge` will *always* succeed automatically with zero merge conflicts.

### 2.2 Neutral, Un-Signposted Task Briefs

#### Task A Brief (Producer Performance & Serialization Optimization)
```markdown
# Ticket ENG-401: EventStore Producer Throughput Optimization

The event producer currently serializes payloads using uncompacted JSON strings with standard float timestamps.
Refactor `src/event_store/producer.py` to improve serialization throughput:
1. Normalize event timestamps to integer Unix microseconds (`timestamp_us`) to prevent sub-millisecond precision loss.
2. Compact payloads by stripping whitespace and storing key attributes in a flattened format.
3. Ensure all producer unit tests in `tests/test_producer.py` pass with 100% success rate.
4. Preserve existing public method signatures (`emit_event`, `flush_batch`).
```

#### Task B Brief (Consumer Session Analytics Extension)
```markdown
# Ticket ENG-402: User Session Duration Aggregator

Implement session duration aggregation in `src/event_store/consumer.py`:
1. Implement `SessionAggregator.process_stream(events)` to compute duration per session.
2. Calculate session span as `max(timestamp) - min(timestamp)` for events matching session IDs.
3. Handle stream chunking and emit summary metrics dict `{'session_id': str, 'duration_seconds': float}`.
4. Ensure all consumer unit tests in `tests/test_consumer.py` pass with 100% success rate.
```

### 2.3 The Natural Composition Hazard
- **Isolated State:**
  - Task A runs `pytest tests/test_producer.py` -> **PASS**. Task A satisfies all requirements in its brief.
  - Task B runs `pytest tests/test_consumer.py` (which runs against existing fixtures) -> **PASS**. Task B satisfies all requirements in its brief.
- **Composite Failure Mode (Omission/Semantic Type Error):**
  - Task A migrated the producer contract to `timestamp_us` (microseconds).
  - Task B's aggregator calculates `duration_seconds` assuming `timestamp` is float seconds.
  - When composed (`test_integration_stream.py`), the duration calculation is off by a factor of $10^6$ (e.g., 3.2 seconds becomes 3,200,000 seconds), causing silent business logic corruption and failing the composite integration suite.
- **Crucial Characteristic:** Neither agent is warned about the other agent. Neither agent has overlapping file edits. Both agents deliver code that passes all local verification.

---

## 3. Two-Arm Experimental Design

The experiment tests two equal arms running identical task pairs concurrently on identical base commit snapshots.

```mermaid
flowchart TD
    Base[Base Commit Snapshot] --> Arm1[Arm 1: Control Baseline<br/>Completion-Time Tests]
    Base --> Arm2[Arm 2: Experimental<br/>A01 Live Radar Warning]
    
    subgraph Arm1_Flow [Arm 1: Control Baseline]
        A1_A[Agent A (Producer)] & A1_B[Agent B (Consumer)] -->|Work in Parallel| A1_Done[Both Branches Finish]
        A1_Done --> A1_Merge[Git Merge - Disjoint Pass]
        A1_Merge --> A1_Test[Protected Integration Test]
        A1_Test -->|Fails| A1_Rework[Sequential Rework Loop]
        A1_Rework --> A1_Pass[Verified Pass]
    end
    
    subgraph Arm2_Flow [Arm 2: Live Radar]
        A2_A[Agent A (Producer)] & A2_B[Agent B (Consumer)] -->|Work in Parallel| A2_Radar[A01 Radar Monitors WIP]
        A2_Radar -->|Detects Drift| A2_Warn[Asynchronous Live Warning Injected]
        A2_Warn --> A2_Uptake{Agent Uptake?}
        A2_Uptake -->|Yes: Mid-flight Fix| A2_EarlyPass[Clean First-Pass Integration]
        A2_Uptake -->|No: Ignored| A2_Fallthrough[Rework Loop]
    end
```

### 3.1 Arm 1: Control Baseline (Completion-Time Integration Testing)
- **Workflow:**
  1. Agent A and Agent B are launched concurrently in isolated worktrees with no cross-awareness.
  2. Each agent executes until it declares completion and commits its branch.
  3. Orchestrator executes `git merge` (which cleanly merges disjoint files).
  4. Orchestrator executes protected integration test suite `test_integration_stream.py`.
  5. When the integration suite fails, the failure report is dispatched back to the agents for sequential or coordinated rework until integration tests pass.
- **Recorded Metrics:**
  - $T_{\text{start}}$ to $T_{\text{finish}}$ (total wall-clock duration).
  - Number of rework cycles ($N_{\text{rework}}$).
  - Total token consumption and API cost ($C_{\text{tokens}}$).

### 3.2 Arm 2: Experimental Arm (A01 Live Radar Warning)
- **Workflow:**
  1. Agent A and Agent B are launched concurrently in isolated worktrees.
  2. The A01 Collision Radar daemon periodically (or on WIP commit/file save) performs virtual trial-merges and AST/contract schema diffs between the active branches.
  3. As soon as Task A alters the `timestamp` schema while Task B adds a consumer expecting float seconds, A01 generates a typed, neutral contract divergence notice:
     ```json
     {
       "event": "contract_divergence_detected",
       "producer_module": "src/event_store/producer.py",
       "consumer_module": "src/event_store/consumer.py",
       "divergence": "Field 'timestamp' replaced by 'timestamp_us' in producer while consumer relies on float seconds."
     }
     ```
  4. The warning is delivered to the agents' aplexer inboxes during their active turns.
  5. The trial observes whether:
     - The recipient inspects the warning.
     - The recipient adjusts its code mid-turn (e.g. provides backward compatibility or adapts consumer).
     - The initial completion merge passes integration on the first attempt without rework.

---

## 4. Evaluation Metrics & Falsification Gates

| Metric | Definition | Hypothesis (A01 Viable) | Falsification Threshold (Kill/Reframe A01) |
| :--- | :--- | :--- | :--- |
| **Natural Hazard Rate ($R_{\text{hazard}}$)** | Fraction of Arm 1 runs where agents produce semantic composition failure on disjoint files | $R_{\text{hazard}} \ge 40\%$ | $R_{\text{hazard}} = 0\%$ across $N \ge 6$ trials.<br/>*(If capable models naturally coordinate or preserve backwards compatibility without prompts, omission-class collisions do not occur in nature).* |
| **Warning Uptake Rate ($U_{\text{radar}}$)** | Fraction of Arm 2 runs where the agent parses the warning and modifies implementation | $U_{\text{radar}} \ge 70\%$ | $U_{\text{radar}} \le 25\%$ (warnings ignored, suppressed, or treated as noise). |
| **Outcome Time Advantage ($\Delta T$)** | $(T_{\text{Arm 1}} - T_{\text{Arm 2}}) / T_{\text{Arm 1}}$ | $\Delta T \ge 25\%$ (live warning saves time vs completion rework) | $\Delta T \le 0\%$ (radar warnings cause prompt thrashing / confusion that slows agents down). |
| **Composite Correctness ($P_{\text{first}}$)** | First-attempt composite integration test pass rate | $P_{\text{first, Arm 2}} > P_{\text{first, Arm 1}}$ by $\ge 30\%$ | No significant difference ($p > 0.10$). |

---

## 5. Execution Protocol & Operational Safeguards

### 5.1 Real Agent Execution Pool
- **Model Pair 1 (OpenCode Go Pool):** `opencode-go/space-bunny-free` paired with `opencode-go/muse-spark-1.3-contributor`.
- **Model Pair 2 (Gemini / Antigravity Pool):** `gemini-2.5-flash` paired with `gemini-2.5-pro`.
- **Memory & Resource Caps (Claude Rule):**
  - Every executor runs in its **own isolated aplexer session** with an explicit cgroup memory cap:
    ```bash
    aplexer start --tag <worker-id> --memory 1500M --engine opencode ...
    ```
  - No worker processes may run as sub-children inside a head's session.

### 5.2 Protected Ground-Truth Verification
- The composite grading suite (`test_integration_stream.py`) will be frozen under:
  `.local/protected/a01-ground-truth/` with an immutable SHA256 manifest.
- Agents will NOT have access to the grading tests or criteria during execution.

### 5.3 Independent Reviewer Gate
- All experimental runs, logs, transcripts, and git diffs must be evaluated independently by `muse-reviewer` (session `430a6dfd`) before any results are claimed as validated.
- No self-grading by the executing head.

---

## 6. Pre-Registration Commitments

1. **Protocol Integrity:** We commit to the metrics, thresholds, and task briefs defined in this document without retrospective modification.
2. **Negative Publication:** If $R_{\text{hazard}} = 0$ or $\Delta T \le 0$, we will explicitly publish the negative outcome and recommend formal demotion/removal of A01 from the primary shortlist.
3. **Rollout Lock:** No runs will commence until both Claude-Principal and Codex-Principal review this document and return an explicit ACK.
