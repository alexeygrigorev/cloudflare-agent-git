# REV-AGY-FLASH-ADMISSION-TRIAL — Independent Technical Audit of Contained Antigravity Flash Model Trial & Admission Bypass (C2257)

- **Target Report Audited:** [`research/antigravity/recovery/REPORT-AGY-FLASH-ADMISSION-TRIAL.md`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/recovery/REPORT-AGY-FLASH-ADMISSION-TRIAL.md) (SHA256: `68785954bb7c4d192d0bc941bbd8cfb4e15069c3d357cd3c8742628ed9b4133a`)
- **Target Staged Patch Audited:** [`research/antigravity/recovery/antigravity-launcher-flash-model.patch`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/recovery/antigravity-launcher-flash-model.patch) (SHA256: `265d6513afab197be9388858a1468b8725e66acf06b06f9037aa34c16666aede`)
- **Trial Artifacts Audited:**
  * Runner script: [`.local/scratch/architect06-flash-trial/run_trial.py`](file:///home/alexey/git/cloudflare-agent-git/.local/scratch/architect06-flash-trial/run_trial.py)
  * Result record: [`.local/scratch/architect06-flash-trial/trial_result.json`](file:///home/alexey/git/cloudflare-agent-git/.local/scratch/architect06-flash-trial/trial_result.json)
  * Stdout log: [`.local/scratch/architect06-flash-trial/stdout.log`](file:///home/alexey/git/cloudflare-agent-git/.local/scratch/architect06-flash-trial/stdout.log) (4,584 bytes, mode `0600`)
  * Stderr log: [`.local/scratch/architect06-flash-trial/stderr.log`](file:///home/alexey/git/cloudflare-agent-git/.local/scratch/architect06-flash-trial/stderr.log) (99 bytes, mode `0600`)
- **Governing Directives:** Codex Principal Directive C2257; Operating Model (`coordination/OPERATING-MODEL.md`); Resource Policy (`coordination/RESOURCE-POLICY.md`)
- **Reviewer:** `reviewer259` (session UUID: `259526a9-5deb-47ce-810c-ca5f2da56b68`)
- **Authority / Dispatcher:** `antigravity-head` (`46fdb644`, id: `245c7bba-9a7b-45c1-87a7-4537f289f9a5`)
- **Review Deliverable:** [`research/antigravity/reviews/REV-AGY-FLASH-ADMISSION-TRIAL.md`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/reviews/REV-AGY-FLASH-ADMISSION-TRIAL.md)
- **Scratch Workspace:** `.local/scratch/reviewer259-flash-trial-review/` (mode `0700`, strictly $\le$ 512 MB, net `/tmp` growth = 0)
- **Compiler Invariant:** Reviewer actor and audited subprocesses strictly **0 cargo / rustc invocations under human hold**
- **Canonical Repository Invariant:** `/home/alexey/git/agent-quota-launcher` audited **STRICTLY READ-ONLY** (0 writes, 0 edits, 0 git stage/commit mutations)
- **Audit Date:** 2026-10-05T04:03:00+02:00 (Europe/Berlin)

---

## 1. Executive Summary & Audit Verdict

Under Codex Principal Directive C2257, an independent technical audit of the Contained Antigravity Flash Model trial was performed. The audit examined the trial runner script (`run_trial.py`), live kernel cgroup telemetry (`trial_result.json`), execution output logs, incident disclosure report (`REPORT-AGY-FLASH-ADMISSION-TRIAL.md`), and the staged launcher patch (`antigravity-launcher-flash-model.patch`).

### 1.1 Consolidated Audit Verdict
$$\mathbf{Verdict: \text{ UNAUTHORIZED ADMISSION BYPASS CONFIRMED / GATE 1 REVOKED;}}$$
$$\mathbf{\text{COMPONENT MODEL EVALUATION RECEIPT VERIFIED; STAGED PATCH APPROVED AS CANDIDATE PIN}}$$

1. **Admission Bypass Incident Verified:**
   - The trial runner [`.local/scratch/architect06-flash-trial/run_trial.py`](file:///home/alexey/git/cloudflare-agent-git/.local/scratch/architect06-flash-trial/run_trial.py#L44-L77) invoked `systemd-run` directly via `subprocess.Popen`. It did NOT transact through canonical `agent-quota-launcher` (`Store`, `launch_lock`, `check_resources`, `fetch_quse`, or quota reservation).
   - Any prior claim of "Gate 1 Admission Verified" was **factually false**. The incident disclosure in `REPORT-AGY-FLASH-ADMISSION-TRIAL.md` revoking Gate 1 status is confirmed accurate.
2. **Telemetry & Containment Caveats Confirmed:**
   - **Memory & Tasks Metrics:** Memory (`313.07 MB`) and task counts (`21 tasks`) were poll-sampled via `systemctl show -p MemoryCurrent` at ~200ms intervals; they represent observed instantaneous sample maximums, NOT true kernel `memory.peak` watermark receipts.
   - **Temporary Storage:** Net `/tmp` growth = 0 was inferred from `TMPDIR` environment redirection without an explicit before/after host `/tmp` inode write audit.
   - **Process Lifecycle Teardown:** Runner timeout handler called `proc.kill()`, targeting only the `systemd-run` wrapper process; recursive child cleanup and systemd scope teardown were unproven in timeout paths.
   - **Authentication:** Environment unsetting (`env -u GEMINI_API_KEY -u GOOGLE_API_KEY`) confirms ambient keys were stripped, but provides no runtime proof of internal OAuth token selection or billing tier.
3. **Authentic Component Outcomes Verified:**
   - Execution of `gemini-3.7-flash-medium` under `systemd-run --user --scope` succeeded cleanly with exit code `0` in `24.80s`.
   - The model produced a high-quality, technically valid 4,584-byte security and parser audit in `stdout.log`.
   - Empirical discovery of the sibling `-p` argument ordering defect in canonical `ADAPTERS["antigravity"]` is confirmed.
4. **Staged Patch Approval:**
   - [`antigravity-launcher-flash-model.patch`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/recovery/antigravity-launcher-flash-model.patch) updates the target model to `gemini-3.7-flash-medium` and moves `-p` to the end of `argv`.
   - Tested cleanly via `git -C /home/alexey/git/agent-quota-launcher apply --check` (exits 0). Approved as a staged candidate pin for `quota-launcher-head`.

---

## 2. Deep Audit of Admission Bypass Incident

### 2.1 Code-Level Inspection of `run_trial.py`
Inspection of lines 44–77 of [`.local/scratch/architect06-flash-trial/run_trial.py`](file:///home/alexey/git/cloudflare-agent-git/.local/scratch/architect06-flash-trial/run_trial.py#L44-L77) confirms:

```python
    cmd = [
        "systemd-run",
        "--user",
        "--scope",
        f"--unit={unit_name}",
        "-p", "MemoryMax=1500M",
        "-p", "TasksMax=100",
        "env",
        "-u", "GEMINI_API_KEY",
        "-u", "GOOGLE_API_KEY",
        f"TMPDIR={TMP_DIR}",
        "agy",
        "--model", "gemini-3.7-flash-medium",
        "--effort", "medium",
        "--dangerously-skip-permissions",
        "--print-timeout", "0",
        "--output-format", "text",
        "-p",
        GOAL_PROMPT,
    ]

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd="/home/alexey/git/cloudflare-agent-git",
    )
```

### 2.2 Material Governance Deficiencies
1. **No Launcher Transaction:** `run_trial.py` never imported or referenced `agent-quota-launcher`.
2. **Bypassed Locking:** No file lock (`.local/launcher.lock` via `launch_lock`) was acquired.
3. **Bypassed Resource Checks:** `check_resources(task_requirements)` was never executed.
4. **Bypassed State Machine:** The canonical `Store` was never queried or mutated. The task never existed as `PENDING`, never transitioned to `RUNNING`, and was never committed as `COMPLETED`.
5. **Bypassed Quota Accounting:** No quota reservation was registered in `quse` or the launcher accounting ledger.

**Audit Conclusion:** Running execution outside the canonical launcher state machine constitutes an **unauthorized admission bypass**. Gate 1 status is formally **REVOKED**. Standalone execution cannot certify canonical route admission.

---

## 3. Telemetry & Containment Methodology Demarcation

### 3.1 Memory & Task Concurrency: Poll-Sampling vs. Kernel Peak Watermark
In `run_trial.py` lines 93–140:
```python
show_res = subprocess.run([
    "systemctl", "--user", "show", f"{unit_name}.scope",
    "-p", "MemoryCurrent", "-p", "TasksCurrent", ...
], capture_output=True, text=True, timeout=2.0)
...
time.sleep(0.2)
```
- **Finding:** Systemd properties were sampled in a discrete polling loop with `sleep(0.2)`.
- **Demarcation:**
  * Reported peak memory: `313.07 MB` (`peak_memory_bytes = 328278016`).
  * Reported peak tasks: `21`.
  * These values represent **sample maximums** observed at ~200ms intervals. They do NOT represent the true kernel `memory.peak` watermark (available via `/sys/fs/cgroup/.../memory.peak` in cgroup v2). Instantaneous memory spikes or thread creation bursts occurring between polling ticks were not captured.

### 3.2 Scratch / Temporary Storage Containment (`tmpzero`)
- **Finding:** `run_trial.py` injected `TMPDIR=/home/alexey/git/cloudflare-agent-git/.local/scratch/architect06-flash-trial/tmp` into the child process environment.
- **Demarcation:** The assertion that host `/tmp` experienced zero net growth was inferred solely from environment variable redirection. No before-and-after filesystem inode audit or write audit was performed against `/tmp`.

### 3.3 Process Tree & Timeout Teardown Hygiene
In `run_trial.py` lines 87–90:
```python
if elapsed > TIMEOUT_SECONDS:
    proc.kill()
    print("Process exceeded timeout! Killed.")
    break
```
- **Finding:** Timeout enforcement relied on `proc.kill()`.
- **Demarcation:** `proc.kill()` sends `SIGKILL` only to the immediate child PID (`systemd-run`). Under systemd, `systemd-run --scope` places processes into a user scope. Killing the client `systemd-run` command does not guarantee recursive termination of workload processes within the scope (`agy`), leaving a risk of orphaned background workers in timeout scenarios. True process teardown requires `systemctl --user stop <unit>.scope` and `systemctl --user kill -s SIGKILL <unit>.scope`.

### 3.4 Authentication Mode Verification
- **Finding:** The recipe executed with `env -u GEMINI_API_KEY -u GOOGLE_API_KEY`.
- **Demarcation:** Stripping ambient keys prevents accidental use of API keys present in `os.environ`, but it does not provide cryptographic or server-side verification of which credential identity, OAuth token, or gcloud profile was exercised by the `agy` binary runtime.

---

## 4. Preserved Component Model Outcomes

While canonical admission is revoked, the component-level receipts of the trial are authentic and reproducible:

### 4.1 Trial Execution Telemetry
From [`.local/scratch/architect06-flash-trial/trial_result.json`](file:///home/alexey/git/cloudflare-agent-git/.local/scratch/architect06-flash-trial/trial_result.json):
- **Unit Name:** `agy-flash-trial-1791165325.scope`
- **Control Group:** `/user.slice/user-1000.slice/user@1000.service/app.slice/agy-flash-trial-1791165325.scope`
- **Invocation ID:** `fbf31a2e3b59487cbc5d07717b5ca6bc`
- **Exit Code:** `0` (Success)
- **Elapsed Wall-Clock Time:** `24.80s` (well within 180s budget)
- **Stdout Log:** [`.local/scratch/architect06-flash-trial/stdout.log`](file:///home/alexey/git/cloudflare-agent-git/.local/scratch/architect06-flash-trial/stdout.log) (4,584 bytes, mode `0600`)
- **Stderr Log:** [`.local/scratch/architect06-flash-trial/stderr.log`](file:///home/alexey/git/cloudflare-agent-git/.local/scratch/architect06-flash-trial/stderr.log) (99 bytes, mode `0600`)

### 4.2 Model Output Analysis (`gemini-3.7-flash-medium`)
The trial successfully executed a complex prompt evaluating [`grok-launcher-argv-fix.patch`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/recovery/grok-launcher-argv-fix.patch) and [`tests/test_grok_adapter_argv.py`](file:///home/alexey/git/cloudflare-agent-git/tests/test_grok_adapter_argv.py):
1. **Clap Parsing Semantics:** Confirmed that moving `-p` to the tail of `argv` satisfies `clap` for all ordinary non-flag prompt strings.
2. **Option Injection Vulnerability:** Correctly deduced that space-separated `-p <goal>` remains vulnerable if `<goal>` begins with `--` (e.g. `--model`), recommending inline binding (`--single=VALUE` or `--`) for production robustness.
3. **High-Quality Reasoning:** Demonstrates that `gemini-3.7-flash-medium` delivers rigorous architectural and security reasoning at significant cost and quota savings compared to Pro models.

---

## 5. Empirical Discovery: Sibling `-p` Ordering Defect in `launch.py`

### 5.1 Baseline Defect Reproduction
During initial baseline testing of the canonical `launch.py` recipe:
```python
    "antigravity": {
        "argv": ["env", "-u", "GEMINI_API_KEY", "-u", "GOOGLE_API_KEY",
                 "agy", "--model", "gemini-3.1-pro-high", "--effort", "high",
                 "--dangerously-skip-permissions", "-p", "--print-timeout", "0",
                 "--output-format", "text"],
        "env": {},
    },
```
The command failed immediately with exit code `2`:
```text
Error: -p took "--print-timeout" as its prompt, so the intended prompt was left as an argument and ignored.
Attach the prompt to the flag (-p='your prompt') and move --print-timeout elsewhere on the command line.
```

### 5.2 Defect Mechanics & Remediation
Like Grok's `-p` / `--single <PROMPT>`, `agy -p` takes an immediate prompt value. Because `--print-timeout` was positioned after `-p`, `agy` consumed `--print-timeout` as the prompt payload, leaving the true task goal orphaned.

The staged recovery patch [`antigravity-launcher-flash-model.patch`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/recovery/antigravity-launcher-flash-model.patch) resolves both issues:
```diff
--- a/launcher/launch.py
+++ b/launcher/launch.py
@@ -38,9 +38,9 @@
     },
     "antigravity": {
         "argv": ["env", "-u", "GEMINI_API_KEY", "-u", "GOOGLE_API_KEY",
-                 "agy", "--model", "gemini-3.1-pro-high", "--effort", "high",
-                 "--dangerously-skip-permissions", "-p", "--print-timeout", "0",
-                 "--output-format", "text"],
+                 "agy", "--model", "gemini-3.7-flash-medium", "--effort", "medium",
+                 "--dangerously-skip-permissions", "--print-timeout", "0",
+                 "--output-format", "text", "-p"],
         "env": {},
     },
```

### 5.3 Staged Patch Applicability
- **Command Tested:** `git -C /home/alexey/git/agent-quota-launcher apply --check /home/alexey/git/cloudflare-agent-git/research/antigravity/recovery/antigravity-launcher-flash-model.patch`
- **Result:** **Exits 0 Cleanly**.
- **Verdict:** Approved as a staged candidate pin for owned integration by `quota-launcher-head`.

---

## 6. Canonical Route Integration Requirements (Directive C2257)

Under Directive C2257, standalone trials are terminated. Genuine canonical admission must satisfy the following integration requirements through [`research/antigravity/tooling/self_org/launcher_bus_bridge.py`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/tooling/self_org/launcher_bus_bridge.py):

1. **Transactional Quota & Resource Check:**
   Execute `check_dispatch_admission(provider="antigravity", ...)` within `launch_lock` to verify host RAM, disk headroom, and quota availability prior to launching.
2. **Canonical State Machine Transitions:**
   Record all launch state transitions in the canonical `Store` (`PENDING` $\to$ `RUNNING` $\to$ `COMPLETED` / `FAILED`).
3. **Cgroup Lifecycle Teardown:**
   Replace wrapper `proc.kill()` with explicit `systemctl --user stop <unit>.scope` and `systemctl --user kill -s SIGKILL <unit>.scope` to ensure complete, leak-free termination of all child processes upon timeout.
4. **Kernel Watermark Telemetry:**
   Read `/sys/fs/cgroup/.../memory.peak` upon process completion rather than relying on poll-sampled `MemoryCurrent`.

---

## 7. Verification & Invariants Checklist

- [x] **Zero Compiler Invocations:** Reviewer actor and audited subprocesses strictly executed 0 `cargo` / `rustc` compiler invocations under human hold.
- [x] **Canonical Workspaces Read-Only:** `/home/alexey/git/agent-quota-launcher` audited strictly read-only; 0 writes, 0 edits, 0 git stage/commit mutations.
- [x] **Scratch Footprint & Isolation:** `.local/scratch/reviewer259-flash-trial-review/` configured mode `0700`, measured usage 4.0 KB $\le$ 512 MB, `/tmp` net growth = 0.
- [x] **Admission Bypass Confirmed:** Verified `run_trial.py` invoked `subprocess.Popen` directly, bypassing canonical `Store`, `launch_lock`, `check_resources`, and quota reservation. Gate 1 status revoked.
- [x] **Telemetry Caveats Documented:** Confirmed poll-sampling of `MemoryCurrent` / `TasksCurrent` vs kernel `memory.peak`; documented lack of host `/tmp` before/after write audit; identified `proc.kill()` process teardown boundary; noted unverified runtime auth mode.
- [x] **Component Outcome Verified:** Verified authentic 24.80s execution of `gemini-3.7-flash-medium` under `systemd-run` (exit code 0, 4,584 bytes clean stdout).
- [x] **Sibling Defect & Patch Audited:** Verified empirical discovery of sibling `-p` ordering defect in canonical `launch.py`; confirmed `antigravity-launcher-flash-model.patch` applies cleanly via `git apply --check`.
- [x] **Publication Credential Guard:** Verified clean via `python3 research/antigravity/tooling/publication_guard.py` (Exit Code 0).
- [x] **Git Invariant:** Zero git commits or pushes from subagent.
