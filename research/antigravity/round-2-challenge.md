# Antigravity Round-2 Independent Challenge & Architectural Synthesis

- **Date:** 2026-10-02 (Europe/Berlin)
- **Author:** `antigravity-head` (aplexer session `2bb80c81-0c15-4577-8ba7-27e56a3c98ec`)
- **Engine:** Google Antigravity (`agy` / Gemini 3.8 Flash)
- **Target Audience / Recipients:** `claude-principal`, `codex-principal`, `grok-head`, `space-bunny-head`, `muse-reviewer`
- **Ownership:** Owns only `research/antigravity/` and `coordination/antigravity.md`. Does not edit peer files.

---

## 1. Executive Summary & Round-2 Calibration

In Round 1, Antigravity identified three fatal architectural fallacies (Air-Traffic Control UI, PR-centric contribution model, syntax-only merging) and proposed two edge-native paradigms: Ephemeral Quarantine & Dual-Phase Promotion (EQ-2PP) and Contract-Enforced Invariant Proofs (CEIP). Both principal peers responded (`01a0fde1-68e4` and `01a0fde1-98e3`), acknowledging core constraints while issuing critical counter-challenges regarding novelty, proof semantics, and stale-head invalidation.

Simultaneously, two critical steerings arrived from the user and orchestrator:
1. **User Message 6 (Exploration vs. Contest Cutoff):** Broad exploration must not be artificially truncated by contest MVP limits or unresolved eligibility. High-value long-term architectures must be evaluated on their merits alongside 12-day contest feasibility.
2. **User Message 7 (Worktree Storage Amplification):** Direct first-hand user pain. Running 5–20 concurrent agent worktrees explodes workstation disk consumption. Codex and Grok fixtures (`research/codex/storage-validation.md`, `research/grok/challenge-r1.md`) confirm that on ext4, `cp --reflink` fails and untracked `node_modules` / build caches consume 75–80% of workspace bytes.

Claude has now published `research/approaches-20.md` (draft v1, approaches A01–A20) with a provisional top 6 (A01, A05, A07, A14, A13, A19). 

**Antigravity's Round-2 Core Finding:**
Claude's provisional top 6 suffers from the **"Demo-Toy Trap"**: it selects superficial, presentation-heavy features (A05 tournament, A07 maintainer quarantine, A13 session undo, A19 batch maintenance) while demoting the highest-value, structurally defensible solutions to verified user pain (A16 storage, A04 semantic contracts, A03 merged-state repair, A12 quarantine forks). 

This document dismantles the unviable candidates in Claude's top 6, provides an independent scoring of all 20 approaches, responds rigorously to Claude and Codex's critiques of CEIP and EQ-2PP, presents an edge-native architectural solution to workspace storage amplification, and nominates a robust, defensible 6-approach shortlist.

---

## 2. Critique of Claude's Draft v1 Integration & Dismantling the Provisional Top 6

Claude's integration in `research/approaches-20.md` successfully establishes a common vocabulary and absorbs Antigravity's critique by dropping Seed 18 (air-traffic dashboard) and mapping CEIP (A04) and EQ-2PP (A12). However, Claude's provisional selection (A01, A05, A07, A14, A13, A19) is deeply flawed.

### A. The Collapse of A07 (Maintainer Inbound Quarantine)
- **Claude's Thesis:** Build a quarantined inbound PR gate for open-source maintainers drowning in AI slop (E-C202, E-C205).
- **The Fatal Flaw (E-A010, Grok G7):** 
  1. *Wrong Buyer / No Migration Incentive:* Open-source maintainers will not migrate their canonical repositories, issue trackers, CI pipelines, and contributor communities from GitHub to Cloudflare Artifacts solely for an inbound quarantine gate. Daniel Stenberg (curl) explicitly documented that forge switching does not stop AI slop; projects either ban AI code (QEMU, OpenBSD) or enforce strict 1-PR limits.
  2. *Commoditization by GitHub Rulesets:* GitHub is already deploying PR velocity limits, contributor verification, and Copilot spam filtering natively (E-C226). 
  3. *Contest Terms Violation:* Rule 4 explicitly prohibits submissions that disparage commercial products ("GitHub is drowning in slop"). Presenting a product whose entire pitch is "GitHub PRs are broken" creates direct regulatory friction with contest terms.
- **Verdict:** **REJECT from Shortlist.** A07 belongs in the exploration archive or as a secondary policy setting within F5.

### B. The Wastefulness of A05 (Fork Tournament with Verified Landing)
- **Claude's Thesis:** Spawn N agents to implement the same task, preview them side-by-side, and pick the winner.
- **The Fatal Flaw:** 
  1. *Token Multiplier without Compositional Value:* Running best-of-N for a single task does not address the actual crisis of multi-agent development: *how do multiple agents work on DIFFERENT features concurrently without breaking the codebase?* 
  2. *Prior Art Dominance:* Cursor `/best-of-n`, Agent HQ, and Codex Cloud already implement parallel attempts. Re-implementing best-of-N on Cloudflare wastes the 50% originality weight.
  3. *Cost & Context Waste:* N attempts consume N times the inference tokens and N container instances, only to discard N-1 implementations.
- **Verdict:** **DEMOTE to Feature.** Tournament execution is a dispatcher feature, not an agent Git platform.

### C. The Triviality of A13 (Session Footprint Undo Across Forks)
- **Claude's Thesis:** Revert an agent's entire multi-fork footprint with a single click.
- **The Fatal Flaw:** This is a standard VCS operation log feature (Jujutsu `jj op undo`, GitButler undo, git reflog). In a system with proper pre-landing quarantine (A12), bad code is rejected *before* landing, making post-landing session unwinding an exceptional fallback rather than a primary product pillar.
- **Verdict:** **DEMOTE to Primitive.** Retain as an operational capability inside the platform publisher.

### D. The Derivative Nature of A19 (Maintenance Swarm with Batch Landing)
- **Claude's Thesis:** 10–50 agents fixing lint and dependency updates landed in batches.
- **The Fatal Flaw:** This is literally Renovate / Dependabot with batched automerge. It addresses low-value mechanical chores rather than high-leverage agent engineering.
- **Verdict:** **MERGE into A01 / A03.** Batch landing is a scheduling strategy for the integration runner, not an independent product.

### E. The Unjustified Demotion of High-Value Approaches (A16, A04, A03)
Claude demoted A16 (Zero-checkout lazy workspaces, LTV 5), A04 (Semantic contract sentinel, LTV 4), and A03 (Merged-state gate, LTV 4) to "long-term candidates" based solely on low provisional feasibility scores (2). This directly violates User Message 6 and ignores the primary first-hand pain expressed in User Message 7!

---

## 3. Storage Amplification (User Message 7 / A16): Physics & The Edge Solution

### A. Empirical Findings from Host Fixtures
User Message 7 reports that worktrees duplicate workspaces and exhaust workstation disk space. Codex (`storage-validation.md`) and Grok (E-G007) executed synthetic benchmarks on the ext4 host filesystem:
1. **Reflink / COW Failure:** ext4 does not support `cp --reflink=always` (`Operation not supported`). Modern Linux workstations without Btrfs/ZFS cannot use filesystem-level block cloning for worktrees.
2. **Byte Distribution (E-A009):** In modern web/Node/Python environments, tracked Git source is negligible (~5–15%), while untracked dependencies (`node_modules/`, virtualenvs) and build outputs (`dist/`, `.next/`, `target/`) account for **75–85% of physical allocated bytes**.
3. **Sparse-Checkout Limitation:** Git sparse checkout only reduces tracked source files. Reducing source files by 75% yields only an ~18% net workspace disk saving if full dependencies are copied or reinstalled.

### B. Why Local Solutions Fall Short
- **Plain Worktrees:** 10 agents = 10 full checkouts + 10 dependency installations = 10x disk explosion (e.g. a 500 MB `node_modules` yields 5 GB across 10 worktrees).
- **pnpm Store / Hardlink Sharing:** While `pnpm` deduplicates immutable package files via hardlinks, local agent builds frequently generate mutable local build artifacts, patch local packages, or corrupt symlink graphs during concurrent runs.
- **Local Containerization:** Spawning 10 local Docker containers duplicates disk via container layers and strains local RAM/CPU.

### C. The Cloudflare Edge Architecture Solution: Cloudflare Artifacts Remote Execution (CARE)
The only structural solution that completely eliminates local disk amplification is **moving agent workspaces off the workstation and onto the Cloudflare Edge**:
1. **Zero Local Worktrees:** The developer's machine maintains only **ONE** local Git checkout (the canonical repository).
2. **Ephemeral Remote Quarantine Forks (EQ-2PP):** When an agent task is dispatched, the platform calls `ARTIFACTS.fork()` to create a remote repository instance on Cloudflare.
3. **Serverless Sandbox Workspace:** The agent runs inside a Cloudflare Sandbox (Micro-VM / Container) or edge Worker adjacent to Artifacts. Dependencies are resolved in the cloud against cached edge stores (R2 / KV).
4. **Local Zero-Footprint Materialization:** The local developer machine only interacts with the canonical branch via standard `git pull`. When an agent succeeds and passes all verification gates, the platform publisher fast-forwards canonical HEAD. 
5. **Disk Amplification Factor:** Exactly **1.0x** locally, regardless of whether 1, 5, or 50 agents are running concurrently!

---

## 4. Refinement of Antigravity's Core Architecture

In response to challenges from Claude (`01a0fde1-68e4`) and Codex (`01a0fde1-98e3`, `codex-round-1-external-responses.md`), Antigravity refines the two core primitives:

### A. From "Invariant Proofs" to Checkable Invariant Probes (CIP)
- **Peer Critique:** Claude and Codex rightly pointed out that "proof" implies formal mathematical verification; agent-written invariants can be just as buggy or hallucinated as agent code; Git Notes store text assertions, not truth.
- **Refinement (Checkable Invariant Probes - CIP):**
  1. *Immutable Baseline Authority:* Invariants are **NOT** generated or modified by the candidate agent. They are derived from the canonical baseline repository (existing test suites, TypeScript type contracts, API schemas).
  2. *Cross-Agent Contract Extraction:* When Agent A alters an exported module/type signature in Fork A, the platform runner extracts the AST contract diff.
  3. *Cross-Fork Probe Execution:* Before landing, the platform runner executes Fork B's consumers against Fork A's exports inside an isolated runner.
  4. *Cryptographically Signed Runner Receipts (A09):* The runner (a trusted execution sandbox, not the agent) executes the probe and signs an attestation:
     ```json
     {
       "attestation_type": "CIP_RUNNER_RECEIPT_V1",
       "canonical_base_sha": "a1b2c3...",
       "candidate_source_sha": "d4e5f6...",
       "trial_merged_sha": "7a8b9c...",
       "probes_executed": ["types:check", "test:integration", "contract:consumers"],
       "exit_code": 0,
       "runner_identity": "cf-sandbox-eu-01",
       "signed_by": "platform-publisher-ed25519-key",
       "timestamp": "2026-10-02T20:45:00Z"
     }
     ```
  This attestation is written to Git Notes (`refs/notes/cip-receipts`). The platform publisher refuses to fast-forward canonical HEAD unless a valid, non-stale receipt signed by the trusted runner key is present.

### B. Refinement of Ephemeral Quarantine & Dual-Phase Promotion (EQ-2PP)
- **Peer Critique:** Claude noted EQ-2PP resembles Cloudflare's own recommendation (repo per agent, E-C309) plus a merge queue. Codex noted it needs distinct user-outcome novelty.
- **Refinement (Distinct User Outcomes):**
  1. *Elimination of Local Disk Usage (U7):* Unlike standard merge queues (which assume local feature branches and local developer machines), EQ-2PP enforces that agent quarantine forks live exclusively on Artifacts, maintaining zero local worktree overhead.
  2. *Optimistic Non-Blocking Development:* Agents never block waiting for locks on a shared queue. They work independently in their forks.
  3. *Two-Phase Gate:*
     - **Phase 1 (Fork Isolation):** Candidate passes its own internal task specification in its isolated fork.
     - **Phase 2 (Speculative Canonical Composition):** The platform runner fetches canonical HEAD, generates an in-memory trial merge, runs the CIP invariant probes, and fast-forwards canonical HEAD if and only if canonical HEAD has not moved since the trial merge started.
  4. *Race Handling (Answering Codex):* If canonical HEAD moved during Phase 2 (a stale-head race), the candidate is NOT forced into an expensive full rewrite ("re-derive"). Instead, the runner attempts an incremental rebase/merge against the fresh HEAD and reruns CIP. Only if an actual invariant fails does it trigger a bounded repair.

---

## 5. Antigravity's Independent Scoring of All 20 Approaches

Evaluation across the 7 required dimensions:
- **Pain:** S (Strong, multi-persona verified), M (Moderate), W (Weak/vendor)
- **Orig:** Originality vs existing products (1-5, 50% contest weight)
- **Conc:** Concurrency / multi-agent coordination visibility (1-5, 25% contest weight)
- **UX:** Clarity in 5–10 min demo (1-5, 25% contest weight)
- **Contest Score (/100):** $20 \times (0.5 \times \text{Orig} + 0.25 \times \text{Conc} + 0.25 \times \text{UX})$
- **Feas:** Real engineering feasibility by Oct 14 on documented primitives (1-5)
- **CF:** Cloudflare fit / edge-native leverage (1-5)
- **LTV:** Long-term product value beyond contest (1-5)

| ID | Approach Name | Fam | Pain | Orig | Conc | UX | Contest | Feas | CF | LTV | Antigravity Disposition |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| **A01** | Live Integration Radar | F1 | S | 4 | 5 | 4 | **85** | 4 | 5 | 4 | **SHORTLIST (Top Contest + Concurrency)** |
| **A02** | Lease-Bound Claims at Landing | F1 | M | 3 | 4 | 3 | **65** | 4 | 4 | 3 | Reject: Foremerge / GitButler prior art collision |
| **A03** | Merged-State Gate + Bounded Repair | F1 | M | 4 | 5 | 3 | **80** | 3 | 4 | 4 | **SHORTLIST (Primary Correctness Engine)** |
| **A04** | Semantic Contract Sentinel (CIP) | F1 | S | 5 | 4 | 4 | **88** | 3 | 4 | 5 | **SHORTLIST (Highest Technical Originality)** |
| **A05** | Fork Tournament with Verified Landing | F2 | M | 3 | 3 | 4 | **65** | 4 | 4 | 2 | Demote: Cursor best-of-n duplicate, token wasteful |
| **A06** | Change-Story Review Queue | F3 | S | 3 | 3 | 4 | **65** | 4 | 3 | 4 | Feature: Merge into review UX layer |
| **A07** | Maintainer Inbound Quarantine | F3 | W | 2 | 2 | 3 | **45** | 3 | 2 | 1 | Reject: Wrong buyer, curl/QEMU anti-evidence, GitHub collision |
| **A08** | Independent Reviewer Panel | F3 | M | 2 | 3 | 3 | **50** | 4 | 3 | 2 | Reject: Commodity AI review, CodeRabbit duplicate |
| **A09** | Exact-SHA Verification Receipts | F4 | M | 4 | 3 | 3 | **68** | 4 | 4 | 4 | Primitive: Integral component of A04 / A12 |
| **A10** | Durable Handoff / Context Branch | F4 | M | 3 | 4 | 3 | **65** | 4 | 4 | 3 | Feature: Entire/SpecStory overlap |
| **A11** | Merge Decision Ledger | F4 | M | 3 | 3 | 3 | **60** | 4 | 4 | 3 | Feature: Telemetry layer for A03/A05 |
| **A12** | Quarantine Forks + Capability Tokens (EQ-2PP) | F5 | S | 4 | 5 | 4 | **85** | 4 | 5 | 5 | **SHORTLIST (Core Platform Architecture & Security)** |
| **A13** | Session Footprint Undo | F5 | M | 3 | 3 | 3 | **60** | 3 | 4 | 3 | Reject: Standard VCS feature, low standalone platform value |
| **A14** | Preview-per-Agent Runtime Isolation | F6 | S | 4 | 4 | 5 | **85** | 4 | 5 | 4 | **SHORTLIST (Top UX / Demo Impact)** |
| **A15** | Push-Triggered Fast Verification Lane | F6 | M | 2 | 3 | 3 | **50** | 3 | 4 | 3 | Reject: Bazel/Nx affected clone |
| **A16** | Zero-Checkout Lazy Workspaces (CARE) | F7 | S | 5 | 4 | 3 | **80** | 3 | 5 | 5 | **SHORTLIST (Solves Direct User Pain U7)** |
| **A17** | Fork-is-the-Task Board | F1/F9 | W | 2 | 2 | 3 | **45** | 5 | 3 | 2 | Reject: Derivative UI wrapper |
| **A18** | Multi-Repo Change Sets with Recovery | F8 | M | 4 | 4 | 3 | **75** | 2 | 5 | 4 | Long-Term: Scope exceeds Oct 14 feasibility |
| **A19** | Maintenance Swarm with Batch Landing | F8 | M | 3 | 4 | 4 | **70** | 4 | 4 | 3 | Demote: Dependabot batch grouping clone |
| **A20** | Earned-Autonomy Policy | F9 | W | 2 | 2 | 3 | **45** | 4 | 3 | 2 | Reject: Needs historical usage data to demo |

---

## 6. Antigravity's Recommended 6-Approach Shortlist

By filtering out derivative clones (A05, A08, A19), unviable buyers (A07), and standard VCS utilities (A13), while promoting high-LTV, high-originality architectures that solve direct user pain, Antigravity nominates the following **6 Cohesive Approaches**:

```
+---------------------------------------------------------------------------------------+
|                       EDGE-NATIVE AUTONOMOUS INTEGRATION PLATFORM                     |
+---------------------------------------------------------------------------------------+
|  [A16: Zero-Checkout Workspaces]  +  [A12: Ephemeral Quarantine Forks (EQ-2PP)]       |
|  - Eliminates local disk bloat (U7)   - Per-agent isolated Artifacts forks            |
|  - 1.0x local disk footprint          - Capability write tokens with TTL              |
+-------------------------------------------+-------------------------------------------+
                                            | Push Event (`cf.artifacts.repo.pushed`)
                                            v
+---------------------------------------------------------------------------------------+
|  [A01: Live Integration Radar]   +   [A14: Preview-per-Agent Runtime Isolation]       |
|  - Real-time pairwise composition     - Live edge preview URLs per fork (Workers)     |
|  - Proactive conflict notification    - Isolated D1/KV fixture state                  |
+-------------------------------------------+-------------------------------------------+
                                            | Promotion Request
                                            v
+---------------------------------------------------------------------------------------+
|  [A04: Semantic Contract Sentinel]  +  [A03: Merged-State Gate & Bounded Repair]      |
|  - Checkable Invariant Probes (CIP)    - Speculative trial merge in trusted runner    |
|  - Signed runner receipts in Git Notes - Bounded single-turn agent repair on conflict |
|  - Fast-forward canonical landing only when invariants pass                           |
+---------------------------------------------------------------------------------------+
```

### The 6 Nominees:
1. **A01: Live Integration Radar (F1 - Coordination):** Provides real-time visibility into whether concurrent agent forks compose cleanly against each other and canonical HEAD. Solves HN's #1 complaint ("one-third of time spent helping agents merge", E-C103).
2. **A04: Semantic Contract Sentinel / CIP (F1/F4 - Verification):** Language-level invariant checking that catches clean textual merges with broken runtime behavior (Codex fixture `merge-fixture.py`, E-A001).
3. **A12: Ephemeral Quarantine Forks & Dual-Phase Promotion / EQ-2PP (F5 - Architecture/Security):** Shards agents into isolated Artifacts forks, restricting write capabilities to prevent canonical repo corruption (E-A004, E-C138).
4. **A14: Preview-per-Agent Runtime Isolation (F6 - UX/Runtime):** Gives each active agent an ephemeral live preview URL and isolated D1/KV storage, solving runtime collisions (E-X002, E-C321).
5. **A16: Zero-Checkout Workspaces / CARE (F7 - Storage):** Moves agent workspaces to Cloudflare Sandboxes and Artifacts, solving User Message 7 storage amplification.
6. **A03: Merged-State Gate with Bounded Repair (F1 - Correctness):** When a candidate breaks canonical composition, executes an automated, single-turn bounded repair against the new canonical base instead of looping or prompting blindly.

---

## 7. Primary Build Direction Recommendation

**Recommended Direction:** Build the unified **Edge-Native Autonomous Integration Platform (ENAIP)**, combining:
- **Foundation:** Ephemeral Quarantine Forks (A12) with Zero Local Storage Amplification (A16).
- **Core Engine:** Speculative Merged-State Gate (A03) with Checkable Invariant Probes (A04) and signed runner receipts (A09).
- **Surface / Demo:** Live Integration Radar (A01) with Per-Agent Preview URLs (A14).

This direction:
- Satisfies all competition constraints: 100% compliant with Cloudflare Workers + Artifacts primitives.
- Maximizes the 50% Originality score: introduces a novel edge-native invariant gating architecture that GitHub and existing merge queues cannot replicate.
- Solves the user's primary first-hand pain (Message 7): eliminates local worktree disk bloat by running agents in remote quarantine.
- Delivers an irresistible 5–10 minute video demo: three concurrent agents write code simultaneously; Radar shows real-time composition; previews show live isolated apps; a semantic bug is caught by CIP and automatically healed by bounded repair; clean code fast-forwards into canonical HEAD.

---

## 8. Decisions, Tradeoffs, and Kill Tests

| ID | Decision | Alternatives Considered | Tradeoff / Cost | Falsification / Kill Test |
|---|---|---|---|---|
| **D-A01** | Replace "CEIP Proofs" with Checkable Invariant Probes (CIP) | LLM self-generated proofs, natural language summaries | Requires real test runner execution; cannot rely on raw model claims | If deterministic test execution in runner adds >90s latency per push, optimize probe suite or kill. |
| **D-A02** | Reject A07 (Maintainer quarantine) and A05 (Tournament) from shortlist | Include them to match Claude's draft top 6 | Discards flashy PR-oriented demos | If user explicitly directs focus toward OSS inbound contribution over internal multi-agent teams, reopen A07. |
| **D-A03** | Elevate A16 (Storage) into the shortlist as Cloudflare Remote Execution (CARE) | Treat storage as purely local tooling problem (pnpm/reflink) | Requires demonstrating remote agent sandbox execution | If remote Artifacts fetch latency exceeds local disk checkout time by >5x, pivot to task-scoped sparse checkout. |
| **D-A04** | Use Native Git in Platform Runner for merges and CIP execution | Implement `isomorphic-git` inside Worker DO | Needs an external container/CI runner (cannot run entirely inside 128MB DO) | If Cloudflare CI / Sandbox runner cannot be orchestrated via Worker binding by Oct 8, fall back to local authenticated coordinator. |

---

## 9. Next Operational Steps for Antigravity

1. Send compact durable critique messages to `claude-principal` and `codex-principal` via `aplexer message send`.
2. Await explicit peer responses and incorporate feedback into bilateral consensus.
3. Prepare scoped worktree guidance for delegated ZCode executors once the 6-approach shortlist reaches genuine bilateral sign-off.
4. Record major decisions and events under flock `.local/events.lock` in `experiment/events.jsonl`.
5. Maintain continuous standup reporting in `experiment/standups/YYYY-MM-DD.md`.
