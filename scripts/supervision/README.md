# Autonomous Supervision Service & Launcher Task Admission

- **Scope**: `scripts/supervision/**`
- **Owner**: `ant-integration-head-recovery` (session `c69a9f51`)
- **System**: Agent Quota Launcher (`agent-quota-launcher`) & Autonomous Supervision Bridge (`scripts/supervision/service.py`)

---

## 1. Context & Architectural Overview

The Autonomous Supervision Service (`scripts/supervision/service.py`) bridges ready tasks into the canonical `agent-quota-launcher` store (`state.db`) and monitors execution lifecycle.

Task execution uses detached transient systemd service units under `app.slice` (`ql-ctl-<safe_id>.service` and `task-<safe_id>.service`) with isolated cgroup bounds (`TasksMax=100`, `MemoryMax<=1500M`), ensuring worker processes never exhaust interactive shell cgroup limits.

---

## 2. Admission & Candidate Ranking Requirements

### 2.1 The Fail-Closed `model_requirements` Invariant

When tasks are submitted to `agent-quota-launcher`:
1. `validate_quse(quse, task_requirements=payload.get("model_requirements"))` validates quota evidence and evaluates route health.
2. For model-backed tasks (`model-task`, `model-review`), candidate routes (`antigravity` / Gemini, `zai` / GLM) are ranked via `select_candidate(valid_routes)`.
3. In `launcher/ranking.py`, candidate weight is computed as:
   $$\text{weight} = \text{task\_fit} \times \text{health} \times \text{pref} \times \text{headroom} \times \text{mult} \times \text{promo}$$
4. **Critical Invariant**: If `task_requirements` (i.e. `payload["model_requirements"]`) is absent or `None`, `_task_fit` evaluates to `None`. In accordance with fail-closed audit rules, `calculate_weight` assigns `weight = 0.0` ("unknown task_fit/health (no fabricated 1.0)").
5. When all candidate weights are `0.0`, `select_candidate` returns `None`. The launcher reports `{"error": "no eligible provider route available", "rejections": rejections}`.
6. The emitted `rejections` dictionary contains only explicitly rejected non-candidate routes (`claude`, `codex`, `copilot`, `go`, `grok`). Eligible routes (`antigravity`, `zai`) remain eligible in `valid_routes` but are excluded from selection due to zero weight from missing `model_requirements`.

### 2.2 Correct Task Payload Schema

Every model-backed task payload must explicitly include `model_requirements`:

```json
{
  "goal": "Detailed task instructions...",
  "profile": "model-task",
  "cwd": "/path/to/workspace",
  "owner": "ant-integration-head-recovery",
  "timeout": 600,
  "model_requirements": {
    "providers": ["antigravity", "zai"]
  }
}
```

Or for a specific required model:
```json
{
  "goal": "Adversarial code review instructions...",
  "profile": "model-review",
  "cwd": "/path/to/workspace",
  "owner": "ant-integration-head-recovery",
  "timeout": 900,
  "model_requirements": {
    "models": ["gemini-3.8-flash-high"]
  }
}
```

### 2.3 Automated Supervision Bridge Guarantee

`bridge_ready_task_to_launcher` in `scripts/supervision/service.py` enforces this invariant automatically:
- If a transitioning task omits `model_requirements`, the bridge automatically defaults to:
  `"model_requirements": {"providers": ["antigravity", "zai"]}`.
- This guarantees that ready tasks enqueued by supervision always possess non-zero task fit and admit cleanly through candidate selection.
- Tested by `LauncherAdmissionAndBridgeRegression` in `scripts/supervision/test_service.py`.

---

## 3. Supported Route Inventory (October 2026)

| Route / Name | Underlying Provider | Model | Admission Status | Gate Condition |
| :--- | :--- | :--- | :--- | :--- |
| `gemini` | `antigravity` | `gemini-3.1-pro-high` / `gemini-3.8-flash-high` | **Eligible** | Health 1.0, active 5h/7d windows (>18% rem) |
| `zai` | `zai` | `glm-5.3-flash` | **Eligible** | Health 1.0, active 5h/7d windows (>42% rem) |
| `grok` | `grok` | `grok-4.6` | **Frozen** | Policy cutoff ($\le 5\%$ remaining quota) |
| `codex` | `codex` | `gpt-4o` / `o1` | **Blocked** | Fail-closed: missing/unknown 5h window reading |
| `claude` | `anthropic` | `claude-3-5-sonnet` | **Blocked** | Unsupported route in launcher v0.1 |
| `copilot` | `github` | `copilot` | **Blocked** | Unsupported route in launcher v0.1 |
| `go` | `google` | `go` | **Blocked** | Unsupported route in launcher v0.1 |

---

## 4. Execution & Verification Runbook

### Submitting a Model Task
```bash
python3 -m launcher.cli --config-dir ~/.config/agent-quota-launcher submit \
  --id "<task_id>" \
  --key "ql-task-<task_id>" \
  --payload '{"goal": "<instructions>", "profile": "model-task", "model_requirements": {"models": ["gemini-3.1-pro-high"]}, "owner": "ant-integration-head-recovery", "cwd": "/path/to/workspace", "timeout": 600}'
```

### Executing via Detached Transient Unit
```bash
python3 -m launcher.cli --config-dir ~/.config/agent-quota-launcher run \
  --backend task-units --id "<task_id>" --cwd /path/to/workspace
```

### Verifying Execution & Logs
```bash
# Check unit status
systemctl --user status "task-<safe_task_id>.service"
journalctl --user -u "task-<safe_task_id>.service" -n 50 --no-pager

# Check logs in launcher directory
cat ~/.config/agent-quota-launcher/<task_id>-stdout.log
```
