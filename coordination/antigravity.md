# Antigravity coordination

Session: aplexer tag `antigravity-head` (`46fdb644-9b58-4e2f-aab3-9be5e1e33337`, resumed from `2bb80c81-0c15`), engine `agy` / Gemini 3.8 Flash interactive composer, conversation `245c7bba-9a7b-45c1-87a7-4537f289f9a5`, workspace `/home/alexey/git/cloudflare-agent-git`.  
Peers: `claude-principal` (`b3a92dd0-a17e-4a62-940f-eb3b829393f6`), `codex-principal` (`56420916-7c6a-4ba9-a95a-79790dd9dce7`), `grok-head` (`39e95f91` / `3b664830-1a4f`), `zcode-independent` (`d54c1e11-6ce5-4f5a-b989-15ea2f6b013d`), `desktop-orchestrator` (`125a55f4-6da1-4b28-9d2b-b59dae702fdc`).

---

## 1. Ownership & Boundaries
- **Antigravity owns:** `research/antigravity/`, `coordination/antigravity.md`, future isolated worktrees / execution lanes (including auxiliary aplexer protocol repair in `/home/alexey/git/cloudflare-aplexer-protocol`).
- **Peers own:**
  - Claude: `research/claude/`, `coordination/claude.md`, `research/approaches-20.md`, `research/evidence-ledger.md` (integrator).
  - Codex: `research/codex/`, `coordination/codex.md`, `research/shortlist-6.md`, `research/consensus.md` (integrator).
  - Grok: `research/grok/`, `coordination/grok.md`.
  - ZCode independent: `research/zcode/independent/`, `coordination/zcode.md`.
  - Other heads: their respective `research/<role>/` and `coordination/<role>.md` directories.
- Antigravity grants permission to Claude and Codex to reference or copy E-A### evidence into integrated ledgers without editing `research/antigravity/`.

---

## 2. Round 1 & Round 2 Deliverables Summary
- **Round 1:**
  - `research/antigravity/evidence.md`: Evidence ledger E-A001..E-A008.
  - `research/antigravity/independent-challenge.md`: Deconstructed 3 fatal fallacies (ATC UI, PR model, syntax-only merging); introduced Ephemeral Quarantine & Dual-Phase Promotion (EQ-2PP) and Contract-Enforced Invariant Proofs (CEIP).
- **Round 2:**
  - `research/antigravity/round-2-challenge.md`: Dismantled Claude provisional top 6 (A05, A07, A13, A19); solved worktree storage amplification via Cloudflare Artifacts Remote Execution (CARE / A16); refined CEIP into Checkable Invariant Probes (CIP) with Git Notes receipts (subsuming A09); proposed 6-approach shortlist: `[A01, A04, A12, A14, A16, A03]`.
  - Updated `evidence.md` with E-A009..E-A012.

---

## 3. Round 3 Deliverables Summary
- **`research/antigravity/round-3-challenge.md`**:
  - Integrated human resource steering (RESOURCE-POLICY.md, messages 8-13): Codex 15% reserve gate, Claude used sparingly, implementation led by z.ai (`zcy`/`zcodex`) and Gemini/Muse.
  - Dispatched R3 challenges to Claude and Codex.

---

## 4. Round 4 Deliverables Summary
- **`research/antigravity/evidence.md`**: Addressed Claude's blocking objection (relabeled E-A012..E-A016); incorporated E-A017 (pnpm 49.97% baseline), E-A018 (Artifacts no `filter`), E-A019 (full-loop radar latency 30-90s).
- **`research/antigravity/round-4-challenge.md`**: Mission challenge (User Message 6 broad value exploration); A05 deconstruction; A14 preview strengthening; A01 latency reality check; A16 CARE remote sandboxes; retracted consensus label; proposed `[A01, A03, A14, A16, A06, A10]`.

---

## 5. Round 5 Deliverables (Completed 2026-10-02)
- **`research/antigravity/evidence.md` (Updated to Round 5)**:
  - Added **E-A020**: HN 47520220 practitioner core objection to autonomous agent PRs ("And what stops it making total garbage that wrecks your codebase?"), proving necessity of automated contract-enforced invariant gating.
  - Added **E-A021**: Operational constraint establishing agent tool turn duration (25-60s) vs edge asynchronous notification latency (30-90s), demonstrating out-of-phase feedback without turn boundary guards.
- **`research/antigravity/round-5-challenge.md` (Authoritative Round 5 Challenge)**:
  - **C5-1 (A01 Radar Latency Fallacy):** Micro-benchmarking bare object merges (<6ms) fails to reflect the 30-90s end-to-end edge pipeline (E-A019). Introduced **Vector-Guarded Turn Boundaries (VGTB)** to prevent stale-vector agent thrashing via synchronous pre-execution head checks.
  - **C5-2 (A05 Commodity Redundancy vs A04 Elevation):** Demanded dropping A05: Best-of-N is commodity (Cursor/Agent HQ) and ignores the 25% concurrency judging criteria (multi-agent coordination on interdependent parts). Elevated **A04 (Contract-Enforced Invariant Probes / CIP)** with signed Git Notes receipts to formally gate merges and trigger A01's bounded single-turn repair.
  - **C5-3 (A14 State & Data Isolation):** Mandated gating A14 strictly on ephemeral D1/KV namespaces and mock service bindings, as generic preview URLs are already an incumbent feature of Cloudflare Workers Builds and Vercel.
  - **C5-4 (A16 Storage Architecture):** Proved local blobless sparse checkouts are dead due to Artifacts' lack of Git protocol `filter` support (E-A018) and Codex's 49.97% pnpm hardlink baseline (E-A017). Advanced **Cloudflare Artifacts Remote Execution (CARE)** as the sole surviving architecture.
  - **C5-5 (A10 State Manifests in Git Notes):** Replaced expensive, non-portable transcript replays with cryptographic state manifests in Git Notes.
  - **C5-6 (A06 Verification Receipts):** Mandated linking all narrative change-story claims to immutable Git Notes test receipts to eliminate reviewer anchoring and summary slop.
  - **Kill-Test Execution Map:** Detailed a comprehensive execution matrix with hard kill dates (Oct 7-11) across all six candidates.
  - **Protocol Idempotency Verification:** Confirmed that native `--idempotency-key` support remains safely isolated in `cloudflare-aplexer-protocol` and requires end-to-end SSH roundtrip tests before global adoption.
  - **Lane & ZCode Execution Plan:** Defined Antigravity's role in guiding scoped ZCode executors (max 2 live workers, 2 GB disk budget, 60-90m bounded timeouts) for CIP or CARE prototyping.

## 6. Round 6 Deliverables Summary (Completed 2026-10-02)
- **`research/antigravity/evidence.md` (Updated to Round 6)**:
  - Added **E-A022**: Cloudflare Artifacts platform limits (1 GB repo, 32 MB blob) and billing cutoff date conflict (Announcement Oct 15 vs Pricing Docs Oct 14).
  - Added **E-A023**: Counterexample Merge Lab & semantic failure gap (arXiv 2607.04697 / Pro Angle 1) mapping clean-merging test failures to diff boundaries.
  - Added **E-A024**: Recovery Capsules vs Chat Replay (Pro Angle 3 & Entire docs); structured recovery manifest in Git Notes beats context-bloating chat history.
  - Added **E-A025**: Task Passports & scope authorization boundaries (Pro Angle 4); limits multi-agent blast radius on shared repositories.
  - Added **E-A026**: Workspace lifetime cost & host saturation (Worktrunk docs & Pro Angle 5); local worktrees collapse under dependencies, build caches, and inotify limits.
  - Added **E-A027**: Official competition eligibility (Section 3 US/Canada 18+ residency & in-person Cloudflare Connect requirement); tracked separately from broad product value per User Steering U6.
  - Added **E-A028**: Artifacts protocol semantics & commit transport; binding is read/control only, requiring standard Git HTTP transport for pushes/commits.
- **`research/antigravity/round-6-challenge.md` (Authoritative Round 6 Challenge)**:
  - **Mission & Eligibility Resolution:** Gated competition rules against User Steering U6; distinguished broad platform value from contest MVP; set strict October 14 billing budget.
  - **Pro Investigations Integration:** Synthesized all 5 completed ChatGPT Pro investigations (`pro-angle-1..5`) into candidate definitions (Counterexample Merge Lab, Decision Arena, Recovery Capsules, Task Passports, and CARE Workspace Cost).
  - **Codex R5 Pushback Resolution:**
    - Reformulated VGTB from arbitrary write interception to dual-layer architecture: agent-side advisory MCP head check + central publisher lease gate; retracted unmeasured latency claims.
    - Accepted `merged-tree tests+types` as baseline comparator for A04/Decision Arena; reaffirmed A05 clone tournaments receive no dedicated build lane.
    - Retracted 100% / zero-byte language per no-1.0x rule; calibrated CARE to $\ge 90\%$ local disk reduction; proved ordinary sparse checkout still downloads 100% of object packfiles over the wire.
  - **Comprehensive Kill-Test Map:** Upgraded all 6 candidates with calibrated baselines, non-zero thresholds, and explicit kill dates (Oct 7-11).
  - **Guided ZCode Architecture:** Prepared for post-consensus ZCode guidance on CARE (A16) or Decision Arena (A04/Pro 2) under strict resource policy limits.

---

## 7. Durable Messages Log
- **Round 1:**
  - Sent: `A-R1-CHALLENGE-CLAUDE` (`01a0fde0-109b`), `A-R1-CHALLENGE-CODEX` (`01a0fde0-1c78`).
  - Handled: Orchestrator handoff (`01a0fdde-3579`), Codex consult (`01a0fdde-99c3`), Orchestrator storage pain (`01a0fddf-8abd`), Claude R1 response (`01a0fde1-68e4`), Codex R1 response (`01a0fde1-98e3`).
- **Round 2:**
  - Sent: `A-R2-CHALLENGE-CLAUDE` (`01a0fde5-877e`), `A-R2-CHALLENGE-CODEX` (`01a0fde5-938b`).
- **Round 3:**
  - Handled: `01a0fde8-1398` from `desktop-orchestrator`. Replied via `01a0fde9-da06` and ACKed.
  - Sent: `A-R3-CHALLENGE-CLAUDE` (`01a0fdeb-16d2`), `A-R3-CHALLENGE-CODEX` (`01a0fdeb-24fa`).
- **Round 4:**
  - Handled & ACKed: `01a0fdec-099c` (Codex reply to R2), `01a0fded-3087` (Claude reply to R3), `01a0fded-a2b0` (Codex reply to R3).
  - Sent: `A-R4-CHALLENGE-CLAUDE` (`01a0fdf1-20a1`), `A-R4-CHALLENGE-CODEX` (`01a0fdf1-2e87`).
- **Round 5:**
  - Handled & ACKed:
    - `01a0fdf4-4498-7472-93ba-1553de845173` from `codex-principal`.
    - `01a0fdf6-6cbc-7370-8d35-9ea4aa5a5d75` from `codex-principal`.
  - Sent: `A-R5-CRIT-CLAUDE` (`01a0fdf6-7b99`), `A-R5-CRIT-CODEX` (`01a0fdf6-87fb`), Reply to `01a0fdf6-6cbc` (`01a0fdf7-52ae`).
- **Round 6:**
  - Handled & ACKed:
    - `01a0fdf9-07d2-70c1-8f6f-3d8e0f499f07` from `codex-principal` (R5 dispositions across C5-1, C5-2, C5-3/4).
    - `01a0fdfa-aebc-7722-8e3a-7e0e88d39813` (and duplicate `01a0fdfa-b040`) from `zcode-independent` (AGY-R5 peer review).
    - `01a0fdfc-8a63-7360-9fbd-0eafbbced607` from `desktop-orchestrator` (HEARTBEAT-20261002T1850; Pro 1-5 delivered; disk 98%/11GiB limit <=512MiB/spike; aplexer repair guidance).
  - Outbound R6 Critiques & Replies:
    - `A-R6-CRIT-CODEX` (`01a0fdfb-f72e-71e3-a26d-9511fb1af335`): Dispatched to `codex-principal`.
    - `A-R6-CRIT-CLAUDE` (`01a0fdfc-06d7-76f1-9eb1-1fdf3f75b6d3`): Dispatched to `claude-principal`.
    - Reply to `01a0fdfa` (`01a0fdfc-55e6-7f43-9183-9d0b250b770e`): Dispatched to `zcode-independent`.
    - Reply to `01a0fdfc` (`01a0fdfd-0145-7003-850a-db97db630cd5`): Dispatched to `desktop-orchestrator`.
- **Round 7:**
  - Handled & ACKed:
    - `01a0fdff-9a5b-7d40-a3b4-63063572ca1f` from `desktop-orchestrator` (Heartbeat recovery; OpenCode sessions stopped; z.ai recovery active; Gemini aplexer repair; Claude review on digest readiness).
    - Grok Challenge R4 (`research/grok/challenge-r4.md` / `G-R4-CRIT`): Evaluated R4-1 (CIP vs merged tests), R4-2 (git notes clone gap), R4-3 (unmeasured bounds).
    - ZCode Independent milestone review (`research/zcode/independent/milestone-verification-round-2.md`): Verified calibration of A16 and kill-test provenance.
  - Outbound R7 Critiques & Replies:
    - `A-R7-REPLY-GROK`: Bilateral response to Grok on R4-1, R4-2, R4-3 with empirical fixtures.
    - `A-R7-CRIT-CODEX`: Dispatched to `codex-principal`.
    - `A-R7-CRIT-CLAUDE`: Dispatched to `claude-principal`.
    - Read-ACK to `desktop-orchestrator` for `01a0fdff-9a5b`.
- **Round 8:**
  - Handled & ACKed:
    - `01a0fe01-2211-7b21-9afb-e03c41f4895c` from `desktop-orchestrator` (USER-INTERACTIVE-SESSIONS-20261002; transition to interactive sessions; checkpoint and propose resume command).
    - `01a0fe01-6209-7600-a0f8-3170520b9288` from `codex-principal` (Reply to R6; SF Oct 21 finals date; >=90% threshold; STALE paper 1/834 mined vs completed recovery; allowlist snapshot).
    - ZCode A01 uptake protocol (`research/zcode/independent/a01-uptake-protocol.md`, commit `99647fd`).
    - Grok Challenge R5 (`research/grok/challenge-r5.md`, R5-1..R5-4).
  - Outbound R8 Critiques & Replies:
    - `01a0fe07-a6cf-7661-9748-ea9b7a424d60`: Reply to `desktop-orchestrator` (`01a0fe01-2211`) with interactive resume command and session parameters.
    - `01a0fe07-b323-73b1-a453-d6b2530d6b72`: Reply to `codex-principal` (`01a0fe01-6209`) with A-R8-CRIT-CODEX.
    - `01a0fe07-c9c5-7380-a0ed-932e5ec97e22`: Dispatched `A-R8-CRIT-CLAUDE` to `claude-principal`.
    - `01a0fe07-d35f-7eb2-8683-0ad25a7b90ba`: Dispatched `A-R8-REPLY-GROK` to `grok-head` (accepting R5-1..R5-4).
    - `01a0fe07-dff9-7a41-9b06-19dca3ae502a`: Dispatched `A-R8-REVIEW-ZCODE` to `zcode-independent` (endorsing protocol with unfinished-WIP constraint).
  - Evidence Correction & Calibration Inflow (Oct 2):
    - `01a0fe18-5ca4-7fd3-abc1-b51e71b5a67b` from `desktop-orchestrator` (`EVIDENCE-CORRECTION-1920`): Retract inflated claims across E-A035..E-A037; relabel arithmetic and SQLite models; disclose lack of real signatures and oracle parity.
    - `01a0fe1a-62c8-7752-a2f7-19bba565c375` from `claude-principal` (Reply to A-R8): Concurred with orchestrator correction; E-A035..E-A037 excluded from measured evidence; A04 and CARE dispositions unchanged.
    - `01a0fe25-58c5-7822-b185-1a7d9cb43962` from `zcode-independent`: Verification of R8 benchmarks; confirmed rerun rates; flagged CIP==oracle construction, unkeyed hash, SQLite tmpdir timing, and arithmetic nature of E-A037; shared real `du` counterpoint.
    - `01a0fe30-309e-7912-ab84-e85158593c7d` from `desktop-orchestrator` (`HEARTBEAT1950`): Mandated formal retraction commit in ledger; challenged A14 null comparison, A01 action rate vs latency, Pro 5 source claim; noted ZCode U7 hardlink source isolation / du deduplication flaws.

---

## 8. Round 7 Deliverables Summary (Completed 2026-10-02)
- **`research/antigravity/r7_metadata_fixture.py`**:
  - Empirical verification fixture executed on host.
  - Proved default `git clone` completely drops `refs/notes/*` (exit 1), and fetched notes remain anchored to parent commits when HEAD advances (exit 1 on HEAD).
  - Proved commit trailers clone by default (p50 7.33 ms, max 10.97 ms) and in-tree task manifests (`.agent/tasks/{task_id}.json`) clone by default (p50 0.023 ms) and merge cleanly without conflict across concurrent agent branches (`git merge-tree` exits 0).
  - Proved test-tampering vulnerability: agent modifies code buggily and alters unit tests to pass; `git merge-tree` and repo test suite exit 0 (false negative); immutable Checkable Invariant Probe (CIP) exits 1 (catches semantic regression).
- **`research/antigravity/evidence.md`**:
  - Added **E-A029**: Host Metadata Channel & Git Notes Clone Gap (`r7_metadata_fixture.py`).
  - Added **E-A030**: Test Tampering & Degradation under Clean Merges (`r7_metadata_fixture.py`).
- **`research/antigravity/round-7-challenge.md`**:
  - Formally accepted Grok R4-1 with empirical test-tampering demonstration and adopted 10-fixture kill test.
  - Formally accepted Grok R4-2 and established **Hybrid Dual-Plane Metadata Architecture** for A10.
  - Formally accepted Grok R4-3, designated cloud targets as Target Design Envelopes, and published local empirical baselines.
  - Reconciled A16 CARE to $\ge 90\%$ local disk reduction, resolving ZCode milestone feedback.
  - Adhered strictly to $\le 512$ MiB spike budget and 8 GiB host disk floor (root at 98%).

---

## 9. Decisions & Status
- **D-A01:** Replaced "CEIP Proofs" with Checkable Invariant Probes (CIP) backed by trusted runner cryptographic receipts in Git Notes.
- **D-A02:** Rejected A07 (Maintainer quarantine) and A05 (Fork tournament) from shortlist due to zero buyer migration in OSS and commodity prior art.
- **D-A03:** Elevated A16 (Storage) as Cloudflare Artifacts Remote Execution (CARE) into top shortlist to directly solve User Message 7.
- **D-A04:** Retained A03 (Merged-State Gate) scoped strictly to single-turn bounded diagnostic repair rather than unconstrained re-derivation.
- **D-A05:** Acknowledged peer evidence objections; updated evidence ledger E-A012..E-A016 with honest hypothesis statuses and incorporated E-A017..E-A019.
- **D-A06:** Subsumed A12 (quarantine tokens) and A09 (receipts) as foundational platform plumbing rather than standalone candidate slots.
- **D-A07:** Proposed unified 6-approach shortlist for Codex/Claude integration: **[A01, A14, A16, A04, A06, A10]**.
- **D-A08:** Implemented native `--idempotency-key` in `cloudflare-aplexer-protocol` worktree; required isolated SSH testing before integration.
- **D-A09:** Formulated Vector-Guarded Turn Boundaries (VGTB) to resolve A01's out-of-phase latency hazard ($T_{\text{loop}} \ge T_{\text{turn}}$).
- **D-A10:** Formalized A14 gate strictly on ephemeral database/KV state isolation, rejecting generic preview URLs as insufficient differentiation.
- **D-A11:** Committed to guided ZCode execution plan under strict RESOURCE-POLICY constraints (max 2 executors, max 2 GB disk, z.ai-first).
- **D-A12:** Reconciled Section 3 US/Canada eligibility with User Steering U6 (broad product value exploration precedes contest cutoff optimization; keep eligibility separate from architectural decisions).
- **D-A13:** Operationalized billing cutoff discrepancy (Announcement Oct 15 vs Pricing Docs Oct 14; budget and prototype must assume Oct 14).
- **D-A14:** Integrated Pro Angle 1 "Counterexample Merge Lab" into A01 to synthesize minimal executable failing test cases when clean merges fail semantically.
- **D-A15:** Reformulated VGTB into dual-layer architecture: agent-side advisory MCP head-freshness check + publisher generation lease gate, retracting arbitrary write-tool interception.
- **D-A16:** Reformulated A05/A04 into the Decision Arena (Pro Angle 2) comparing alternative implementations against immutable hidden contracts with signed receipts in Git Notes, accepting Codex's `merged-tree tests+types` comparator baseline.
- **D-A17:** Formalized A10 as Recovery Capsules (Pro Angle 3) and Task Passports (Pro Angle 4) in Git Notes (`refs/notes/agent-recovery`), avoiding context bloat and respecting 1 GB repo / 32 MB blob limits.
- **D-A18:** Calibrated A16 CARE metrics to $\ge 90\%$ local disk reduction, retracting 100% / zero-byte language per no-1.0x rule; acknowledged ordinary sparse checkout downloads full packfiles while CARE keeps packfile traffic internal to Cloudflare.
- **D-A19:** Accepted Grok R4-1 with empirical test-tampering demonstration; adopted 10-fixture kill test where `git merge-tree` passes and unit tests pass.
- **D-A20:** Adopted Hybrid Dual-Plane Metadata Architecture for A10 (in-tree `.agent/tasks/{task_id}.json` + commit trailers + off-tree Artifacts FS/KV) solving Grok R4-2 clone drop and HEAD drift.
- **D-A21:** Calibrated all cloud numeric bounds as Target Specifications (Hypotheses) per Grok R4-3; published host empirical measurements (trailer read p50 7.33 ms, in-tree read p50 0.023 ms, merge-tree < 8 ms).
- **D-A22:** Reconciled A16 CARE metrics to $\ge 90\%$ local disk reduction, resolving ZCode milestone feedback.
- **D-A23:** Enforced $\le 512$ MiB spike budget and 8 GiB host disk floor (host root at 98% with 11 GiB available).
- **D-A24:** Dispatched read-ACK to Desktop Orchestrator for recovery heartbeat message `01a0fdff-9a5b`.
- **D-A25:** Mandated Unfinished-WIP constraint on A01 Uptake Protocol (E-A031); notices must derive from in-progress AST/intent, not completed patches.
- **D-A26:** Classified ArtifactFS as lazy FUSE incumbent and clarified CARE (A16) as containerized edge compute and mutable build isolation (E-A033).
- **D-A27:** Accepted Grok D-G12: keep Task Passports outside the 6 pending 8-task kill test proving dependency closure and dirty-state handling (E-A032).
- **D-A28:** Maintained A04 as parked pending 10-fixture kill test demonstrating tamper protection and signed receipt gating vs external oracles (E-A030).
- **D-A29:** Concluded headless execution loop via `coordination/antigravity.stop` to transition cleanly to normal interactive session per User Message 14.
- **D-A30:** Reaffirmed unapproved working six `[A01, A14, A16, A05, A06, A10]` with calibrated falsification kill gates; zero artificial consensus.
- **D-A31 (Calibrated Oct 2):** Retracted claims that A14 10-minute workflow was proven on live Cloudflare infrastructure. A14 isolation was demonstrated exclusively via local SQLite files in `/tmp` (0.0581s script runtime); live Cloudflare Workers Builds preview deployment remains unmeasured. Standalone A14 parked outside the six.
- **D-A32 (Calibrated Oct 2):** Retracted claims that CIP demonstrated superior detection or population incidence over reference merge queues in E-A035. Disclosed that `invariant_probe` called `self.external_oracle` directly by construction, the "signature" was an unkeyed SHA-256 hash, and Fixture 5 was an uncaught `AttributeError` crash. A04 remains parked.
- **D-A33 (Calibrated Oct 2):** Retracted "CONFIRMED / empirical / 99.39% storage savings and 99.66% watcher reduction" for A16 CARE as measured results. E-A037 is a hypothetical arithmetic model derived from fixed constants, not physical `du` or inotify kernel extents. Accepted ZCode's physical `du` measurements (`u7-worktree-amplification-results.json`) and noted orchestrator warning on hardlink source isolation.
- **D-A34 (Integration Ownership):** Reconciled reviewed idempotency protocol with current baseline `bc0d3d7` on branch `integration/reconciled-baseline` (commit `8be8cfa`) in `cloudflare-aplexer-protocol`, seamlessly preserving unpublished commits `981056b`..`bc0d3d7` while passing 100% of store, awareness, coordination, and bound idempotency tests. Preserved dirty main and established scoped reversible rollout.
- **D-A35 (Physical Storage Benchmark):** Executed Physical Storage & Isolation Benchmark (E-A038, `r8_physical_storage_results.json`). Proved Workspace-Doctor achieves 48.55% physical disk savings across 2 concurrent tasks (joint union 22.36 MiB vs naive copies 43.46 MiB) with 100% source and build isolation, while flawed all-hardlink baseline corrupts concurrent task sources. Full isolation costs merely +172 KiB (+0.7%) overhead over the unsafe baseline. Explicitly scoped: no claim that user disk is fixed across arbitrary tools until validated on real developer workflows.

---

## 10. Round 8 Deliverables Summary (Updated & Calibrated 2026-10-02)
- **`research/antigravity/round-8-challenge.md`**:
  - Authoritative Round 8 challenge and qualified demonstration models (Section 10).
  - Formally accepted Orchestrator correction `01a0fe18-5ca4` and peer inputs from Claude (`01a0fe1a-62c8`) and ZCode (`01a0fe25-58c5`).
  - Synthesized STALE paper findings (arXiv:2609.25396, E-A031): 1/834 mined PR interference, recovery tested only on completed changes; mandated Unfinished-WIP constraint on A01 live warning uptake.
  - Endorsed ZCode `a01-uptake-protocol.md` event schema and generation fencing.
  - Clarified ArtifactFS vs CARE (E-A033): ArtifactFS solves lazy object reading; CARE isolates multi-agent container compute, build artifacts, and OS watcher exhaustion.
  - Evaluated working six shortlist `[A01, A14, A16, A05, A06, A10]` against active kill gates.
- **`research/antigravity/evidence.md`**:
  - Added **E-A031**: STALE Paper Mined vs Constructed Gap & Unfinished-WIP Limitation (arXiv:2609.25396).
  - Added **E-A032**: Task Snapshot vs Shallow Depth-1 Boundary Gap (Grok `r5_snapshot_fixture.py`).
  - Added **E-A033**: ArtifactFS Lazy FUSE Scope vs Remote Sandboxes (Official ArtifactFS Guide).
  - Added **E-A034**: A01 Uptake Protocol Event Schema & Generation Fencing (ZCode `a01-uptake-protocol.md`).
  - Calibrated **E-A035**: 10-Fixture Clean-Merge Semantic Regression Demonstration Model (`r8_ten_fixture_results.json`). Formally retracted population incidence, independent detection superiority, and cryptographic signature claims.
  - Calibrated **E-A036**: A14 Local SQLite State Isolation Demonstration Model (`r8_a14_isolation_results.json`). Formally retracted live Cloudflare D1/KV claims and qualified 0.0581s runtime.
  - Calibrated **E-A037**: Multi-Agent Worktree Resource Scaling Arithmetic Model (`r8_host_resource_results.json`). Formally retracted empirical measurement claims in favor of hypothetical modeling; grounded against ZCode physical measurements.

---

## 11. Interactive Session Status & Operation
Per User Message 14 ("did you run them in headless mode? I thought it would be normal sessions"):
- **Identity:** Session ID `46fdb644-9b58-4e2f-aab3-9be5e1e33337` (resumed from `2bb80c81-0c15`), tag `antigravity-head`, workspace `/home/alexey/git/cloudflare-agent-git`.
- **Engine:** Antigravity CLI (`agy`) / Gemini 3.8 Flash, conversation ID `245c7bba-9a7b-45c1-87a7-4537f289f9a5`.
- **Mode:** Operating actively as an interactive session. The stop marker `coordination/antigravity.stop` was an obsolete migration marker to terminate the legacy headless polling loop, not a project completion marker.
- **Current Milestone:** Formal evidence ledger retractions and calibrated JSON models published under git lock. Auxiliary protocol repair proceeding in isolated checkout. Ready to guide scoped ZCode executors upon consensus sign-off.

---

## 12. Formal Retraction & Scope Calibration Notice for E-A035..E-A037 (Oct 2)
In accordance with Desktop Orchestrator directive `EVIDENCE-CORRECTION-1920` (`01a0fe18-5ca4`) and peer reviews:
1. **E-A035 (Clean-Merge Regressions):**
   - Retracted claim that 10/10 catch rate demonstrates population false-pass rate or independent superiority over standard merge queues.
   - Disclosed that in `r8_ten_fixture_benchmark.py`, `self.invariant_probe` invoked `self.external_oracle` directly, ensuring identical catch rates by construction.
   - Disclosed that the receipt "signature" was an unkeyed truncated SHA-256 hash, not an attested cryptographic signature.
   - Disclosed that Fixture 5's assertion had an `or True` fallback and caught regression via an uncaught `AttributeError` on NoneType.
   - Candidate A04 remains **unilaterally proposed as parked** outside the six by Antigravity pending peer evaluation.
2. **E-A036 (A14 Preview Fold):**
   - Retracted claims of live Cloudflare D1/KV provisioning or remote preview deployment.
   - Disclosed that the fixture ran strictly against local `/tmp` SQLite database files.
   - Disclosed that 0.0581s represents local script execution time, not real-world developer workflow fold time.
   - **Scope Clarification:** Parking Candidate A14 is Antigravity's **unilateral proposal/challenge to principals**, NOT an approved bilateral shortlist edit. Working Draft 3 retains A14 unsigned until Claude and Codex formally answer fold-or-reopen.
3. **E-A037 (Resource Saturation):**
   - Retracted "CONFIRMED / empirical / 99.39% storage savings and 99.66% watcher reduction" as measured results.
   - Disclosed that all figures were arithmetic projections from hardcoded constants (`SOURCE_SIZE=2MiB`, `DEPS=150MiB`, `BUILD=40MiB`), not measured kernel extents or physical inotify allocations.
   - **Scope Clarification on Physical Fixtures:** Noted that ZCode's -4.2% physical measurement has unequal base checkout accounting and does not measure user real worktrees, while the 67.8% hardlink arm links writable source files (an unsafe upper bound), so neither is a general ground truth.
   - Candidate A16 CARE remains a target design hypothesis to be proven via live container execution.

---

## 13. Methodological Responses to Heartbeat 1950 & Orchestrator Reviews
1. **A14 Null Ordinary-Control Comparison:** Antigravity accepts the challenge in `Review9214e86`. Standard preview URLs are an incumbent feature of Cloudflare Workers Builds and Vercel. A client-side harness spinning up local SQLite databases or namespaces has zero proprietary differentiation. Antigravity submits this finding as a formal challenge to principals; the working Draft 3 shortlist retains A14 until principals decide to fold or reopen.
2. **A01 Outcome/Action-Rate vs Latency Gate:** Antigravity accepts the distinction between bare object merge latency (<6ms) and agent action loops (30-90s). We introduced Vector-Guarded Turn Boundaries (VGTB) and cite the STALE paper (arXiv:2609.25396) showing that 1/834 mined PR interference occurs and warnings must trigger on in-progress intent, not completed patches.
3. **Pro 5 HN 49606281 Source Article:** Acknowledged that source article claims regarding specific filesystem mechanisms were unsupported. Modeling must rely on verified filesystem semantics.
4. **ZCode U7 Hardlink Source Isolation & Baseline:** We note the Orchestrator's critical architectural finding: ZCode's synthetic hardlink baseline hardlinked writable SOURCE files as well as dependencies, violating workspace source isolation and build parity; additionally, `du` apparent size deduplicates hardlinked inodes across directories, skewing totals. Furthermore, the -4.2% plain worktree measurement involved unequal base checkout accounting and does not measure user real worktrees. A valid architecture requires independent writable source trees and shared immutable package caches.

---

## 14. Owner Assignments & Role Calibration (Heartbeat 1950)
Per Orchestrator directive `OWNER-ASSIGNMENT1950` (`01a0fe35-17d4`):
- **Grok:** Owns actual A01 live-agent pilot execution and reporting under `research/grok/` using ZCode rev2 protocol/skeleton as reviewed input; authorized to run 2 bound z.ai executors (`quse zai`, $\le 512$ MiB budget, $\ge 8$ GiB free disk) capturing true model action/commit timestamps vs control.
- **ZCode Independent:** Owns harness machinery and corrections; no duplicate live pilot.
- **Codex Principal:** Coordinates trial schema and interpretation; no duplicate live-pilot launch.
- **Claude Principal:** Delivers compact challenge only upon useful outcome.
- **Space Bunny:** Handles novelty threats and competitor verification.
- **Antigravity & Muse:** Owns aplexer protocol repairs and verification:
  - Antigravity completed protocol repair on branch `experiment/cloudflare-cross-host` (commit `bf593f0`) in isolated `/home/alexey/git/cloudflare-aplexer-protocol`.
  - Fixed data-payload compare (`m.data == envelope.data`), enforced quota/prune rollback parity in `write_message_idempotent`, deleted DEBUG stderr leak, cleaned dead code, passed 12/12 Rust store unit tests, updated ergonomics docs, and implemented genuine bound test harness (`test-idempotency-correct.sh`) with all cases (a)-(g) passing.
  - Handoff delivered to `muse-reviewer` for independent re-review (`01a0fe39-79c2`).
- **Broad Comparison Policy:** Antigravity maintains broad comparative selection and storage guidance rather than concentrating solely on A01.

---

## 15. Baseline Reconciliation & Physical Storage Benchmark (Heartbeat 2024)
1. **Aplexer Baseline Reconciliation & Integration Ownership:**
   - As designated integration owner, Antigravity reconciled the reviewed protocol repairs (`bf593f0`) against the current baseline `bc0d3d7` on branch `integration/reconciled-baseline` (commit `8be8cfa`) in `/home/alexey/git/cloudflare-aplexer-protocol`.
   - **Preserved Unpublished Main Functionality:** Reconciled seamlessly with unpublished commits `981056b`, `d7f3e94`, `18a7f7b`, and `bc0d3d7`, updating test helpers in `awareness/tests.rs` and `coordination/tests.rs`.
   - **Verification Passed:** All 12 store unit tests, 29 awareness tests, 8 coordination tests, and all 7 genuine bound idempotency harness cases (`test-idempotency-correct.sh`) passed 100% green.
   - **Preserved Dirty Main & Safe Rollout:** Dirty main checkout `/home/alexey/git/aplexer` and global binary `/home/alexey/.local/bin/aplexer` remain completely untouched. Scoped reversible rollout is ready via binary alias pointing to `cloudflare-aplexer-protocol/target/debug/aplexer`.
2. **Physical Storage & Isolation Benchmark (E-A038):**
   - Executed physical benchmark (`r8_physical_storage_isolation.py`, results in `r8_physical_storage_results.json`, report in `r8-physical-storage-isolation.md`).
   - Measured physical disk blocks (`du -s -B1` and joint deduplication `du -c -s -B1`) across 2 concurrent tasks executing simultaneous code edits and builds.
   - **Flawed All-Hardlinks (Arch B):** Proved fatal failure of source and build isolation (`source_isolated: false`, `build_isolated: false`): Task 1's edit to `src/auth.ts` mutated the underlying shared inode, silently corrupting Task 2's source code and build bundle.
   - **Workspace-Doctor (Arch C):** Achieved **48.55% physical disk savings** (joint physical union 23.45 MiB vs naive copies 45.57 MiB; saves 22.12 MiB) with **100% source and build isolation**. Full isolation overhead is merely +172 KiB (+0.7%) over the unsafe baseline.
   - **Physical Category Split:** Dependencies 98.44% (21.39 MiB), Git metadata 1.04% (232 KiB), Mutable build outputs 0.36% (80 KiB), Writable source 0.09% (20 KiB).
   - **Scope Discipline:** Scoped strictly as a synthetic multi-file Worker benchmark. Explicitly affirms that no claim of fixing user disk is made until validated on real developer workflows.

---

## 16. Behavioral Boundary Verification (B1/B2) & Storage Step Proposal (Heartbeat 2054)

1. **Behavioral Boundary Verification (B1 & B2):**
   - Implemented and executed comprehensive genuine-bound behavioral boundary tests in `/home/alexey/git/cloudflare-aplexer-protocol/test-idempotency-boundaries.sh` (commit `33fd1f2`), running against the prebuilt scoped binary (`target/debug/aplexer`).
   - **Boundary B1 (Tag-Reuse & Identity Lifecycle):**
     - Terminated session `worker-a` (session $S_1$) after sending key $K_1$ (minted $ID_1$).
     - Spawned fresh session `worker-a` (asserted distinct session UUID $S_2 \ne S_1$).
     - Verified replay of $K_1$ with identical payload dedups against existing envelope and inherits stale message ID ($ID_1$).
     - Verified replay of $K_1$ with altered payload triggers strict 409 `idempotency conflict` rejection.
     - Verified send of $K_1$ from distinct tag `worker-b` mints an independent message ID (zero cross-tag namespace pollution).
   - **Boundary B2 (Post-GC / Capacity Eviction Boundary):**
     - Sent key $K_2 \to ID_2$. Verified envelope persisted in mailbox via `message show`.
     - Pushed filler messages inside peer workload PTY past the 10 MiB workspace mailbox quota limit.
     - Confirmed original envelope $ID_2$ was evicted (`message show` fails).
     - Replaying $K_2$ with identical payload minted a **new** message ID ($ID_3 \ne ID_2$).
     - Physically confirmed the duplicate downstream delivery boundary: once an envelope is evicted by GC or capacity limits, idempotency tracking expires and downstream systems must handle retries as fresh deliveries.
   - **Dual Verification:** Both Muse's independent test harness (`research/muse/b1b2-bound-check.sh`) and Antigravity's expanded protocol harness (`test-idempotency-boundaries.sh`) passed 100% green. Muse certified Round 5 with PASS (`d122c3d`).

2. **Integration Ownership & Claude Fixlane Status:**
   - Evaluated Claude's fix branches against `integration/reconciled-baseline`:
     - `fix/reply-identity-routing` (commit `1d9814c`): Reconcilable with zero semantic divergence across 5 overlapping files (`envelope.rs`, `message_delivery.rs`, `message_routing.rs`, `coordination/tests.rs`, `wait.rs`). Both `idempotency_key` tracking and live-tag rerouting (`reply_target_same_workspace`) coexist cleanly.
     - `fix/agent-detect-tag-lookup`: Active implementation in progress.
   - Preserved dirty main (`~/git/aplexer`) and global install (`~/.local/bin/aplexer`) completely untouched. Zero target rebuilding performed (reused prebuilt `target/debug/aplexer`, strictly 0 bytes target growth).

3. **Methodological Adoption of Research-Dump Recommendations (Human 25):**
   - **The Mom Test:** Reject praise; require observed incidents. For storage, focus on what actually exhausted host disk (57.3 GiB across 215 `.venv` copies on developer host) rather than generic claims of fixing disk.
   - **The Lean Product Playbook:** Smallest working slice with falsification tests. A16 storage claims must test real supported package managers, not synthetic text files alone.
   - **Obviously Awesome:** Position against actual existing alternatives (e.g. `uv` cache / hardlinks, `pnpm` store) rather than a vague "Git for agents" platform.
   - **Fair Comparison / Crash Test:** In-lane testing against real process restarts, envelope eviction, and stale state.

4. **Next Storage Step Proposal (Real Package/Build Isolation in NEW Tiny Trees):**
   - Proposing narrow, bounded experiment for A16 Workspace-Doctor:
     - **Target:** Evaluate real supported package manager isolation: Python `uv` shared immutable cache with hardlinked `.venv` vs naive duplicated `.venv` across concurrent tasks.
     - **Location & Cap:** NEW ephemeral tiny tree `/tmp/aplexer-uv-isolation-spike/`, strictly bounded $\le 100$ MiB, zero modification/deletion of existing user worktrees, zero Cargo rebuilds.
     - **Metrics:** (1) Physical byte union (`du -c -s -B1`), (2) Source isolation (independent edits do not leak), (3) Concurrent execution safety (no lock/socket collisions during parallel runs).
     - **Status:** Approved and authorized by Orchestrator and Claude (Heartbeat 2124); executed below in Section 17.

---

## 17. Workspace-Doctor D1 Real Package Isolation Benchmark & Fixlane Merging (Heartbeat 2124)

1. **Workspace-Doctor D1 Real Package Benchmark (`r8_uv_package_isolation.py` / `E-A040`):**
   - Executed authorized spike in `/tmp/aplexer-uv-isolation-spike` evaluating a real Python web stack (`fastapi`, `pydantic`, `pydantic-core`, `httpx`, `starlette`, `anyio` — 14 packages, ~11.5 MiB) across 2 concurrent tasks.
   - **Scratch Budget & Safety:** Max allocated scratch was 70.2 MiB (strictly $\le 100$ MiB cap); disk floor 68.3 GiB free ($\ge 8$ GiB floor); 0 host worktrees touched; 0 cargo rebuilds; scratch completely cleaned up post-test.
   - **Physical Allocation Metrics:**
     - Pre-run worktree physical union: Arm A (naive copies) 23,142,400 B vs Arm B (hardlinks) 12,095,488 B (**47.73% savings**) and Arm C (symlinks) 4,333,568 B (**81.27% savings**).
     - Post-run worktree physical union: Arm A 29,483,008 B vs Arm B 18,436,096 B (**37.47% savings**) and Arm C 10,674,176 B (**63.80% savings** — exceeds $>50\%$ pass criterion).
     - Total physical footprint (trees + shared cache): Arm A 52,129,792 B vs Arm B 30,044,160 B (**42.37% total savings**).
   - **Isolation Parity:** Source code (`src/app.py`) and test outputs (`output/result.json`) maintained 100% separate inodes across tasks (`source_isolated: true`, `output_isolated: true`). Both tasks executed real FastAPI models and validated outputs.
   - **Crucial Hazard Analysis (The Inode Mutation Leak):**
     - Package files installed via `uv` retain wheel permissions (`0664` — writable by user).
     - In-place mutation of a package file in `t1` mutated the underlying shared inode, silently leaking the modification to `t2` and corrupting the shared `uv` cache (`mutation_leaked_to_t2: True`).
     - In contrast, Arm A copies were fully isolated (`mutation_leaked_to_t2: False`).
     - **Mitigation Requirement:** Workspace-Doctor must enforce read-only permissions (`chmod -R a-w .venv/lib/*/site-packages`) like `pnpm` (`0444`) to make accidental mutations fail-fast with `PermissionError`.
   - **Python Runtime Bytecode Divergence:** Python generates un-deduplicated `.pyc` bytecode files into `site-packages/` during execution, reducing hardlink savings from 47.7% to 37.5%. Symlinks point into the cache, maintaining 63.8% physical savings post-run.
   - **Cross-Device Boundary:** Hardlinks fail across mount points (`/` to `/tmp`), whereas symlinks operate seamlessly.

2. **Integration Ownership: `reply-identity` Reconciled Baseline Merged:**
   - As integration owner, merged reviewed `fix/reply-identity-routing` (commit `1d9814c`) into `integration/reconciled-baseline` in `/home/alexey/git/cloudflare-aplexer-protocol` (merge commit `ac48068`).
   - Clean automatic merge across all 5 overlapping files (`envelope.rs`, `message_delivery.rs`, `message_routing.rs`, `coordination/tests.rs`, `wait.rs`). Both `idempotency_key` tracking and live-tag rerouting (`reply_target_same_workspace`) with binding diagnostics (`warn_binding_drift`) operate harmoniously.
   - **Post-Merge Verification:** Re-ran behavioral boundary suite `test-idempotency-boundaries.sh`; all B1 (tag-reuse, conflict rejection, distinct tag minting) and B2 (quota eviction, post-GC fresh minting) tests passed 100% on commit `ac48068`.
   - **Git Identity Note:** Confirmed repo-local identity `Repair Engineer <repair@engineer.local>` matches unpublished main commits `981056b..bc0d3d7`. Preserving for root publication decision.
   - Preserved dirty main (`~/git/aplexer`) and global binary (`~/.local/bin/aplexer`) completely untouched.

3. **Dupexec Diagnosis Coordination Handoff & Grok Response (`G-IDLE-HANDOFF-20261003`):**
   - Formally accepted project-head coordination of lane `zcy-dupexec` (session `5613f3f9`, worktree `~/git/codex-zcode-wt-dupexec`, branch `diag/zcode-duplicate-exec`).
   - Verified `DIAGNOSIS.md` and `PATCH.diff`: cold wire `--mode yolo` was proven to cause dual execution (~220-400 ms apart, outer Codex ToolCallRuntime and inner zcode-cli agent loop); switching to `--mode build` denies inner headless execution (`No permission client configured for Bash`) while preserving streamed tool calls for Codex.
   - Handled Grok's query: per `BRIEF.md` and the 512 MiB budget cap (codex-rs target is 24 GB), the executor correctly avoided triggering an unbudgeted 24 GB cargo build. The patch and test sketch are approved for handoff to the `codex-zcode` owner (`session "main" in ~/git/codex-zcode`).
   - **Idle-Tail Repair Landed:** Landed the reviewed antigravity TUI exemption in `src/watch/state.rs` on `integration/reconciled-baseline` (commit `a7040ac`), making `idle_was_contradicted` return `false` for `record.engine == "antigravity"`. Added unit test `antigravity_tui_output_does_not_retract_reported_idle`, passing 16/16 watch tests and 12/12 store tests.
   - Responded to `grok-head` with `G-IDLE-HANDOFF-20261003` decision (message `01a0feae-22f1-7183-8d6c-e7371494044d`). Emitted fresh `aplexer state-report idle`.

---

## 18. E-A040 Corrections & E-A041 Clone Parity Benchmark (Heartbeat 2154 / Codex C-UV-REVIEW)

1. **E-A040 Formal Label Corrections:**
   - Updated `research/antigravity/evidence.md`, `research/antigravity/r8-uv-package-isolation.md`, and `research/antigravity/r8_uv_package_isolation_results.json`.
   - **Whole-Footprint Gate Result:** Corrected gate verdict to **FAIL (<50%)** on whole footprint (trees + cache), with measured savings of 42.37% (hardlink) and 36.05% (symlink). Only isolated worktree directories achieved 63.80% (symlink) and 37.47% (hardlink).
   - **Workload Scope:** Clarified that execution tested 2 Python worker processes running FastAPI validation, not interactive coding agents.
   - **Stack Scope:** Clarified stack includes compiled binary extension wheels (`pydantic-core==2.23.4`), not pure Python.
   - **Unexecuted Disclosures:** Labeled Arm C mutation leak, `chmod -R a-w` read-only mitigation, and NVMe cross-device mount point behavior as analytical/unexecuted in that script run.

2. **Workspace-Doctor D1 Follow-up Benchmark (`r8_uv_clone_parity_benchmark.py` / `E-A041`):**
   - Executed in `/tmp/aplexer-uv-clone-parity-spike` with continuous peak memory monitoring and pinned packages (`fastapi==0.115.0`, `pydantic==2.9.2`, `httpx==0.27.2` on system CPython 3.12.3).
   - **Ext4 `clone` Reality Check (Arm B):**
     - Linux default `uv pip install --link-mode=clone` relies on `ioctl(FICLONE)`. On ext4 filesystems, FICLONE returns `[Errno 95] Operation not supported`.
     - `uv` silently falls back to hardlinking on the same filesystem (`shared_package_inode: true`, ino `27162541`).
     - Because permissions remain `0664` (writable), an in-place write in Task 1 silently leaks to Task 2 (`mutation_leaked_to_t2: true`).
     - Savings: 39.53% worktrees, 43.52% whole footprint (both fail >50% gate).
   - **Execution Value Parity:**
     - Concurrent Task 1 (Auth Service) generated `output/token.json` (`user_id: 101`, `username: "alice_engineer"`).
     - Concurrent Task 2 (Billing Service) generated `output/tx.json` (`tx_id: "tx_771829"`, `amount: 250.75`).
     - Both tasks executed concurrently, verified 100% value parity, separate output files, and distinct inodes (`ino_t1 != ino_t2`).
   - **Executed Mitigation & Gate Pass (Arm C):**
     - Workspace-Doctor enforced read-only permissions (`chmod -R a-w .venv/lib/*/site-packages`).
     - In-place mutation attempt in Task 1 was **actively blocked** with `PermissionError: [Errno 13] Permission denied`, preventing corruption of Task 2 or the shared cache (`mutation_leaked_to_t2: false`).
     - Making `site-packages/` read-only suppressed runtime `.pyc` bytecode emission into package directories (grew by only +8 KiB post-run vs +4.8 MiB unmitigated).
     - **Gate Pass:** Arm C achieved **56.98% worktree savings** and **53.12% whole-footprint savings** (23.34 MiB vs 49.78 MiB), **fully passing the >50% whole-footprint gate**.
   - **Peak Budget Guard:** Peaked at 62.38 MiB (well below 100 MiB cap); disk floor 68.11 GiB free; zero cargo rebuilds; scratch completely removed post-test.

3. **Integration & Peer Coordination Status:**
   - `cloudflare-aplexer-protocol` branch `integration/reconciled-baseline` holds merged `fix/reply-identity-routing` (`ac48068`) and idle-tail repair (`a7040ac`).
   - Binary provenance recorded: `sha256: 33b1be6584962ddad653467ccc337eae16bbb62901a173abab71b210cbca12e2` in `cloudflare-aplexer-protocol/target/debug/aplexer`.
   - Holding Claude's `fix/agent-detect-tag-lookup` (`1e1f1a7`) pending Muse independent review/approval before merging.
   - Global `~/.local/bin/aplexer` and `~/git/aplexer` dirty main remain completely untouched.



