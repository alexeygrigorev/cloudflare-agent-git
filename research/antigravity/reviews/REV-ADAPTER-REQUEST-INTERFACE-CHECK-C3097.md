# Independent Technical Review: Adapter Request Interface Compatibility Check (Directive C3097)

**Date & Time**: 2026-10-07T00:10:00Z (2026-10-07 02:10:00 Berlin)  
**Task ID**: `review-adapter-request-interface-check-c3097`  
**Directive**: Directive C3097 / C3091 dogfood verification (re-evaluating C3048 QL repair `d3a4276`)  
**Auditor / Independent Reviewer**: Antigravity Independent Review Agent  
**Reviewer Conversation ID**: `2531d952-f943-4fa5-8559-e9ad98224536`  
**Parent Caller ID**: `ea14b401-20e9-4e48-ab08-d15be08da30d`  
**Target Candidate Artifact**: `/home/alexey/git/cloudflare-agent-git/research/zcode/adapter-request-interface-check-20261007.md`  
**Target Artifact Commit**: `202d29a43dbd4357725d187901177450396ed0ba` (in `cloudflare-agent-git`)  
**Author / Proposer Session**: D3 (`zcode-quota-recovery-head-20261006`, engine `zcodex`)  
**Referenced Candidate Commit**: `d3a4276b7dc290c75adb4e992b2416e0a22ee4c0` (in `/home/alexey/git/agent-quota-launcher`, branch `ql-telemetry-tool-dedup-c3030`)  
**Referenced Adapter Implementation**: `/home/alexey/git/cloudflare-agent-git/scripts/coordination/consumer_execution_adapter.py` (lines 154–165 on branch `coord-adapter-launcher-align-c3046`, commit `3017d4a`)  

---

## 1. Executive Summary & Verdict

This report presents an objective, adversarial technical verification and code QA of D3's candidate artifact `research/zcode/adapter-request-interface-check-20261007.md` (published in commit `202d29a43dbd4357725d187901177450396ed0ba`), conducted under Directive C3097.

D3's artifact asserts static CLI interface compatibility between the consumer execution adapter (`scripts/coordination/consumer_execution_adapter.py`) and the `request` subcommand introduced in commit `d3a4276` of `agent-quota-launcher`. D3 further concludes with an integration recommendation claiming commit `d3a4276` "can be safely merged into the QL main branch immediately... No synchronized cross-repository updates or prerequisite pull requests in the coordination repository are required prior to this merge."

### Final Verdict: **ACCEPTED WITH CONDITIONS**

1. **Static Interface Compatibility Confirmed**: Every argument conditionally or unconditionally passed by `LauncherRequestRunner.__call__` (`--goal`, `--cwd`, `--profile`, `--timeout`, `--paths`, `--target-commit`, `--target-worktree`) is accurately implemented and supported by `launcher/cli.py` (`parser_request` lines 780–791 in commit `d3a4276`).
2. **Condition 1 (Scope Limitation to F1 CLI Interface Only)**: D3's compatibility check strictly proves CLI syntax and parameter invocation compatibility (resolving issue F1 from c3047). It does **NOT** constitute or demonstrate end-to-end runtime acceptance for Coord/Win35, which requires active systemd controller unit lifecycle supervision, socket/bus message dispatch, and multi-host admission validation.
3. **Condition 2 (Protected QL Main Lease Held by QL Head)**: D3's recommendation that commit `d3a4276` can be merged into the QL `main` branch immediately is **REJECTED AS WRITTEN**. Under Directive C3097 and project operating rules, the main QL repository integration lease is protected and owned exclusively by the QL project head (`0f125477-96a0-4474-b516-bd90ea78872d`). No delegate or worker session is authorized to execute or mandate a unilateral main branch merge. Isolated dogfooding of `d3a4276` is authorized and active in isolated worktrees/stores, but canonical promotion requires explicit QL head custody ACK.
4. **Condition 3 (Branch Location Alignment)**: `LauncherRequestRunner` in `consumer_execution_adapter.py` is currently on branch `coord-adapter-launcher-align-c3046` (commit `3017d4a`), not on `cloudflare-agent-git` `main`. Stating that "no synchronized cross-repository updates... are required" ignores the reality that both repositories have unmerged feature branches that must be promoted in coordination.
5. **Condition 4 (Provider Guard & Quota Discipline)**: Any subsequent execution or dogfooding must strictly adhere to C3065 and C3097 provider gates: preferred Space Bunny / Muse Spark 1.3 require fresh admitted maintained route receipts; no ZAI headroom may be inferred (the C3065 occupancy gate of 28 > 26 strictly holds); and no raw, ungoverned provider calls are permitted.

---

## 2. Pinned Source & Repository Verification

| Item | Target Ref | Observed State | Status |
|---|---|---|:---:|
| **Candidate Artifact Commit** | `202d29a` in `cloudflare-agent-git` | Commit `202d29a43dbd4357725d187901177450396ed0ba` contains `research/zcode/adapter-request-interface-check-20261007.md` (32 lines, 1667 bytes, author Alexey Grigorev, 2026-10-07 01:55:15 +0200). | **VERIFIED** |
| **Referenced QL Commit** | `d3a4276` in `agent-quota-launcher` | Commit `d3a4276b7dc290c75adb4e992b2416e0a22ee4c0` (`git show d3a4276 --stat`: 5 files changed, 190 insertions, 6 deletions, author Alexey Grigorev, 2026-10-06 23:49:26 +0200). | **VERIFIED** |
| **Adapter Branch Location** | `scripts/coordination/consumer_execution_adapter.py` | Lines 154–165 containing `LauncherRequestRunner` reside on branch `coord-adapter-launcher-align-c3046` (commit `3017d4a`). On `main`, lines 154–165 belong to `ConsumerExecutionAdapter.__init__`. | **NOTED / QUALIFIED** |
| **Independent Test Suite** | `tests/test_head_request.py`, `tests/test_task_profiles.py` in `agent-quota-launcher` | 26 passed in 3.26s (`pytest`). Matches prior QA in `REV-QL-REPAIR-REQUEST-PROFILE-DETECTION-C3048.md`. | **VERIFIED** |

---

## 3. Static CLI Flag Compatibility Audit

### 3.1 Parameter Mapping Table

The adapter's `LauncherRequestRunner.__call__` constructs command-line arguments as follows:

```python
req_args = ["request", "--goal", goal, "--cwd", str(cwd)]
if profile:
    req_args += ["--profile", str(profile)]
if timeout:
    req_args += ["--timeout", str(float(timeout))]
for path in payload.get("paths") or []:
    req_args += ["--paths", str(path)]
if payload.get("target_commit"):
    req_args += ["--target-commit", str(payload["target_commit"])]
    req_args += ["--target-worktree", str(payload.get("target_worktree") or cwd)]
```

Against `launcher/cli.py` (lines 780–791 in commit `d3a4276`):

```python
parser_request = subparsers.add_parser("request", help="one-command admission, validation, and execution")
parser_request.add_argument("--goal", required=True, help="Task goal/prompt")
parser_request.add_argument("--cwd", help="Task working directory")
parser_request.add_argument("--target-commit", help="Target commit SHA to validate")
parser_request.add_argument("--target-worktree", help="Path to worktree to validate commit")
parser_request.add_argument("--profile", help="Task profile")
parser_request.add_argument("--memory-mb", type=int, help="Memory override")
parser_request.add_argument("--timeout", type=float, help="Timeout override")
parser_request.add_argument("--paths", action="append", default=[])
parser_request.add_argument("--id", help="Explicit task ID")
parser_request.add_argument("--key", help="Idempotency key; resubmitting with the same key and payload safely replays (Store.submit_task)")
parser_request.set_defaults(func=request)
```

| Flag | Adapter Invocation Type | `launcher request` Parser Definition | Runtime Compatibility |
|---|---|---|:---:|
| `request` | Subcommand verb (`sub_args[0]`) | `subparsers.add_parser("request", ...)` | **COMPATIBLE** |
| `--goal` | String, unconditional | `add_argument("--goal", required=True)` | **COMPATIBLE** |
| `--cwd` | String, unconditional | `add_argument("--cwd")`, handler falls back to `os.getcwd()` if omitted | **COMPATIBLE** |
| `--profile` | String, conditional (`if profile:`) | `add_argument("--profile")`, handler passes to `resolve_task_bounds` | **COMPATIBLE** |
| `--timeout` | Float formatted as string (`str(float(timeout))`) | `add_argument("--timeout", type=float)` | **COMPATIBLE** |
| `--paths` | String per path (`action="append"`) | `add_argument("--paths", action="append", default=[])`, handler splits commas | **COMPATIBLE** |
| `--target-commit` | String, conditional | `add_argument("--target-commit")`, handler triggers `validate_source_commit` | **COMPATIBLE** |
| `--target-worktree` | String, conditional | `add_argument("--target-worktree")`, handler provides repo path to validator | **COMPATIBLE** |
| `--memory-mb` | Omitted by adapter | `add_argument("--memory-mb", type=int)`, optional override | **COMPATIBLE** |
| `--id` | Omitted by adapter | `add_argument("--id")`, defaults to `task-{uuid4().hex[:8]}` | **COMPATIBLE** |
| `--key` | Omitted by adapter | `add_argument("--key")`, defaults to `str(uuid4())` | **COMPATIBLE** |

### 3.2 Invocation Envelope and Status Polling

- **Top-Level Envelope**: `LauncherRequestRunner` invokes `[python_executable, "-m", "launcher", "--config-dir", config_dir] + sub_args`. Top-level `--config-dir` is declared in `launcher/cli.py` (`parser.add_argument("--config-dir", ...)`).
- **Status Subcommand**: Status polling issues `["status", "--id", launcher_task_id]`. In `launcher/cli.py`, `parser_status.add_argument("--id", ...)` parses this and queries `store.get_task(args.id)`.
- **Response Schema Matching**:
  - `request` returns JSON stdout: `{"task_id": ..., "controller_unit": ..., "status": ..., "profile": ..., "timeout": ..., "source_receipt": ...}`.
  - `LauncherRequestRunner` extracts `task_id = request_res.get("task_id")`, `controller_unit = request_res.get("controller_unit")`, and `source_receipt = request_res.get("source_receipt")`.
  - The JSON schema matches precisely.

---

## 4. Policy Identity and Provider Guard Evaluation (Directive C3097)

### 4.1 Evaluation of D3's Claims & Scope Limitations
In Section 3 of `adapter-request-interface-check-20261007.md`, D3 asserts:
> "Commit `d3a4276` can be safely merged into the QL main branch immediately. Because the interface surface exposed by `d3a4276` (`launcher/cli.py`, lines 780-791) fully satisfies the `request` invocation contract statically built by the consumer execution adapter (`scripts/coordination/consumer_execution_adapter.py`, lines 154-165), the changes are backward compatible with the current coordinator logic. No synchronized cross-repository updates or prerequisite pull requests in the coordination repository are required prior to this merge."

This statement is evaluated and corrected under Directive C3097 on three critical grounds:

1. **F1 CLI Interface Surface vs Full Coord/Win35 Runtime Acceptance**:
   - D3's document verifies static CLI syntax. CLI argument parsing compatibility is a necessary prerequisite, but it does **not** equal runtime admission, systemd socket activation, or multi-host transport acceptance across the coordinator bus.
   - F1 (CLI interface compatibility) is resolved, but full Coord/Win35 runtime acceptance remains open pending end-to-end multi-host execution receipts.
2. **QL Main Lease Ownership**:
   - The integration lease for `/home/alexey/git/agent-quota-launcher` `main` branch is protected and held by QL head (`0f125477-96a0-4474-b516-bd90ea78872d`).
   - Neither D3 nor any other delegate may unilaterally merge to QL `main`. Merging requires explicit custody handoff and execution by the QL project head.
   - Per Directive C3097, isolated dogfooding of `d3a4276` in isolated worktrees (such as `/home/alexey/storagebox/worktrees/ql-telemetry-tool-dedup-c3030`) and isolated stores (such as `.local/zcode-quota-recovery-head-20261006/ql-dogfood-store`) is authorized and need not wait for main merge. However, declaring that `d3a4276` can be merged immediately without coordination violates repository lease boundaries.
3. **Branch Divergence in Coordination Repo**:
   - In `cloudflare-agent-git`, `LauncherRequestRunner` is not in `main`. It resides on branch `coord-adapter-launcher-align-c3046` (commit `3017d4a`).
   - If `d3a4276` were merged into QL `main` while `cloudflare-agent-git` remained on `main`, the coordination adapter would not invoke `request`. A synchronized promotion of both branches is needed for production rollout.

### 4.2 Provider Guard & Quota Invariants
- **ZAI Occupancy Invariant**: Under Directive C3065, ZAI occupancy stands at 28 > 26. No ZAI headroom may be inferred, even if a dry-run tool reports remaining fraction 1.0. D3 properly respected this gate by forcing `model_requirements.providers=["antigravity"]` and disallowing fallback to ZAI.
- **Alternative Provider Routing**: Where Space Bunny or Muse Spark 1.3 are requested for reviews or worker tasks, they are acceptable **only** with fresh, verified admission receipts from maintained routes.
- **Anti-Self-Review Rule**: D3 generated the candidate artifact using Gemini via Antigravity. To avoid self-review, this QA review is conducted independently by a distinct reviewer session under Directive C3097, evaluating the published artifact and commit history without authoring bias.

---

## 5. Negative Cases & Invariants Audit

### 5.1 Negative Cases
1. **Missing `--goal`**:
   - In `launcher/cli.py`, `--goal` has `required=True`. Invocation without `--goal` causes `argparse` to exit with code 2 and standard error message.
   - In `LauncherRequestRunner.__call__`, `if not goal: raise ValueError(...)` fails closed before spawning any subprocess.
2. **Missing `--cwd`**:
   - In `LauncherRequestRunner.__call__`, `if not cwd: raise ValueError(...)` fails closed before spawning any subprocess.
3. **Invalid Profile**:
   - In `launcher/cli.py`, `resolve_task_bounds` raises `ValueError` for unknown profiles. Commit `d3a4276` catches this and emits structured JSON `{"error": "Profile resolution failed: ..."}` with exit code 1.
   - `LauncherRequestRunner._run` detects `res.returncode != 0` and raises `RuntimeError` containing the structured error output, causing `ExecutionUnit` to transition truthfully to `state="failed"`.
4. **Duplicate Task ID / Key Conflict**:
   - Commit `d3a4276` catches `sqlite3.IntegrityError` in `Store.submit_task` and returns structured JSON `{"error": "Task submission failed (duplicate id '...')"}` with exit code 1.

### 5.2 Physical and Environmental Invariants
- **Zero Rust Builds**: Verified. No rust toolchains or builds invoked.
- **Zero NPM Builds**: Verified. No npm/node build commands executed.
- **Zero Purchases**: Verified. No financial or billable resources engaged.
- **Zero Disk Leaks**: Verified. No uncommitted scratch files or untracked state created outside designated review output.
- **Zero Code Modification**: Verified. No implementation files modified in `cloudflare-agent-git` or `agent-quota-launcher`. Zero git commits created.

---

## 6. Review Summary & Next Steps

| Checkpoint | Target | Result | Action Required |
|---|---|---|---|
| **CLI Argument Surface** | `consumer_execution_adapter.py` vs `d3a4276:launcher/cli.py` | **100% MATCH** | None for CLI surface. |
| **Test Verification** | `agent-quota-launcher` 26 tests | **26/26 PASSED** in 3.26s | Baseline functional integrity confirmed. |
| **Runtime Acceptance** | Coord/Win35 multi-host runtime | **PENDING** | End-to-end controller & transport verification required. |
| **QL Main Integration Lease** | Custody with QL Head `0f125477` | **PROTECTED** | Do not merge to `main` without explicit QL head ACK. Continue isolated dogfood in worktree. |
| **Coordination Repo Branch** | `coord-adapter-launcher-align-c3046` | **UNMERGED** | Keep tracked for coordinated release when QL main integration is scheduled. |

**Final Verdict**: **ACCEPTED WITH CONDITIONS**
