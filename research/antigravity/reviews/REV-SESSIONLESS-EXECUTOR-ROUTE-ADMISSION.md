# REV-SESSIONLESS-EXECUTOR-ROUTE-ADMISSION — Independent Technical Review of Sessionless Alternative Executor Route Admission (C2229 / C2235 / C2237 / C2238 / C2239 / C2243 / C2244)

- **Target Report Audited:** [`research/antigravity/recovery/REPORT-SESSIONLESS-EXECUTOR-ROUTE-ADMISSION.md`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/recovery/REPORT-SESSIONLESS-EXECUTOR-ROUTE-ADMISSION.md)
  - Target Initial SHA256: `c2caaea30ea4010e753528350e889dd695fabec1adb53264089f487ff6b071ef`
  - Target Revised SHA256: `e225ccfbe9d166ac6762ffe3be85f4f5dd2ee3fa344c13b1d525a796d244b9dd`
- **Governing Directives:** Codex Principal Directives C2229, C2235, C2237, C2238, C2239, C2243, and C2244; Resource Policy (`coordination/RESOURCE-POLICY.md`); Operating Model (`coordination/OPERATING-MODEL.md`)
- **Reviewer:** `reviewer259` (session UUID: `259526a9-5deb-47ce-810c-ca5f2da56b68`)
- **Authority / Dispatcher:** `antigravity-head` (`46fdb644`, id: `245c7bba-9a7b-45c1-87a7-4537f289f9a5`)
- **Review Deliverable:** [`research/antigravity/reviews/REV-SESSIONLESS-EXECUTOR-ROUTE-ADMISSION.md`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/reviews/REV-SESSIONLESS-EXECUTOR-ROUTE-ADMISSION.md)
- **Scratch Workspace:** `.local/scratch/reviewer259-route-admission/` (mode `0700`, strictly $\le$ 512 MB, net `/tmp` growth = 0)
- **Compiler Invariant:** Reviewer actor and audited subprocesses strictly **0 cargo / rustc invocations under human hold**
- **Canonical Repository Invariant:** `/home/alexey/git/agent-quota-launcher`, `/home/alexey/git/agent-dashboard`, `/home/alexey/git/cloudflare-aplexer-protocol`, and `/home/alexey/git/agent-bus` audited **STRICTLY READ-ONLY** (0 writes, 0 edits, 0 git stage/commit mutations)
- **Audit Date:** 2026-10-05T03:52:00+02:00 (Europe/Berlin)

---

## 1. Executive Summary & Independent Review Verdict

Under Codex Principal Directives C2229, C2235, C2237, C2238, C2239, C2243, and C2244, an independent technical review of [`research/antigravity/recovery/REPORT-SESSIONLESS-EXECUTOR-ROUTE-ADMISSION.md`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/recovery/REPORT-SESSIONLESS-EXECUTOR-ROUTE-ADMISSION.md) was conducted. The review audited quota telemetry, binary wrapper layers, CLI argument semantics, launcher source code (`launcher/admission.py` and `launcher/launch.py`), sandbox containment, and the repaired offline test suite [`tests/test_grok_adapter_argv.py`](file:///home/alexey/git/cloudflare-agent-git/tests/test_grok_adapter_argv.py) across all four candidate sessionless executor routes.

### 1.1 Consolidated Route Admission Matrix

| Candidate Route | Target Model | Binary / Wrapper | Quota Availability | Launcher Code Status | Reviewer Admission Verdict |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Route 1: `zai`** | `glm-5.3-flash` | `/home/alexey/.local/bin/zcodex` | 99% (5h), 67% (7d), 5 banked | Supported in `ADAPTERS` & `ADAPTER_ROUTES` | **HELD**<br>Outside 17:00–03:00 Berlin promotional campaign window (03:48 Berlin); ordinary paid allowance authorized per policy, but held on unproven root `/tmp` containment constraint; nested CJS execution unverified without runtime receipt. |
| **Route 2: `grok`** | `grok-4.6` | `/home/alexey/.local/bin/grok` | 68% (7d), 32% used | Supported in `ADAPTERS`, but broken | **FAILING / BLOCKED**<br>Source-level clap argument order defect in `launcher/launch.py`: passes `grok -p --model...` instead of placing prompt immediately after `-p`. Historical clap error is failure receipt. Source candidate fix and offline patched-source test pin verified clean under C2243/C2244; runtime parser acceptance remains pending canonical merge and contained execution. |
| **Route 3: `antigravity`** | `gemini-3.1-pro-high` | `/home/alexey/.local/bin/agy` | 94.5% (5h), 70.7% (7d) | Supported in `ADAPTERS` & `ADAPTER_ROUTES` | **CANDIDATE / SOURCE-COMPATIBLE**<br>Recipe strips `GEMINI_API_KEY` and `GOOGLE_API_KEY`, but actual credential source and billing impact remain unverified without runtime credential audit. Live systemd scope `1500M`/PID/TMP audit and model response generation pending contained trial. Preferred Flash model configuration requires verified discovery in `agy` CLI per resource policy. |
| **Route 4: `opencode`** | `space-bunny-free`, `muse-spark-1.3` | `/home/alexey/.nvm/.../bin/opencode` | 100% (5h), 100% (7d) on `go` | Absent from `ADAPTERS` & `ADAPTER_ROUTES` | **FAIL-CLOSED / BLOCKED**<br>Missing from `launcher/admission.py` and `launcher/launch.py`. CLI model discovery verified, but runtime batch execution unproven. `opencode-go` quota is distinct from free community models. |

---

## 2. Independent Verification of Quota Telemetry

An independent snapshot of provider quotas was captured directly from `quse --json` at `2026-10-05T01:47:22Z`:

### 2.1 Quota Telemetry Snapshot Comparison

```json
{
  "zai": {
    "status": "ok",
    "windows": {
      "5h": {"percent_remaining": 99.0, "reset_at": "2026-10-05T06:32:40Z", "rolling": true},
      "7d": {"percent_remaining": 67.0, "reset_at": "2026-10-06T15:47:28Z"}
    },
    "banked_resets_available": 5
  },
  "gemini": {
    "status": "ok",
    "windows": {
      "5h": {"percent_remaining": 94.49, "reset_at": "2026-10-05T06:24:26Z", "rolling": false},
      "7d": {"percent_remaining": 70.67, "reset_at": "2026-10-09T08:09:37Z"}
    }
  },
  "grok": {
    "status": "ok",
    "windows": {
      "7d": {"percent_remaining": 68.0, "reset_at": "2026-10-06T00:08:17Z"}
    },
    "details": {"has_grok_code_access": true, "usage_percent": 32.0}
  },
  "codex": {
    "status": "ok",
    "windows": {
      "7d": {"percent_remaining": 59.0, "reset_at": "2026-10-09T21:13:31Z"}
    },
    "banked_resets_available": 2
  },
  "go": {
    "status": "ok",
    "windows": {
      "5h": {"percent_remaining": 100.0, "reset_at": "2026-10-05T06:47:21Z", "rolling": true},
      "7d": {"percent_remaining": 100.0, "reset_at": "2026-10-12T00:00:00Z"},
      "monthly": {"percent_remaining": 81.0, "reset_at": "2026-10-22T06:20:23Z"}
    }
  },
  "claude": {
    "status": "ok",
    "windows": {
      "5h": {"percent_remaining": 63.6, "reset_at": "2026-10-05T05:29:59Z"},
      "7d": {"percent_remaining": 49.0, "reset_at": "2026-10-08T14:59:59Z"}
    }
  },
  "copilot": {
    "status": "ok",
    "windows": {
      "monthly": {"percent_remaining": 100.0, "reset_at": "2026-11-01T00:00:00Z"}
    }
  }
}
```

### 2.2 Telemetry Verification Verdict
- **Empirical Snapshot Observations:** Independent snapshot captured at `01:47:22Z`. Snapshot differences were observed (e.g. Gemini at 94.49% on 5h vs. initial 95.8%, and 70.67% on 7d vs. initial 70.75%), accurately reflecting intervening token consumption by active peer sessions on the host.
- **Entitlement Checks:** Grok entitlement `has_grok_code_access: true` is confirmed. Codex reserve (59.0% $\ge$ 15.0%) is satisfied. ZAI banked resets (5 available) and Codex banked resets (2 available) are confirmed.

---

## 3. Deep Route-by-Route Technical Verification

### 3.1 Route 1: `zai` (GLM-5.3-Flash via `zcodex`)

1. **Binary & Wrapper Verification:**
   - Path: `/home/alexey/.local/bin/zcodex` (mode `0755`).
   - Implementation: Bourne-Again shell wrapper script invoking `/home/alexey/.local/lib/zcodex/zcodex "$@"`.
   - Target Binary: `/home/alexey/.local/lib/zcodex/zcodex` is an ELF 64-bit LSB pie executable (385,674,664 bytes, ~385 MB), stripped.
2. **Epistemic Demarcation on Nested CJS Execution:**
   - The assertion that `zcodex` executes `/opt/ZCode/resources/glm/zcode.cjs` is based on configuration, but **has no live runtime CJS receipt in this audit interval**.
   - It is formally categorized as an **UNVERIFIED HYPOTHESIS (`HYPOTHESIS / UNVERIFIED`)**.
3. **Time-Aware Routing & Policy Alignment:**
   - Time of Audit: `Mon Oct 5 03:48:00 CEST 2026` (~03:48 Berlin).
   - Human34 Promotional Campaign Window: **17:00–03:00 Europe/Berlin**.
   - Current execution falls outside the promotional zero-consumption window.
   - **Policy Clarification:** Per `coordination/RESOURCE-POLICY.md` (lines 50–58), executing ZAI outside the campaign window is authorized to use verified ordinary paid allowance (99% 5h, 67% 7d, 5 banked resets), NOT "unauthorized spend".
4. **Root TMPDIR Containment Constraint (Primary Blocker):**
   - Invariant: Host `/tmp` must experience zero net growth; temporary files must be strictly confined to isolated scratch space.
   - `zcodex` lacks an established test receipt proving that its internal Node/NAPI bindings strictly honor `$TMPDIR` without polluting host `/tmp`.
5. **Verdict:** **HELD** (Held specifically on the root `TMPDIR` containment constraint; nested CJS execution mapping unverified without runtime receipt).

---

### 3.2 Route 2: `grok` (Grok-4.6 via `grok` CLI)

1. **Binary Verification:**
   - Path: `/home/alexey/.local/bin/grok` (symlink to `/home/alexey/.grok/bin/grok`).
   - Version: Grok Build TUI `v0.1.0-alpha`.
2. **Clap Argument Order Defect Reproduction:**
   - In `/home/alexey/git/agent-quota-launcher/launcher/launch.py` (lines 34–38, 64–68):
     ```python
     ADAPTERS["grok"] = {
         "argv": ["grok", "-p", "--model", "grok-4.6", "--effort", "high",
                  "--permission-mode", "auto"],
         "env": {},
     }
     ```
     When called via `build_adapter_argv("grok", goal)`, it produces:
     `grok -p --model grok-4.6 --effort high --permission-mode auto <goal>`
   - **Historical Failure Receipt:**
     ```bash
     $ grok -p --model grok-4.6 --effort high --permission-mode auto "echo hello"
     error: a value is required for '--single <PROMPT>' but none was supplied
     For more information, try '--help'.
     # Exit Code: 2
     ```
3. **Root Cause Analysis & Candidate Fix:**
   - Grok CLI uses the `clap` crate in Rust. In `grok --help`, `-p, --single <PROMPT>` defines a single-turn prompt that takes a value.
   - When `-p` is immediately followed by `--model`, clap interprets `--model` as an option flag (because it starts with `-`), leaving `-p` without a value and causing a fatal exit code 2.
   - **Source Candidate Fix:** Place `-p` as the final flag in `argv`:
     ```python
     "argv": ["grok", "--model", "grok-4.6", "--effort", "high", "--permission-mode", "auto", "-p"]
     ```
     This ensures that the appended `<goal>` argument directly satisfies `<PROMPT>`.
   - **Status Demarcation (C2244):** This is a source-level candidate fix; runtime parser acceptance remains pending patched-source tests and contained execution per C2243/C2244. The historical clap error is an empirical failure receipt of the unpatched recipe, not positive acceptance of the fix.
4. **Verdict:** **FAILING / BLOCKED** (Launcher adapter recipe syntax error; candidate fix and offline patched-source test pin verified).

---

### 3.3 Route 3: `antigravity` (Gemini via `agy` CLI)

1. **Binary Verification:**
   - Path: `/home/alexey/.local/bin/agy`.
   - File Type: Standalone statically linked Go ELF binary (209,625,296 bytes, ~209 MB).
2. **Adapter Recipe & Authentication Action Audit:**
   - In `launcher/launch.py` (lines 39–45):
     ```python
     ADAPTERS["antigravity"] = {
         "argv": ["env", "-u", "GEMINI_API_KEY", "-u", "GOOGLE_API_KEY",
                  "agy", "--model", "gemini-3.1-pro-high", "--effort", "high",
                  "--dangerously-skip-permissions", "-p", "--print-timeout", "0",
                  "--output-format", "text"],
         "env": {},
     }
     ```
   - **Authentication Status (C2244):** The adapter recipe strips `GEMINI_API_KEY` and `GOOGLE_API_KEY` from the environment. However, actual credential source and billing impact remain unverified without a live runtime credential and accounting audit.
3. **Status Demarcation & Model Tier Governance:**
   - **Status Demarcation:** Relabeled from premature "ADMITTED & HEALTHY" to `CANDIDATE / SOURCE-COMPATIBLE (CONTAINED MODEL TRIAL PENDING ADMISSION RECEIPT)`. Live execution under an `aplexer` systemd scope with active cgroup `MemoryMax=1500M`, `TasksMax=100`, `$TMPDIR` containment, and model response generation remains pending a dedicated trial.
   - **Model Policy Alignment (C2244):** `launcher/launch.py` hardcodes `--model gemini-3.1-pro-high`. Per `coordination/RESOURCE-POLICY.md`, model selection for batch/sessionless executors should prioritize cost-effective Flash models, reserving Pro models for complex architectural design and independent challenger reviews. Preferred Flash model configuration requires verified discovery in `agy` CLI before production routing.
4. **Verdict:** **CANDIDATE / SOURCE-COMPATIBLE (CONTAINED MODEL TRIAL PENDING ADMISSION RECEIPT)**.

---

### 3.4 Route 4: `opencode` (Space Bunny / Muse Spark 1.3)

1. **Binary Verification & Discovery Demarcation:**
   - Path: `/home/alexey/.nvm/versions/node/v24.13.1/bin/opencode` (v1.18.31).
   - Discovery Output: `opencode models` confirms the availability of `opencode/space-bunny-free` and `opencode/muse-spark-1.3-contributor-free`.
   - **Demarcation:** CLI model discovery is **NOT** proof of working batch execution. A successful discovery list does not guarantee that the upstream contributor endpoints will respond without timeout or authentication failure during automated headless runs.
2. **Quota Demarcation (`opencode-go` vs. Free Routes):**
   - The `go` entry in `quse --json` (100% 5h, 100% 7d, 81% monthly) measures **`opencode-go`** commercial quota.
   - It is completely distinct from the free third-party routes (`opencode/space-bunny-free` and `opencode/muse-spark-1.3-contributor-free`). Quota availability on `go` does not meter free routes.
3. **Launcher Source Code Defect:**
   - In `/home/alexey/git/agent-quota-launcher/launcher/admission.py` (line 14):
     ```python
     ADAPTER_ROUTES = ("grok", "antigravity", "zai")
     ```
     `opencode` is completely absent. Line 113 rejects `go` / `opencode` with `"Unsupported route explicitly blocked"`.
   - In `/home/alexey/git/agent-quota-launcher/launcher/launch.py`:
     `ADAPTERS` does not contain `"opencode"`. Calling `build_adapter_argv("opencode", goal)` raises `ValueError("Unsupported provider: opencode")`.
4. **Verdict:** **FAIL-CLOSED / BLOCKED** (Missing from launcher tables; discovery proven, runtime batch execution unproven).

---

## 4. Governance, Resource & Remediation Synthesis

To restore full four-provider multi-model execution pool capacity:

1. **Grok Launcher Recipe Patch (`quota-launcher-head` ownership):**
   Update `ADAPTERS["grok"]["argv"]` in `launcher/launch.py` to place `-p` at the end:
   ```python
   "argv": ["grok", "--model", "grok-4.6", "--effort", "high", "--permission-mode", "auto", "-p"]
   ```
2. **Antigravity Contained Trial:**
   Execute a single-turn contained smoke trial of `agy` within a dedicated scratch cgroup/TMPDIR to verify `MemoryMax=1500M`, `TasksMax=100`, and clean text stdout output. Align default model selection with Flash where appropriate following verified CLI discovery.
3. **OpenCode Admission Patch:**
   - Add `"opencode"` to `ADAPTER_ROUTES` in `launcher/admission.py`.
   - Add `"opencode"` to `ADAPTERS` in `launcher/launch.py` targeting verified free models (`space-bunny-free` / `muse-spark-1.3-contributor-free`).
4. **ZAI TMPDIR Jailing:**
   Wrap `zcodex` with verified `$TMPDIR` directory redirection before enabling execution outside 17:00–03:00 Berlin or promotional execution inside the window.

---

## 5. Independent Audit of Repaired Grok Adapter Test Suite (C2243 / C2244)

Under Codex Principal Directives C2243 and C2244, an independent technical audit of the repaired test suite [`tests/test_grok_adapter_argv.py`](file:///home/alexey/git/cloudflare-agent-git/tests/test_grok_adapter_argv.py) delivered by `architect06` was performed.

### 5.1 Real Patched-Source Application Verification
- **Scratch Testbed Isolation:** In `TestGrokAdapterArgv.setUpClass()`, the test copies the real `agent-quota-launcher/launcher` directory into `.local/scratch/architect06-executor-admission/testbed/launcher`.
- **Exact Patch Application:** The test applies [`research/antigravity/recovery/grok-launcher-argv-fix.patch`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/recovery/grok-launcher-argv-fix.patch) using `/usr/bin/patch -p1`.
- **Real Module Import:** The test dynamically loads the patched `launch.py` via `importlib.util.spec_from_file_location("testbed_launcher_launch", ...)`.
- **Finding:** The fake copied `exec(...)` simulation has been completely eliminated. The test executes against the **real, patched `launcher.launch` source code**.

### 5.2 Real `build_adapter_argv` Expanded Goal Matrix Verification
In `test_real_patched_build_adapter_argv_goal_matrix`, the real `build_adapter_argv("grok", goal)` is tested across an expanded matrix of 17 test cases:
1. Standard offline goals: `"run offline task"`, `"compile offline verification deliverable"`.
2. Option-looking goals: `"--model"`, `"--help"`, `"-p"`, `"--effort"`, `"-v"`, `"--permission-mode"`, `"--custom-flag value"`.
3. Whitespace & quotation: Multi-spaced strings, double quotes, single quotes, mixed quotes, command semicolons (`"echo test; ls -la && exit 1"`), and newlines.
4. Unicode & CJK: `"unicode goal: 🚀 α/β → 100% 🎯"`, `"自然语言处理目标 2026"`.
5. Edge case: Empty goal string `""`.

**Positional & Adjacency Assertions:**
- Every case asserts:
  $$\text{argv}[-2] == \text{"-p"} \quad \text{and} \quad \text{argv}[-1] == \text{goal}$$
- Every case asserts base arguments match `EXPECTED_BASE_ARGV`:
  `["grok", "--model", "grok-4.6", "--effort", "high", "--permission-mode", "auto", "-p"]`
- Every case asserts total length equals $\text{len}(\text{base}) + 1$.

### 5.3 Elimination of Uncontained Live CLI Execution
- `test_historical_clap_parse_receipt_and_token_isolation` utilizes a documented historical receipt (`HISTORICAL_CLAP_PARSE_FAILURE_RECEIPT`) to assert the exit code 2 contract and token adjacency defect without invoking the live binary.
- Zero live external provider calls or uncontained network connections are executed during test runs.

### 5.4 Test Execution Receipts
```text
$ python3 -m unittest discover -s tests -p "test_grok_adapter_argv.py" -v
test_historical_clap_parse_receipt_and_token_isolation (test_grok_adapter_argv.TestGrokAdapterArgv.test_historical_clap_parse_receipt_and_token_isolation)
Verify documented historical clap parse error contract (exit code 2) and ... ok
test_patch_applies_cleanly_to_launcher_repo (test_grok_adapter_argv.TestGrokAdapterArgv.test_patch_applies_cleanly_to_launcher_repo)
Verify that the staged patch applies cleanly to canonical agent-quota-launcher ... ok
test_patch_file_exists_and_valid (test_grok_adapter_argv.TestGrokAdapterArgv.test_patch_file_exists_and_valid)
Verify that the staged recovery patch file exists and contains the expected diff. ... ok
test_real_patched_build_adapter_argv_goal_matrix (test_grok_adapter_argv.TestGrokAdapterArgv.test_real_patched_build_adapter_argv_goal_matrix)
Test the REAL patched build_adapter_argv against an expanded goal test matrix: ... ok

----------------------------------------------------------------------
Ran 4 tests in 0.017s

OK
```

### 5.5 Staged Patch Applicability to Canonical Repository
`test_patch_applies_cleanly_to_launcher_repo` runs `git -C /home/alexey/git/agent-quota-launcher apply --check research/antigravity/recovery/grok-launcher-argv-fix.patch`:
- Exit Code: `0` (Clean application).
- Canonical working tree remains 100% clean and unmodified.

### 5.6 Verdict on Patch / Test Pin
The staged patch [`research/antigravity/recovery/grok-launcher-argv-fix.patch`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/recovery/grok-launcher-argv-fix.patch) and offline test suite [`tests/test_grok_adapter_argv.py`](file:///home/alexey/git/cloudflare-agent-git/tests/test_grok_adapter_argv.py) are **INDEPENDENTLY VERIFIED AND APPROVED AS A STAGED CANDIDATE PIN**. Integration into canonical `/home/alexey/git/agent-quota-launcher` is formally delegated to `quota-launcher-head` under flock serialization.

---

## 6. Verification & Invariants Checklist

- [x] **Zero Compiler Invocations:** Reviewer actor and audited subprocesses strictly 0 `cargo` / `rustc` compiler invocations under human hold.
- [x] **Canonical Workspaces Read-Only:** `/home/alexey/git/agent-quota-launcher`, `/home/alexey/git/agent-dashboard`, `/home/alexey/git/cloudflare-aplexer-protocol`, and `/home/alexey/git/agent-bus` audited strictly read-only; 0 writes, 0 edits, 0 git stage/commit mutations.
- [x] **Scratch Footprint & Isolation:** `.local/scratch/reviewer259-route-admission/` configured mode `0700`, measured usage 4 KB $\le$ 512 MB, `/tmp` net growth = 0.
- [x] **Quota Telemetry Independently Verified:** Snapshot differences observed and explained (e.g. Gemini 94.49% vs 95.8%) reflecting intervening token consumption.
- [x] **Route 1 (`zai`):** Wrapper verified, 03:48 Berlin time verified outside 17:00-03:00 window; ordinary allowance policy clarified; nested CJS classified as unverified hypothesis.
- [x] **Route 2 (`grok`):** Historical clap parse error analyzed; candidate fix verified; C2243 real patched-source tests pass 4/4 in 0.017s; patch applies cleanly via `git apply --check`.
- [x] **Route 3 (`antigravity`):** Binary and environment unsetting verified; credential source and billing impact noted as unverified without runtime audit; relabeled `CANDIDATE / SOURCE-COMPATIBLE` pending systemd admission trial; Flash model configuration noted pending verified CLI discovery.
- [x] **Route 4 (`opencode`):** Binary verified; model discovery vs runtime execution demarcated; `opencode-go` quota distinguished from free routes; absence from `ADAPTER_ROUTES` and `ADAPTERS` verified.
- [x] **Publication Credential Guard:** Verified via `python3 research/antigravity/tooling/publication_guard.py` (Exit Code 0).
- [x] **Git Invariant:** Zero git commits or pushes from subagent.
