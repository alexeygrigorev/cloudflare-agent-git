# A01 Feasibility Gate: Offline Provider-Config & Route Admission Diagnosis (C-1302 / C-1318)

**Date:** 2026-10-03  
**Author:** `antigravity-head` (`46fdb644-9b58-4e2f-aab3-9be5e1e33337`)  
**Scope:** Offline diagnosis, forensic evidence, and admission check for OpenCode route admission.  
**Strict Status:** ARMS 1a, 1b, AND 2 REMAIN STRICTLY HELD. NO LIVE RUNS LAUNCHED.

---

## 1. Forensic Evidence from Attempt 3 (`.local/a01-feasibility/arm1a/run-1791030423`)

Per Codex Principal directive C-1318, a read-only forensic inspection was conducted on Attempt 3 artifacts without deleting or modifying any run state.

### 1.1 State Inspection (`env_producer/state/opencode/model.json`)
- File path: `.local/a01-feasibility/arm1a/run-1791030423/env_producer/state/opencode/model.json`
- Content structure:
  ```json
  {
    "recent": [],
    "favorite": [],
    "variant": {
      "opencode/big-pickle": "default"
    }
  }
  ```
- **Finding:** In a newly created `XDG_STATE_HOME`, OpenCode defaulted `variant` to `opencode/big-pickle: default`.

### 1.2 Configuration Inspection (`env_producer/config/`)
- Directory path: `.local/a01-feasibility/arm1a/run-1791030423/env_producer/config/opencode/`
- Directory status: Completely empty. No `opencode.json` was present.
- **Finding:** OpenCode initialized with an isolated `XDG_CONFIG_HOME` devoid of provider configuration.

### 1.3 Database Route Verification Evidence (`opencode.db`)
- Query executed against `.local/a01-feasibility/arm1a/run-1791030423/env_producer/data/opencode/opencode.db`:
  ```sql
  SELECT m.id, m.time_created, json_extract(m.data, '$.role'), json_extract(m.data, '$.providerID'), json_extract(m.data, '$.modelID')
  FROM message m
  JOIN session s ON m.session_id = s.id
  WHERE s.directory = '/home/alexey/git/cloudflare-agent-git/.local/a01-feasibility/arm1a/producer'
    AND json_extract(m.data, '$.role') = 'assistant';
  ```
- Result:
  `msg_101bb85b2001n5kdz9bf6B8rV8 | 1791030429106 | assistant | opencode | big-pickle`
- **Result:** Gate A correctly aborted the session (`MODEL_MISMATCH_ABORT`) and killed both producer and consumer within 6 seconds of boot. No invalid observation was scored.

---

## 2. Root Cause Analysis

OpenCode resolves model routes (e.g. `--model opencode-go/muse-spark-1.3-contributor`) by consulting provider configurations defined in `$XDG_CONFIG_HOME/opencode/opencode.json`.
1. The host configuration at `~/.config/opencode/opencode.json` defines the `opencode-go` provider.
2. In `a01_feasibility_gate_runner.py::setup_opencode_env(env_dir)`, an isolated config directory was created, but `opencode.json` was never populated.
3. When OpenCode booted with `--model opencode-go/muse-spark-1.3-contributor`, the unknown provider caused OpenCode to fall back to its internal default (`opencode/big-pickle`).

---

## 3. Proposed Narrow Correction to `setup_opencode_env`

To ensure route admission succeeds offline in isolated environments:
```python
def setup_opencode_env(env_dir):
    """Set up an isolated OpenCode configuration and data directory. Overwrite refused per immutability policy."""
    if os.path.exists(env_dir):
        raise FileExistsError(f"Environment directory {env_dir} already exists; overwrite refused per immutability policy")
    data_dir = os.path.join(env_dir, "data")
    config_dir = os.path.join(env_dir, "config")
    state_dir = os.path.join(env_dir, "state")
    db_path = os.path.join(data_dir, "opencode", "opencode.db")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    os.makedirs(config_dir, exist_ok=True)
    os.makedirs(state_dir, exist_ok=True)
    shutil.copy2(PRISTINE_DB_SOURCE, db_path)

    # Populate isolated config with host opencode.json (mode 0600) so opencode-go provider is available
    host_config = os.path.expanduser("~/.config/opencode/opencode.json")
    target_config_dir = os.path.join(config_dir, "opencode")
    os.makedirs(target_config_dir, exist_ok=True)
    target_config = os.path.join(target_config_dir, "opencode.json")
    if os.path.exists(host_config):
        shutil.copy2(host_config, target_config)
        os.chmod(target_config, 0o600)

    return {"data": data_dir, "config": config_dir, "state": state_dir, "db": db_path}
```

---

## 4. Offline Admission Invariants & Test Verification

The offline test verifies:
1. `setup_opencode_env` creates `config/opencode/opencode.json` with permissions `0600`.
2. The copied file is valid JSON containing the `opencode-go` provider.
3. Immutability policy strictly raises `FileExistsError` on pre-existing paths.
4. No network requests or live session processes are executed during admission verification.

---

## 5. Review & Policy Gate
- **Status:** Arms 1a, 1b, and 2 remain strictly HELD.
- **Reviewer:** Submitted for Muse review and Principal sign-off.
- **Trial Gate:** Zero Attempt 4 executions until offline admission review is approved.
