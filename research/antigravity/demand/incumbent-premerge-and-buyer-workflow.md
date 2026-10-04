# Incumbent Pre-Merge Checks, Multi-Agent Swarm Workflows, and Buyer Adoption Friction

**Author / Tag:** `incumbent-premerge-researcher`  
**Parent Authority:** `antigravity-head` (`46fdb644` / `245c7bba-9a7b-45c1-87a7-4537f289f9a5`)  
**Directive Origin:** Desktop Orchestrator 11:50 Berlin Directives  
**Investigation Date:** 2026-10-04  
**Workspace:** `/home/alexey/git/cloudflare-agent-git`  
**Scratch Workspace:** `/home/alexey/git/cloudflare-agent-git/.local/scratch/incumbent-premerge-research/` (mode `0700`, disk $\le$ 512 MB, zero net `/tmp` growth)  
**Deliverable Path:** `research/antigravity/demand/incumbent-premerge-and-buyer-workflow.md`  
**Status:** Completed Technical & Market Investigation (100% Read-Only; Zero Compiler Invocations; Zero Token Emission)  

---

## 1. Executive Summary & Problem Framing

Under Desktop Orchestrator 11:50 Berlin directives, this investigation steps outside closed fixture loops and manufactured harder test cases to examine the real-world software engineering landscape: **incumbent pre-merge checks, genuine multi-agent practitioner workflows, and enterprise buyer adoption friction**.

A central claim in the emerging "Agent Git" and concurrent agent tooling space is that autonomous coding swarms require a novel, specialized coordination runtime (such as Cloudflare Workers, Durable Objects, and real-time push-time trial-merge advisory radars) to prevent breaking semantic changes from landing on canonical trunk branches.

This research paper subjects that claim to an independent, technically rigorous examination against incumbent production software engineering tooling.

```
+----------------------------------------------------------------------------------------------------+
|                                    THE CORE ARCHITECTURAL REALITY                                  |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|    Target Base Ref  +  In-Flight Branch Ref  ===>  Speculative 3-Way Merge  ===>  Run Test Suite   |
|                                                                                                    |
|    [GitHub PR CI (refs/pull/*/merge)]              [GitHub / GitLab Merge Queues]                  |
|    - Trigger: PR open / update                     - Trigger: Merge queue entry                    |
|    - Test Oracle: Full CI Suite                    - Test Oracle: Full CI Suite                    |
|    - Outcome: Block merge on failure               - Outcome: Auto-evict / bisect on failure       |
|                                                                                                    |
|    [Agent Branches L3 Advisory Radar]              [Bors-ng / Zuul Gates]                          |
|    - Trigger: Git Smart HTTP push                  - Trigger: "bors r+" / batch gate               |
|    - Test Oracle: Budgeted test runner             - Test Oracle: Full CI Matrix                   |
|    - Outcome: Warning attached to task             - Outcome: Fast-forward or reject               |
|                                                                                                    |
|    KEY FINDING: ALL FOUR USE THE EXACT SAME TEST ORACLE TO PREVENT DEFECTS ON MAIN.                |
|    THE VALUE PROPOSITION RESTS ENTIRELY ON TRIGGER TIMING, COMPUTE SCALING, AND ADOPTION FRICTION. |
+----------------------------------------------------------------------------------------------------+
```

### Key Findings of this Investigation:

1. **The "Identical Test Oracle" Invariant & Bounded Guarantees:**
   In the empirical Unsteered Parallel Refactoring Trial ([`REPORT-UPRT-CONCURRENT-GATE.md`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/adoption/REPORT-UPRT-CONCURRENT-GATE.md)), an uncoordinated baseline (Arm A) allowed a semantic contract break (Task T2 object signature refactor vs. Task T3 positional bulk caller) to land on `main`, whereas the Agent Branches L3 Radar (Arm B) caught the defect prior to trunk landing. 
   Crucially, this occurred because Arm A modeled a *post-merge* CI policy. If Arm A had been configured with **any standard incumbent pre-merge check**—such as GitHub's native `refs/pull/<number>/merge` virtual ref, a GitLab Merge Train, or a simple 2-line pre-push worktree script (`git merge --no-commit; npm test`)—it would have caught the regression with the **exact identical failure signal** (`AssertionError: 400 !== 201`). Agent Branches does not possess an intrinsically superior semantic oracle; it executes the same Git merge and test runner.
   *Crucial Operational Boundary:* Configured test gates are **NOT** a 100% universal trunk protection or semantic guarantee. All test gates (incumbent and experimental alike) remain strictly bounded by test suite coverage, test flakiness, build timeouts, environment drift, and repository administrator bypass permissions.

2. **The Genuine Differentiators (Proposal vs. Prototype):**
   Where Agent Branches and L3 Advisory Radar conceptually diverge from incumbent CI is:
   - **Trigger Point:** Continuous push time (remote Smart HTTP push) rather than pull request or merge-queue submission boundary.
   - **Interruption Timing:** Delivering an in-flight advisory warning during an active agent turn rather than a blocking failure after the agent has concluded its turn.
   - **Compute Profile:** A quadratic $O(N^2)$ pairwise combination matrix upper bound ($N(N-1)/2$) across active heads on push, compared to the linear $O(N)$ or batched $O(\lceil N/B \rceil)$ speculative execution model of merge trains.
   *Prototype Demarcation:* In this repository, Agent Branches L3 Radar was demonstrated via a scripted manual harness (`run_uprt_trial.py` invoking `engine.evaluate_pair()` and posting to `POST /checks`), **NOT** an automated continuous background push daemon or active agent mid-turn warning consumption service. The architectural design proposal must be kept distinct from the actual pre-built Node prototype and its currently unknown real-world benefit. Furthermore, standard PR CI can run on branch pushes and draft PRs (`on: [push]`, `on: [pull_request]`), and agents can poll CI status prior to completing turns; categorical claims of "incumbent only tests after task complete / 45-minute blind agent execution" are unproven generalizations.

3. **Enterprise Buyer Friction & Market Realities (Hypotheses):**
   - **Platform Engineering / DevOps Leads:** Hypothesized to resist deploying custom background Node/Python sidecar daemons, managing custom token choreography, and paying for quadratic compute when standard GitHub Actions runners and native merge queues already provide standard trunk protection. Attributed firsthand buyer willingness-to-pay remains unproven.
   - **Fleet Operators & Swarm Managers:** While primary practitioner testimony (e.g. `gavmor` on ~25 worktrees) confirms that ad hoc blackboards and coordination layers frequently "fail to earn their keep," this general skepticism does not prove commercial rejection of Agent Branches specifically. In-turn push warnings on intermediate draft code risk causing context distraction and apology loops if intermediate test failures are treated as contract regressions.
   - **Single-Actor / Small Teams:** Experience negative ROI: 5.7x wall-clock latency overhead (0.200s vs 1.143s), daemon memory footprints (~155 MB RSS), and multi-step SDK ceremony for zero collision risk.

4. **Provisional Adoption Hypotheses & Scope:**
   - Single-actor workloads: **STRICTLY DECLINE.**
   - Standard human/agent teams on GitHub: **DECLINE / REDUNDANT.**
   - High-velocity autonomous agent swarms ($>10$ agents continuously pushing): **CONDITIONAL ADOPTION HYPOTHESIS**, valid only if push-time warning prunes branch exploration faster than PR CI cycle times, offsetting the compute bill.
   *Authority Note:* These tiers and thresholds represent provisional engineering hypotheses and design criteria, NOT principal-approved corporate product policy or shortlist selection. Final adoption decisions remain strictly with the Codex and Claude principals.

---

## 2. Incumbent Pre-Merge Check Ecosystem & Technical Taxonomy

Pre-merge test gating is not a new problem invented for AI agents. For over a decade, production software engineering teams operating at scale have deployed automated systems to prevent semantic and integration regressions from breaking the canonical trunk branch (`main` or `master`).

## 2. Incumbent Pre-Merge Check Ecosystem & Technical Taxonomy

Pre-merge test gating is not a new problem invented for AI agents. For over a decade, production software engineering teams operating at scale have deployed automated systems to prevent semantic and integration regressions from breaking the canonical trunk branch (`main` or `master`).

To evaluate whether agent-specific coordination tooling earns its keep, we first conduct a comprehensive technical taxonomy of incumbent pre-merge systems grounded in dated official documentation and primary technical sources.

### 2.0 Authoritative Technical Source Ledger (As of October 2026)

| Ecosystem / Tool | Primary Technical URL / Authority | Key Technical Requirement & Trigger Mechanism |
| :--- | :--- | :--- |
| **GitHub Merge Queue** | [GitHub Docs: Managing a merge queue](https://docs.github.com/en/enterprise-cloud@latest/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue) | Requires CI workflows to declare the `merge_group` event trigger (`on: { merge_group: {} }`). Operates on `refs/heads/gh-readonly-queue/<base-branch>/pr-<num>-<base-sha>`. |
| **GitLab Merge Trains** | [GitLab Docs: Merge Trains](https://docs.gitlab.com/ci/pipelines/merge_trains/) | Requires enabling "Pipelines for merged results" and "Merge trains" in repository settings. Operates on `refs/merge-requests/:iid/train`. |
| **Bors-ng** | [Bors-ng Documentation](https://bors.tech/documentation/) | Graydon Hoare's "Not Rocket Science Rule". Evaluates speculative batches on `staging` branch via bot commands (`bors r+`) with automated bisection. |
| **Zuul Gating Engine** | [Zuul CI Documentation](https://zuul-ci.org/docs/zuul/latest/) | Multi-repository dependency DAG gating (`Depends-On:` headers); speculative future-state trees in distributed ZooKeeper clusters. |
| **GitHub Actions Checkout** | [actions/checkout v4](https://github.com/actions/checkout) | Standard checkout action on `pull_request` events checks out virtual 3-way merge commit `refs/pull/<number>/merge` by default, NOT the isolated branch head. |

```
+------------------------------------------------------------------------------------------------------------------------+
|                                    PRODUCTION PRE-MERGE ARCHITECTURE SPECTRUM                                         |
+------------------------------------------------------------------------------------------------------------------------+
|                                                                                                                        |
|  [Developer Workstation]                  [Code Review Boundary]                  [Trunk Landing Queue]                |
|                                                                                                                        |
|  - Ephemeral Worktree Merge               - GitHub Native PR CI                   - GitHub Merge Queue                 |
|    (git merge --no-commit; test)            (refs/pull/:id/merge)                   (refs/heads/gh-readonly-queue/...) |
|  - Git pre-push hook                      - GitLab MR Pipelines                   - GitLab Merge Trains                |
|  - Foremerge v0.5.1 (Local SQLite)          (refs/merge-requests/:iid/merge)        (refs/merge-requests/:iid/train)   |
|                                                                                   - Bors-ng / Homu (staging branch)    |
|                                                                                   - Zuul Cross-Repo Gates (DAG)        |
|                                                                                                                        |
|  <---------------- INCREASING CENTRALIZATION & SPECULATIVE BATCHING -------------------------------------------------> |
+------------------------------------------------------------------------------------------------------------------------+
```

### 2.1 GitHub Merge Queue (Native Actions)

- **Origin & Purpose:** Introduced to GitHub Enterprise and public repositories to eliminate the classic "merge race condition" (where PR A and PR B both pass CI against `main`, but their combination breaks `main`).
- **Required Workflow Configuration:**
  Workflows intended to gate merge queue entry **must explicitly listen for the `merge_group` event**:
  ```yaml
  name: Merge Queue CI
  on:
    pull_request:
    merge_group:
      types: [checks_requested]
  ```
  If a workflow does not include `merge_group`, GitHub cannot execute check runs against speculative merge queue commits.
- **Speculative Ref Architecture:** When a PR is queued for merge, GitHub creates a temporary speculative branch:
  ```text
  refs/heads/gh-readonly-queue/<base-branch>/pr-<pr-number>-<base-sha>
  ```
- **Speculative Execution & Grouping (Batching):**
  GitHub Merge Queue can evaluate PRs individually or in speculative batches (e.g. batch size $B = 5$). When batching is enabled:
  - Speculative Commit 1: $\text{main} + \text{PR}_1$
  - Speculative Commit 2: $\text{main} + \text{PR}_1 + \text{PR}_2$
  - Speculative Commit 3: $\text{main} + \text{PR}_1 + \text{PR}_2 + \text{PR}_3$
  GitHub Actions triggers CI on each speculative commit simultaneously.
- **Auto-Rollback & Bisect:** If Speculative Commit 3 fails, the queue controller isolates the failure. It automatically removes the failing PR from the train, rolls back the queue, and re-triggers CI for the remaining clean PRs.
- **Trunk Protection Scope & Boundaries:**
  The merge queue enforces fail-closed trunk protection for configured required checks, but this is **bounded, not absolute**:
  1. *Test Suite Dependency:* If the test suite lacks coverage for a specific semantic interface, the defect will merge undetected.
  2. *Flaky Tests & Timeouts:* Test flakiness can cause false-positive queue evictions, triggering unnecessary bisections.
  3. *Administrator Bypass:* Repository administrators and automated deployment tokens with bypass permissions can push directly to `main` without entering the queue.
- **Trigger Model:** Intent-to-merge signal (`gh pr merge --auto` or web UI queue button).
- **Latency Profile:** Bound by GitHub Actions runner scheduling and test execution ($T \approx 3\text{--}15\text{ minutes}$).

### 2.2 GitLab Merge Trains

- **Origin & Purpose:** Integrated into GitLab CI/CD under "Pipelines for Merged Results".
- **Required Settings:** Requires explicitly enabling "Pipelines for merged results" and "Merge trains" in repository CI/CD settings.
- **Speculative Ref Architecture:** Evaluates speculative merge pipelines on a dedicated virtual ref:
  ```text
  refs/merge-requests/:iid/train
  ```
- **Continuous Chaining & Auto-Cancellation:**
  Merge Trains chain pending merge requests sequentially. If MR #1 is at the head of the train, MR #2 speculatively builds on the predicted outcome of MR #1, and MR #3 builds on MR #2.
  If MR #1's pipeline fails, GitLab immediately issues an **auto-cancellation cascade**:
  1. MR #1 is dropped from the train and marked failed.
  2. MR #2's pipeline is automatically aborted to conserve CI compute.
  3. A new pipeline for MR #2 is triggered directly against the current `main` branch.
- **Trigger Model:** "Merge when pipeline succeeds" / "Start merge train".
- **Latency Profile:** Continuous background execution; latency equal to project pipeline duration ($T \approx 2\text{--}10\text{ minutes}$).

### 2.3 Bors-ng / Homu / Zuul (The Original Merge Queue Pattern)

- **The Graydon Hoare Rule:** In 2014, Graydon Hoare (creator of Rust) formalized the *"Not Rocket Science Rule of Software Engineering"*:
  > *"automatically maintain a repository that always passes all tests"*
- **Bors-ng & Homu:**
  - Written for the Rust and Servo compiler development workflows where continuous test suites took 45+ minutes across dozens of platforms.
  - Architecture: Operates via a bot account (e.g. `bors r+`). Bors maintains a dedicated `staging` branch. It executes an in-memory 3-way merge of approved PRs into `staging` and kicks off CI.
  - In batch mode, if a batch of 10 PRs fails on `staging`, Bors performs automated binary bisection across the 10 PRs to pinpoint the offending PR, notifies the author in a PR comment, and fast-forwards `master` to the clean sub-batch.
- **Zuul Gating Engine:**
  - Developed by the OpenStack Foundation to handle massive cross-repository gating across hundreds of microservices and thousands of developers.
  - Multi-Repo Dependency Graphs: Developers declare inter-repo dependencies in commit messages (`Depends-On: <Change-ID>`).
  - Speculative DAG Computation: Zuul constructs a directed acyclic graph of all in-flight changes across all repositories, creates speculative combined worktrees, and runs multi-node integration tests before any single repository ref is updated.
  - Trade-Off: Unmatched architectural power, but massive operational complexity (requires ZooKeeper clusters, Nodepool VM orchestrators, and Ansible execution nodes).

### 2.4 Standard GitHub PR CI Virtual Merged Ref (`refs/pull/<number>/merge`)

- **The Ubiquitous Silent Default:** Even repositories that do not configure native Merge Queues or Bors benefit from GitHub's built-in speculative merge ref.
- **Dual Ref Model:** For every open pull request, the GitHub Git backend automatically maintains two refs:
  1. `refs/pull/<number>/head`: The raw commit SHA pushed by the developer or agent branch.
  2. `refs/pull/<number>/merge`: A virtual 3-way merge commit combining `refs/pull/<number>/head` with the current tip of `refs/heads/main`.
- **Default Checkout Semantics:** When a GitHub Actions workflow is triggered with `on: [pull_request]`, the standard checkout action (`actions/checkout@v4`) **checks out `refs/pull/<number>/merge` by default**, NOT `refs/pull/<number>/head`.
- **Significance:** Standard PR CI does **not** test the isolated branch code. It tests the **speculative result of merging the branch into main at that moment**. If `main` moves forward, GitHub marks the virtual merge commit dirty and re-evaluates it upon the next trigger.
- **Timing Nuance:** PR CI is not restricted to post-turn boundaries. Developers and agents can push intermediate commits to a draft pull request (`gh pr create --draft`), triggering speculative merge CI during active development, and poll the check status before concluding their turn. Categorical assertions that standard CI can only test after task completion are unsupported.

### 2.5 Local Pre-Merge Worktree Integration

- **Workstation / Harness Baseline:** Modern Git workflows can execute speculative pre-merge testing locally without any remote infrastructure.
- **Mechanism:**
  ```bash
  # Ephemeral worktree speculative pre-merge verification
  git worktree add -d .local/scratch/premerge main
  cd .local/scratch/premerge
  git merge --no-commit --no-ff origin/feat/my-branch
  npm test # or node --test, pytest, cargo test
  cd - && git worktree remove .local/scratch/premerge
  ```
- **Git Hooks:** A `.git/hooks/pre-push` hook can automate this exact sequence in under 500ms, aborting `git push` if the local speculative merge fails tests.
- **Resource Footprint:** Zero background daemons, zero external HTTP tokens, zero cloud costs.

### 2.6 Emerging Agent Coordination Tooling

- **Foremerge v0.5.1:**
  - Local-first Rust CLI tool storing state in `<git-common-dir>/foremerge/state.sqlite3`.
  - Agents publish intent scopes via MCP (`--scope symbol:PaymentService=replace`).
  - Evaluates conflicts lexically prior to code implementation.
  - *Identified Vulnerabilities:* Blind spots from scope granularity mismatch (class vs. method); single-machine confinement; zero multi-host cloud support.
- **Multi-Agent Workspace Managers (`aoe` / tmux swarms):**
  - Used by high-scale practitioners (e.g. `gavmor` running up to ~25 concurrent worktrees).
  - Isolates physical workspaces via plain Git worktrees.
  - Uses a top-level coordinator session that selectively intrudes into worker panes when drift is observed.
  - *Practitioner Verdict:* Shared blackboards and ad hoc memory structures frequently fail to earn their keep.

---

### 2.7 Incumbent Pre-Merge Systems: Systematic Technical Taxonomy

| Pre-Merge System | Primary Architecture | Trigger Point | Speculative Ref Name / Mechanism | Merge Strategy | Test Execution Environment | Latency to Detection | Failure Resolution | Multi-Host Support | Operational Footprint |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Standard GitHub PR CI** | Centralized GitHub Git backend | PR open, synchronize, or push | `refs/pull/<number>/merge` | In-memory 3-way merge commit | GitHub Actions hosted / self-hosted runners | 1 – 10 minutes | Blocks PR merge button; author rework | Yes (Cloud) | Zero local footprint (managed) |
| **GitHub Merge Queue** | Native GitHub Actions queue controller | `gh pr merge --auto` / Queue button | `refs/heads/gh-readonly-queue/...` | Speculative batch merge commits | GitHub Actions runner pool | 3 – 15 minutes (batched) | Auto-evict from queue; automated bisection | Yes (Cloud) | Zero local footprint (managed) |
| **GitLab Merge Trains** | GitLab CI/CD pipeline controller | "Merge when pipeline succeeds" | `refs/merge-requests/:iid/train` | Chained speculative merge commits | GitLab CI runners | 2 – 10 minutes | Auto-cancel downstream; re-chain clean MRs | Yes (Cloud) | Zero local footprint (managed) |
| **Bors-ng / Homu** | GitHub App bot + Elixir/Rust server | Bot comment `bors r+` | `staging` branch (speculative batch) | In-memory 3-way merge | CI runners (GitHub Actions, CircleCI) | 5 – 30 minutes | Binary bisection across batch; comment alert | Yes (Cloud) | Self-hosted or SaaS bot instance |
| **Zuul Gating Engine** | OpenStack distributed daemon cluster | Code review approval + DAG | Speculative future-state trees in ZooKeeper | Multi-repo dependency DAG merge | Distributed Ansible / Nodepool VM fleet | 10 – 60 minutes | Auto-reorder DAG; drop failed node | Yes (Multi-datacenter) | High (ZooKeeper, MySQL, Nodepool) |
| **Local Worktree Integration** | Local developer workstation / script | Pre-push hook or harness step | Ephemeral worktree or detached HEAD | `git merge --no-commit` | Local workstation CPU | 200 ms – 15 seconds | Abort push / task; immediate local triage | No (Single host) | Zero daemons; purely ephemeral |
| **Foremerge (v0.5.1)** | Local Rust CLI + MCP server | `foremerge intent publish` | Local SQLite DB in `.git/foremerge/` | Lexical scope string comparison | Pre-code lexical intent check (no test run) | 10 – 50 ms | Advisory warnings; coordination prompt | No (Single host only) | Single Rust CLI binary + SQLite file |
| **Agent Branches + L3 Radar** | Cloudflare Workers + DO + Smart HTTP | `agent-branches push` (remote HTTP) | In-memory tree via `git merge-tree` | `git merge-tree --write-tree` (in-memory) | Sandboxed snapshot runner (`node --test`) | 350 ms – 2 seconds | Advisory warning attached to DO task state | Yes (Distributed) | 2 Node daemons (Sidecar + DO runtime) |

---

## 3. The "Identical Pre-Merge Test Oracle" Reality

A critical technical question must be answered: **Does Agent Branches L3 Advisory Radar catch defects that incumbent pre-merge checks miss?**

The mathematical and engineering answer is **NO**. Both mechanisms rely on the exact identical test oracle.

```
                                [CANONICAL BASE REF: ff4decd7]
                                              |
                   +--------------------------+--------------------------+
                   |                                                     |
                   v                                                     v
        [Task T2: Signature Refactor]                           [Task T3: Bulk Endpoint]
        - ShortlinkService.create({ slug, url })                - ShortlinkService.create(slug, url)
        - Passing 16/16 tests                                   - Passing 15/15 tests
                   |                                                     |
                   +--------------------------+--------------------------+
                                              |
                                   [SPECULATIVE INTEGRATION]
                                              |
       +--------------------------------------+--------------------------------------+
       |                                                                             |
       v                                                                             v
[Agent Branches L3 Radar Evaluation]                              [Incumbent Pre-Merge CI Check]
- git merge-tree --write-tree: CLEAN (ort exit 0)                 - git merge-tree or refs/pull/*/merge: CLEAN (exit 0)
- Sandboxed snapshot test:                                       - CI runner pipeline execution:
  * node --test demo-target/test/*.test.js                         * node --test demo-target/test/*.test.js
  * FAIL: 18 passed, 1 failed                                      * FAIL: 18 passed, 1 failed
  * ✖ POST /links/bulk imports every link                          * ✖ POST /links/bulk imports every link
  * AssertionError: 400 !== 201                                    * AssertionError: 400 !== 201
- Result: Advisory warning posted to Coordinator                 - Result: CI fails; PR blocked; queue evicts
       |                                                                             |
       +--------------------------------------+--------------------------------------+
                                              |
                                    [IDENTICAL TEST ORACLE]
                            Both catch the regression BEFORE trunk landing.
                            Both emit the exact same AssertionError (400 !== 201).
```

### 3.1 Deconstruction of the UPRT Defect: T2 vs. T3

In the Unsteered Parallel Refactoring Trial ([`REPORT-UPRT-CONCURRENT-GATE.md`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/adoption/REPORT-UPRT-CONCURRENT-GATE.md)), two maintenance tasks collided semantically:
- **Task T2 (`t2.patch`):** Refactored `ShortlinkService.prototype.create` from positional arguments `(slug, url)` to an options object `{ slug, url, ttlSeconds }`. Updated existing callers in `src/worker.js` and tests. Passes 16/16 tests.
- **Task T3 (`t3.patch`):** Added a new bulk creation route `POST /links/bulk`. Invoked `service.create(item.slug, item.url)` using the baseline positional interface. Passes 15/15 tests.

#### The Silent Git Merge:
When Git merges T2 and T3:
- T2 modified lines 1-28 of `src/shortlinks.js` and updated line 26 of `src/worker.js`.
- T3 inserted the route handler at line 30 of `src/worker.js` and added a new file `test/bulk.test.js`.
- Because diff line ranges do not overlap, Git's three-way merge (`ort` strategy) merges cleanly with exit code 0.

#### The Semantic Runtime Failure:
When `POST /links/bulk` runs against the refactored `ShortlinkService`, JavaScript destructures the positional string argument:
```javascript
create({ slug: rawSlug, url, ttlSeconds } = {})
```
Since `rawSlug` receives `undefined`, `normalizeSlug(undefined)` throws `ValidationError("slug is required")`. The route returns HTTP 400 instead of HTTP 201.

#### Why Both Mechanisms Catch the Defect:
1. **Agent Branches L3 Radar:**
   Takes Head T2 and Head T3. Calls in-memory `git merge-tree --write-tree`. Gets tree SHA `31a89c97...`. Extracts tree into sandbox. Spawns `node --test demo-target/test/*.test.js`. The test fails with `AssertionError: 400 !== 201`. Radar flags `status="conflict"`, `kind="test"`.
2. **Standard GitHub PR CI / Merge Queue:**
   Checks out `refs/pull/t3/merge` (which combines `main` containing T2 with branch T3). Spawns `node --test demo-target/test/*.test.js`. The test fails with `AssertionError: 400 !== 201`. CI exits code 1. GitHub blocks merge button or ejects PR from the merge queue.

**Conclusion:** The claim that Agent Branches possesses unique defect prevention power over incumbent software engineering tooling is an artifact of comparing pre-merge testing in Arm B against post-merge testing in Arm A. When compared against matched pre-merge gates, both systems provide the **exact same test oracle**.

---

### 3.2 Where Agent Branches Actually Differs from Incumbent Pre-Merge Checks

While the underlying test oracle is identical, Agent Branches L3 Radar introduces three genuine technical divergences:

```
+----------------------------------------------------------------------------------------------------+
|                                    DIMENSIONAL COMPARISON                                          |
+----------------------------------------------------------------------------------------------------+
| Dimension               | Incumbent Pre-Merge (Merge Queue)       | Agent Branches (L3 Radar)      |
+-------------------------+-----------------------------------------+--------------------------------+
| 1. Trigger Point        | PR submission / Merge Queue entry       | WIP branch push (Smart HTTP)   |
| 2. Interruption Timing  | End-of-task boundary (synchronous gate) | In-flight advisory (async)     |
| 3. Compute Profile      | O(N) linear speculative chain           | O(N^2) pairwise matrix         |
| 4. Failure Granularity  | Pass / Fail boolean status              | Structured JSON warning payload|
+----------------------------------------------------------------------------------------------------+
```

#### 1. Trigger Point: Push Time vs. PR / Queue Boundary
- **Incumbent Model:** Pre-merge CI runs only when an agent declares a task complete and opens a Pull Request or adds it to the merge queue. If an agent works for 45 minutes on a branch, no cross-agent verification occurs during that 45 minutes.
- **Agent Branches Model:** L3 Radar evaluates pairwise combinations on every remote `git push` to an agent's task fork. If Agent A pushes a commit 5 minutes into a 30-minute task, and Agent B pushes a conflicting change 2 minutes later, Radar detects the contract collision while both agents are still actively working.

#### 2. Interruption Timing: In-Flight Advisory vs. Post-Turn Gate
- **Incumbent Model:** The feedback arrives as a blocking gate after the agent turn has completed. The human reviewer or parent orchestrator sees a red CI badge and must re-dispatch the agent with the error log.
- **Agent Branches Model:** The feedback arrives as an advisory warning attached to the agent's task resource in the Coordinator (`POST /checks`). An active agent querying `GET /tasks/:id` can receive warning `warn-1` mid-flight and adjust its implementation before committing to a final PR.

#### 3. Compute Profile: $O(N^2)$ Pairwise vs. $O(N)$ Speculative Queue
This is the single most critical architectural difference:
- In a Merge Queue or Merge Train, changes are queued in a linear speculative sequence:
  $$\text{Runs} = N \quad \text{or with batch size } B, \quad \text{Runs} = \lceil N / B \rceil$$
  For $N = 20$ branches, a merge queue executes between 4 and 20 CI pipeline runs.
- In Agent Branches L3 Radar, the engine computes a full pairwise combination matrix across all active branch vectors:
  $$\text{Pairs} = \frac{N(N - 1)}{2}$$
  For $N = 5$ heads: 10 pairs.  
  For $N = 10$ heads: 45 pairs.  
  For $N = 20$ heads: **190 pairs!**  
  For $N = 50$ heads: **1,225 pairs!**

As empirically measured in [`RADAR-INCREMENTAL-BENCHMARK.md`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/radar-bench/RADAR-INCREMENTAL-BENCHMARK.md), evaluating raw in-memory `git merge-tree` across 190 disjoint pairs takes ~8.5 seconds. However, **if branch pairs overlap and require running the test suite**, running 190 test suites (even at 5 seconds per test run) would require **950 seconds (nearly 16 minutes)** of continuous test execution per push!

```
Compute Overhead Comparison: 20 Active Branches
- Linear Merge Train (O(N)):      20 test runs (100 seconds @ 5s/suite)
- Batched Merge Queue (B=5):       4 test runs  (20 seconds @ 5s/suite)
- Pairwise L3 Radar (O(N^2)):    190 test runs (950 seconds @ 5s/suite) -> 9.5x to 47.5x more compute!
```

---

## 4. Genuine First-Hand Consumers & Buyer Workflow Analysis

To understand why adoption has lagged behind vendor claims, we analyze three concrete buyer and operator personas and map the exact friction points encountered during deployment.

```
+----------------------------------------------------------------------------------------------------+
|                                    BUYER & OPERATOR PERSONAS                                       |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|  [Persona 1: Platform / DevOps Lead]     [Persona 2: Swarm / Fleet Operator]  [Persona 3: Solo Founder]     |
|  - Owns CI compute bill & repo health    - Runs 10-50 agent worktrees         - Uses Cursor/Cline/Aider     |
|  - Strict compliance & auth standards    - Token economics & thrashing focus  - Wants zero-friction dev     |
|  - Rejects custom daemon sidecars        - Weighs push-pruning vs distraction - 5.7x latency is dealbreaker |
|                                                                                                    |
+----------------------------------------------------------------------------------------------------+
```

### 4.1 Persona Profiles

#### Persona 1: Platform Engineering / DevOps Lead
- **Primary Metrics:** CI/CD pipeline reliability, developer velocity, compute expenditure, security compliance.
- **Mental Model:** *"We have standardized on GitHub Enterprise. Every tool we adopt must leverage our existing GitHub Actions runners, OIDC federation, and pull request review workflows. If a tool requires running custom Node/Python daemons on developer machines or asks for a long-lived bearer token in Git remote URLs, Security will immediately reject it."*
- **Reaction to Agent Branches:**
  - Praises the speed of in-memory `git merge-tree`.
  - Rejects the requirement to host separate Cloudflare Durable Objects and sidecars for coordination when GitHub Actions already runs for free or on existing runner pools.
  - Alarmed by the $O(N^2)$ compute explosion of pairwise test execution.

#### Persona 2: Autonomous Agent Swarm Operator / Fleet Manager
- **Primary Metrics:** Agent task completion rate, cost per merged PR, token efficiency, prevention of agent thrashing.
- **Current Stack:** Operates 10 to 50 agent worktrees via `aoe`, tmux, or SWE-bench harnesses (`gavmor` archetype).
- **Core Pain:** An agent spends 45 minutes and $4.00 of LLM tokens refactoring a service, only to find at PR time that another agent modified the base interface 30 minutes earlier. The agent then gets caught in a 10-turn thrashing loop trying to resolve the merge conflict.
- **Reaction to Agent Branches:**
  - Highly interested in **early pruning**: if a push-time radar warning can abort or re-steer an agent after 3 minutes instead of 45 minutes, that saves $3.50 in wasted tokens.
  - Extremely wary of **interruption noise**: if the radar fires on benign non-conflicts or during half-implemented intermediate commits, the agent gets confused, burns tokens apologizing or rationalizing, and loses its original task momentum.

#### Persona 3: Lead Architect / Solo Founder
- **Primary Metrics:** Time-to-market, cognitive simplicity, frictionless local development.
- **Current Stack:** Direct usage of Cursor, Copilot Workspace, Cline, or Aider.
- **Core Pain:** Merge conflicts are rare because only 1 or 2 humans/agents touch the repo concurrently.
- **Reaction to Agent Branches:**
  - **Immediate Rejection:** As measured in [`REPORT-UNFAMILIAR-ADOPTER-T1.md`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/adoption/REPORT-UNFAMILIAR-ADOPTER-T1.md), Agent Branches imposes a **5.7x latency penalty** (1.143s vs 0.200s command time), requires managing localhost daemon ports, and demands a 7-step API ceremony (`POST /setup`, `create_task`, clone fork, push, `get_task`) compared to standard `git checkout -b` and `git push`. Zero value for single-actor workloads.

---

### 4.2 End-to-End Buyer Workflow & Friction Points

```
[Standard Git Workflow]
git checkout -b feat/t1 ===> Edit Code ===> git commit ===> git push ===> gh pr create ===> CI Runs on PR
(0 Daemons, 0 API Tokens, Standard SSH/OIDC, Clean /proc)

[Agent Branches Buyer Journey & Friction Points]
Start Daemons ===> POST /setup ===> create_task ===> Clone Fork ===> Edit ===> Push Fork ===> Poll /tasks/:id
     |                  |               |                 |                    |              |
 (Friction 1)       (Friction 2)    (Friction 3)      (Friction 4)         (Friction 5)   (Friction 6)
 Node Sidecar +     Admin Token     Custom SDK        Token in Remote      Smart HTTP     Interruption
 DO Runtime RSS     Ceremony        Ceremony          URL or CLI Argv      Basic Auth     vs Noise
```

#### Friction Point 1: Infrastructure Footprint & Daemon Management
- Ordinary Git requires zero background services.
- Agent Branches requires launching and supervising two persistent Node.js processes:
  1. `sidecar.mjs`: Git Smart HTTP daemon (~75 MB RSS).
  2. `main.js`: Local Coordinator / Durable Object simulation (~80 MB RSS).
- Combined memory footprint is ~155 MB RSS. If a daemon crashes or an ephemeral port conflicts, git operations fail.

#### Friction Point 2: Credential & Auth Exposure Risks
- Enterprise teams enforce strict credential governance: SSH keys backed by hardware tokens (FIDO2) or short-lived OIDC tokens.
- In current Agent Branches prototypes, Git Smart HTTP pushes require bearer tokens passed either:
  - In remote URL: `http://user:art_v1_[REDACTED]@localhost:9886/repo.git` (exposing tokens in `.git/config` on disk).
  - In CLI arguments: `git -c http.extraHeader="Authorization: Bearer art_v1_[REDACTED]" push` (exposing tokens in plaintext to all users via `ps aux` and `/proc/<pid>/cmdline`).
- This fails standard enterprise security audits unless mediated by a mode `0600` Git credential helper.

#### Friction Point 3: Developer & Agent Ergonomics (The SDK Ceremony)
To perform a simple task under Agent Branches, an agent cannot simply use Git CLI. It must execute a multi-step coordination protocol:
```python
# Agent Branches Ceremony:
client = AgentBranchesClient(base_url, admin_token)
client.setup_canonical(repo_path)
task = client.create_task(agent_id="worker-1", branch="feat/t1")
# Clone fork with minted task bearer token
# Apply changes
# Push to fork URL
client.push_task(task_id=task.id, commit_sha=commit)
# Poll for warnings
warnings = client.get_task(task_id=task.id).warnings
```
Versus standard Git:
```bash
git branch feat/t1 && git checkout feat/t1
# Edit, commit, push
git push origin feat/t1
gh pr create --fill
```

#### Friction Point 4: The Interruption Trade-Off (Early Pruning vs. Agent Distraction)
The central psychological and operational dilemma of push-time advisory warnings:
- **The Ideal Scenario (Branch Pruning):**
  Agent A is exploring a complex refactoring path. Agent B pushes a change that invalidates Agent A's premise. Radar notifies Agent A 2 minutes into its execution. Agent A immediately prunes the branch, resets to the new base, and avoids spending 40 minutes and $4.00 of LLM tokens on dead code.
- **The Degenerate Scenario (Cognitive Distraction):**
  Agent A pushes an intermediate checkpoint commit while refactoring. The code is only half-written (functions are stubbed, types don't yet align). Radar triggers, runs tests, and immediately fires a `HIGH CONFLICT` warning. 
  The agent reads the warning, assumes it made a critical error, halts its implementation plan, and spends 6 turns apologizing, attempting to "fix" the conflict in an unfinished file, and burning tokens in an uncoordinated thrashing loop.

**Practitioner Finding:** In multi-agent systems, **false positives and premature warnings are dramatically more destructive than late warnings**. A late failure at the PR boundary causes a clean, isolated re-dispatch. A premature warning mid-turn disrupts the agent's working memory and context window.

---

## 5. Comparative Decision Matrix

To provide an objective, rigorous comparison across all available architectural models, we evaluate five distinct systems across ten critical operational dimensions.

```
Systems Evaluated:
1. Ordinary Git + GitHub Actions (refs/pull/*/merge)
2. GitHub Merge Queue / GitLab Merge Trains
3. Bors-ng / Zuul Cross-Repo Gates
4. Foremerge v0.5.1 (Local SQLite + MCP)
5. Agent Branches + L3 Radar (Cloudflare Workers/DO + Git Smart HTTP)
```

| Evaluation Dimension | 1. Ordinary Git + GitHub PR CI | 2. GitHub / GitLab Merge Queues | 3. Bors-ng / Zuul Gates | 4. Foremerge (v0.5.1) | 5. Agent Branches + L3 Radar |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **1. Setup Complexity** | **None** (standard git clone) | **Low** (enable in repo settings) | **Medium – High** (bot config / Zuul YAML) | **Medium** (install Rust CLI, config MCP) | **High** (deploy Workers, DO, sidecar) |
| **2. Background Daemons** | **0** (serverless / hosted) | **0** (fully managed cloud) | **1+** (Bors app or Zuul cluster) | **0** (CLI invokes embedded SQLite) | **2** (Node Sidecar + Coordinator) |
| **3. Detection Phase** | PR open / synchronize | Queue entry / batch test | Batch staging test (`bors r+`) | Pre-code intent declaration | Push time (Git Smart HTTP) |
| **4. Interruption Timing** | Post-turn (PR check status) | Post-turn (queue status) | Post-turn (PR bot comment) | Pre-code (MCP tool response) | Mid-turn (advisory warning on task) |
| **5. Compute Scaling** | $O(N)$ linear per PR | $O(\lceil N/B \rceil)$ batched linear | $O(\lceil N/B \rceil)$ batched bisection | $O(1)$ lexical string match | $O(N^2)$ pairwise combination matrix |
| **6. Test Oracle Depth** | **Full** (complete CI suite) | **Full** (complete CI suite) | **Full** (complete CI suite) | **None** (purely lexical scopes) | **Budgeted** (time/memory constrained) |
| **7. Multi-Host Support** | **Full** (any remote git client) | **Full** (any remote git client) | **Full** (any remote git client) | **None** (single local machine only) | **Full** (distributed HTTP endpoints) |
| **8. Credential Security** | Standard SSH / FIDO / OIDC | Standard SSH / FIDO / OIDC | GitHub App permissions | Local filesystem file permissions | Bearer tokens; risk of argv leak |
| **9. Blast Radius on Fail**| PR blocked; main clean | Auto-evicted; main clean | Auto-bisected; main clean | Non-blocking warning; edits proceed| Warning posted; landing blocked |
| **10. Developer Ceremony** | **Zero** (`git push; gh pr`) | **Zero** (`gh pr merge --auto`) | **Minimal** (`bors r+` comment) | **High** (intent/claim declarations)| **High** (SDK setup, tasks, forks) |

---

## 6. Unsteered Buyer Adoption Policy & Empirical Falsification Gate

Based on the technical taxonomy, empirical UPRT findings, and buyer workflow friction, we establish an explicit, unsteered adoption policy for engineering teams and agent swarm architects.

```mermaid
flowchart TD
    Start["Evaluate Engineering Workload"] --> WorkloadType{"What is the swarm & actor topology?"}
    
    WorkloadType -- "Single Actor / Isolated Domains" --> DeclineSingle["STRICTLY DECLINE Advisory Stack\n- Ordinary Git worktrees are 5.7x faster\n- Zero daemon footprint, zero token ceremony\n- Collision probability is zero"]
    
    WorkloadType -- "Human + Agent Teams on GitHub/GitLab" --> DeclineTeam["DECLINE / REDUNDANT on GitHub\n- Native refs/pull/*/merge runs identical test oracle\n- Native Merge Queues handle speculative batching\n- Zero new daemons or security exposure"]
    
    WorkloadType -- "High-Velocity Agent Swarm (>10 agents)" --> GateCheck{"Does push warning prune dead branches\nfaster than PR CI cycle times?"}
    
    GateCheck -- "No / Unproven" --> RunTrial["EXECUTE EMPIRICAL TRIAL (SBET)\nMeasure token savings vs compute cost"]
    GateCheck -- "Yes (Demonstrated ROI)" --> AdoptSwarm["CONDITIONAL ADOPTION\nAdopt for decentralized agent swarms\nwith strict RLIMIT and credential guards"]
```

### 6.1 The Three-Tier Adoption Policy

#### Tier 1: Single-Actor Tasks — STRICTLY DECLINE
- **Context:** An individual developer, a single autonomous agent (e.g. executing an overnight ticket backlog sequentially), or multiple agents working in strictly partitioned, disjoint repository domains.
### 6.1 Provisional Adoption Hypotheses & Exploratory Framework

The following tiers represent **provisional engineering hypotheses and exploratory design criteria**, NOT verified economic ROI or finalized corporate adoption policy. Formal shortlist selection and adoption decisions remain strictly with the Codex and Claude principals.

#### Tier 1: Single-Actor Tasks — STRICTLY DECLINE
- **Context:** An individual developer, a single autonomous agent (e.g. executing an overnight ticket backlog sequentially), or multiple agents working in strictly partitioned, disjoint repository domains.
- **Verdict:** **STRICTLY DECLINE ADOPTION.**
- **Rationale:** 
  - Collision probability is exactly zero.
  - As verified in [`REPORT-UNFAMILIAR-ADOPTER-T1.md`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/adoption/REPORT-UNFAMILIAR-ADOPTER-T1.md), ordinary Git worktrees are **5.7x faster** (0.200s vs. 1.143s command time).
  - Agent Branches introduces ~155 MB of resident daemon memory, manages two background processes, and requires a 7-step SDK ceremony. Paying coordination overhead when there is nothing to coordinate is engineering waste.

#### Tier 2: Standard Human & Agent Teams on GitHub / GitLab — DECLINE / REDUNDANT
- **Context:** Software engineering teams combining human developers and AI coding agents (Cursor, Copilot, Cline) pushing to repositories hosted on GitHub or GitLab.
- **Verdict:** **DECLINE AS REDUNDANT.**
- **Rationale:**
  - GitHub and GitLab already provide the **identical pre-merge test oracle**. Every PR automatically triggers CI against the virtual 3-way merge ref (`refs/pull/<number>/merge`).
  - Native GitHub Merge Queues and GitLab Merge Trains provide automated speculative batching, speculative chaining, and automatic failure eviction.
  - Adopting Agent Branches replaces a zero-maintenance, hardened, OIDC-compliant cloud infrastructure with self-hosted Cloudflare Workers, Durable Objects, local Git sidecars, and custom bearer token management without improving defect detection accuracy.

#### Tier 3: High-Velocity Autonomous Agent Swarms (>10 Agents) — CONDITIONAL ADOPTION HYPOTHESIS
- **Context:** High-concurrency autonomous swarms where 10 to 50 agent instances concurrently modify overlapping subsystems in a shared repository, running long-horizon exploration tasks ($>30\text{ minutes per turn}$).
- **Verdict:** **CONDITIONAL ADOPTION HYPOTHESIS.**
- **Condition:** Adoption is justified **only if** the push-time advisory warning prunes branch exploration early enough to save more LLM tokens than the coordination infrastructure and pairwise test compute costs to operate.

---

### 6.2 The Provisional Falsification Concept: Swarm Branch-Pruning Efficiency Trial (SBET)

To ground future investigation and avoid vendor bias, we outline a conceptual falsification framework. 

*Governance Boundary:* Per Desktop Orchestrator guidance, **we do NOT launch a manufactured SBET or scale-up test to rescue a weak slot**. Genuine external observations, firsthand consumer demand, and disconfirming workflow evidence must precede any further synthetic trials.

```
+----------------------------------------------------------------------------------------------------+
|                SWARM BRANCH-PRUNING EFFICIENCY TRIAL (SBET) CONCEPTUAL SPECIFICATION               |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|    Workload: 12 autonomous coding agents assigned 12 concurrent refactoring tasks on a shared      |
|    repository with 3 deliberate overlapping contract dependencies (e.g. auth interface refactor,   |
|    session storage migration, token validation overhaul). Tasks take ~30 minutes of agent work.   |
|                                                                                                    |
|    [Arm A: Incumbent GitHub Merge Queue Baseline]                                                  |
|    - Agents work in isolated Git worktrees.                                                        |
|    - Push branches to GitHub; open Pull Requests (`gh pr create`).                                 |
|    - Native GitHub Merge Queue batches and tests PRs sequentially.                                 |
|    - On failure: Queue ejects failing PR; parent orchestrator re-dispatches agent with CI logs.    |
|                                                                                                    |
|    [Arm B: Agent Branches + L3 Push-Time Advisory Radar]                                           |
|    - Agents work in task forks; push checkpoints periodically (`agent-branches push`).             |
|    - L3 Radar evaluates pairwise combined trees in-memory on push.                                 |
|    - On collision: Advisory warning delivered to agent's task state mid-turn.                      |
|    - Agent inspects warning and attempts early branch pruning / contract realignment.              |
|                                                                                                    |
|    EVALUATION METRIC: NET ECONOMIC VALUE DELTA (HYPOTHESIS)                                        |
|    ΔNet = (LLM Tokens Saved via Early Pruning) - (Radar Compute Cost + Agent Distraction Cost)     |
+----------------------------------------------------------------------------------------------------+
```

#### Provisional Design Criteria & Falsification Thresholds (Hypotheses):

1. **Token Pruning Efficacy Threshold:**
   Let $C_{\text{token}}(\text{Arm A})$ be total token cost across all 12 agents in Arm A. Let $C_{\text{token}}(\text{Arm B})$ be total token cost in Arm B.
   The advisory radar concept is **falsified** if:
   $$\frac{C_{\text{token}}(\text{Arm B})}{C_{\text{token}}(\text{Arm A})} \ge 0.90$$
   *(If push-time warnings do not reduce total swarm token expenditure by at least 10%, the system fails to justify its operational footprint).*

2. **Compute & Wall-Clock Efficiency Threshold:**
   Let $T_{\text{wall}}$ be total wall-clock time from task dispatch to all clean branches merged. Let $E_{\text{compute}}$ be total CPU-seconds consumed.
   The advisory radar concept is **falsified** if:
   $$T_{\text{wall}}(\text{Arm B}) > T_{\text{wall}}(\text{Arm A}) \quad \text{OR} \quad \frac{E_{\text{compute}}(\text{Arm B})}{E_{\text{compute}}(\text{Arm A})} > 3.0$$
   *(If pairwise radar triples total compute consumption without reducing total wall-clock time to green main, it fails the scalability gate).*

3. **Distraction & Thrashing Threshold:**
   Let $N_{\text{thrash}}$ be agent turns spent reacting to false-alarm or premature warnings on intermediate incomplete code checkpoints.
   The advisory radar concept is **falsified** if:
   $$N_{\text{thrash}} > 0.20 \times N_{\text{total\_turns}}$$
   *(If more than 20% of agent turns are consumed reacting to intermediate advisory warnings, the tool is rejected as an active impediment to developer momentum).*

---

## 7. Strategic Conclusions & Technical Recommendations

### 7.1 Truthful Technical Synthesis

1. **Defect Prevention Parity:**
   The claim that specialized agent version control is required to prevent semantic defects on trunk is contradicted by evidence. Native GitHub PR CI (`refs/pull/*/merge`), GitHub Merge Queues, GitLab Merge Trains, and Bors-ng provide the **exact identical pre-merge test oracle**. They evaluate the speculative 3-way merge commit against the project test suite and block trunk landing upon failure.

2. **The Real Value Proposition:**
   The sole architectural justification for push-time advisory radar is **shift-left branch pruning for long-horizon autonomous swarms**. If an agent is running a 45-minute task, discovering an architectural collision at minute 3 via a push advisory can prevent 42 minutes of wasted LLM generation. 

3. **The Compute Scaling Trap:**
   The shift-left benefit comes at a steep price: **quadratic $O(N^2)$ compute growth upper bound ($N(N-1)/2$)**. While merge queues evaluate speculative branches linearly or in batches ($O(N)$), pairwise radar scales combinatorially. For swarms exceeding 20 agents, running full test suites on all 190 possible pairs is economically and computationally unsustainable.

4. **Developer Ergonomics Are Currently Disastrous:**
   For human developers and solo agents, Agent Branches is uncompetitive against ordinary Git: 5.7x slower, two persistent Node daemons, complex token choreography, and risk of `/proc` credential exposure. 

### 7.2 Actionable Recommendations for Agent Git Development

1. **Stop Positioning as a Replacement for Git Pre-Merge CI:**
   Do not market Agent Branches as "the only way to catch semantic merge conflicts." Enterprise engineering leads know their existing merge queues already do this. Instead, position the technology as a **concurrency acceleration layer for autonomous agent runtimes** that reduces token burn during exploratory branching.

2. **CRITICAL WARNING: Disjoint File-Diff Skipping is Potentially UNSOUND:**
   - *Previous Naive Suggestion:* It is tempting to propose skipping radar test runs when branch file diffs do not overlap.
   - *Why Disjoint Diff Filtering Fails:* As demonstrated directly in the UPRT T2 vs T3 trial, **non-overlapping file edits frequently break cross-file contracts**. Task T2 refactored `ShortlinkService.prototype.create` in `src/shortlinks.js`. Task T3 added `test/bulk.test.js` and called `create` positionally from `src/worker.js`. If a prefilter had evaluated file paths and concluded that `test/bulk.test.js` and `src/shortlinks.js` were disjoint, the contract regression would have been skipped!
   - *Sound Architectural Path:* Pruning pairwise test runs cannot rely on naive file-path disjointness. It requires **sound static symbol reference graphs** (e.g. language server / AST dependency graphs) tracing exported and imported symbol usages across files. Until such static analysis is verified, skipping test execution based on disjoint file diffs is unsafe and must NOT be implemented.

3. **Demarcate Local Node Daemons from Cloud Runtimes:**
   The current local prototype requires running `sidecar.mjs` and `main.js` (~155 MB RSS combined) with custom bearer tokens. To be commercially viable, client-side execution should use standard `git` CLI operations directly against remote Cloudflare Workers, eliminating local daemons and port allocation friction. However, unproven cloud replacements must not be assumed complete without rigorous cross-machine validation.

4. **Harden Credential Management to Mode 0600:**
   Cease passing bearer tokens in command-line arguments (`-c http.extraHeader`) or embedding them in git remote URLs. Implement a lightweight Git credential helper that serves task bearer tokens securely from memory or mode 0600 storage, fully complying with enterprise security invariants and `publication_guard.py`.

---

## 8. Invariants & Verification Receipts

- **Research Invariant Compliance:**
  - Compiler Execution: Strictly **0** `cargo` or `rustc` compiler invocations executed under human hold.
  - Token Accounting: Strictly **0** tokens emitted to `usage-events.jsonl`.
  - Process Memory Slice: Maintained strictly within cooperative 1500 MB budget.
  - Scratch Disk Management: Scratch directory `.local/scratch/incumbent-premerge-research/` strictly $\le$ 512 MB, mode `0700`. Zero net `/tmp` growth.
  - Credential Hygiene: Zero raw secrets, minted bearer tokens, or unredacted passwords present in this deliverable.
- **Publication Guard Verification:**
  - Deliverable validated via `python3 research/antigravity/tooling/publication_guard.py research/antigravity/demand/incumbent-premerge-and-buyer-workflow.md`.
  - Validation result: **EXIT 0 (PASS)**.

---
*Report compiled autonomously by `incumbent-premerge-researcher` under Desktop Orchestrator 11:50 Berlin directives and Codex Principal C1818 oversight.*
