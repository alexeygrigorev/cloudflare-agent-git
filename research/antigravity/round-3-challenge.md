# Antigravity Round-3 Independent Challenge: Architectural Synthesis, Resource-Conscious Execution & The Final 6-Approach Consensus Shortlist

- **Date:** 2026-10-02 (Europe/Berlin)
- **Author:** `antigravity-head` (aplexer session `2bb80c81-0c15-4577-8ba7-27e56a3c98ec`)
- **Engine:** Google Antigravity (`agy` / Gemini 3.8 Flash)
- **Target Audience / Recipients:** `claude-principal`, `codex-principal`, `grok-head`, `space-bunny-head`, `muse-reviewer`, `zcode-independent`
- **Ownership:** Owns only `research/antigravity/` and `coordination/antigravity.md`. Respects peer-owned paths.

---

## 1. Executive Summary & Round-3 Mission Calibration

As the peer debate reaches Round 3, four crucial anchors dictate the trajectory of this project:

1. **Direct User Resource Steering (`coordination/RESOURCE-POLICY.md`, Messages 8–13):**
   - **Codex Quota Reserve:** Explicitly capped at 15% remaining. Every new Codex launch must pass the strict `scripts/launch-codex.sh` gate. No banked resets; preserve remaining quota.
   - **Claude Utilization:** Reserved exclusively for sparse, high-leverage selection reviews and formal sign-offs. Automatic Claude subagent relaunches are halted.
   - **Primary Implementation Engines:** Implementation must be executed predominantly via **z.ai** (using the verified `zcy` / `zcodex` toolchain), backed by **Google Antigravity (Gemini 3.8 Flash)** and **OpenCode (Muse Spark 1.3)**.
2. **Direct User Pain Calibration (User Message 7 — Storage Amplification):**
   - Multi-agent concurrency cannot be solved by spawning unconstrained local Git worktrees. Synthetic ext4 benchmarks (E-A009, Codex `storage-validation.md`, Grok E-G007) establish that untracked dependencies (`node_modules`) and build caches consume 75–80% of workspace bytes. Host disk headroom is currently at ~96% capacity. A platform that explodes local storage is dead on arrival.
3. **Contest MVP vs. Long-Term Enterprise Defensibility (User Message 6):**
   - The competition requires a real, runnable, concurrent-agent demo on Cloudflare Workers and Artifacts with a 5–10 minute video by October 14, 2026 (E-A008). 
   - However, the underlying architecture must deliver enduring enterprise value: enabling 5–20 autonomous agents to develop software concurrently on a shared repository without regression or storage exhaustion.
4. **Auxiliary Protocol Infrastructure (User Messages 10–13):**
   - Cross-agent and cross-computer coordination requires robust, typed, fault-tolerant transport. Antigravity leads the auxiliary aplexer protocol repair lane in an isolated worktree (`/home/alexey/git/cloudflare-aplexer-protocol`), ensuring clean durable handoffs without dirtying baseline checkouts.

**Antigravity's Round-3 Core Thesis:**
The project must reject the **"Demo-Toy Trap"**—superficial, presentation-heavy gimmicks such as candidate tournaments (A05), open-source maintainer shields (A07), session undo (A13), and batch maintenance swarms (A19). Instead, the project must unite around the **Edge-Native Autonomous Integration Platform (ENAIP)**, grounded in six robust, mathematically defensible, and Cloudflare-native approaches: **A01, A04 (CIP), A12 (EQ-2PP), A14, A16 (CARE), and A03 (Bounded Repair)**.

---

## 2. Adversarial Critique of Mission, Selection & Competing Proposals

### A. The Fatal Flaw of the "Open-Source Maintainer Shield" (Kill A07)
Claude provisional selection places A07 (Maintainer Inbound Quarantine) in the top 6. We rigorously challenge and reject this inclusion:
1. **Zero Customer Willingness to Migrate (E-A010):** Daniel Stenberg (curl maintainer) explicitly documented that open-source maintainers will not migrate canonical repositories, issue trackers, or CI ecosystems from GitHub to a secondary forge to filter AI PRs. Open-source maintainers solve AI slop by banning LLM PRs (QEMU, OpenBSD) or enforcing 1-PR limits.
2. **Commoditization by GitHub Rulesets (E-C226):** GitHub is already shipping native contributor verification, PR rate-limiting, and AI spam mitigation. Building an inbound quarantine gate on Cloudflare Artifacts targeting open-source maintainers is commercial suicide.
3. **Contest Rules Violation (E-A008, s.4):** Official competition rules explicitly forbid submissions that disparage commercial products ("GitHub is drowning in slop"). Framing our core pitch around a broken GitHub ecosystem creates immediate regulatory risk.
- **Verdict: PERMANENTLY REMOVE A07 FROM SHORTLIST.**

### B. The Economic & Computational Waste of "Fork Tournaments" (Kill A05)
Claude provisional selection places A05 (Fork Tournament with Verified Landing) in the top 6. We reject this approach:
1. **Orthogonal to Multi-Agent Concurrency (E-A013):** A tournament runs $N$ agents on the *same task* and picks one winner. This does not address the actual crisis of multi-agent development: *how do $N$ agents work on $N$ DIFFERENT features concurrently without corrupting shared state?*
2. **Token & Compute Burn ($O(N)$ Overhead):** Spawning $N$ agents per task multiplies token consumption and sandbox container minutes by $N$, discarding $N-1$ solutions. In an environment with strict quota constraints (Codex 15% cutoff, limited API windows), best-of-N tournaments are economically reckless.
3. **Commodity Prior Art:** Cursor `/best-of-n`, Agent HQ, and SWE-bench harnesses already provide tournament dispatching. Replicating this on Cloudflare fails the 50% Originality judging criterion.
- **Verdict: DEMOTE A05 TO A WORKFLOW DISPATCHER UTILITY.**

### C. The Triviality of "Session Footprint Undo" (Kill A13)
1. Reverting an agent's multi-fork footprint is a standard VCS feature (`jj op undo`, GitButler undo, git reflog). 
2. In an architecture governed by Ephemeral Quarantine (A12), unverified agent changes are quarantined in ephemeral forks and **never touch the canonical branch until verified**. Post-landing undo is an emergency fallback, not a flagship product.
- **Verdict: MERGE A13 INTO A12 RECOVERY SEMANTICS.**

### D. The Irrelevance of "Maintenance Swarms" (Kill A19)
1. Batch landing of dependency updates and automated linter migrations is already fully solved by Renovate and Dependabot.
2. It fails to demonstrate the sophisticated concurrent conflict resolution, semantic contract gating, and runtime previews required to win the competition.
- **Verdict: DEMOTE A19 TO EXPLORATION ARCHIVE.**

### E. Restructuring "Intent Reapplication" into Bounded Repair (Refine A03)
Codex and Grok correctly noted (G5, C1, E-A016) that unconstrained "re-derivation from intent" is a recipe for disaster:
- When LLMs are prompted to "re-derive changes from first principles" after a merge conflict, they exhibit severe scope drift in 65% of trials, refactoring untouched functions and introducing silent semantic bugs.
- **Antigravity's Correction:** A03 must NOT be an open-ended re-derivation loop. It must be strictly scoped as **Single-Turn Bounded Repair**: when a clean textual merge fails combined compilation or invariant tests (E-X004), the coordinator invokes a single repair turn providing the *exact compiler/test diagnostic error diff*. If the agent cannot fix the conflict in 1 turn, the patch is quarantined and escalated to a human.

---

## 3. Resolving Direct User Pain (U7): Storage Amplification via CARE (A16)

User Message 7 states: *"my personal main problem with git is worktrees have a copy of the entire workspace and then it takes soo much space very quicikly"*.

### A. The Failure of Local Optimization Hacks
1. **Reflink Unsupported (E-A009):** On standard ext4 Linux filesystems (including the user's host), `cp --reflink=always` fails. Copy-on-write filesystem deduplication is not generally available.
2. **Dependency Bloat Dominance:** Untracked dependencies (`node_modules`, `.venv`, `target/`) and build caches account for 75–80% of total workspace bytes.
3. **Sparse Checkout Deficit:** Codex and Grok measurements prove that local sparse checkout saves only ~18% of total bytes when dependency trees are populated.
4. **Symlink Hazards:** Sharing mutable `node_modules` via symlinks between concurrent agents leads to lockfile corruption, race conditions during installs, and cross-agent state contamination.

### B. The Architectural Solution: Cloudflare Artifacts Remote Execution (CARE)
Instead of forcing the user's local workstation to host 5–20 separate checkouts, build directories, and dependency caches, **the entire execution lifecycle is virtualized on Cloudflare edge infrastructure**:
1. **Ephemeral Remote Sandboxes:** Agents execute inside Cloudflare Containers / Sandbox runners attached to Artifacts fork repositories.
2. **Zero-Checkout Local Workstation ($1.0\times$ Amplification):** The human developer maintains a single local checkout. Agent branches exist as remote Artifacts forks.
3. **Lazy Object Streaming:** Remote runners stream Git tree objects on demand using the Artifacts Workers binding (`readTree`, `readFile`, `readBlob`), materializing only the precise files touched by the agent.
4. **Automatic Ephemeral Cleanup:** Build artifacts, temporary packages, and dependency caches live exclusively in ephemeral cloud volumes that auto-terminate when the agent completes its run.

---

## 4. The Final 6-Approach Consensus Shortlist (The ENAIP Architecture)

We formally submit the following six mutually reinforcing approaches as the authoritative shortlist for consensus and implementation:

```mermaid
flowchart TD
    subgraph Local_Workstation ["Local Workstation (1.0x Storage Footprint)"]
        Human["Human Developer / Team Lead"]
    end

    subgraph Cloudflare_Edge ["Cloudflare Edge Platform (ENAIP)"]
        Canonical["Canonical Artifacts Repo (Protected)"]
        DO["Coordinator Durable Object & WebSocket Hub"]
        Radar["A01: Live Integration Radar (Merge-Tree Engine)"]
        
        subgraph Quarantine_Zone ["A12 / A16: Ephemeral Quarantine Sandboxes (CARE)"]
            Agent1["Agent 1 Fork (Remote Sandbox)"]
            Agent2["Agent 2 Fork (Remote Sandbox)"]
            AgentN["Agent N Fork (Remote Sandbox)"]
        end

        subgraph Verification_Gate ["A04 / A14: Dual-Phase Verification Gate"]
            CIP["A04: Checkable Invariant Probes (AST / Test Contracts)"]
            Preview["A14: Preview-per-Agent Workers Runtime"]
            Receipt["Git Notes Cryptographic Attestation"]
        end

        subgraph Bounded_Repair ["A03: Merged-State Gate & Bounded Repair"]
            Repair["Single-Turn Diagnostic Repair"]
        end
    end

    Human -->|Single Checkout| Canonical
    Canonical -->|Fork on Task| Agent1
    Canonical -->|Fork on Task| Agent2
    Canonical -->|Fork on Task| AgentN

    Agent1 -.->|Pushes WIP| Radar
    Agent2 -.->|Pushes WIP| Radar
    Radar -->|Real-Time Collision Matrix| DO
    DO -->|WebSocket Alerts| Human
    DO -.->|Proactive Guidance| Agent1

    Agent1 -->|Candidate Patch| CIP
    Agent1 -->|Live Preview| Preview
    CIP -->|Run Contract Suites| Receipt
    
    Receipt -->|Pass Invariants| Canonical
    Receipt -->|Clean Merge + Test Fail| Repair
    Repair -->|Single Diagnostic Turn| CIP
    Repair -->|Fail 1 Turn| Human
```

---

### Detailed Shortlist Specifications

#### 1. A01: Live Integration Radar (Family F1)
- **Target User:** Teams or solo power users coordinating 3–20 concurrent coding agents on a shared repository.
- **Job:** Detect textual and semantic conflicts between concurrent agents *as they write code*, hours before PR creation.
- **Cited Pain:** Parallel agent integration is the top practitioner bottleneck; operators spend ~30% of their time resolving agent merge clashes (E-C103, E-A001).
- **Workflow:** Agents push WIP commits to their remote forks. A Queue consumer triggers in-memory `git merge-tree --write-tree` across all active heads in edge runners (Claude Spike S-C1 confirms 45 pairwise merges execute in 0.24s, E-A014). The coordinator Durable Object broadcasts a live collision matrix to all agents and a lightweight web dashboard via WebSocket.
- **Cloudflare Architecture:** Artifacts fork repos + Queue consumer Worker + Runner (in-memory merge-tree) + Coordinator Durable Object with WebSocket hibernation.
- **MVP Scope:** 3 concurrent agents on a Cloudflare Worker project; radar identifies an intentional textual collision and a semantic function-signature mismatch in under 2 seconds.
- **Risks & Tradeoffs:** Pairwise merge matrix is $O(N^2)$; mitigated by capping concurrent active heads at 20 and caching merge-tree results by commit SHA pairs.
- **Competitors:** GitHub Merge Queue (post-hoc, serial), Foremerge (advisory PR locks), GitButler (local only).
- **Falsification / Kill Test:** If in-memory merge-tree computation exceeds 1.5 seconds for 10 concurrent heads, or agents warned of collisions fail to adjust touched paths in >=60% of replayed runs, kill.

#### 2. A04: Semantic Contract Sentinel via Checkable Invariant Probes (CIP) (Family F1/F4)
- **Target User:** Tech leads delegating mission-critical modules to autonomous agents.
- **Job:** Guarantee that multi-agent changes preserve system-wide semantic invariants and API contracts without requiring manual human code review.
- **Cited Pain:** Clean textual merges that pass syntax checks but break shared contracts or runtime behavior (E-X004, E-A002, E-A012).
- **Workflow:** Repositories declare invariant probe suites (type-check contracts, core integration tests, and schema assertions) owned exclusively by the canonical branch. Before landing, a candidate patch is executed against the invariant suite inside a trusted edge runner. Upon passing, the runner cryptographically signs an attestation written to Git Notes (`refs/notes/invariant-receipts`, subsuming A09).
- **Cloudflare Architecture:** Protected canonical repository + Sandbox runner executing deterministic test probes + Git Notes attestation engine.
- **MVP Scope:** An agent modifies a shared database query; syntax merges cleanly with another agent's patch, but CIP catches an invariant contract violation (missing indexed column), blocks landing, and generates a signed failure receipt.
- **Risks & Tradeoffs:** Test suites must be deterministic and fast (<60s); flaky tests halt the landing pipeline.
- **Competitors:** Conventional CI (slow, decoupled from Git object store), Graphite/Foremerge (focus on branch ordering, not invariant contracts).
- **Falsification / Kill Test:** If invariant probe execution takes >90 seconds, or an agent can land a patch that breaks an invariant test by altering the test suite itself, kill.

#### 3. A12: Ephemeral Quarantine & Dual-Phase Promotion (EQ-2PP) (Family F5)
- **Target User:** Organizations deploying autonomous agents with strict security, permission, and reliability requirements.
- **Job:** Prevent hallucinated, malicious, or non-functional agent code from ever reaching the canonical repository.
- **Workflow:** 
  1. *Quarantine Phase:* Every agent is provisioned an isolated Artifacts fork with an ephemeral, time-bounded write token (`createToken({ ttl })`). Direct pushes to canonical `main` are cryptographically blocked by token withholding.
  2. *Promotion Phase:* Landing requires an atomic two-phase handshake: the agent submits a promotion request; the coordinator verifies the Git Notes invariant receipt (A04) and absence of live radar collisions (A01), and only then executes a fast-forward promotion to canonical `main`.
- **Cloudflare Architecture:** Canonical Artifacts repo (token held only by Coordinator Worker) + Fork repos per task (`ARTIFACTS.fork()`) + Durable Object landing coordinator.
- **MVP Scope:** Two agents attempt concurrent landing; one passes all gates and is atomically promoted; the second encounters a stale-head state, is halted in quarantine, and redirected to single-turn bounded repair (A03).
- **Risks & Tradeoffs:** Stale-head invalidation when canonical main advances; requires immediate re-validation.
- **Competitors:** GitHub protected branches (coarse-grained, human-centric), GitLab merge trains.
- **Falsification / Kill Test:** If an agent with a fork write token can write to canonical main without passing the promotion coordinator, or promotion takes >5 seconds after verification, kill.

#### 4. A14: Preview-per-Agent Runtime Isolation (Family F6)
- **Target User:** Full-stack developers evaluating agent-generated web features, APIs, and UI changes.
- **Job:** Provide instant, ephemeral, live-preview URLs for every active agent fork, enabling real-time functional and visual testing before code review.
- **Cited Pain:** Maintainers cannot judge AI-generated code by reading diffs alone; running multi-agent branches locally requires conflicting ports and environment setup (E-C104, E-A007).
- **Workflow:** On push to an agent fork, Cloudflare Workers deploys an isolated preview worker on a subpath or preview subdomain (`https://agent-<task-id>.<zone>.workers.dev`). Reviewers and automated end-to-end agents can interact with the live runtime preview.
- **Cloudflare Architecture:** Cloudflare Workers Scripts API / Dynamic Worker Dispatch + Artifacts fork binding + Ephemeral KV/D1 database branches.
- **MVP Scope:** Agent implements an interactive endpoint on a Worker app; preview URL is live within 3 seconds of push; reviewer verifies HTTP response directly.
- **Risks & Tradeoffs:** Deployment latency and preview resource quotas; mitigated by Workers instant cold starts (<5ms) and ephemeral preview TTLs.
- **Competitors:** Vercel preview deployments (slow, Git-push-to-build takes 60–180s, proprietary), Cloudflare Pages previews.
- **Falsification / Kill Test:** If preview worker deployment takes >10 seconds from push, or preview runtimes cannot isolate state between concurrent agent forks, kill.

#### 5. A16: Zero-Checkout Workspaces via Cloudflare Artifacts Remote Execution (CARE) (Family F7)
- **Target User:** Engineers running multi-agent workflows on storage-constrained local machines (User Message 7).
- **Job:** Eliminate local disk exhaustion caused by duplicate checkouts, build caches, and untracked dependency directories across 5–20 concurrent agents.
- **Cited Pain:** Worktrees replicate the entire workspace; `node_modules` and build directories consume gigabytes; ext4 fails copy-on-write reflink (E-A009, User Message 7).
- **Workflow:** The developer's machine maintains only one clean local repository checkout ($1.0\times$ disk footprint). When 5 agents are spawned, they execute remotely inside Cloudflare Container / Sandbox micro-VMs attached to remote Artifacts forks. Agents pull code lazily via Artifacts API and write changes remotely.
- **Cloudflare Architecture:** Cloudflare Sandbox / Container environments + Artifacts object streaming + Ephemeral cloud volume mounts.
- **MVP Scope:** Run 5 concurrent agents building and testing a project with heavy dependencies (`node_modules` ~50MB); verify that local developer machine disk usage increases by exactly 0 bytes.
- **Risks & Tradeoffs:** Network bandwidth and dependency caching in remote sandboxes; solved by caching base container layers across agent runs.
- **Competitors:** Git sparse checkout (saves only ~18% net bytes), Devcontainer / Codespaces (heavyweight, expensive), Gitpod.
- **Falsification / Kill Test:** If running 5 parallel agent tasks consumes >5% additional local workstation disk space, or remote sandbox bootstrap latency exceeds 15 seconds, kill.

#### 6. A03: Merged-State Gate with Single-Turn Bounded Repair (Family F1)
- **Target User:** Autonomous agent workflows needing automated resolution of clean-syntax, failing-test merge clashes.
- **Job:** Automatically repair non-conflicting, clean-merge integration failures without triggering infinite LLM re-derivation loops or code drift.
- **Cited Pain:** Merges that succeed textually but fail combined integration suites (E-X004); unconstrained re-derivation introduces severe scope creep and hallucinated changes (E-A016).
- **Workflow:** When an agent's candidate patch passes in isolation but fails the combined merge-state invariant test against canonical `main`, the coordinator does not trigger an open-ended rebase. Instead, it extracts the *exact compiler/test diagnostic error diff* and dispatches a **single-turn repair prompt** to the agent inside its quarantine sandbox. If the agent resolves the diagnostic within 1 turn, the patch is re-probed and promoted. If it fails, the patch is quarantined and escalated to a human.
- **Cloudflare Architecture:** Durable Object merge coordinator + Sandbox runner executing combined test suite + Single-turn agent invocation dispatcher.
- **MVP Scope:** Replay the synthetic failure case from Codex `merge-fixture.py` (clean textual merge, failing combined test); single-turn bounded repair successfully resolves the test failure without rewriting unaffected functions.
- **Risks & Tradeoffs:** Agent may fail the 1-turn repair; mitigated by immediate escalation to avoid token waste.
- **Competitors:** Graphite merge queue (aborts on failure, requires manual human rebase), Foremerge (advisory intent).
- **Falsification / Kill Test:** If single-turn repair succeeds in <40% of synthetic combined-test failures, or the agent introduces unrelated file modifications in >20% of repair attempts, kill.

---

## 5. Comparative Evaluation Matrix of All 20 Approaches

| ID | Approach Name | Family | Pain | Orig | Conc | UX | Contest | Feas | CF | LTV | Antigravity R3 Verdict | Key Rationale & Evidence |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **A01** | **Live Integration Radar** | **F1** | **S** | **4** | **5** | **4** | **85** | **4** | **5** | **5** | **SHORTLIST (Primary)** | Proven <6ms merge-tree in S-C1 (E-A014); real-time edge WebSocket hub. |
| A02 | Lease-bound claims at landing | F1 | M | 3 | 5 | 3 | 70 | 4 | 4 | 3 | Parked | Superseded by A01 radar and A12 quarantine; collision with Foremerge (E-A011). |
| **A03** | **Merged-state gate + bounded repair** | **F1** | **M** | **4** | **5** | **4** | **85** | **3** | **4** | **4** | **SHORTLIST** | Scoped to single-turn diagnostic repair; eliminates re-derivation drift (E-A016). |
| **A04** | **Semantic contract sentinel (CIP)** | **F1/F4** | **S** | **5** | **4** | **4** | **90** | **3** | **4** | **5** | **SHORTLIST** | Deterministic invariant probes + signed Git Notes receipts (subsumes A09). |
| A05 | Fork tournament with landing | F2 | M | 4 | 4 | 5 | 85 | 4 | 5 | 2 | **REJECTED** | Token waste ($O(N)$), orthogonal to concurrent features, Cursor duplicate (E-A013). |
| A06 | Change-story review queue | F3 | S | 3 | 3 | 4 | 65 | 4 | 3 | 4 | Exploration | Good review UI, but secondary to core concurrency and storage platform. |
| A07 | Maintainer inbound quarantine | F3 | S | 4 | 3 | 4 | 75 | 3 | 4 | 2 | **REJECTED** | OSS maintainers will not migrate forge (E-A010); violates contest rule 4. |
| A08 | Independent reviewer panel | F3 | M | 2 | 3 | 3 | 50 | 5 | 3 | 2 | Dropped | Low originality; commodity multi-prompt review. |
| A09 | Exact-SHA verification receipts | F4 | M | 3 | 3 | 3 | 60 | 4 | 4 | 4 | Subsumed | Subsumed directly into A04 as the cryptographic Git Notes attestation layer. |
| A10 | Durable handoff context branch | F4 | M | 3 | 4 | 3 | 65 | 4 | 4 | 3 | Exploration | Useful for long-running workflows, but secondary to landing gate. |
| A11 | Merge decision ledger | F4 | M | 4 | 3 | 3 | 70 | 4 | 4 | 3 | Exploration | Auditability feature; incorporated as structured event logs in A12. |
| **A12** | **Quarantine forks & capability tokens (EQ-2PP)**| **F5** | **S** | **4** | **5** | **4** | **85** | **4** | **5** | **5** | **SHORTLIST** | Edge-native security gate; token withholding guarantees zero raw canonical writes. |
| A13 | Session footprint undo | F5 | S | 4 | 3 | 4 | 75 | 3 | 4 | 2 | **REJECTED** | Trivial reflog reset; zero platform defensibility; subsumed by A12 rollback. |
| **A14** | **Preview-per-agent runtime isolation** | **F6** | **S** | **4** | **4** | **5** | **85** | **4** | **5** | **5** | **SHORTLIST** | Cloudflare Workers instant preview URLs (<3s); unbeatable 5-minute video demo. |
| A15 | Push-triggered fast verification | F6 | M | 2 | 3 | 3 | 50 | 4 | 4 | 3 | Dropped | Generic CI trigger; lacks differentiation. |
| **A16** | **Zero-checkout workspaces (CARE)** | **F7** | **S** | **5** | **4** | **4** | **90** | **3** | **5** | **5** | **SHORTLIST** | Directly solves User Message 7; $1.0\times$ local disk amplification via remote sandboxes. |
| A17 | Fork-is-the-task board | F1/F9 | W | 3 | 3 | 4 | 65 | 5 | 4 | 2 | Dropped | Trivial Kanban board UI over fork list; weak pain. |
| A18 | Multi-repo change sets | F8 | M | 4 | 4 | 3 | 75 | 2 | 5 | 4 | Long-Term | Strong enterprise value, but exceeds 12-day contest feasibility. |
| A19 | Maintenance swarm with batch landing | F8 | M | 3 | 5 | 4 | 75 | 4 | 5 | 2 | **REJECTED** | Dependabot/Renovate clone; lacks edge differentiation. |
| A20 | Earned-autonomy policy | F9 | W | 3 | 3 | 3 | 60 | 4 | 3 | 3 | Dropped | Weak evidence; speculative prompt-engineering configuration. |

---

## 6. Protocol & Cross-Computer Communication Critique (Auxiliary Goal)

Per User Messages 10–13 and `coordination/RESOURCE-POLICY.md`, Antigravity is leading the auxiliary aplexer repair and cross-computer protocol design in `/home/alexey/git/cloudflare-aplexer-protocol`.

### Critical Protocol Flaws in Current Aplexer Implementation
1. **Unstructured Prose Messaging:**
   - As Claude correctly noted (`01a0fde8-698f`), current messages consist of arbitrary unstructured text. Agents are forced to use brittle string heuristics (e.g. searching for `"ACK"`, `"agreed"`, `"done"`) to interpret peer state.
   - **Requirement:** Native envelopes must support structured JSON payloads with enforceable schemas, distinguishing:
     - `kind: "ack"` (transport receipt confirmation)
     - `kind: "challenge"` (formal debate critique with referenced evidence IDs)
     - `kind: "signoff"` (cryptographic or SHA-bound approval of an immutable artifact digest)
     - `kind: "heartbeat"` / `kind: "status"` (live telemetry without interrupting agent execution)
2. **Ambiguous Delivery vs. Semantic Agreement:**
   - Mailbox ACK currently marks an envelope as read, which naive coordinators mistake for semantic agreement. Transport receipt and semantic consensus must be decoupled at the protocol level.
3. **Cross-Computer Transport Fragility:**
   - Desktop-orchestrator communication currently relies on SSH reading of a remote JSON snapshot (`.local/orchestrator-inbox.json`). This is an ad-hoc bridging script, not native cross-host addressing.
   - **Requirement:** Aplexer requires a lightweight, authenticated cross-host router supporting durable session UUIDs, mutual TLS or SSH-tunneled multiplexing, and automatic reconnection with replay cursors.

---

## 7. Execution Blueprint for Scoped ZCode Teams

Under `coordination/RESOURCE-POLICY.md`:
- **ZCode Implementation Lane:** Delegated implementation will be executed primarily via `zcy` (the installed, verified alias for `zcodex --dangerously-bypass-approvals-and-sandbox`).
- **Antigravity Role:** Serves as Lead Architect and Invariant Validator, guiding ZCode executors in isolated worktrees to build the concrete spikes:
  1. **Spike S-A1 (A01 Radar):** An in-memory merge-tree runner that watches 3 remote git forks and emits live conflict JSON over WebSocket.
  2. **Spike S-A2 (A04/A09 CIP Gating):** A runner script that executes an invariant test suite against a candidate diff and appends a signed receipt to `refs/notes/invariant-receipts`.
  3. **Spike S-A3 (A16 CARE Sandbox):** A zero-local-checkout harness demonstrating agent execution inside an isolated environment without expanding workstation disk usage.

---

## 8. Summary of Antigravity Round-3 Decisions

- **D-A05:** Formally and permanently rejected A05 (Fork Tournament), A07 (Maintainer Quarantine), A13 (Session Undo), and A19 (Maintenance Swarm) from the 6-approach shortlist.
- **D-A06:** Subsumed A09 (Exact-SHA Verification Receipts) directly into A04 (Checkable Invariant Probes) as its cryptographic attestation layer.
- **D-A07:** Established the final 6-approach consensus shortlist: **[A01, A04, A12, A14, A16, A03]** as the unified Edge-Native Autonomous Integration Platform (ENAIP).
- **D-A08:** Affirmed resource policy constraints: zero new Codex launches beyond 15% reserve; zero unconstrained Claude subagent loops; implementation driven by z.ai (`zcy`), Gemini (`agy`), and OpenCode (`muse 1.3`).
