# Antigravity coordination

Session: aplexer tag `antigravity-head` (`2bb80c81-0c15-4577-8ba7-27e56a3c98ec`), engine `agy` / Gemini 3.8 Flash, workspace `/home/alexey/git/cloudflare-agent-git`.
Peers: `claude-principal` (`92336dc8-cc9a-4c14-a49b-8eef0780cf4b`), `codex-principal` (`338df944-a3fc-4973-9ed0-17708c73769c`), `grok-head` (`3b664830-1a4f-4f30-ba94-67828f32021c`), `space-bunny-head` (`30aaf73a-2b18-4c1f-8969-09688833299d`), `muse-reviewer` (`a1d6b8f3-2139-49a8-a32a-785386dbb389`), `zcode-independent` (`d54c1e11-6ce5-4f5a-b989-15ea2f6b013d`).

---

## 1. Ownership & Boundaries
- **Antigravity owns:** `research/antigravity/`, `coordination/antigravity.md`, future isolated worktrees / execution lanes.
- **Peers own:**
  - Claude: `research/claude/`, `coordination/claude.md`, `research/approaches-20.md`, `research/evidence-ledger.md` (integrator).
  - Codex: `research/codex/`, `coordination/codex.md`, `research/shortlist-6.md`, `research/consensus.md` (integrator).
  - Grok: `research/grok/`, `coordination/grok.md`.
  - Other heads: their respective `research/<role>/` and `coordination/<role>.md` directories.
- Antigravity grants permission to Claude and Codex to reference or copy E-A### evidence into integrated ledgers without editing `research/antigravity/`.

---

## 2. Round 1 Deliverables (Completed 2026-10-02)
- **`research/antigravity/evidence.md`**: Evidence ledger E-A001..E-A008 covering multi-agent concurrency bugs misdiagnosed as model degradation (E-A001), runaway agent code generation and abstract merge conflicts (E-A002), harness engineering requirements (E-A003), Artifacts physical API constraints (E-A004..E-A006), and competition scoring rules (E-A008).
- **`research/antigravity/independent-challenge.md`**: Comprehensive independent challenge:
  - Deconstruction of the 3 fatal fallacies: Air-Traffic Control UI, PR-centric contribution model, and syntax-only merging.
  - Critique of Claude's Seed 22 ("re-derive don't rebase": nondeterminism, latency, scope creep).
  - Critique of Codex's provisional direction ("intent reapplication + exact-SHA": prior art collision with Foremerge + GitHub Merge Queue, lack of edge differentiation, exact-SHA invalidation fragility).
  - Cloudflare execution reality: no server-side merge API, non-blocking post-hoc events, 128MB DO memory limits, prohibition of single-shared-queue repos.
  - Three distinct edge-native paradigms:
    1. *Ephemeral Quarantine & Dual-Phase Promotion (EQ-2PP)*
    2. *Contract-Enforced Invariant Proofs (CEIP) & Semantic Gating*
    3. *Speculative Concurrency Matrix (SCM) via Edge Probing*
  - Primary recommended build direction: EQ-2PP + CEIP.

---

## 3. Round 2 Deliverables (Completed 2026-10-02)
- **`research/antigravity/round-2-challenge.md`**: Comprehensive Round 2 challenge, calibration, and architectural synthesis:
  - **Calibration with User Steering:** Integrates User Message 6 (wide exploration + separate contest from LTV) and Message 7 (worktree storage amplification crisis).
  - **Dismantling Claude's Provisional Top 6:** Deconstructs why A07 (Maintainer quarantine), A05 (Fork tournament), A13 (Session undo), and A19 (Maintenance swarm) are demo toys with weak pain, zero buyer migration, or commodity prior art.
  - **Storage Amplification Solution (A16 / CARE):** Synthesizes ext4 benchmark results (reflink unsupported; dependencies/build caches account for 75-80% of bytes). Explains why local sparse checkout underdelivers (~18% net savings) and introduces **Cloudflare Artifacts Remote Execution (CARE)**: executing agents in remote Cloudflare Sandboxes/forks keeps local workspace amplification at exactly 1.0x.
  - **Refinement of Antigravity Paradigms:**
    - Refines CEIP to **Checkable Invariant Probes (CIP)**: platform-owned executable test/type assertions in trusted runners with cryptographic Git Notes receipts (A09), eliminating reliance on untrusted model self-claims.
    - Refines **EQ-2PP**: combines remote ephemeral sandboxes (solving U7) with speculative trial merging and bounded single-turn repair (solving E-X004 clean-merge failures).
  - **Independent Scoring of All 20 Approaches:** Complete evaluation matrix across Pain, Orig, Conc, UX, Feas, CF, and LTV.
  - **Recommended 6-Approach Shortlist:**
    1. A01: Live Integration Radar (F1)
    2. A04: Semantic Contract Sentinel / CIP (F1/F4)
    3. A12: Ephemeral Quarantine & Dual-Phase Promotion / EQ-2PP (F5)
    4. A14: Preview-per-Agent Runtime Isolation (F6)
    5. A16: Zero-Checkout Workspaces / CARE (F7)
    6. A03: Merged-State Gate with Bounded Repair (F1)
  - **Primary Build Direction:** Unified *Edge-Native Autonomous Integration Platform (ENAIP)*.
- **`research/antigravity/evidence.md`**: Updated with E-A009..E-A012 covering ext4 storage benchmarks, curl maintainer testimony against forge-switching, Foremerge/Graphite prior art collision, and deterministic invariant probe validity.

---

## 4. Durable Messages Log
- **Round 1 Dispatched Critiques:**
  - `A-R1-CHALLENGE-CLAUDE` (`01a0fde0-109b-79b2-b7d2-dc2f95783225`): Sent to `claude-principal`.
  - `A-R1-CHALLENGE-CODEX` (`01a0fde0-1c78-7412-be5f-3edf65875396`): Sent to `codex-principal`.
- **Round 1 Received & Acknowledged:**
  - `01a0fdde-3579-7a32-a86a-26dadee77210` from `orchestrator-relay`: Replied (`01a0fde0-ad51`); ACKed.
  - `01a0fdde-99c3-7780-8a5a-c62a1243827b` from `codex-principal`: Replied (`01a0fde0-b877`); ACKed.
  - `01a0fddf-8abd-7353-bd83-9ebd9ead8f19` from `orchestrator-worktree-pain`: Replied (`01a0fde0-c764`); ACKed.
  - `01a0fde1-68e4-7872-8f52-bfdd59ba0bc1` from `claude-principal`: Round 1 challenge response and critique of EQ-2PP / CEIP; ACKed.
  - `01a0fde1-98e3-7952-879b-520cf638e8f3` from `codex-principal`: Round 1 challenge response in `codex-round-1-external-responses.md`; ACKed.
- **Round 2 Dispatched Critiques:**
  - `A-R2-CHALLENGE-CLAUDE` (`01a0fde5-877e-74d3-86fa-9f58a3f3b505`): Dispatched with critique of provisional top 6, presentation of CIP refinement, and demand to elevate A16/A04/A12.
  - `A-R2-CHALLENGE-CODEX` (`01a0fde5-938b-76d2-9043-35f44febd3ae`): Dispatched with response to `codex-round-1-external-responses.md`, ext4 storage analysis, and proposed shortlist alignment.

---

## 5. Decisions & Status
- **D-A01:** Replaced "CEIP Proofs" with Checkable Invariant Probes (CIP) backed by trusted runner cryptographic receipts in Git Notes.
- **D-A02:** Rejected A07 (Maintainer quarantine) and A05 (Fork tournament) from shortlist due to zero buyer migration in OSS and commodity prior art.
- **D-A03:** Elevated A16 (Storage) as Cloudflare Artifacts Remote Execution (CARE) into top shortlist to directly solve User Message 7.
- **D-A04:** Retained A03 (Merged-State Gate) but scoped to single-turn bounded repair rather than full open-ended "re-derive".
- **Current Milestone:** Round 2 independent challenge complete and published; critiques dispatched to principals. Awaiting bilateral response. Next: guide scoped ZCode executors once consensus shortlist is signed.
