# Independent Peer Review: Audit of `coord-dashboard-launcher-hosts` (Device Registry & Multi-Host Tracking)

**Date & Time**: 2026-10-06T00:05:00Z (2026-10-06 02:05:00 Berlin)  
**Auditor / Reviewer**: `antigravity` (Independent Reviewer Subagent)  
**Parent Caller ID**: `ea14b401-20e9-4e48-ab08-d15be08da30d`  
**Target Repository**: `/home/alexey/git/agent-coordination`  
**Audited Task ID**: `coord-dashboard-launcher-hosts`  
**Audited Task Title**: `Verify multi-host device registry tracking in coordination/device_registry.py across distinct device IDs`  
**Task Log File**: `/home/alexey/git/agent-quota-launcher/.local/launcher-config/coord-dashboard-launcher-hosts-stdout.log`  
**Stderr Log File**: `/home/alexey/git/agent-quota-launcher/.local/launcher-config/coord-dashboard-launcher-hosts-stderr.log`  
**Telemetry File**: `/home/alexey/git/agent-quota-launcher/.local/launcher-config/coord-dashboard-launcher-hosts-telemetry.jsonl`  
**Audited Session / Conversation ID**: `a2851763-0761-4d6c-a508-9688f30d96e7`  
**Target Deliverables**:
- `/home/alexey/git/agent-coordination/coordination/device_registry.py`
- `/home/alexey/git/agent-coordination/tests/test_device_registry.py`

**Explicit Verdict**: **ACCEPTED**

---

## 1. Executive Summary & Audit Matrix

An independent technical audit was conducted on task `coord-dashboard-launcher-hosts` executed under the task-units launcher system in `/home/alexey/git/agent-coordination`.

### Core Objectives & Scope:
- **Execution Authenticity**: Verify model identity (`gemini-3.1-pro-high`), verify genuine FIRST MODEL TOOL execution before output generation, and verify exit status 0 and `SUCCESS`.
- **Deliverable Implementation & Accuracy**:
  - Multi-host tracking (`desktop`, `hetzner`, local nodes) via `DeviceRegistry` and `Device`.
  - Duplicate alias and duplicate device ID rejection/handling (preventing silent squashing of distinct nodes).
  - Device state serialization, deserialization, and allowlist enforcement.
  - Regression testing across all unit test suites in `/home/alexey/git/agent-coordination/tests/`.
- **Code Safety & Hygiene**: Zero hardcoded secrets, robust typed error handling, and clean architectural boundaries.

### Key Audit Findings:
1. **Harness & Process Execution**: Sibling task unit executed under `gemini-3.1-pro-high` (`conversation_id: a2851763-0761-4d6c-a508-9688f30d96e7`). The model performed a genuine first tool call (`view_file` on `coordination/device_registry.py`) before synthesizing any textual response. The task completed with status `SUCCESS` in 295.15s, stderr was 0 bytes, and launcher `state.db` confirms status `completed-awaiting-review | task-units sibling unit exit 0`.
2. **Deliverable Architecture & Multi-Host Tracking**:
   - `DeviceKind` distinguishes native `APLEXER_HOST` (`aplexer-host`) from client-only `SSH_CLIENT_HOST` (`ssh-client-host`).
   - `Device` model encapsulates host identity, allowlisted SSH aliases, SSH user, native aplexer availability (`can_run_aplexer()`), outbound-only constraints (`outbound_ssh_only`), and workspace root boundaries.
   - Accurately models the cross-host topology (e.g., Linux remote server `hetzner-rmthz` vs. Windows client desktop `windows-desktop`).
3. **Collision & Duplicate Rejection**:
   - The implementer diagnosed that dictionary comprehensions in `DeviceRegistry.__init__` previously allowed duplicate device IDs or duplicate SSH aliases to silently overwrite existing entries, creating configuration loss in multi-host topologies.
   - Refactored `DeviceRegistry.__init__` to explicitly track entries and raise `ValueError(f"Duplicate device ID: {d.id}")` or `ValueError(f"Duplicate SSH alias: {d.ssh_alias}")`.
4. **Test Suite & Verification**:
   - Added unit tests `test_duplicate_device_id_raises` and `test_duplicate_ssh_alias_raises` to `tests/test_device_registry.py`.
   - Verified that all 5 tests in `test_device_registry.py` pass cleanly.
   - Verified that all 35 tests in `/home/alexey/git/agent-coordination/tests/` pass with 100% pass rate in 2.65s without regressions.
5. **Code Hygiene & Safety**:
   - No hardcoded secrets, credentials, or private configuration.
   - Proper use of dataclasses (`frozen=True` on `Device`), Enums, and typing annotations.
   - Domain errors (`UnknownDevice`, `UnregisteredAlias`) are properly typed with error codes.

### Audit Evaluation Matrix

| # | Inspection Item | Verification Requirement | Observed Evidence | Verdict |
|---|---|---|---|:---:|
| **1** | Model Identity | Model configured and run as `gemini-3.1-pro-high` | `coord-dashboard-launcher-hosts-stdout.log` line 1: `init.model: "gemini-3.1-pro-high"`. Session ID: `a2851763-0761-4d6c-a508-9688f30d96e7`. | **PASS** |
| **2** | First Model Tool Execution | Genuine first tool invocation by model before output generation | Step index 1 generated tool call; Step index 2 executed `view_file` on `coordination/device_registry.py` (duration: 0.020s) before any text output. | **PASS** |
| **3** | Sibling Unit Exit & Status | Finished with status `SUCCESS` and exit code 0 | Stderr log is 0 bytes; stdout reports `status: "SUCCESS"`; launcher `state.db` records `completed-awaiting-review \| task-units sibling unit exit 0`. | **PASS** |
| **4** | Multi-Host Tracking | Supports desktop, hetzner, local nodes without hardcoded two-host limits | `DeviceKind` enum, `Device` dataclass, `examples/devices.example.json` schema supporting arbitrary topologies with distinct roles and constraints. | **PASS** |
| **5** | Duplicate Rejection | Duplicate device ID and duplicate SSH alias rejected | `DeviceRegistry.__init__` raises explicit `ValueError` on ID or alias collision. Tested and verified by unit tests. | **PASS** |
| **6** | State Deserialization & Allowlist | Loads configuration from JSON, enforces allowlisted aliases | `DeviceRegistry.load()` and `DeviceRegistry.from_dict()`. `get()` enforces known IDs; `require_alias()` rejects unregistered aliases. | **PASS** |
| **7** | Full Test Suite Pass | All tests in `agent-coordination/tests/` pass without regressions | 35 passed in 2.65s across all 11 test modules. Zero failures. | **PASS** |
| **8** | Code Safety & Hygiene | No hardcoded secrets, proper typed error handling | Clean code, typed exceptions (`UnknownDevice`, `UnregisteredAlias`), frozen dataclass immutability. | **PASS** |

---

## 2. Sibling Task Unit Execution Audit

### 2.1 Initialization & Model Identity
Inspection of `/home/alexey/git/agent-quota-launcher/.local/launcher-config/coord-dashboard-launcher-hosts-stdout.log`:
```json
{
  "event": "init",
  "conversation_id": "a2851763-0761-4d6c-a508-9688f30d96e7",
  "init": {
    "model": "gemini-3.1-pro-high",
    "cwd": "/home/alexey/git/agent-coordination",
    "tools": ["ask_custom_permission", "view_file", "run_command", "replace_file_content", ...],
    "permission_mode": "always-proceed"
  }
}
```
- **Audited Model**: `gemini-3.1-pro-high`
- **Working Directory**: `/home/alexey/git/agent-coordination`
- **Initial User Request**: `"Verify multi-host device registry tracking in coordination/device_registry.py across distinct device IDs."`

### 2.2 Genuine First Model Tool Execution
The prompt sequence in `coord-dashboard-launcher-hosts-stdout.log` demonstrates proper agentic workflow:
1. `step_index: 0`: User prompt delivered.
2. `step_index: 1`: Planner response generated (duration: 4.73s, 335 thinking tokens, calling `view_file`).
3. `step_index: 2`: **FIRST MODEL TOOL EXECUTION**:
   - `tool_name`: `view_file`
   - `tool_info`: `{"AbsolutePath": "/home/alexey/git/agent-coordination/coordination/device_registry.py"}`
   - `duration_seconds`: `0.020265792`
   - Output: `89 lines, 2760 bytes`
4. Only subsequent steps executed commands (`run_command`), modified files (`replace_file_content`), ran pytest, and synthesized the final report.

### 2.3 Exit Code & Status Verification
- Final event in `coord-dashboard-launcher-hosts-stdout.log`:
  ```json
  {
    "event": "result",
    "result": {
      "conversation_id": "a2851763-0761-4d6c-a508-9688f30d96e7",
      "status": "SUCCESS",
      "duration_seconds": 295.152644044,
      "num_turns": 1,
      "usage": {
        "input_tokens": 284986,
        "output_tokens": 21445,
        "thinking_tokens": 14470,
        "cache_read_tokens": 2210888,
        "total_tokens": 306431
      }
    }
  }
  ```
- **Stderr Log**: `/home/alexey/git/agent-quota-launcher/.local/launcher-config/coord-dashboard-launcher-hosts-stderr.log` has size **0 bytes**.
- **Launcher State DB**: Querying `/home/alexey/git/agent-quota-launcher/.local/launcher-config/state.db`:
  ```sql
  SELECT id, state, reason FROM tasks WHERE id = 'coord-dashboard-launcher-hosts';
  ```
  Returns:
  ```
  ('coord-dashboard-launcher-hosts', 'completed-awaiting-review', 'task-units sibling unit exit 0')
  ```

---

## 3. Deliverable Implementation & Accuracy Analysis

### 3.1 Multi-Host Tracking (`coordination/device_registry.py`)
`DeviceRegistry` and `Device` provide an explicit allowlist and capability model for cross-host agent coordination:

```python
class DeviceKind(str, Enum):
    APLEXER_HOST = "aplexer-host"
    SSH_CLIENT_HOST = "ssh-client-host"


@dataclass(frozen=True)
class Device:
    id: str
    kind: DeviceKind
    ssh_alias: str | None
    hostname: str
    ssh_user: str | None
    aplexer_bin: str | None
    workspace_roots: tuple[str, ...]
    role: str
    native_aplexer: bool
    outbound_ssh_only: bool
    notes: str = ""

    def can_run_aplexer(self) -> bool:
        return self.kind is DeviceKind.APLEXER_HOST and bool(self.aplexer_bin) and self.native_aplexer
```

Key architectural strengths:
- **Explicit Capabilities**: Distinguishes hosts capable of executing native aplexer commands (`can_run_aplexer() == True`) from client-only/outbound-only hosts (such as Windows desktop connecting via SSH with `outbound_ssh_only == True` and `native_aplexer == False`).
- **Flexible Topology**: Not locked to a rigid two-node topology; can register arbitrary clusters of desktop, hetzner, and local nodes.
- **Immutability**: `Device` is decorated with `@dataclass(frozen=True)`, preventing accidental runtime mutation of registered node properties.

### 3.2 Duplicate Collision Rejection
Prior to this task, `DeviceRegistry.__init__` populated internal lookups via dictionary comprehensions:
```python
# PREVIOUS VULNERABILITY (Silently overwritten):
self._by_id = {d.id: d for d in devices}
self._by_alias = {d.ssh_alias: d for d in devices if d.ssh_alias}
```
If two device definitions had collided on `id` or `ssh_alias`, earlier definitions were silently lost, which could cause routing failures or unintended impersonation in multi-node configurations.

The implementer replaced this with strict collision validation:
```python
# CURRENT IMPLEMENTATION (Fail-closed on collision):
class DeviceRegistry:
    def __init__(self, devices: list[Device]):
        self._by_id = {}
        self._by_alias = {}
        for d in devices:
            if d.id in self._by_id:
                raise ValueError(f"Duplicate device ID: {d.id}")
            self._by_id[d.id] = d
            
            if d.ssh_alias:
                if d.ssh_alias in self._by_alias:
                    raise ValueError(f"Duplicate SSH alias: {d.ssh_alias}")
                self._by_alias[d.ssh_alias] = d
```
Any collision immediately raises `ValueError` with the offending identifier, preventing partial or corrupt registry states from being loaded.

### 3.3 State Serialization & Persistence
- `DeviceRegistry.load(path: str | Path) -> DeviceRegistry`: Reads UTF-8 JSON from file.
- `DeviceRegistry.from_dict(data: dict[str, Any]) -> DeviceRegistry`: Validates dictionary schema and constructs immutable `Device` instances with proper tuple conversions and type coercions.
- Query methods:
  - `get(device_id: str) -> Device`: Retrieves by ID or raises typed `UnknownDevice(device_id)` (`code = "unknown_device"`).
  - `require_alias(alias: str) -> Device`: Retrieves by SSH alias or raises typed `UnregisteredAlias(alias)` (`code = "unregistered_alias"`).
  - `all() -> list[Device]`: Returns all registered devices.
  - `aplexer_hosts() -> list[Device]`: Returns only devices capable of hosting native aplexer instances.

---

## 4. Test Suite Execution & Verification

### 4.1 Unit Test Coverage in `tests/test_device_registry.py`
The unit tests cover:
1. `test_loads_more_than_two_host_slots`: Verifies loading `devices.example.json`, checking IDs `hetzner-rmthz` and `windows-desktop`, and inspecting kind and outbound SSH flags.
2. `test_unknown_device_and_alias`: Verifies typed exceptions `UnknownDevice` and `UnregisteredAlias` when querying non-existent devices or aliases.
3. `test_existing_ssh_alias_is_allowlisted`: Verifies alias lookup and `can_run_aplexer()` capability.
4. `test_duplicate_device_id_raises`: Verifies `ValueError` raised on duplicate device IDs.
5. `test_duplicate_ssh_alias_raises`: Verifies `ValueError` raised on duplicate SSH aliases.

Execution output:
```
tests/test_device_registry.py::test_loads_more_than_two_host_slots PASSED [ 20%]
tests/test_device_registry.py::test_unknown_device_and_alias PASSED      [ 40%]
tests/test_device_registry.py::test_existing_ssh_alias_is_allowlisted PASSED [ 60%]
tests/test_device_registry.py::test_duplicate_device_id_raises PASSED    [ 80%]
tests/test_device_registry.py::test_duplicate_ssh_alias_raises PASSED    [100%]

============================== 5 passed in 0.03s ===============================
```

### 4.2 Full Repository Regression Test Suite
Execution of all test suites in `/home/alexey/git/agent-coordination/tests/`:
```
tests/test_adapter_cli.py .                                              [  2%]
tests/test_bus.py .....                                                  [ 17%]
tests/test_bus_dogfood.py .                                              [ 20%]
tests/test_cursors.py ...                                                [ 28%]
tests/test_device_registry.py .....                                      [ 42%]
tests/test_envelope.py ..                                                [ 48%]
tests/test_guards.py ...                                                 [ 57%]
tests/test_offline_network.py .                                          [ 60%]
tests/test_sessionless_worker_bus.py .......                             [ 80%]
tests/test_ssh_relay.py ......                                           [ 97%]
tests/test_worker_bus_cli.py .                                           [100%]

============================== 35 passed in 2.65s ==============================
```
**Result**: 35 passed in 2.65s. Zero failures, zero regressions.

---

## 5. Code Safety & Hygiene

1. **Secrets & Credentials**: No credentials, tokens, or SSH private keys are hardcoded in `coordination/device_registry.py` or `tests/test_device_registry.py`. Aliases reference existing local OpenSSH client configurations.
2. **Error Handling**: Failures to resolve devices or aliases raise domain-specific, typed exceptions inheriting from `CoordinationError`. Collisions raise standard `ValueError` during initialization.
3. **Immutability & Safety**: `Device` instances are immutable dataclasses, preventing post-initialization tampering.
4. **Git Commit Status**: The changes are committed cleanly to the repository at commit `8ee61d98e544285b123692ff421330d87344209d` ("Implement SessionlessWorkerBus CLI commands and fix SSH relay/registry duplicate checks").

---

## 6. Verdict & Acceptance

Task **`coord-dashboard-launcher-hosts`** meets all audit criteria:
- Model used was `gemini-3.1-pro-high`.
- Executed genuine first model tool invocation prior to response synthesis.
- Exited with status 0 and `SUCCESS`.
- Accurately tracks multi-host topologies (desktop, hetzner, local nodes).
- Enforces strict collision rejection on duplicate IDs and SSH aliases.
- 100% of test suites in `/home/alexey/git/agent-coordination/tests/` pass cleanly without regressions.

**Final Verdict**: **ACCEPTED**
