# Automated Seeded Transport & Conflict Comparison: Scripted Two-Actor Profile Fixture vs. Ordinary Git Baseline

**Tag**: `consumer-decision-observer` (Native harness subagent helper under `antigravity-head` `46fdb644`)  
**Parent Authority**: `antigravity-head` (`46fdb644-9b58-4e2f-aab3-9be5e1e33337`)  
**Directive**: Codex Principal C1525 Task C / C1534 review: Automated seeded transport and conflict comparison with actor fiction explicit, removal of adoption/winner overclaims, and preregistration of authentic newcomer task  
**Workspace**: `/home/alexey/git/cloudflare-agent-git`  
**Scratch Root**: `/home/alexey/git/cloudflare-agent-git/.local/scratch/consumer-decision-observation` (mode 0700, <= 512 MB budget; measured 429 KiB)  
**Date**: 2026-10-04  
**Status**: RESCOPED & FACTUAL (Scripted Comparative Smoke & Negative Infrastructure Cost Receipts)

---

## 1. Executive Summary & Verification Scope

> [!CAUTION]
> **Explicit Scope & Actor Fiction Disclosure (C1534)**:
> This document records an **automated, scripted transport and conflict comparison** executed by a test script simulating two scripted personas ("Alice" and "Bob") on a synthetic user profile fixture (`src/profile_service.py`). **This is NOT an independent newcomer agent observation, nor is it evidence of consumer adoption or human developer decision-making.**

### Confounding Factor Disclosure
In this scripted run, Workflow 1 simulates a developer leaving changes **uncommitted in a dirty working tree** and executing `git pull`, triggering Git's local change collision protection and requiring `git stash`. In contrast, Workflow 2 commits work directly to an isolated task fork.

**This comparison confounds workspace isolation mechanisms with commit policy.** A developer utilizing ordinary Git best practices (e.g. isolated Git worktrees, dedicated topic branches, or local WIP commits combined with `git merge-tree`) preserves canonical `main`, avoids dirty working tree pull aborts, and eliminates stash stack corruption—entirely within standard Git without running HTTP sidecars or coordinator daemons.

### Comparative Mechanics Summary

| Metric / Dimension | Workflow 1: Scripted Ordinary Git Pull/Stash | Workflow 2: Scripted Agent-Branches Protocol | Observed Trade-offs & Mechanics |
|---|---|---|---|
| **Script Execution Wall Time** | **0.48 s** | **1.48 s** | Ordinary Git runs ~3x faster; protocol requires daemon startup and HTTP handshakes |
| **Commands to First WIP** | **4 commands** (`clone`, `config` x2, edit) | **7 commands** (API `create_task`, auth clone, config x2, edit, commit, push) | Ordinary Git requires fewer onboarding steps before local work begins |
| **Total Scripted Commands** | **26 commands** | **24 commands** | Comparable command sequence length |
| **Encountered Script Errors** | **3 errors** (dirty-tree pull reject, stash-pop conflict, syntax error in test) | **1 error** (URL credential encoding failure) | Reflects script setup: uncommitted pull forces stash; raw query token breaks curl |
| **Dirty Tree / Stash Overhead** | **Manual stash cycle**: `git stash push` + `pop` failed with conflict | **Zero stash**: WIP committed and pushed directly to isolated task fork | Ordinary Git worktrees or topic branches achieve identical stash elimination |
| **Conflict Discovery Latency** | **Pull-time / Reactive**: Detected upon `git pull` / `git stash pop` | **Push-time / Background**: **74.29 ms** via background `git merge-tree` | Background radar discovers textual overlap at push time before local merge |
| **Semantic Test Execution in Radar** | N/A (tested locally after conflict) | **None** (`policy.tests.command: null`) | This radar run only executed textual `merge-tree`; no semantic tests collected |
| **Rollback / Recovery Mechanics** | Requires manual resolution and `git stash drop` | 1 command clean clone from fork or reset; canonical `main` untouched | Both workflows preserve canonical `main` if topic branches/worktrees are used |
| **Infrastructure Dependencies** | **Zero dependencies**: Standard native Git CLI | **Heavy dependencies**: Requires Git Smart-HTTP sidecar + Coordinator daemons | Agent-Branches introduces external operational failure modes |

---

## 2. Preregistered Friction Criteria & Execution Bounds

Four concrete developer friction criteria and strict wall-clock time limits were preregistered prior to running the scripted comparison:

```json
{
  "tag": "consumer-decision-observer",
  "max_disk_budget_mb": 512.0,
  "time_limit_per_workflow_sec": 120.0,
  "friction_criteria": {
    "F1": {
      "name": "Onboarding & Auth Complexity",
      "description": "Number of setup steps, credentials, headers, and encoding needed before first commit"
    },
    "F2": {
      "name": "WIP Isolation & Stash Overhead",
      "description": "Risk of dirty working tree collisions or manual stashing overhead when upstream advances"
    },
    "F3": {
      "name": "Conflict Visibility & Detection Latency",
      "description": "Time elapsed and mechanisms required before concurrent divergence is detected"
    },
    "F4": {
      "name": "Recovery & Rollback Ergonomics",
      "description": "Ease of restoring clean state on broken experiments and avoiding detached HEAD / lingering stash"
    }
  }
}
```

---

## 3. Scripted Execution Traces

### 3.1 Scenario Fixture Definition

Both workflows run against a synthetic profile service fixture:
- **Baseline Commit (`a02107a9...`)**:
  - `src/profile_service.py`: defines `get_user_profile(user_id)` returning `{id, status, email}`.
  - `tests/test_profile_service.py`: unit tests verifying profile retrieval and email updates (PASS 3/3).
- **Actor Alice (Scripted)**: Edits `get_user_profile` to add user bio:
  ```python
  "bio": "Software engineer and distributed systems enthusiast"
  ```
- **Actor Bob (Scripted Concurrent Colleague)**: Concurrently edits `get_user_profile` on the identical dictionary lines to add a phone number:
  ```python
  "phone": "+1-555-0199-CONCURRENT"
  ```

```mermaid
flowchart TB
    subgraph Baseline["Baseline Commit (main)"]
        BASE["get_user_profile() -> {id, status, email}"]
    end

    subgraph AliceLane["Alice (Scripted Persona)"]
        ALICE_EDIT["Edit: add 'bio' field"]
    end

    subgraph BobLane["Bob (Scripted Persona)"]
        BOB_EDIT["Edit: add 'phone' field (identical lines)"]
    end

    BASE --> ALICE_EDIT
    BASE --> BOB_EDIT

    subgraph W1["Workflow 1: Ordinary Git Pull/Stash"]
        W1_STASH["1. git pull -> REJECTED (uncommitted dirty tree)\n2. git stash push\n3. git pull -> OK\n4. git stash pop -> CONFLICT\n5. SyntaxError in tests (conflict markers)\n6. Orphaned stash@{0} on stack"]
    end

    subgraph W2["Workflow 2: Agent-Branches Protocol"]
        W2_FORK["1. SDK create_task -> isolated fork\n2. git push WIP to fork (main untouched)\n3. Post-receive webhook (139ms)\n4. Radar trial-merge (74.29ms)\n5. Warning in GET /status\n6. Zero stash; canonical main 100% clean"]
    end

    ALICE_EDIT -.-> W1
    BOB_EDIT -.-> W1
    ALICE_EDIT -.-> W2
    BOB_EDIT -.-> W2
```

---

### 3.2 Workflow 1: Scripted Ordinary Git Execution Trace

1. **Setup**: Central bare Git repository `upstream.git` seeded with baseline profile service.
2. **Alice Local Setup**: Cloned `upstream.git` to `alice_local`. Made uncommitted edits to `src/profile_service.py` to add `bio`.
3. **Bob Concurrent Push**: Cloned `upstream.git` to `bob_local`. Modified `src/profile_service.py` to add `phone`, committed, and pushed directly to `origin/main` (`bob_sha`: `e1ddffe8...`).
4. **Alice Integration Attempt**:
   - Alice executes `git pull origin main`.
   - **Failure 1 (F2 Dirty Tree Collision)**: Git aborts because uncommitted local changes would be overwritten:
     ```
     error: Your local changes to the following files would be overwritten by merge:
             src/profile_service.py
     Please commit your changes or stash them before you merge.
     Aborting
     ```
   - Script runs `git stash push -m "WIP bio changes"`.
   - Script runs `git pull origin main` (succeeds).
   - Script runs `git stash pop`.
   - **Failure 2 (F3 Merge Conflict on Pop)**:
     ```
     Auto-merging src/profile_service.py
     CONFLICT (content): Merge conflict in src/profile_service.py
     Unmerged paths:
             both modified:   src/profile_service.py
     The stash entry is kept in case you need it again.
     ```
   - **Failure 3 (F3 Test Breakage due to Conflict Markers)**: Running `python3 -m unittest discover tests` fails with a `SyntaxError` due to raw Git conflict markers:
     ```python
     <<<<<<< Updated upstream
             "phone": "+1-555-0199-CONCURRENT",
     =======
             "bio": "Software engineer and distributed systems enthusiast",
     >>>>>>> Stashed changes
     ```
   - **Failure 4 (F4 Lingering Stash State)**: `git stash list` retains `stash@{0}: On main: WIP bio changes`. Because a conflict occurred during pop, Git preserves the stash entry on the stack until manually dropped.
5. **Resolution & Recovery**:
   - Script manually edits `src/profile_service.py` to combine both `bio` and `phone`.
   - Script stages and commits: `git add src/profile_service.py && git commit -m "fix(profile): resolve conflict"`.
   - Script executes `git stash drop stash@{0}` to clean the stash stack.

---

### 3.3 Workflow 2: Agent-Branches Protocol Execution Trace

1. **Setup**:
   - Spun up ephemeral Smart-HTTP sidecar (`port: 45273`) and Coordinator runtime (`port: 33659`).
   - Created canonical repository `profile-service-canonical` and seeded baseline (`base_sha`: `a02107a9...`).
2. **Alice Task Creation & Onboarding (F1)**:
   - Script calls `AgentBranchesClient.create_task()`:
     ```python
     alice_task = client.create_task(
         repo="profile-service-canonical",
         base_sha="a02107a9...",
         intent="add user profile bio",
         branch="main",
         agent="alice-agent",
         admin_token=ADMIN_TOKEN,
     )
     ```
   - Returned `taskId`: `task-0001`, `agentId`: `alice-agent-0001`, `fork`: `{name: "profile-service-canonical-alice-agent-0001", remote: "..."}`, `token.plaintext`: `[REDACTED]?expires=1791083674`.
   - **F1 Authentication Hurdles Observed**:
     - *Hurdle A (Unencoded Token in URL)*: Attempting to clone with raw token in URL (`http://token:secret?expires=123@host/...`) failed with:
       ```
       fatal: unable to access 'http://127.0.0.1:45273/...': URL rejected: Port number was not a decimal number between 0 and 65535
       ```
       *Root Cause*: Git's `libcurl` parses `?` as the query string delimiter, misinterpreting `@host:port` as query parameters.
       *Remedy*: Credentials embedded in HTTP URLs must be explicitly percent-encoded (`urllib.parse.quote(token, safe="")`).
     - *Hurdle B (401 Challenge Handshake)*: Probes (`GET /info/refs?service=git-upload-pack`) receive `401 Unauthorized` with `WWW-Authenticate: Basic realm="git"` before git retries with basic auth headers.
3. **Alice WIP Isolation & Push (F2)**:
   - Script clones fork using the percent-encoded URL.
   - Script edits `src/profile_service.py` to add `bio`.
   - Script commits WIP locally and pushes:
     ```bash
     git commit -am "WIP: add bio to profile"
     git push origin HEAD:refs/heads/main
     ```
   - Sidecar post-receive hook delivered push notification to coordinator `/events/push` in **139.0 ms**.
   - Coordinator head vector updated: `heads: {"alice-agent-0001": "11495d3a..."}`.
4. **Bob Concurrent Task & Push**:
   - Script creates task `task-0002` (`bob-agent-0002`), clones fork, edits `src/profile_service.py` to add `phone`, commits, and pushes (`bob_sha`: `4065a511...`).
   - Sidecar post-receive webhook updated coordinator head vector in **211.4 ms**.
5. **Background Radar Evaluation & Textual Conflict Detection (F3)**:
   - Evaluation runner fetched heads from Alice and Bob's bare forks into the evaluation repo.
   - `RadarEngine.run_matrix()` executed `git merge-tree --write-tree --merge-base=a02107a9... 11495d3a... 4065a511...`.
   - Total radar execution & submission latency: **74.29 ms**.
   - **Disclosure on Test Scope**: The submitted policy declared `"tests": { "command": null, "budget_s": 15.0 }`. **No semantic tests were executed or collected during this radar evaluation.** Only textual conflict detection was performed.
   - CONTRACT 0.1 payload submitted via `client.send_checks()`:
     ```json
     {
       "contract": "0.1",
       "vector": {
         "alice-agent-0001": "11495d3a2edf1a7e0ab413bf45c2b4c6c41054a5",
         "bob-agent-0002": "4065a51133f937bbd1279db347f899732372f286"
       },
       "policy": { "merge": "git-merge-tree", "tests": { "command": null, "budget_s": 15.0 } },
       "results": [
         {
           "pair": ["alice-agent-0001", "bob-agent-0002"],
           "heads": {
             "alice-agent-0001": "11495d3a2edf1a7e0ab413bf45c2b4c6c41054a5",
             "bob-agent-0002": "4065a51133f937bbd1279db347f899732372f286"
           },
           "status": "conflict",
           "kind": "textual",
           "evidence": {
             "summary": "Auto-merging src/profile_service.py\nCONFLICT (content): Merge conflict in src/profile_service.py",
             "files": ["src/profile_service.py"]
           }
         }
       ]
     }
     ```
   - Coordinator created active warning `warn-1` on pair `[alice-agent-0001, bob-agent-0002]`.
   - Script queries `client.get_status()` and observes the warning prior to canonical merge.
6. **Recovery & Rollback Mechanics (F4)**:
   - Canonical `main` branch verified untouched at `a02107a9...`.
   - Disposable recovery clone of Alice's fork verified byte-for-byte SHA match (`11495d3a...`).

---

## 4. Measured Performance & Physical Receipts

### 4.1 Script Execution Wall-Clock Latency

| Phase / Step | Workflow 1: Scripted Ordinary Git | Workflow 2: Scripted Agent-Branches Protocol |
|---|---|---|
| **Infrastructure & Environment Startup** | 135.1 ms (local git init & seed) | 600.9 ms (sidecar + coordinator daemons) |
| **Alice Onboarding & Clone** | ~20 ms | 114.8 ms (HTTP auth handshake & clone) |
| **Alice WIP Commit & Push** | N/A (uncommitted local dirty edit) | 139.1 ms (git push HTTP + webhook update) |
| **Bob Concurrent Commit & Push** | 70.2 ms (push directly to `origin/main`) | 211.4 ms (push HTTP + webhook update) |
| **Conflict Discovery Latency** | **171.1 ms** (measured at scripted `git pull` & `stash pop`) | **74.29 ms** (measured at scripted `git merge-tree` radar) |
| **Recovery / Resolution Time** | 79.1 ms (manual resolution & stash drop) | 58.7 ms (disposable recovery clone) |
| **Total Script Wall-Clock Elapsed** | **0.48 s** | **1.48 s** |

*Note: The 0.48s vs 1.48s timings reflect the raw execution duration of the Python test script on localhost. They do not represent human developer cognitive time, autonomous agent action-rates, or real-world repair effort.*

### 4.2 Storage and Memory Utilization

- **Scratch Disk Usage**: `0.41 MB` (**429,916 bytes**), strictly conforming to the **<= 512 MB budget** (< 0.08% of budget).
- **Sidecar Process RSS**: `81,228 KB` (**79.3 MB**).
- **Coordinator Process RSS**: `80,588 KB` (**78.7 MB**).
- **Host Cleanup**: All background Node daemons and child processes cleanly terminated upon completion (0 leaked zombies).

---

## 5. Authentic Negative Infrastructure Costs & Usability Friction

The primary empirical value of this run is documenting the real operational hurdles introduced by the Agent-Branches infrastructure:

1. **Mandatory Daemon & Infrastructure Overhead**:
   - Ordinary Git requires no background services; developers operate 100% offline with standard CLI tooling.
   - Agent-Branches introduces two mandatory network daemons (Git Smart-HTTP sidecar + Coordinator). If either daemon crashes or experiences network degradation, git push, task creation, and radar checks fail completely.
2. **URL Credential Encoding Trap**:
   - Tokens containing expiration queries (`?expires=<timestamp>`) break standard Git HTTP clone URLs because `libcurl` parses `?` as a query delimiter.
   - Developers or tooling must percent-encode credentials or configure custom `http.extraHeader` directives.
3. **Multi-Tier Bearer Token Hierarchy**:
   - The protocol requires managing three distinct credential classes: Admin Bearer token, Runner Bearer token, and Scoped Repository tokens. This creates higher cognitive and configuration complexity than standard SSH keys or personal access tokens.
4. **Tooling & API Boundary**:
   - Ordinary Git CLI cannot create tasks or forks autonomously. Developers must use the Python SDK (`AgentBranchesClient`) or make raw HTTP `POST /tasks` calls.

---

## 6. Preregistration: Authentic Next-Step Newcomer Task

Per Codex Principal C1534 review, scripted two-actor fixtures on toy repositories cannot substitute for genuine multi-agent coordination observation. We therefore preregister the following authentic newcomer task:

### Specification: Authentic Bound Newcomer Adoption Task
1. **Target Artifact**: An existing independent bound actor (e.g. `zcode-sdk-adopt` or Muse) will consume the real product diff and runner artifacts generated during the Real Product First-Use Run (`REAL-PRODUCT-FIRSTUSE-REPORT.md` / `product_firstuse_results.json`).
2. **Matched Baseline**:
   - **Arm A (Ordinary Git Worktree Baseline)**: The actor undertakes an authentic maintenance task on `agent_branches` in a standard Git worktree with local topic branches and WIP commits.
   - **Arm B (Agent-Branches Protocol)**: The actor undertakes the identical maintenance task using `AgentBranchesClient` task forks and Smart-HTTP.
3. **Measurement & Preregistration**:
   - Record actual model reasoning traces, executed shell commands, tool invocations, and wall-clock repair effort.
   - Preregister expected error rates and friction checkpoints *before* the actor observes any radar warnings or coordinator status payloads.
   - Zero manufactured conflicts, zero forced synthetic bugs, and zero fictional actor scripting.
