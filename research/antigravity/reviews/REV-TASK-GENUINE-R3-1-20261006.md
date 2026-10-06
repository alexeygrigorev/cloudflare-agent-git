# Independent Technical Audit: Task `task-genuine-r3-1` in `agent-quota-launcher`

**Date & Time**: 2026-10-06T00:50:00Z (2026-10-06 02:50:00 Berlin)  
**Auditor / Reviewer**: `antigravity` (Independent Technical Auditor)  
**Caller / Invoker**: `ea14b401-20e9-4e48-ab08-d15be08da30d`  
**Target Repository**: `/home/alexey/git/agent-quota-launcher`  
**Audited Task**: `task-genuine-r3-1` (Idempotency Key: `ql-core-3-genuine-1`)  
**Child Session ID**: `568e4017-5b38-4f4a-bf5e-1eaeffef3c73`  
**Child Tag**: `task-task-genuine-r3-1`  
**Provider & Model**: `zai` / `glm-5.3-flash` (via `zcodex exec`)  
**Deliverables Audited**:
1. `/home/alexey/git/agent-quota-launcher/.local/first-action-task-genuine-r3-1.json`
2. `/home/alexey/git/agent-quota-launcher/examples/launch-contract-report.md`
3. `/home/alexey/git/agent-quota-launcher/.local/launch-task-genuine-r3-1.json`
4. `/home/alexey/git/agent-quota-launcher/.local/launch-task-genuine-r3-1-start.json`
5. `/home/alexey/git/agent-quota-launcher/.local/launcher-config/state.db`

**Final Audit Verdict**: **ACCEPTED**

---

## 1. Executive Summary & Acceptance Matrix

An adversarial, rigorous peer review and technical audit was conducted on task `task-genuine-r3-1` in `agent-quota-launcher`. The task represents the core-3 genuine run executed on 2026-10-04, launched via the `launcher run` command to produce a genuine first-action artifact and an in-depth review comparing `README.md` against `SPEC.md`.

Every acceptance criterion defined for this audit was rigorously examined against disk artifacts, Git commit history (`b79ae70`, `c19c787`), database records, and line-by-line file verification.

### Audit Acceptance Matrix

| # | Inspection Criterion | Requirement | Observed Evidence | Verdict |
|---|---|---|---|:---:|
| **1** | **First Tool Action JSON Schema** | Whoami-shaped JSON containing **only** `id`, `tag`, `workspace`, `timestamp`. | `.local/first-action-task-genuine-r3-1.json` contains exactly 4 keys: `id`, `tag`, `workspace`, `timestamp`. No wrapper start keys (`command`, `phase`, `parent_session`, `schema_version`) or extra keys exist. | **PASS** |
| **2** | **First Tool Action Identity Match** | `id`, `tag`, and `workspace` must match the actual launched session. | `id`: `568e4017-5b38-4f4a-bf5e-1eaeffef3c73`<br>`tag`: `task-task-genuine-r3-1`<br>`workspace`: `/home/alexey/git/agent-quota-launcher`. All three perfectly match `launch-task-genuine-r3-1-start.json` and `launch-task-genuine-r3-1.json`. | **PASS** |
| **3** | **Deliverable Axis 1: Identity & First Action** | Report must cover whoami-shaped JSON vs wrapper start records, and SPEC requirements. | Section 1 (lines 30–50) and Appendix (lines 96–111) explicitly detail whoami vs engine start records, cite SPEC.md:6 & 12, explain wrapper field exclusion, and note residual `--paths` CLI convention. | **PASS** |
| **4** | **Deliverable Axis 2: Accept vs Exit 0** | Report must cover guarded state transitions (`completed-awaiting-review -> accepted`), reviewer identity, and exit 0 != acceptance. | Section 2 (lines 52–68) and Appendix (lines 112–125) thoroughly analyze "Exit 0 is not acceptance", the mandatory `--reviewer` requirement, confirmed native death, and non-empty result evidence gates. | **PASS** |
| **5** | **Deliverable Axis 3: Resource Gates** | Report must verify 1500MiB worker cap, 10GiB MemAvailable floor, and 50GiB+512MiB disk budget. | Section 3 (lines 69–80) and Appendix (lines 126–141) audit worker memory <= 1500 MiB, host MemAvailable >= 10 GiB, 50 GiB + 512 MiB spike budget, `/tmp` rejection, and TMPDIR `.local/tmp` containment. | **PASS** |
| **6** | **Verifiable File & Line References** | All citations to `SPEC.md` and `README.md` must be verifiable with line accuracy. | Verified against `SPEC.md` (lines 4, 6, 10, 12, 14, 16) and `README.md` (lines 16–22, 24–26, 30, 43, 46–47, 55, 76). Line numbers are exact. | **PASS** |
| **7** | **Truthful Discrepancies Noted** | Gaps, limitations, and historical contract evolutions must be stated honestly. | Report honestly documents residual CLI gap (no dedicated `--first-action-path` flag), pre-b79ae70 omissions, and explicitly caveats that it is a documentation review, not a self-certification of execution. | **PASS** |
| **8** | **Lifecycle & Non-Self-Acceptance** | Task must not be self-accepted by worker; state must reflect completed-awaiting-review. | Verified in `launcher-config/state.db`: task state is `completed-awaiting-review`, reviewer is `quota-launcher-core-3`, leases held until independent review. | **PASS** |

---

## 2. Artifact Inspection & Verification

### 2.1 First Tool Action: `.local/first-action-task-genuine-r3-1.json`

The file `/home/alexey/git/agent-quota-launcher/.local/first-action-task-genuine-r3-1.json` was inspected directly:

- **Filesystem Metadata**: Size 181 bytes, permissions `0600` (`-rw-------`), modified `2026-10-04 14:30:34` (local) / `2026-10-04T12:30:34Z`.
- **Exact File Content**:
```json
{
  "id": "568e4017-5b38-4f4a-bf5e-1eaeffef3c73",
  "tag": "task-task-genuine-r3-1",
  "workspace": "/home/alexey/git/agent-quota-launcher",
  "timestamp": "2026-10-04T12:28:32Z"
}
```

#### Schema and Key Whitelist Verification
- **Key count**: Exactly 4 keys.
- **Key presence**: `{"id", "tag", "workspace", "timestamp"}`.
- **Absence of engine/wrapper start keys**: Zero occurrences of `command`, `phase`, `parent_session`, `schema_version`, `worker_pid`, `limits`, or other start-record fields.
- **Timestamp format**: Valid UTC ISO-8601 string (`2026-10-04T12:28:32Z`).
- **Timestamp temporal correlation**:
  - Task started: `2026-10-04T12:28:31.002776+00:00` (from `launch-task-genuine-r3-1.json`).
  - First action generated: `2026-10-04T12:28:32Z` (exactly 1 second after launch).
  - First action validated by launcher: `2026-10-04T12:30:34.794894+00:00`.
- **Identity correlation**:
  - `id` matches `launch-task-genuine-r3-1.json:session_id` (`568e4017-5b38-4f4a-bf5e-1eaeffef3c73`).
  - `workspace` matches `/home/alexey/git/agent-quota-launcher`.
  - `tag` matches `task-task-genuine-r3-1`.

#### Adversarial Finding: The Double Prefix in Tag (`task-task-genuine-r3-1`)
A critical inquiry was made into why the tag is `task-task-genuine-r3-1` rather than `task-genuine-r3-1`.
1. In `launcher/launch.py` at commit `b79ae70` (line 240), the launcher computed the run tag as:
   ```python
   run_tag = f"task-{task_id}"
   ```
   Because `task_id` was already named `task-genuine-r3-1`, string interpolation produced `task-task-genuine-r3-1`.
2. When the subagent started in `aplexer`, `aplexer whoami --json` faithfully returned `tag: "task-task-genuine-r3-1"`.
3. In accordance with its prompt instructions ("run \`aplexer whoami --json\`, then write ONLY these four keys taken from its output..."), the child subagent extracted this exact tag without altering it.
4. Subsequently, in commit `c19c787` (QL-CORE-003 R1), the project team noticed this prefix duplication bug and created `launcher/tags.py` with `run_tag_for(task_id)`:
   ```python
   def run_tag_for(task_id):
       tid = str(task_id)
       return tid if tid.startswith("task-") else f"task-{tid}"
   ```
   **Auditor Assessment**: The presence of `task-task-genuine-r3-1` in the first-action JSON is genuine, un-faked, photographic proof of actual subagent execution under `b79ae70`, rather than synthetic hindsight data.

---

### 2.2 Deliverable Inspection: `examples/launch-contract-report.md`

The deliverable `/home/alexey/git/agent-quota-launcher/examples/launch-contract-report.md` (145 lines, 9,871 bytes) was thoroughly inspected.

The document is organized into two primary segments:
1. **Re-verification Section (Lines 8–92)**: Re-evaluates `README.md` at commit `c19c787` (R1) following the documentation rewrite in `b79ae70`.
2. **Original Review Appendix (Lines 94–145)**: Preserves verbatim the initial review produced by child session `568e4017` on `2026-10-04T12:28:32Z` against the pre-`b79ae70` working draft.

#### Detailed Coverage of Three Mandatory Axes:

#### Axis 1: Identity and First Action
- **Report Analysis (Lines 30–50, 96–111)**:
  - Details the contract requiring that the child's first tool action must write native `whoami` output to the designated first-action artifact path.
  - Explains the distinction between agent-written first actions and wrapper/engine start records (which contain `command`, `phase`, `parent_session`, and `schema_version`).
  - Verifies compliance with [SPEC.md:12](file:///home/alexey/git/agent-quota-launcher/SPEC.md#L12) (whoami tag/workspace match, native first action distinct from the wrapper started marker).
  - Documents the historical transition in `validate_first_action`: from the initial strict 4-key blacklist to the R1 identity matching against the launch start record (which accepts rich native whoami while rejecting byte-identical or reformatted echoes of the start record).
  - **Residual Discrepancy Noted**: Honestly highlights that [SPEC.md:6](file:///home/alexey/git/agent-quota-launcher/SPEC.md#L6) requires tasks to carry dedicated first-action and expected-result artifact paths, whereas the CLI implements this by convention inside generic `--paths` without dedicated CLI arguments.

#### Axis 2: Accept versus Exit 0
- **Report Analysis (Lines 52–68, 112–125)**:
  - Strongly asserts the core architectural invariant: **"Exit 0 is not acceptance."**
  - References [SPEC.md:14](file:///home/alexey/git/agent-quota-launcher/SPEC.md#L14) and [SPEC.md:4](file:///home/alexey/git/agent-quota-launcher/SPEC.md#L4).
  - Verifies that `accept` only permits transitioning tasks from `completed-awaiting-review -> accepted` and requires `--reviewer <identity>`.
  - Confirms that queued, running, and `launch-uncertain` states cannot be accepted or marked complete.
  - Documents the R1 strengthened guards: `complete` refuses execution until native process death is confirmed and requires non-empty result artifact evidence; death without evidence must be closed via `fail --reason`.
  - Confirms `plan` is strictly dry-run without state transitions.

#### Axis 3: Resource Gates
- **Report Analysis (Lines 69–80, 126–141)**:
  - Confirms worker memory cap: **requested worker memory <= 1500 MiB** ([SPEC.md:12](file:///home/alexey/git/agent-quota-launcher/SPEC.md#L12)).
  - Confirms host memory floor: **MemAvailable minus active reservations >= 10 GiB** ([SPEC.md:12](file:///home/alexey/git/agent-quota-launcher/SPEC.md#L12)).
  - Confirms disk requirements: **cwd and TMPDIR filesystems >= 50 GiB + active reservations + 512 MiB spike budget** ([SPEC.md:12](file:///home/alexey/git/agent-quota-launcher/SPEC.md#L12)).
  - Confirms TMPDIR path containment: `/tmp` is strictly rejected ([SPEC.md:16](file:///home/alexey/git/agent-quota-launcher/SPEC.md#L16)), and TMPDIR must resolve under the owned repository path `<repo>/.local/tmp` via `Path.is_relative_to`.
  - Verifies ranking constraints: bounded reset multiplier `[1, 3]`, unknown health/task_fit weighted at 0, and promotional cutoff `2026-10-06T16:00Z` ([SPEC.md:10](file:///home/alexey/git/agent-quota-launcher/SPEC.md#L10)).

---

## 3. Verifiable File & Line Reference Audit

Every citation in `examples/launch-contract-report.md` was cross-checked against the referenced files:

| Citation | Cited Text / Subject | Target File Line | Actual Line Content / Verification | Status |
|---|---|---|---|:---:|
| `SPEC.md:4` | Runnable examples for subcommands; plan is dry-run | Line 4 | *"Subcommands init, submit, plan, run, status, complete/accept, report; names may vary but document exact runnable examples. Plan is always dry-run and never represented as live execution."* | **EXACT MATCH** |
| `SPEC.md:6` | Task fields: first-action artifact path, expected result artifact path | Line 6 | *"Tasks require stable id/idempotency key, goal, owner/head, cwd, exclusive owned paths... first-action artifact path, expected result artifact path..."* | **EXACT MATCH** |
| `SPEC.md:10` | Ranking formula, [1, 3] reset multiplier, 2026-10-06T16:00Z cutoff | Line 10 | *"Rank eligible candidates using task fit, health/outcome evidence... reset-pressure bonus... Promotion ONLY verified ZCode >=3.10... cutoff 2026-10-06T16:00Z."* | **EXACT MATCH** |
| `SPEC.md:12` | 1500MiB worker memory, 10GiB MemAvailable floor, 50GiB+512MiB disk, .local/tmp, whoami verification | Line 12 | *"Admission: atomic sum of live reservations, requested worker memory <=1500MiB and host available minus reservations and requested budget >=10GiB; actual target cwd and TMPDIR filesystem >=50GiB + active disk reservations + 512MiB spike; use owned root .local/tmp... inside wrapper aplexer whoami --json must match expected tag/workspace."* | **EXACT MATCH** |
| `SPEC.md:14` | Lifecycle, exit zero != accepted, reviewer identity | Line 14 | *"Durable lifecycle queued/reserved/starting/running/completed-awaiting-review/accepted/failed/blocked/launch-uncertain. Head reviews artifacts; exit zero != accepted."* | **EXACT MATCH** |
| `SPEC.md:16` | /tmp reject, genuine bounded launched task | Line 16 | *"Tests need adverse behavior (... /tmp reject ...). Include one genuine bounded launched useful task with first action, incremental artifact and reviewed result."* | **EXACT MATCH** |
| `README.md:25` | Generic `--paths` in submit example | Line 25 | `    --paths .local/artifact.json` | **EXACT MATCH** |
| `README.md:34` | `--tmpdir` resolving under `.local/tmp` | Line 34 | `    --tmpdir /home/alexey/git/agent-quota-launcher/.local/tmp` | **EXACT MATCH** |
| `README.md:43-48` | `complete`, `accept`, `fail` requiring `--reviewer` | Lines 43–48 | Run examples explicitly include `--reviewer head-x` on all completion subcommands. | **EXACT MATCH** |
| `README.md:55` | "Exit 0 is not acceptance" invariant | Line 55 | `**Exit 0 is not acceptance.** accept only moves completed-awaiting-review -> accepted...` | **EXACT MATCH** |
| `README.md:76` | Resource gate thresholds | Line 76 | `Worker memory <= 1500 MiB; host MemAvailable must retain >= 10 GiB... 50 GiB + active reservations + 512 MiB spike; /tmp is rejected...` | **EXACT MATCH** |

All line references in `examples/launch-contract-report.md` are completely verifiable, truthful, and precise.

---

## 4. State Database & Lifecycle Verification

The SQLite state database at `/home/alexey/git/agent-quota-launcher/.local/launcher-config/state.db` was queried directly to verify the lifecycle state and lease tracking for `task-genuine-r3-1`:

### Task Row Data (`tasks` table)
```json
{
  "id": "task-genuine-r3-1",
  "idempotency_key": "ql-core-3-genuine-1",
  "state": "completed-awaiting-review",
  "created_at": "2026-10-04 12:28:10",
  "updated_at": "2026-10-04 12:45:21",
  "reviewer": "quota-launcher-core-3",
  "reason": "head marked complete; native death confirmed"
}
```

### Leased Paths (`task_paths` table)
- `/home/alexey/git/agent-quota-launcher/examples/launch-contract-report.md`
- `/home/alexey/git/agent-quota-launcher/.local/first-action-task-genuine-r3-1.json`

### Reserved Resources (`task_resources` table)
- `memory_mb`: 1500
- `disk_mb`: 512

### Lifecycle Compliance Findings
1. **Adherence to Non-Self-Acceptance**: The child worker did not execute `accept` on its own task.
2. **Guarded Completion**: The task was transitioned from `running` to `completed-awaiting-review` by `quota-launcher-core-3` only after confirming native process death and verifying the existence of non-empty deliverables.
3. **Lease Preservation**: Path leases remain active in `task_paths` to protect deliverables from concurrent overwrites while awaiting independent technical audit.

---

## 5. Adversarial Cross-Examination & Historical Context

1. **Evolution of `validate_first_action`**:
   - At launch (`b79ae70`), the launcher required an exact 4-key JSON (`id`, `tag`, `workspace`, `timestamp`) and strictly failed if any engine key (`command`, `phase`, `schema_version`) was present.
   - During R1 review (`c19c787`), this exact blacklist was recognized as a flaw because genuine un-filtered `aplexer whoami --json` naturally produces engine keys. The validator was amended to match identities against the launch start record and reject direct start-record clones.
   - In subsequent rounds (`4c2bfec`), the validator was hardened to verify live execution state progression (such as `phase: "running"` and advancing timestamps).
   - `examples/launch-contract-report.md` explicitly noted this distinction and acknowledged that its own runs were executed under the earlier contract. This transparency exemplifies high evidentiary standards.

2. **Integrity of Findings**:
   - The report does not sugarcoat missing features: it explicitly notes that `submit` lacked a dedicated `--first-action-path` parameter.
   - The report does not falsely certify execution; it is explicitly framed as a static documentation audit between `README.md` and `SPEC.md`.

---

## 6. Audit Conclusion & Final Verdict

Task `task-genuine-r3-1` in `agent-quota-launcher` satisfies all acceptance criteria with complete rigor:
1. `.local/first-action-task-genuine-r3-1.json` contains exactly the four required keys (`id`, `tag`, `workspace`, `timestamp`) and matches the launched session identity.
2. `examples/launch-contract-report.md` thoroughly and accurately evaluates all three required axes (identity/first-action, accept vs exit 0, and resource gates).
3. All file and line citations are verifiable, precise, and accompanied by honest reporting of discrepancies.
4. The lifecycle rules were strictly observed, leaving the task in `completed-awaiting-review` without illicit self-acceptance.

**Final Audit Verdict**: **ACCEPTED**
