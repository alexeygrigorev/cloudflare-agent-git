# REPORT: Authoritative Technical Audit & Diagnostic of Sessionless Executor Routes & Admission Gates

**Directives**: Codex Principal Directives C2229, C2238, C2239  
**Author / Role**: Self-Organization Architect (tag: `architect06`)  
**Parent**: `antigravity-head` (`46fdb644`, id: `245c7bba-9a7b-45c1-87a7-4537f289f9a5`)  
**Workspace**: `/home/alexey/git/cloudflare-agent-git`  
**Scratch Root**: `/home/alexey/git/cloudflare-agent-git/.local/scratch/architect06-executor-admission/` (mode `0700`, <= 512 MB)  
**Date**: 2026-10-05  
**Credential Validation**: `research/antigravity/tooling/publication_guard.py` (Exit Code `0` CLEAN)  

---

## 1. Executive Summary

Under Codex Principal Directives C2229, C2238, and C2239, an authoritative technical audit and diagnostic of all sessionless alternative executor routes and admission gates was conducted for `agent-quota-launcher` and the self-organization subsystem.

### 1.1 Key Diagnostic Findings & Route Summary

| Route / Provider | Target Model | Binary Path | Quota Status | Admission Gate Status | Execution Verdict |
|---|---|---|---|---|---|
| **Route 1: `zai`** | `glm-5.3-flash` | `/home/alexey/.local/bin/zcodex` | 99% (5h), 67% (7d) | **HELD** | Outside 17:00–03:00 Berlin promotional campaign window (~03:44; uses verified ordinary allowance per policy), but held on unconfined `/tmp` containment risk; nested CJS execution unverified without runtime receipt. |
| **Route 2: `grok`** | `grok-4.6` | `/home/alexey/.local/bin/grok` | 68% (7d) | **FAILING / BLOCKED** | Syntax error in launcher recipe: passes `grok -p --model...` instead of `grok -p <PROMPT>`, causing exit code 2 argument error. Fix: place `-p` at end of argv. |
| **Route 3: `antigravity`** | `gemini-3.1-pro-high` | `/home/alexey/.local/bin/agy` | 95.8% (5h), 70.8% (7d) | **CANDIDATE / SOURCE-COMPATIBLE** | Syntax & OAuth unsetting verified; live execution under systemd scope with active cgroup MemoryMax/PID/TMP audit and model response remains pending contained trial. Prefer Flash models per resource policy. |
| **Route 4: `opencode`** | `space-bunny-free`, `muse-spark-1.3` | `/home/alexey/.nvm/.../bin/opencode` | 100% (5h), 100% (7d) on `go` | **FAIL-CLOSED / BLOCKED** | Completely absent from `launcher/admission.py` (`ADAPTER_ROUTES`) and `launcher/launch.py` (`ADAPTERS`); `models` listing proves discovery only, not runtime execution. |

---

## 2. Fresh Quota Verification across All Provider Windows

An audit reading was captured directly via `quse --json` on 2026-10-05T01:43:58Z:

### 2.1 Provider Window Readings
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
  "gemini (antigravity)": {
    "status": "ok",
    "windows": {
      "5h": {"percent_remaining": 95.8, "reset_at": "2026-10-05T06:24:26Z", "rolling": false},
      "7d": {"percent_remaining": 70.75, "reset_at": "2026-10-09T08:09:37Z"}
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
  "go (opencode-go)": {
    "status": "ok",
    "windows": {
      "5h": {"percent_remaining": 100.0, "reset_at": "2026-10-05T06:43:56Z", "rolling": true},
      "7d": {"percent_remaining": 100.0, "reset_at": "2026-10-12T00:00:00Z"},
      "monthly": {"percent_remaining": 81.0, "reset_at": "2026-10-22T06:20:23Z"}
    }
  },
  "claude": {
    "status": "ok",
    "windows": {
      "5h": {"percent_remaining": 63.6, "reset_at": "2026-10-05T05:30:00Z"},
      "7d": {"percent_remaining": 49.0, "reset_at": "2026-10-08T15:00:00Z"}
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

---

## 3. Route-by-Route Admission & Execution Diagnostic

### 3.1 Route 1: `zai` (GLM-5.3-Flash via `zcodex`)

1. **Binary & Wrapper Verification**:
   - Location: `/home/alexey/.local/bin/zcodex` (mode `0755`).
   - Implementation: Bourne-Again shell wrapper script invoking `/home/alexey/.local/lib/zcodex/zcodex "$@"`.
   - Execution Mapping: The underlying binary maps to `/opt/ZCode/resources/glm/zcode.cjs`. This nested CJS execution mapping remains unverified in this audit without a live, contained runtime execution receipt.
2. **Quota Policy & Time Window Clarification (Human34 Directive)**:
   - Time of Audit: `Mon Oct 5 03:44:08 CEST 2026` (~03:44 Berlin).
   - Campaign Window: The promotional zero-consumption campaign for GLM-5.3-Flash operates strictly between **17:00–03:00 Europe/Berlin**.
   - Allowance Status: Per `coordination/RESOURCE-POLICY.md` (lines 50–58), execution outside the 17:00–03:00 Berlin window is authorized to use verified ordinary paid allowance (not unauthorized spend). However, during this window, free zero-consumption routing does not apply.
3. **Root TMPDIR Containment Constraint (Primary Hold)**:
   - Invariant: Host `/tmp` must experience zero net growth; all temporary files must reside strictly within isolated scratch storage.
   - Finding: Invoking `zcodex` risks unconfined `/tmp` file creation by the Node.js/NAPI/CJS runtime unless strictly wrapped with verifiable nested temp jail isolation.
4. **Verdict**: **HELD** (Held specifically on the root `TMPDIR` containment constraint; nested CJS execution mapping unverified without runtime receipt).

---

### 3.2 Route 2: `grok` (Grok-4.6 via `grok` CLI)

1. **Binary Verification**:
   - Location: `/home/alexey/.local/bin/grok` -> `/home/alexey/.grok/bin/grok`.
   - Tool Version: Grok Build TUI v0.1.0-alpha.
2. **Launcher Adapter Recipe Defect**:
   - In `/home/alexey/git/agent-quota-launcher/launcher/launch.py`:
     ```python
     ADAPTERS["grok"] = {
         "argv": ["grok", "-p", "--model", "grok-4.6", "--effort", "high", "--permission-mode", "auto"],
         "env": {},
     }
     ```
   - When `build_adapter_argv("grok", goal)` is called, it constructs:
     ```bash
     grok -p --model grok-4.6 --effort high --permission-mode auto <goal>
     ```
3. **Empirical Execution & Failure Reproduction**:
   - Command tested: `["grok", "-p", "--model", "grok-4.6", "--effort", "high", "--permission-mode", "auto", "echo hello"]`
   - Exit Code: `2`
   - Exact Stderr Captured:
     ```text
     error: a value is required for '--single <PROMPT>' but none was supplied

     For more information, try '--help'.
     ```
4. **Root Cause Analysis & Concrete Candidate Fix**:
   - In `grok --help`, the definition of `-p` is `-p, --single <PROMPT>`: A single-turn prompt flag that expects `<PROMPT>` immediately following `-p`.
   - Because clap/rust treats tokens starting with `-` as option flags rather than argument values, `--model` is rejected as a prompt value for `--single`.
   - **Candidate Fix**: Place `-p` at the end of the argument vector so that the appended `<goal>` becomes the immediate value for `-p`:
     ```python
     "argv": ["grok", "--model", "grok-4.6", "--effort", "high", "--permission-mode", "auto", "-p"]
     ```
5. **Verdict**: **FAILING / BLOCKED** (Launcher adapter recipe syntax error; fix identified).

---

### 3.3 Route 3: `antigravity` (Gemini-3.1-pro-high via `agy` CLI)

1. **Binary Verification**:
   - Location: `/home/alexey/.local/bin/agy`.
   - Type: Standalone statically linked Go ELF binary (209,625,296 bytes).
2. **Launcher Adapter Recipe Audit**:
   - In `launcher/launch.py`:
     ```python
     ADAPTERS["antigravity"] = {
         "argv": [
             "env", "-u", "GEMINI_API_KEY", "-u", "GOOGLE_API_KEY",
             "agy", "--model", "gemini-3.1-pro-high", "--effort", "high",
             "--dangerously-skip-permissions", "-p", "--print-timeout", "0",
             "--output-format", "text"
         ],
         "env": {},
     }
     ```
   - Invocation: Stripping ambient `GEMINI_API_KEY` and `GOOGLE_API_KEY` forces OAuth authentication against local credentials, avoiding unauthorized API billing.
3. **Status Demarcation & Model Preference**:
   - **CLI Compatibility**: The CLI flag syntax, OAuth environment unsetting, and argument positioning are verified source-compatible.
   - **Pending Trial**: Live execution under an `aplexer` systemd scope with active cgroup `MemoryMax=1500M`, `TasksMax=100`, `$TMPDIR` containment audit, and verified model response generation remains pending a dedicated contained trial before full production admission.
   - **Model Policy Alignment**: Per current resource policy, model routing should prefer eligible Flash models (e.g. Gemini 2.5 Flash / Flash-Lite) where supported, matching exact model tier quotas and preserving Pro quotas for high-complexity architectural reasoning.
4. **Verdict**: **CANDIDATE / SOURCE-COMPATIBLE (CONTAINED MODEL TRIAL PENDING ADMISSION RECEIPT)**.

---

### 3.4 Route 4: `opencode` (Space Bunny / Muse Spark 1.3)

1. **Binary Verification & CLI Discovery Boundary**:
   - Location: `/home/alexey/.nvm/versions/node/v24.13.1/bin/opencode` (v1.18.31).
   - Discovery vs. Proven Execution: `opencode models` confirms that `opencode/space-bunny-free` and `opencode/muse-spark-1.3-contributor-free` appear in model discovery. However, CLI discovery does NOT demonstrate proven runtime execution or successful model invocation under batch constraints.
2. **Quota Demarcation (`opencode-go` vs. Free Routes)**:
   - In `quse --json`, the `go` provider entry reflects **opencode-go** commercial allowance (100% 5h, 100% 7d, 81% monthly).
   - This `opencode-go` quota is distinct from the third-party contributor/free routes (`opencode/space-bunny-free`, `opencode/muse-spark-1.3-contributor-free`).
3. **Launcher Admission & Dispatch Defect**:
   - In `launcher/admission.py`:
     ```python
     ADAPTER_ROUTES = ("grok", "antigravity", "zai")
     ```
     `opencode` is completely absent from `ADAPTER_ROUTES`. When `validate_quse` parses `quse_data["go"]`, line 113 blocks it with:
     ```text
     "Unsupported route explicitly blocked"
     ```
   - In `launcher/launch.py`:
     `ADAPTERS` does not define `"opencode"`. Calling `build_adapter_argv("opencode", goal)` raises `ValueError("Unsupported provider: opencode")`.
4. **Verdict**: **FAIL-CLOSED / BLOCKED** (Missing from launcher adapter and admission tables; discovery proven, runtime unproven).

---

## 4. Remediation Recommendations for Self-Organization

To restore multi-provider execution capacity under strict containment:

1. **Fix Grok Launcher Recipe**:
   Update `ADAPTERS["grok"]["argv"]` in `launcher/launch.py` to place `-p` at the end:
   ```python
   "argv": ["grok", "--model", "grok-4.6", "--effort", "high", "--permission-mode", "auto", "-p"]
   ```
2. **Conduct Contained Antigravity Trial**:
   Execute a single-turn contained smoke trial of `agy` within a dedicated scratch cgroup/TMPDIR to verify MemoryMax, PID bounds, and clean stdout text emission before full admission. Align default model selection with Flash where appropriate.
3. **Add OpenCode Route to Launcher**:
   - Add `"opencode"` to `ADAPTER_ROUTES` and `ADAPTER_MODELS` in `launcher/admission.py`.
   - Add `"opencode"` to `ADAPTERS` in `launcher/launch.py` with verified free model targets (`space-bunny-free` / `muse-spark-1.3-contributor-free`).
4. **Verify ZCode Runtime Jailing**:
   Implement and prove isolated `TMPDIR` redirection for `zcodex` before enabling ordinary allowance execution outside 17:00–03:00 Berlin or promotional execution inside the window.

---

## 5. Invariant Compliance Checklist

- [x] **Zero cargo / rustc invocations**: Verified zero calls. Standard Linux CLI inspection only.
- [x] **Zero Credential Leaks**: Never printed private tokens, secrets, or raw keys.
- [x] **Canonical Isolation**: Canonical `/home/alexey/git/agent-bus` remains 100% untouched.
- [x] **Scratch Footprint**: Scratch usage strictly in `.local/scratch/architect06-executor-admission/` (<= 512 MB, zero net `/tmp` growth).
- [x] **Publication Credential Guard**: Ran `python3 research/antigravity/tooling/publication_guard.py research/antigravity/recovery/REPORT-SESSIONLESS-EXECUTOR-ROUTE-ADMISSION.md` with zero violations (exit code 0).
- [x] **Git Hygiene**: Subagent did NOT perform git commit or tag mutations.
