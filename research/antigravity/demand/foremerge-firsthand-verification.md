# Foremerge Demand & Practitioner-Signal Verification: Independent Critical Source Analysis

**Tag:** `foremerge-demand-verifier`  
**Parent Orchestrator:** `antigravity-head` (`46fdb644` / `245c7bba-9a7b-45c1-87a7-4537f289f9a5`)  
**Directive Origin:** Codex Principal C1818 Directives  
**Investigation Date:** 2026-10-04  
**Workspace:** `/home/alexey/git/cloudflare-agent-git`  
**Deliverable Path:** `research/antigravity/demand/foremerge-firsthand-verification.md`  
**Status:** Completed Independent Verification (100% Read-Only; Zero Build Invocations; Zero Token Emission)

---

## 1. Executive Summary & Audit Context

Under Codex Principal C1818 directives, this report provides an independent, source-grounded verification of the demand signals, practitioner experiences, and competitive architecture surrounding **Foremerge** (a pre-1.0 coordination layer above Git) and related multi-agent coordination approaches.

Principal discovery via x.ai web search identified Hacker News discussion thread 49789356. To avoid promotional bias and ensure rigorous evidence hygiene, this verifier independently queried the native Hacker News Firebase API for exact item timestamps and payloads, inspected the raw Foremerge repository documentation (v0.5.1 README), and extracted firsthand practitioner experiences.

### Key Verification Takeaways:
1. **Demand for Semantic Conflict Prevention is Real but Constrained:** Both vendors and active multi-agent practitioners report painful integration failures where multiple agents execute architectural changes that cannot simultaneously hold true (such as one agent replacing a class or abstraction while another concurrently extends it). Standard Git text-based three-way merges silently merge these changes if lines do not collide, resulting in dead code or runtime breakage.
2. **Existing Coordination Tooling Frequently Fails to "Earn Its Keep":** Primary practitioner testimony reveals significant skepticism toward ad hoc coordination layers. Builders report that blackboard patterns, shared memory structures, and coordination tools often introduce high maintenance and token overhead without delivering proportionate value. Concurrency conflicts occur less frequently than anticipated when proper domain boundaries are maintained.
3. **Foremerge is a Local-First Pre-Code Advisory Prototype, Not a Distributed Solution:** Foremerge v0.5.1 relies on a single-machine SQLite store in the local repository's Git common directory (`<git-common-dir>/foremerge/state.sqlite3`), advisory leases, and deterministic matching of self-declared scopes (`symbol:X=replace` vs `extend`). Its README explicitly acknowledges that multi-machine coordination is out of scope and that published benchmarks comparing coordinated vs. uncoordinated workflows do not exist.
4. **Vulnerability of Self-Declared Scopes:** Foremerge's deterministic conflict engine depends on agents choosing identical semantic scope keys. The author openly documented real-world blind spots where one agent declared scope by class name while another declared scope by internal method name, causing the conflict to go undetected.
5. **Architectural Contrast with Agent Branches:** Whereas Foremerge attempts to shift conflict resolution earlier via pre-code declarations and agent-to-agent advisory messaging on a single local host, the **Agent Branches** runtime protocol addresses distributed, multi-agent teams via a Cloudflare Workers/Durable Objects coordinator, remote Git Smart HTTP forks, scoped lease tokens, and automated pairwise trial-merges (`git merge-tree --write-tree`) coupled with budgeted combined-tree test execution (L3 Radar).

---

## 2. Primary Source Provenance & Verification Ledger

Every source item was retrieved directly from authoritative native endpoints (Hacker News Firebase REST API and raw GitHub content). Timestamps reflect exact UTC epoch timestamps. In accordance with project evidence invariants, full verbatim quotes are avoided; precise short excerpts, structured paraphrases, and exact attribution are used throughout.

### Primary Source Ledger

| Source ID | Author / Persona | Exact Date & Timestamp (UTC) | Endpoint / Context | Primary Verified Signal |
|---|---|---|---|---|
| **HN Story 49789356** | `naw103` (Vendor / GPTree Founder) | 2026-09-21T16:22:06Z (Epoch: `1790007726`) | `Show HN: Foremerge – Catch intent conflicts between parallel coding agents` | Vendor announcement detailing intent conflicts in parallel agent worktrees (e.g. class replacement vs. extension), claiming pre-code conflict detection across 98 agents. |
| **HN Comment 49797952** | `ttoze` (Practitioner / Enterprise Architect) | 2026-09-22T07:59:42Z (Epoch: `1790063982`) | Reply to `ttoinou` (49795370) on custom merge solutions | Argues code ownership value increases with agents; details team-owned harnesses, independent agent remits, adversarial negotiation across boundaries, and queue subsystems. Notes concurrency issues were rarer than expected. |
| **HN Comment 49811149** | `gavmor` (Practitioner / Agent Fleet Operator) | 2026-09-23T03:04:07Z (Epoch: `1790132647`) | Top-level practitioner assessment | Reports using `weave` and ad hoc blackboard patterns, but notes they have not earned their keep; queries whether failure is due to low parallelism or over-reliance on a parent coordinator. |
| **HN Comment 49820059** | `gavmor` (Practitioner / Agent Fleet Operator) | 2026-09-23T18:01:25Z (Epoch: `1790186485`) | Followup reply to `naw103` (49819493) | Clarifies fleet scale: operates up to ~25 sessions using `aoe` for session spawning and worktree-isolated communication, with a coordinator agent selectively intruding to resolve conflicts. |
| **Foremerge Repo README** | `naw103` / Foremerge Project | Current v0.5.1 (Opened 2026-10-04, 597 lines) | `https://raw.githubusercontent.com/naw103/foremerge/main/README.md` | Documents local-first Rust CLI, 18 MCP tools, SQLite store in Git common directory, advisory claims, verification gates (`changeset validate`), and explicit limitations (no benchmarks, no cross-machine). |

### Corroborating Contextual Records

| Source ID | Author | Exact Timestamp (UTC) | Significance / Signal |
|---|---|---|---|
| **HN Comment 49819493** | `naw103` | 2026-09-23T16:47:11Z | Vendor acknowledges that prior to Foremerge, shared blackboards failed because agents were aware of memory but still drifted and burned tokens resolving post hoc conflicts. Highlights value when alternating between Claude and Codex without a single parent. |
| **HN Comment 49825814** | `naw103` | 2026-09-24T05:32:04Z | Recommends Foremerge as a logical synchronization layer to complement physical worktree/session managers like `aoe`. |
| **HN Comment 49795854** | `naw103` | 2026-09-22T04:03:19Z | Explains why advisory claims are used instead of locks (locks cause deadlocks/queues in active repos); acknowledges lack of push notifications and diff comparison at acceptance. |
| **HN Comment 49801139** | `naw103` | 2026-09-22T12:47:01Z | Clarifies that HIGH conflict warnings require explicit human or agent resolution rationale before acceptance, but do not block ongoing edits. |
| **HN Comment 49795370** | `ttoinou` | 2026-09-22T02:44:27Z | Establishes that overlapping developer changes were already a burden pre-AI, but agent swarms make coordination significantly more non-trivial. |
| **HN Comment 49797141** | `adityamishra241` | 2026-09-22T06:40:17Z | Questions how to differentiate actionable conflicts from benign overlapping edits without interrupting agent momentum. |

---

## 3. Persona Extraction & Practitioner Signal Analysis

A critical reading of the primary sources reveals sharp divergences between promotional vendor claims and practical engineering realities encountered by real-world practitioners.

```
+-------------------------------------------------------------------------------+
|                             Practitioner Landscape                            |
+-------------------------------------------------------------------------------+
|                                                                               |
|  [Vendor: naw103]                   [Architect: ttoze]                        |
|  - "98 agents, zero conflicts"      - "Code ownership value increases"        |
|  - Single local SQLite database     - Area-specific harnesses & model config  |
|  - Advisory intent declarations     - Adversarial agent negotiation           |
|  - Pre-code conflict alerts         - "Concurrency less an issue than thought"|
|                                                                               |
|  [Operator: gavmor]                 [Inquirer: adityamishra241]               |
|  - ~25 worktrees via `aoe`          - "When is conflict worth stopping?"      |
|  - Tried `weave` & blackboards      - Sifting real architecture hazard        |
|  - "Haven't earned their keep"      - from benign parallel noise              |
|  - Selective coordinator intrusion                                            |
|                                                                               |
+-------------------------------------------------------------------------------+
```

### 3.1 Persona Profiles

#### 1. The Vendor / Tool Creator (`naw103`)
- **Profile:** Founder/engineer at GPTree building developer tooling for parallel agents.
- **Framing & Tone:** Promotional yet technically candid. Relies on impressive-sounding headline claims (*"tested this up to 98 parallel agents with zero conflicts"*, *"first conflict in under five minutes"*), but discloses significant architectural bounds when pressed in comments and documentation.
- **Admitted Caveats:** Acknowledges that Foremerge is an advisory, single-machine local tool; does not provide distributed consensus; cannot prevent blind spots if agents misalign scope declarations (class vs. method); lacks push notifications; and has published zero empirical benchmark comparisons against uncoordinated baselines.

#### 2. The Enterprise Multi-Agent Architect (`ttoze`)
- **Profile:** Engineering leader managing multiple teams and service areas using AI coding agents.
- **Perspective on Ownership:** Directly challenges the vendor premise that autonomous agents diminish the need for code ownership. Instead, asserts that code ownership *increases* in importance.
- **Workflow & Boundaries:** Establishes clear code ownership domains where individual teams configure their own agent harnesses, models, instructions, and domain skills.
- **Coordination Mechanism:** Cross-area work is governed by an orchestration layer featuring *adversarial negotiation* between agents, with automatic escalation to human engineers when consensus fails.
- **Empirical Observation:** Reports that concurrency conflicts were surprisingly less frequent than anticipated when strong ownership boundaries were enforced. Acknowledges that structured negotiation is slower than unrestricted agent execution, but prevents costly architectural drift.

#### 3. The Power Fleet Operator (`gavmor`)
- **Profile:** Practitioner managing substantial agent parallelism (running up to ~25 simultaneous worktree-isolated sessions).
- **Tooling Stack:** Uses `aoe` for session spawning, tmux multiplexing, and worktree isolation; previously evaluated `weave` and ad hoc blackboard pattern skills.
- **Core Friction ("Earned Their Keep"):** States plainly that blackboard patterns and external coordination skills have not justified their overhead. Suggests this friction arises either because parallel tasks are naturally more disjoint than expected, or because relying on a parent coordinator session that selectively intrudes into worker sessions is more direct and effective.

---

### 3.2 Reported Firsthand Symptoms and Pains

Across both vendor and practitioner reports, five distinct symptoms emerge:

1. **Incompatible Semantic Architecture ("Cannot Both Be True"):**
   - *Symptom:* Two agents receive tickets that appear disjoint at the requirement level, but lead to mutually exclusive design decisions.
   - *Concrete Case:* One agent introduces a new provider interface (`StripePaymentService`) and deprecates the old class, while another agent simultaneously adds new features (`PayPal`) to the legacy class.
   - *Impact:* Neither agent breaks local compilation in isolation. When merged, the extension work is stranded on an abandoned abstraction.

2. **Git's Line-Level Blind Spot:**
   - *Symptom:* Traditional version control verifies textual disjointness, not architectural coherence.
   - *Impact:* If two agents modify different files or non-overlapping line ranges within the same repository, `git merge` succeeds with exit code 0. Semantic divergence is discovered only at integration test time, PR review, or in staging.

3. **PR-Time Review and Rework Overhead:**
   - *Symptom:* Discovering architectural clashes at PR creation forces extensive rework.
   - *Impact:* Human reviewers are forced to cross-reference multiple in-flight pull requests to detect conceptual collisions. Alternatively, when agents are tasked with resolving merge conflicts autonomously, they exhibit high error rates and thrashing.

4. **Autonomous Token Burn During Conflict Resolution:**
   - *Symptom:* As highlighted by `naw103` (49819493), when subagents operate without strict coordination, they often detect contradictions only after code is written, burning large numbers of LLM tokens attempting to reconcile incompatible branches.

5. **Noise vs. Actionable Hazard Distinction:**
   - *Symptom:* As articulated by `adityamishra241` (49797141), coordination tools that alert on any shared file or symbol risk generating excessive noise. If an agent is interrupted for benign overlaps (e.g. both adding helper methods to a common utility file), developer momentum is destroyed.

---

### 3.3 Practitioner Workarounds in Production

Rather than adopting complex global coordination protocols, practitioners currently rely on three pragmatic workarounds:

1. **Strict Code Ownership & Adversarial Negotiation (`ttoze`):**
   - Codebases are segmented into strict functional domains.
   - Agents are bounded to specific directories and skills.
   - When an agent must cross boundaries, it does not directly modify code; it submits a request to the owning agent, which evaluates the proposal adversarially before accepting.

2. **Physical Multiplexing with Selective Coordinator Intrusion (`gavmor`):**
   - Practitioners use lightweight workspace managers (such as `aoe` or plain Git worktrees) to allocate independent file trees and terminals.
   - A single top-level coordinator session monitors progress and selectively intrudes into worker sessions to steer or abort when an architectural conflict is observed.

3. **Ad Hoc Blackboards and Shared Markdown Logs:**
   - Tasks and in-progress intentions are written to shared markdown files or lightweight memory tools.
   - *Observed limitation:* Agents frequently read blackboard entries but still proceed to violate stated boundaries, leading practitioners like `gavmor` to conclude they fail to earn their keep.

---

### 3.4 Reported Adoption Friction & Negative Evidence

The primary evidence reveals four major adoption barriers:

1. **The Overhead-to-Value Deficit:**
   - Extra coordination layers require registration steps, MCP server configuration, and continuous state synchronization. If parallel agents rarely touch the exact same architectural abstraction, the overhead of maintaining an intent registry exceeds the cost of occasional manual conflict resolution.

2. **Throughput Degradation:**
   - Structured negotiation and pre-flight checks introduce latency. As `ttoze` notes, formal inter-agent coordination is noticeably slower than letting agents execute autonomously.

3. **Vocabulary Mismatch in Intent Declarations:**
   - Foremerge's deterministic model requires agents to declare identical scope keys (`symbol:PaymentService`). If Agent A claims `symbol:PaymentService=replace` while Agent B claims `symbol:PaymentService.charge=extend`, a pure deterministic string matcher generates a false negative. The vendor acknowledged this exact blind spot during real-world dogfooding.

4. **Single-Host Confinement:**
   - A coordination database stored inside `<git-common-dir>` cannot coordinate across remote cloud workers, CI environments, or distributed agent pools.

---

## 4. Comparative Architecture Analysis

To evaluate whether Foremerge's approach represents a viable paradigm or an over-engineered local artifact, we compare three architectural models across nine key engineering dimensions:

- **Model A: Ordinary Git + Single Coordinator / Integrator** (Current Industry Baseline)
- **Model B: Foremerge v0.5.1** (Local SQLite + MCP Intent Advisory Layer)
- **Model C: Agent Branches / Cloudflare Runtime Protocol** (Cloudflare Workers/DO + L2 Client + L3 Radar Trial-Merge Engine)

### 4.1 Architectural Comparison Matrix

| Dimension | Model A: Ordinary Git + Single Coordinator | Model B: Foremerge (v0.5.1) | Model C: Agent Branches (Cloudflare Protocol) |
|---|---|---|---|
| **1. System Topology & Store** | Plain Git worktrees / branches; no extra daemon or database. | Single Rust binary (`foremerge`/`fmg`), local SQLite in `<git-common-dir>/foremerge/state.sqlite3`. | Cloudflare Workers + Durable Objects L1 Coordinator; remote Git Smart HTTP forks; zero local daemon. |
| **2. Coordination Scope** | Single machine (worktrees) or remote Git repository (branches/PRs). | Strictly single-machine (linked worktrees sharing local `.git`). Multi-machine explicitly out of scope. | Globally distributed across cloud sandboxes, local worktrees, CI runners, and multi-tenant hosts. |
| **3. Conflict Detection Timing** | Post-implementation at `git merge`, PR creation, or CI build. | Pre-implementation at intent publication (`foremerge intent publish`). | Continuous / near-real-time on WIP commit push (`agent-branches push`). |
| **4. Detection Mechanism** | Textual diff line-collision via 3-way merge (`git merge-tree`). | Deterministic key matching on self-declared scopes (`symbol:X=replace` vs `extend`). No LLM judge. | Automated pairwise in-memory trial merge (`git merge-tree --write-tree`, ~5ms) + budgeted test execution. |
| **5. Claim / Lock Semantics** | Optimistic concurrency (no locks); race resolved at merge. | Advisory non-blocking leases; warnings emitted on overlap; no locks. | Scoped lease bearer tokens; advisory warnings emitted; no blocking locks. |
| **6. Verification Gate** | Manual PR review + CI suite execution. | Named local command (`foremerge changeset validate`) executed against exact Git fingerprint before ref acceptance. | Automated L3 Radar test runner ($T \le 15$s in isolated process groups) with strict fail-closed invariants. |
| **7. Ground Truth & Trust** | Pure Git commits, trees, and refs. | Git refs combined with local SQLite semantic event hash-chain. | Standard Git object database, commit SHAs, and signed webhook / HMAC payloads. |
| **8. Vulnerability / Blind Spots** | Silent semantic divergence if edits are in separate files. | Scope vocabulary mismatch (class vs. method); reliance on agent honesty/accuracy in declaring intent. | Resource budget bounds ($T \le 15$s); test suites that fail to test the shared integration surface. |
| **9. Tooling & Adoption Friction** | Minimal (standard Git CLI); high human/coordinator cognitive load. | High setup overhead (daemon/MCP setup, skill injection, intent/claim lifecycle commands). | Low client overhead (simple REST/CLI push + webhook alerts); zero local DB management. |

---

### 4.2 Deconstruction of Novelty and Demand Claims

#### 1. "Intent Conflict Detection" is Not Proven by Product Launch
- Vendor claims that Foremerge represents a breakthrough in catching intent conflicts must be evaluated critically.
- In practice, Foremerge does not "understand" intent through artificial intelligence or semantic graph reasoning. It performs deterministic key-value comparisons on structured annotations explicitly supplied by the agent (`--scope symbol:PaymentService=replace`).
- If an agent fails to declare a scope, phrases the scope differently, or operates at a different AST granularity, the system fails to detect the collision. Moving conflict detection earlier in the lifecycle only works if the cost of declaring and maintaining semantic scopes is significantly lower than the cost of resolving merge conflicts.

#### 2. Absence of Empirical Benchmarks
- As Foremerge's own documentation explicitly states:  
  > *"Published benchmark results do not yet exist, and coordination between machines is outside this project's scope."* (README lines 23-24).
- The claim of running "98 parallel agents with zero conflicts" in a private vendor test is an unverified synthetic assertion. Without open, reproducible multi-repo benchmarks measuring completion time, token expenditure, and defect escape rates, there is no empirical evidence that pre-code intent publication outperforms standard Git branch isolation.

#### 3. Moving the Conflict Bottleneck vs. Eliminating It
- Foremerge does not eliminate architectural conflict; it shifts the dispute from Git merge time to pre-code negotiation.
- When Foremerge flags a `HIGH` conflict, the agents must engage in agent-to-agent messaging (`coordinate_with_agent`) or wait for a human to log an assessment rationale (`assess record`).
- If agents spend dozens of conversational turns negotiating abstract designs before writing code, they may burn more time and tokens than an ordinary Git workflow where an agent implements a solution and an integrator resolves conflicts at PR time.

---

## 5. Unsteered Falsification / Adoption Gate

To empirically resolve whether intent-conflict advisory tooling earns its keep against an ordinary Git worktree baseline, we specify exactly **one** concrete, unsteered adoption and falsification gate.

### Protocol Specification: The Unsteered Parallel Refactoring Trial (UPRT) Gate

```
                                  [Real Maintenance Task]
                                             |
                         +-------------------+-------------------+
                         |                                       |
                         v                                       v
             [Arm A: Ordinary Baseline]               [Arm B: Advisory Tooling]
             - Isolated Git Worktrees                 - Isolated Git Worktrees
             - Standard Git CLI                       - Advisory Tooling Available
             - Single Integrator / PR                 - Unprompted Choice to Use
                         |                                       |
                         +-------------------+-------------------+
                                             |
                                    [Measure Outcomes]
                                    - First Action & Adoption Choice
                                    - Total Completion Time & Tokens
                                    - Integration Rework & Defects
                                    - Tool Abandonment Rate
```

#### 1. Experimental Design & Neutral Provisioning
- **Actor:** An unfamiliar, capable autonomous coding agent (or developer) assigned to implement real pending maintenance and refactoring tasks on a multi-module repository.
- **Task Scope:** Genuine, non-synthetic maintenance backlog tasks involving overlapping service boundaries (e.g. updating an authentication interface while refactoring session middleware). **Strictly no artificial conflicts may be seeded.**
- **Neutral Access:** The actor is provisioned with two identical environments:
  - **Arm A (Baseline):** Standard Git worktrees with an ordinary single-integrator PR workflow.
  - **Arm B (Candidate):** Standard Git worktrees with the advisory intent-coordination tooling installed and configured (MCP tools and CLI available).
- **Unsteered Choice:** The actor is given standard operational instructions to complete the task efficiently. The prompt **must not steer, require, or incentivize** the use of the advisory tooling. The actor chooses freely whether to register intents, check advisory warnings, or rely purely on Git.

#### 2. Concrete Measured Metrics
1. **Unsteered Adoption Decision (First Action):** Does the actor voluntarily invoke the advisory registration tools, or do they immediately proceed with ordinary Git edits?
2. **Total Wall-Clock Completion Time ($T_{\text{total}}$):** Measured from task assignment to verified merge on `main`, including environment setup, tool registration, coordination messaging, and troubleshooting.
3. **Total Token Expenditure ($C_{\text{token}}$):** Comprehensive prompt and completion tokens consumed across all agent sessions (worker sessions + coordination/negotiation turns).
4. **Integration Defect Rate ($D_{\text{escape}}$):** Number of semantic regressions, dead code occurrences, or broken integration tests detected when combining parallel branches onto `main`.
5. **Rework Overhead ($T_{\text{rework}}$):** Time and tokens spent resolving either pre-code advisory warnings or post-implementation Git conflicts.
6. **Tool Abandonment / Override Frequency:** Number of times advisory warnings were suppressed, overridden, or ignored due to false positives or distraction.

#### 3. Strict Falsification & Pass/Fail Rules
- **Rule 1 (Falsification Condition):** The advisory coordination tool is **falsified** (declared to have failed to earn its keep) if:
  $$\frac{T_{\text{total}}(\text{Arm B})}{T_{\text{total}}(\text{Arm A})} > 1.20 \quad \text{OR} \quad \frac{C_{\text{token}}(\text{Arm B})}{C_{\text{token}}(\text{Arm A})} > 1.25$$
  without achieving a statistically significant reduction in post-merge integration defects ($D_{\text{escape}}$).
- **Rule 2 (No Tie Credit):** A tie in defect rates where no architectural hazard occurred naturally **cannot** be counted as evidence of efficacy for the advisory tool. Efficacy requires demonstrating a prevented defect that offsets the operational overhead.
- **Rule 3 (Adoption Success Gate):** The advisory tool passes the adoption gate if and only if:
  1. The actor willingly adopts the tool in $\ge 80\%$ of eligible parallel tasks without coercion.
  2. The net integration time and rework overhead is reduced by $\ge 15\%$ compared to the ordinary Git baseline.
  3. Zero architectural regressions slip past the verification gate.

---

## 6. Strategic Synthesis & Recommendations

### 6.1 Findings Summary
1. **Practitioner Validation:** Independent analysis of Hacker News primary sources (`ttoze`, `gavmor`) confirms that multi-agent teams face genuine friction around semantic conflicts. However, existing blackboard and coordination layers are viewed skeptically because they often fail to justify their overhead.
2. **Competitive Landscape (Foremerge):** Foremerge v0.5.1 provides a clean, well-crafted local-first prototype of pre-code advisory coordination. However, its architectural reliance on a local SQLite database in `<git-common-dir>`, its vulnerability to scope naming mismatches, and its lack of distributed capabilities make it unsuitable for distributed, multi-cloud agent swarms.
3. **Validation of Agent Branches Architecture:** The architectural decisions of the **Agent Branches** protocol (Cloudflare Workers/Durable Objects for global coordination, Git Smart HTTP forks, and L3 Radar's automated pairwise trial merges and budgeted test execution) directly target the primary limitations of Foremerge. Instead of relying on subjective agent-declared intent strings, Agent Branches validates actual code outputs via fast in-memory Git merge trees and isolated test execution.

### 6.2 Actionable Next Steps
- **Maintain Execution Hygiene:** Do not install or compile external unverified binaries on shared hosts; continue evaluating coordination models through clean API contracts and controlled sandboxes.
- **Implement the UPRT Gate:** Prior to committing to mandatory pre-code advisory gates across the project, execute the single unsteered trial specified in Section 5 on a pending maintenance task to verify whether advisory warnings provide measurable net benefit over ordinary Git worktrees.
- **Keep Ordinary Git as the Durable Source of Truth:** Regardless of coordination layers, preserve standard Git commit graphs, refs, and ordinary recovery paths as non-negotiable invariants.

---
*Report compiled autonomously by `foremerge-demand-verifier` under Codex Principal C1818 directives. All primary records verified against native Firebase API and raw repository payloads.*
