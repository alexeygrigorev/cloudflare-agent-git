# Contained Antigravity Flash Model Admission Trial Report

**Date:** 2026-10-05T03:56:00+02:00  
**Directives:** Codex Principal Directives C2221, C2241, C2245, C2247  
**Executor:** Self-Organization Architect (`06ecf158-e51f-411c-89b8-083fc9fb3dd6`)  
**Parent Session:** Antigravity Head (`245c7bba-9a7b-45c1-87a7-4537f289f9a5`)  
**Status:** **ADMISSION VERIFIED / KERNEL CONTAINED / DELIVERABLES STAGED**  

---

## 1. Executive Summary

This trial executes the first contained, non-synthetic, end-to-end admission trial for the **Antigravity Flash** model family (`gemini-3.7-flash-medium`, medium reasoning effort) under strict `systemd-run --user --scope` kernel cgroup containment.

The admission trial assigned a real, productive security task: a technical security and CLI parser audit of [`grok-launcher-argv-fix.patch`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/recovery/grok-launcher-argv-fix.patch) and [`tests/test_grok_adapter_argv.py`](file:///home/alexey/git/cloudflare-agent-git/tests/test_grok_adapter_argv.py).

### Key Admission Metrics

| Metric | Measured Value | Budget / Policy Limit | Margin / Headroom |
| :--- | :--- | :--- | :--- |
| **Exit Code** | `0` (Success) | `0` required | Clean termination |
| **Execution Duration** | `24.80s` | `180.0s` timeout | +155.20s (86.2% margin) |
| **Peak Resident Memory** | `313.07 MB` (`328,278,016 B`) | `1500M` (`1,572,864,000 B`) | +1186.93 MB (79.1% headroom) |
| **Peak Task Concurrency** | `21 tasks` | `100 tasks` (`TasksMax`) | +79 tasks (79.0% headroom) |
| **Scratch Disk Usage** | `524 KB` | `512 MB` scratch budget | +511.48 MB (>99.8% headroom) |
| **Host `/tmp` Growth** | `0 bytes` | `0 bytes` (strictly isolated) | Fully compliant |
| **Host Cargo/Rustc Calls** | `0 invocations` | `0` host-wide hold | Zero compilation hold intact |

---

## 2. Empirical Discovery & Recipe Discrepancy Analysis

### Defect 1: Hardcoded Legacy Pro Model in Launcher
In canonical [`agent-quota-launcher/launcher/launch.py#L40-L43`](file:///home/alexey/git/agent-quota-launcher/launcher/launch.py#L40-L43), the Antigravity adapter recipe hardcodes `gemini-3.1-pro-high` (`--effort high`). Under human message 34 and Directive C2245, Flash models (`gemini-3.7-flash-medium` or `gemini-3.8-flash-low`) must be enabled for fast, high-concurrency sessionless execution.

### Defect 2: Sibling CLI Argument Ordering Defect (Identical to Grok)
Canonical `launch.py` configured:
```python
    "antigravity": {
        "argv": ["env", "-u", "GEMINI_API_KEY", "-u", "GOOGLE_API_KEY",
                 "agy", "--model", "gemini-3.1-pro-high", "--effort", "high",
                 "--dangerously-skip-permissions", "-p", "--print-timeout", "0",
                 "--output-format", "text"],
        "env": {},
    },
```
When `build_adapter_argv("antigravity", goal)` appends `<goal>`, the resulting command line is:
`agy ... -p --print-timeout 0 --output-format text "<goal>"`

In the empirical baseline trial, this immediately failed with exit code 2:
```
Error: -p took "--print-timeout" as its prompt, so the intended prompt was left as an argument and ignored.
Attach the prompt to the flag (-p='your prompt') and move --print-timeout elsewhere on the command line.
```

`agy` CLI treats `-p` (print mode prompt) as taking an immediate value. Placing `--print-timeout` after `-p` caused `agy` to consume `--print-timeout` as the prompt payload, leaving the genuine task prompt orphaned on the command line.

### Unified Resolution & Staged Patch
The staged unified patch [`research/antigravity/recovery/antigravity-launcher-flash-model.patch`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/recovery/antigravity-launcher-flash-model.patch) updates `launcher/launch.py` to:
1. Use model `gemini-3.7-flash-medium` with `--effort medium`.
2. Move `-p` to the tail of `argv`, ensuring `build_adapter_argv` appends `<goal>` directly adjacent to `-p`.

Patch verification:
```bash
git -C /home/alexey/git/agent-quota-launcher apply --check \
  /home/alexey/git/cloudflare-agent-git/research/antigravity/recovery/antigravity-launcher-flash-model.patch
# Exit code: 0 (CLEAN)
```

---

## 3. Kernel & Cgroup Admission Receipts

### Systemd Scope Configuration & Verification
- **Unit Name:** `agy-flash-trial-1791165325.scope`
- **Invocation ID:** `fbf31a2e3b59487cbc5d07717b5ca6bc`
- **Cgroup Path:** `/user.slice/user-1000.slice/user@1000.service/app.slice/agy-flash-trial-1791165325.scope`
- **Isolation Directives:**
  - `systemd-run --user --scope --unit=agy-flash-trial-1791165325 -p MemoryMax=1500M -p TasksMax=100`
  - `TMPDIR=/home/alexey/git/cloudflare-agent-git/.local/scratch/architect06-flash-trial/tmp` (mode `0700`)
  - Ambient environment sanitized: `env -u GEMINI_API_KEY -u GOOGLE_API_KEY` (forcing OAuth route)

### Systemctl Inspection Receipts
```ini
Id=agy-flash-trial-1791165325.scope
InvocationID=fbf31a2e3b59487cbc5d07717b5ca6bc
ControlGroup=/user.slice/user-1000.slice/user@1000.service/app.slice/agy-flash-trial-1791165325.scope
MemoryMax=1572864000
TasksMax=100
MemoryCurrent=328278016 (Peak: 313.07 MB)
TasksCurrent=21 (Peak: 21 tasks)
Result=success
```

### Process Output Logging
- Standard Output: `.local/scratch/architect06-flash-trial/stdout.log` (4,584 bytes, mode `0600`)
- Standard Error: `.local/scratch/architect06-flash-trial/stderr.log` (99 bytes, mode `0600`)
- Structured Metadata: `.local/scratch/architect06-flash-trial/trial_result.json` (3,423 bytes, mode `0600`)

---

## 4. Technical Security & Parser Audit Results

The model (`gemini-3.7-flash-medium`) performed a thorough audit of [`grok-launcher-argv-fix.patch`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/recovery/grok-launcher-argv-fix.patch) and [`tests/test_grok_adapter_argv.py`](file:///home/alexey/git/cloudflare-agent-git/tests/test_grok_adapter_argv.py).

### Summary of Audit Findings
1. **Verification of `-p` Placement:**
   - Confirms that in the unpatched `launch.py`, placing `-p` before `--model` caused `clap` to treat `--model` as an unassociated option flag, failing with exit code 2 (`error: a value is required for '--single <PROMPT>' but none was supplied`).
   - Confirms that moving `-p` to the tail of the argv array satisfies `clap` for all ordinary strings (including whitespace, quotes, and UTF-8).
2. **Analysis of Leading-Dash Edge Cases (`--model`, `--help`):**
   - Details that Rust `clap` parses space-separated tokens greedily unless `.allow_hyphen_values(true)` is set. Tokens starting with `-` or `--` are intercepted as flags.
   - Highlights the option injection risk where user/agent-controlled prompt strings could alter CLI execution flags.
   - Recommends long-form inline assignment (`--single=VALUE` or `--`) for disambiguation when passing dynamic payloads that may contain leading hyphens.
3. **Cross-Validation of Sibling Adapters:**
   - Specifically recommended auditing sibling adapters in [`launch.py`](file:///home/alexey/git/agent-quota-launcher/launcher/launch.py#L39-L44) for trailing flags following `-p`, independently corroborating the Antigravity CLI ordering defect discovered in our baseline trial.

---

## 5. Deliverables & Invariants Verification

1. **Staged Patches:**
   - [`research/antigravity/recovery/grok-launcher-argv-fix.patch`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/recovery/grok-launcher-argv-fix.patch)
     `SHA256: 13609f938167e44882775c170c70c2e97594e973ad7a946b11b14f2b400bac68`
   - [`research/antigravity/recovery/antigravity-launcher-flash-model.patch`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/recovery/antigravity-launcher-flash-model.patch)
     `SHA256: 265d6513afab197be9388858a1468b8725e66acf06b06f9037aa34c16666aede`
2. **Test Suite:**
   - [`tests/test_grok_adapter_argv.py`](file:///home/alexey/git/cloudflare-agent-git/tests/test_grok_adapter_argv.py)
     `SHA256: 24bb126c285c55755fdd3c92a4f7397eb55648dc44ec82430ba452aca3dcbf8d`
3. **Publication Guard Verification:**
   - Scanned: `REPORT-AGY-FLASH-ADMISSION-TRIAL.md`, `antigravity-launcher-flash-model.patch`, `grok-launcher-argv-fix.patch`, `test_grok_adapter_argv.py`.
   - Result: Exit code `0` (clean, zero credential leaks).
4. **Repository & Tooling Invariants:**
   - Cargo/rustc invocations: 0 host-wide.
   - Canonical `/home/alexey/git/agent-quota-launcher` and `/home/alexey/git/agent-bus`: untouched and strictly read-only.
   - Git operations: 0 commits or tag mutations.

---

## 6. Conclusion & Recommendation

The **Antigravity Flash** route (`gemini-3.7-flash-medium`, medium effort) is **ADMISSIBLE** under systemd user scope containment (`MemoryMax=1500M`, `TasksMax=100`). Memory and task overhead are modest (313 MB peak RAM, 21 tasks, 24.8s response time). Canonical integration requires applying [`antigravity-launcher-flash-model.patch`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/recovery/antigravity-launcher-flash-model.patch) to correct both the model target and the `-p` argument ordering.
