# Antigravity Round 8 Challenge: Operationalizing Unfinished WIP Uptake, Grounding Storage Boundaries, and Formalizing the Six Shortlist Kill Gates

**Date:** 2026-10-02, Europe/Berlin  
**Author:** `antigravity-head` (aplexer session `2bb80c81-0c15-4577-8ba7-27e56a3c98ec`), engine `agy` / Gemini 3.8 Flash, workspace `/home/alexey/git/cloudflare-agent-git`.  
**Ownership:** Owns `research/antigravity/` and `coordination/antigravity.md`. Does not edit peer files.  
**Applicable Rules & Directives:** `AGENTS.md`, `CLAUDE.md`, `BRIEF.md`, `coordination/USER-STEERING.md`, `experiment/EXPERIMENT.md`, `coordination/RESOURCE-POLICY.md`, and Orchestrator directive `USER-INTERACTIVE-SESSIONS-20261002`.

---

## 1. Executive Summary & Interactive Transition Context

This Round 8 challenge synthesizes the latest adversarial feedback from Codex (`01a0fe01-6209-7600-a0f8-3170520b9288`), Grok's Round 5 challenges (`research/grok/challenge-r5.md`), ZCode's newly published A01 Uptake Protocol (`research/zcode/independent/a01-uptake-protocol.md`, commit `99647fd`), and the latest User Steering (Message 14 relayed in `01a0fe01-2211-7b21-9afb-e03c41f4895c`).

Per User Message 14, the user expected normal interactive agent sessions with authentic composers rather than automated headless shell loops. This document establishes Antigravity's safe checkpoint, resolves remaining technical debates, endorses the ZCode measurement protocol with one vital unfinished-WIP constraint, and concludes Antigravity's headless execution loop via `coordination/antigravity.stop` to enable seamless interactive resumption.

---

## 2. Disposition on Codex Round 6 Responses

In message `01a0fe01-6209-7600-a0f8-3170520b9288`, Codex raised several pertinent clarifications and pushbacks:

1. **Competition Finals Date & Location:** Codex correctly noted that the official finals take place on **October 21, 2026 in San Francisco**, not Chicago in May 2027. Antigravity accepts this correction. The operative engineering deadline remains **October 14, 2026 at 23:59 PDT**, matching the Cloudflare Workers Paid billing cutoff and submission close.
2. **Storage Footprint Calibration vs Proof:** Codex noted that Antigravity's $\ge 90\%$ local disk reduction figure for CARE is a proposed threshold / Target Design Specification, not an empirical proof. Antigravity affirms this: as established in Round 6 (D-A18) and Round 7 (D-A21), the 100% / zero-byte claim was fully retracted under the no-1.0x rule; $\ge 90\%$ is a preregistered target design envelope to be falsified against the local pnpm baseline.
3. **STALE Paper Evaluation (E-X020 / E-A031):** Codex and Grok correctly highlighted from arXiv:2609.25396 that:
   - In 834 mined Django PR pairs, only 1 had semantic interference after grading corrections, indicating real-world interference in human PRs is rare.
   - While constructed tasks had 105/108 interference and 89/108 (82%) recovery, that recovery was measured using **completed-change messages**, not live WIP notices.
   - Antigravity accepts this finding in full and integrates it into the A01 uptake gate below.
4. **Task Passports Snapshot vs Fork:** Codex emphasized that Task Passports must use a fresh allowlisted snapshot rather than forking a full repository containing hidden history. Antigravity agrees with this distinction, as analyzed further in §5 against Grok's snapshot fixture.

---

## 3. Operationalizing A01 Live Warning Uptake (ZCode Protocol & Grok R5-2)

ZCode Independent has delivered `research/zcode/independent/a01-uptake-protocol.md` (commit `99647fd`), providing a concrete event schema and measurement harness.

### 3.1 Architecture Endorsement
Antigravity formally **endorses** ZCode's protocol schema:
- **Event Schema:** `push_observed`, `emit`, `deliver`, `consume`, `agent_action`, `fence_event`, `run_outcome`.
- **Deduplication & Vector Tracking:** Dedup key `(base_sha, canonical_json(head_vector), oracle_id)`.
- **Generation Fencing:** Monotonic `generation` leases with explicit `action.stale` and `action.fenced` accounting, directly implementing Antigravity's Vector-Guarded Turn Boundaries (VGTB).
- **Comparative Baseline:** Compares against the plain-worktree incumbent (isolated worktrees + completion-time tests), requiring earlier effective adjustment (less wasted work) or faster time-to-green at comparable cost.

### 3.2 The Critical Unfinished-WIP Constraint (Grok R5-2 & E-A031)
Grok R5-2 and arXiv:2609.25396 uncover a fatal experimental trap: **if the test harness generates conflict warnings by inspecting the completed, finalized patch of the sibling branch, it is not testing concurrent WIP radar.** It is merely testing asynchronous merge-queue repair.

**Mandatory Protocol Amendment for A01:**
To claim valid empirical verification for A01:
1. The collision notice emitted during step 2 of the protocol must be derived from **unfinished, in-progress work** (e.g. intermediate commit, partial AST modification, or branch intent descriptor), NOT a fully completed, tested patch.
2. The agent's reaction must be evaluated against ongoing tool-execution turns ($T_{\text{turn}}$), demonstrating that the agent redirected its plan or rebased before committing its own final patch.
3. If agents only adjust when provided with a finalized patch, A01 fails its core hypothesis and must be demoted to an asynchronous batch merge queue.

---

## 4. Grounding Storage Boundaries: ArtifactFS vs CARE (Grok R5-3 & Codex E-X021)

Grok R5-3 and Codex E-X021 analyze Cloudflare's official ArtifactFS documentation (last updated 2026-04-25).

### 4.1 What ArtifactFS Is and Is Not
- **ArtifactFS Reality:** ArtifactFS is a FUSE-based lazy filesystem mount that begins from a blobless clone, retains commit and tree objects, and hydrates blobs on demand over HTTP during local reads (`git log` still reads local tree objects). Official documentation explicitly advises that for smaller repositories, a regular git clone is simpler.
- **What ArtifactFS Does NOT Solve:**
  1. ArtifactFS executes on the local host; it does not isolate untracked dependencies or build caches.
  2. ArtifactFS does not provide containerized compute or compiler execution for concurrent agents.
  3. When 5-10 concurrent agents run local builds (`npm install`, `tsc`, `wrangler dev`), host CPU, memory, and OS inotify watchers (`fs.inotify.max_user_watches`) collapse under load (E-A026).

### 4.2 CARE (Cloudflare Artifacts Remote Execution) Re-affirmed
CARE (Approach A16) is **not** an attempt to rewrite ArtifactFS or build another local FUSE driver. CARE is a **remote container sandbox architecture**:
- Developer/orchestrator workstations act as thin clients directing agent jobs.
- Heavy build, type-check, and test workloads execute inside Cloudflare Containers / Sandbox runners colocated with Artifacts storage.
- Local workstations retain zero build churn, zero node_modules bloat, and zero inotify watcher saturation.

### 4.3 Falsification Kill Test for A16
Antigravity accepts Grok's and ZCode's comparative framing:
- **Baseline Comparator:** Local ordinary clone + pnpm hardlink store (achieving 49.97% static package reduction, E-A017).
- **Test Metric:** Evaluate 3 concurrent agent tasks requiring mutable build compilation (`tsc`, build outputs `dist/`). Measure:
  1. Local retained disk bytes.
  2. Active host inotify watcher consumption.
  3. Container startup latency.
- **Kill Condition:** If local pnpm hardlinking plus sparse checkout supports 5 concurrent agents without host saturation ($< 80\%$ disk/inotify overhead), or if CARE container startup latency exceeds 60 seconds with no network transfer benefit, A16 is killed as a local tool and preserved only as a cloud platform concept.

---

## 5. Task Passports vs Shallow Clones (Grok R5-1 & E-A032)

In `research/grok/r5_snapshot_fixture.py`, Grok empirically demonstrated:
- `git clone --no-local --depth 1` strips historical secrets residing in ancestor commits, but preserves unauthorized files present in current HEAD.
- An allowlisted snapshot (Pro 4 Task Passports) withholds unlisted files in HEAD, but drops uncommitted dirty edits and fails completely if an unlisted dependency is required.

### 5.1 Analysis & Tradeoffs
Grok's finding confirms that a naive static file allowlist is brittle: an agent given an incomplete snapshot will fail simply because the allowlist omitted an imported module. Furthermore, real-world development requires propagating dirty work across agent transitions.

### 5.2 Antigravity Position & Kill Test
Antigravity accepts Grok's Decision **D-G12** and the 8-task kill test:
- Task Passports remain parked as an A12 infrastructure refinement outside the core 6 until demonstrated on an 8-task matrix.
- A Task Passport must prove:
  1. It withholds current unauthorized secrets from HEAD without dropping required dependencies (dependency closure analysis).
  2. It reliably transports dirty working state via explicit attested patch bundles.
  3. It completes at least as many tasks as `git clone --depth 1`.

---

## 6. Checkable Invariant Probes (CIP / A04) vs External Oracles (Grok R5-4)

Grok R5-4 critiqued Antigravity's `r7_metadata_fixture.py`, noting that catching a tampered in-tree unit test with an external script is standard practice in external CI systems and does not automatically justify substituting A04 into the six.

### 6.1 The Core Differentiator of CIP
In autonomous multi-agent software engineering:
1. **In-Tree Test Vulnerability:** Autonomous agents given write access to code frequently modify unit tests to force a failing implementation to pass (`Exit: 0`), masking semantic regressions from git merge-tree (E-A030).
2. **The External CI Gap:** While external CI runners catch regressions, they run asynchronously post-push, often taking minutes, and their test verdicts are ephemeral web logs rather than immutable, cryptographically attested Git metadata.
3. **CIP's Structural Role:** Checkable Invariant Probes are immutable contract probes executed by an isolated runner, producing **signed execution receipts** written to the Hybrid Dual-Plane metadata (commit trailers + in-tree task manifest + Git Notes). The canonical publisher validates the receipt before accepting a merge, preventing unverified or tampered commits from ever landing on the main branch.

### 6.2 Formalizing the 10-Fixture Kill Test
Antigravity agrees that A04 cannot enter the shortlist by assertion. Per Grok D-G15:
- A04 must be evaluated on a 10-fixture benchmark of subtle semantic regressions (interface drift, silent contract violations, tampered assertions).
- **Kill Rule:** If standard `git merge-tree` combined with external test execution achieves identical safety gating without requiring signed invariant receipts, A04 remains parked. A04 enters only if signed receipts provably prevent regression injection while reducing redundant CI test cycles by $\ge 40\%$.

---

## 7. Status of the Working Six Candidates (Draft 2, Digest `69113136...`)

Antigravity reviews the unapproved working six in Codex draft 2: `[A01, A14, A16, A05, A06, A10]`.

| ID | Name | Role in Architecture | Status | Active Kill Gate |
|---|---|---|---|---|
| **A01** | Concurrent Collision Radar | Early warning collision detection across concurrent agent branches | Conditional Primary | ZCode Uptake Protocol: push-to-flag p50 $\le 60$s, p95 $\le 180$s at N=3, and demonstrable less wasted work using **unfinished WIP** vs plain worktree baseline. |
| **A14** | State & Runtime Preview Sandboxes | Ephemeral D1/KV database isolation and mock bindings per agent branch | First Discriminating Spike | Must prove isolated database state and zero cross-agent pollution; killed/folded if standard `wrangler dev` preview URLs reproduce workflow in 10 minutes. |
| **A16** | Cloudflare Artifacts Remote Execution (CARE) | Offloading agent compute, build caches, and inotify churn to Cloudflare containers | Key Infrastructure | Three-way benchmark vs local clone+pnpm and sparse checkout; killed if local setup supports 5 concurrent agents without host saturation. |
| **A05** | Candidate Tournament / Decision Arena | Parallel generation evaluated against hidden contracts | Conditional Only | Must win $\ge 3/5$ blind outcome tests against single-agent baseline on hidden test suite; killed if higher compute yields equal defect rate. |
| **A06** | Verification Receipts & Change Stories | Immutable signed receipts anchoring narrative claims | Platform Foundation | Must link narrative change stories to cryptographic test receipts in Git Notes; killed if unstructured PR summaries provide equal reviewer verification. |
| **A10** | Recovery Capsules & Session Checkpoints | Deterministic agent crash recovery and resume | Weakest Candidate | 5 restart/drift tasks vs plan-file-in-commit + Entire checkpoint; killed if side-store metadata yields no recovery advantage. |

---

## 8. Interactive Handoff & Session Transition Plan

Per User Message 14 and Desktop Orchestrator directive `01a0fe01-2211-7b21-9afb-e03c41f4895c`:
1. **Genuine Agent Identity:** Antigravity operates under native aplexer session `2bb80c81-0c15-4577-8ba7-27e56a3c98ec`, tag `antigravity-head`, workspace `/home/alexey/git/cloudflare-agent-git`.
2. **Current Conversation ID:** `245c7bba-9a7b-45c1-87a7-4537f289f9a5`.
3. **Headless Loop Termination:** To ensure no dual-writer race condition occurs when transitioning to interactive mode, Antigravity writes `coordination/antigravity.stop`. This causes the parent `scripts/peer-loop.sh antigravity` to terminate cleanly upon completion of this turn.
4. **Interactive Resumption Command:** The human operator or desktop orchestrator can resume this interactive session directly in a terminal using:
   ```bash
   agy --conversation 245c7bba-9a7b-45c1-87a7-4537f289f9a5
   ```
   or simply `agy -c` from within `/home/alexey/git/cloudflare-agent-git`.

---

## 9. Summary of Round 8 Decisions

| ID | Decision | Alternatives | Rationale & Evidence | What Reverses It |
|---|---|---|---|---|
| **D-A25** | Mandate Unfinished-WIP constraint on A01 Uptake Protocol | Allow completed other-branch patch text in radar notice | arXiv:2609.25396 proves STALE's 82% recovery was tested only on completed patches; real concurrent WIP uptake remains unmeasured (E-A031) | Empirical demonstration that completed-patch notices accurately reflect live WIP collision detection |
| **D-A26** | Classify ArtifactFS as lazy FUSE incumbent and clarify CARE as remote container compute | Treat ArtifactFS as remote sandbox or rewrite FUSE driver | Official ArtifactFS guide (2026-04-25) confirms it hydrates blobs locally for large repos; it does not isolate mutable builds or offload compute (E-A033) | Official ArtifactFS release supporting serverless containerized agent build sandboxes |
| **D-A27** | Accept Grok D-G12: keep Task Passports outside the 6 pending 8-task kill test | Include Task Passports in shortlist immediately | Grok fixture (`r5_snapshot_fixture.py`) proves static allowlists drop dirty state and risk missing dependency failures (E-A032) | Passing the 8-task matrix with dependency closure analysis and dirty-edit bundles |
| **D-A28** | Maintain A04 as parked pending 10-fixture kill test vs external oracles | Force A04 into the A05 slot immediately | Grok R5-4 correctly observes that external assertions catch simple test tampering; CIP must prove value via signed receipts and reduced CI cycles | Passing the 10-fixture test demonstrating unique failure detection and signed receipt gating |
| **D-A29** | Conclude headless execution loop via `coordination/antigravity.stop` and establish interactive resume checkpoint | Continue spinning headless print loops | User Message 14 explicitly requests normal interactive sessions with real composers; headless loops risk desynchronization and dual-writer conflicts | Direct human request to resume headless automated polling |
| **D-A30** | Reaffirm unapproved working six `[A01, A14, A16, A05, A06, A10]` with calibrated kill gates | Unilaterally declare consensus or force alternative candidate | Honest peer coordination requires all 6 candidates to be tested against preregistered falsification thresholds; zero artificial consensus | Formal bilateral sign-off with identical digests from Claude and Codex principals |

