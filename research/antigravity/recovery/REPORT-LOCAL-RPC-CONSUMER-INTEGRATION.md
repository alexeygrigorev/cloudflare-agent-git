# REPORT: Sibling Agent-Bus Integration Preparation & Real Local-Process RPC Consumer Verification

**Directives**: Codex Principal Directives C2162, C2164, C2166, C2196, C2201  
**Author / Role**: Self-Organization Architect (tag: `architect06`)  
**Parent**: `antigravity-head` (`46fdb644`, id: `245c7bba-9a7b-45c1-87a7-4537f289f9a5`)  
**Workspace**: `/home/alexey/git/cloudflare-agent-git`  
**Scratch Root**: `/home/alexey/git/cloudflare-agent-git/.local/scratch/architect06-bus-integration/` (mode `0700`, <= 512 MB)  
**Scratch TMPDIR**: `/home/alexey/git/cloudflare-agent-git/.local/scratch/architect06-bus-integration/tmp/` (mode `0700`, zero writes to host `/tmp`)  
**Base Commit**: `f3295f99e188719f5df9fccb22706d8a0e5bb8f8`  
**Integration Branch**: `feat/typed-ssh-filebus-rpc`  
**Integration Commit SHA**: `23b0742b1f00ec027d830763e773577a807dbc39`  
**Patch Artifact**: `/home/alexey/git/cloudflare-agent-git/research/antigravity/recovery/typed-ssh-filebus-rpc-hardened.patch`  
**Patch SHA256**: `444165fd8821c371e01cb5dfb39775e3be50e466e1b54f2eb7ab982176efc976`  
**Date**: 2026-10-05  
**Credential Validation**: `research/antigravity/tooling/publication_guard.py` (Exit Code `0` CLEAN)  

---

## 1. Executive Summary

Under Codex Principal Directives C2196 and C2201, clean sibling integration preparation for `agent-bus` and real local-process RPC consumer verification were executed in complete isolation within `.local/scratch/architect06-bus-integration/`. All 17 restored files have been formally committed to the integration branch `feat/typed-ssh-filebus-rpc` at commit `23b0742b1f00ec027d830763e773577a807dbc39`.

### 1.1 Key Achievements
1. **Canonical Invariant Preserved**: The canonical repository at `/home/alexey/git/agent-bus` was accessed strictly read-only; all pre-existing uncommitted working tree files remain 100% untouched.
2. **Deterministic Patch Application**: The immutable unified patch `typed-ssh-filebus-rpc-hardened.patch` (SHA256: `444165fd8821c371e01cb5dfb39775e3be50e466e1b54f2eb7ab982176efc976`) applied cleanly on branch `feat/typed-ssh-filebus-rpc` at base commit `f3295f99e188719f5df9fccb22706d8a0e5bb8f8`.
3. **17-File Manifest Verification**: All 17 restored files were verified via SHA256 checksums matching expected principal digests.
4. **Integration Branch Commit**: All 17 files were staged and committed on branch `feat/typed-ssh-filebus-rpc` (Commit SHA: `23b0742b1f00ec027d830763e773577a807dbc39`).
5. **Full Test Suite Pass**: All 65 unit, crash, concurrency, dogfood, scoping, RPC, and adversarial security tests passed in **8.05s** (`python3 -m pytest -v tests/`).
6. **Real Local-Process RPC Consumer Verification**: Implemented and executed `verify_local_rpc_consumer.py`, validating raw stdin/stdout streaming against `bus_cli.py rpc`, full multi-agent lifecycle (enroll, send, inbox query, unread tracking, acknowledgement, structured reply), strict boolean typing, correlation enforcement, and fail-closed error omission.
7. **Adoption Scope Clarification**: Alice/Bob/Carol were component protocol fixtures proving wire framing, NOT model-level agent adoption.
8. **Explicit Boundary Disclosures**: Component and local-process verification is proven on Linux. Live two-host execution is authorized under read-only known_hosts and current resource safety rules; operational host network access / SSH host key admission remains the physical dependency.

---

## 2. 17-File Manifest & Checksum Verification

All 17 files restored by unified patch `444165fd` on branch `feat/typed-ssh-filebus-rpc` were verified with `sha256sum`:

| File Path | SHA256 Checksum | Status |
|---|---|---|
| `coordination/__init__.py` | `3fb6276d7c7060a107e549308765e9a40bd695ac85de8428b5569c2ab342479c` | **MATCH** |
| `coordination/bus.py` | `2720c191f0b6a32a6d0ad933737a7239126472e40907a55c4bc55d7396b00370` | **MATCH** |
| `coordination/bus_cli.py` | `a7a8c37459216f011267a37c52006245c91140474d12dd8006d735e1e5300715` | **MATCH** |
| `coordination/cursors.py` | `9962c9914dc2a80195cf71ee5a7b754b49386431d82a5fbce829dc04e5adf7cb` | **MATCH** |
| `coordination/durable.py` | `507cba26399e621e103782a9f3ea9e6ab26b220381e138fbe86fb76722890262` | **MATCH** |
| `coordination/envelope.py` | `a6abcf56dff5145da8b923de88bd1256db27bc26a05367e56b3135c52322c2b8` | **MATCH** |
| `coordination/errors.py` | `3ddd46071abce2d5269cb7804fd5207c8150cb5f23e3777e47aa33de076939e5` | **MATCH** |
| `coordination/headless_worker.py` | `5f8cc069aaa7fb516f8cd2a3561a560fa01d3e6cdf0f41260d315c69a5b94405` | **MATCH** |
| `coordination/ssh_rpc.py` | `98c2d3767c9b6672cb76850cac06a4b47069b9b8a451b233ee4733dc3e081429` | **MATCH (Directive Target)** |
| `tests/test_bus.py` | `0aa2c0fbb8616ff3eda78467f21cd36328b9bb2aaba39fcc1eb80e3a1a1e0ef7` | **MATCH** |
| `tests/test_bus_concurrent.py` | `cd8509285462004c2597333a0aaaa625a620c4dbab59f474a18316f2629bc315` | **MATCH** |
| `tests/test_bus_crash.py` | `1a7f95bc9b9b048ba2028e40cc2039f0e8fd422074862f8c353d707dec2275a8` | **MATCH** |
| `tests/test_bus_dogfood.py` | `8d757b963f3a6aa5ddc1e5ab248b8c15cbe1de1b658f48f821480fd90bfd6822` | **MATCH** |
| `tests/test_bus_scope.py` | `63d4907368fe4d8195fdd8ac011a822ce4bfdebb95119e9f6edd46c17fead2d7` | **MATCH** |
| `tests/test_headless_task.py` | `cbe6bf747b4a6c31fc72aebd306047ff3c3e53d7884f916d48ca50192d230b59` | **MATCH** |
| `tests/test_ssh_rpc.py` | `82d876d0580045756aafadd3cbaa07bd5d4488d78c899158c4fa8fd288de9ab9` | **MATCH** |
| `tests/test_ssh_rpc_security.py` | `b07a6eefeda9ee2cc34adfaeae1ae6a5d40a681f9568acb244017b8f2c3a851d` | **MATCH (Directive Target)** |

---

## 3. Test Suite Execution Receipts (65/65 PASS)

The complete snapshot test suite was executed under isolated `TMPDIR`:

```bash
TMPDIR=/home/alexey/git/cloudflare-agent-git/.local/scratch/architect06-bus-integration/tmp \
PYTHONPATH=.local/scratch/architect06-bus-integration/agent-bus \
python3 -m pytest -v .local/scratch/architect06-bus-integration/agent-bus/tests/
```

### Execution Log Summary
```text
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-9.1.1, pluggy-1.6.0
rootdir: /home/alexey/git/cloudflare-agent-git/.local/scratch/architect06-bus-integration/agent-bus
configfile: pyproject.toml
plugins: anyio-4.12.1, opik-2.2.54
collecting ... collected 65 items

tests/test_bus.py ...........                                            [ 16%]
tests/test_bus_concurrent.py ..                                         [ 20%]
tests/test_bus_crash.py .....                                            [ 27%]
tests/test_bus_dogfood.py .                                              [ 29%]
tests/test_bus_scope.py ....                                             [ 35%]
tests/test_headless_task.py .                                            [ 36%]
tests/test_ssh_rpc.py ..................                                 [ 64%]
tests/test_ssh_rpc_security.py .......................                   [100%]

============================== 65 passed in 8.05s ==============================
```

---

## 4. Real Local-Process RPC Consumer Verification Receipts

A dedicated consumer verification script (`verify_local_rpc_consumer.py`) was created and executed in scratch to validate end-to-end integration:

```bash
TMPDIR=/home/alexey/git/cloudflare-agent-git/.local/scratch/architect06-bus-integration/tmp \
python3 .local/scratch/architect06-bus-integration/verify_local_rpc_consumer.py
```

### Execution Output & Verified Assertions
```text
======================================================================
STARTING REAL LOCAL-PROCESS RPC CONSUMER INTEGRATION VERIFICATION
======================================================================

[Phase 1] Testing Real stdin/stdout JSON Streaming via bus_cli.py rpc...
  [OK] Enrolled Alice over RPC: id=0fa29206-ce99-48ce-bcfa-b934cead41c9
  [OK] Enrolled Bob over RPC:   id=9a867e37-2785-4a44-b47a-129498c25145
  [OK] Sent message Alice -> Bob: msg_id=6cb945d3-097a-4d24-a037-1611a41cc393
  [OK] Bob retrieved message from inbox: verified contents and sender
  [OK] Bob acknowledged message 6cb945d3-097a-4d24-a037-1611a41cc393: acked_at=2026-10-05T00:59:40Z
  [OK] Verified Bob's unread inbox is empty after acknowledgement
  [OK] Bob replied to Alice: reply_id=5358a8d0-db63-42ef-9b37-7f5754e375ae
  [OK] Alice verified reply correlation and payload in inbox

[Phase 2] Testing SshFileBusClient API with Local Subprocess Runner...
  [OK] SshFileBusClient enrolled Carol: f6a7ad1f-7786-499c-a270-3c7b1634c2aa
  [OK] SshFileBusClient sent message: f3cfa809-1604-4398-99bc-632ad5652ed1
  [OK] SshFileBusClient idempotent replay verified: f3cfa809-1604-4398-99bc-632ad5652ed1
  [OK] SshFileBusClient verified message in Alice's inbox

[Phase 3] Testing Protocol Hardening & Fail-Closed Omission Invariants...
  [OK] Strict boolean type checking verified (string 'true' rejected)
  [OK] Request ID correlation mismatch verified (request_id_mismatch from None)
  [OK] Fail-closed raw output omission verified (zero stderr leak, cause=None, context=None)
  [OK] Rejection of StrictHostKeyChecking=accept-new verified
  [OK] Rejection of StrictHostKeyChecking=no verified

======================================================================
ALL LOCAL-PROCESS RPC CONSUMER VERIFICATION CHECKS PASSED in 1.13s
======================================================================
```

---

## 5. Explicit Environmental Boundaries & Negative Findings

To prevent over-claiming capability or conflating local tests with multi-host operational readiness, the following explicit boundaries are documented:

1. **Protocol Fixtures vs. Model-Level Adoption**:
   Alice/Bob/Carol were component protocol fixtures proving wire framing, NOT model-level agent adoption.
2. **Local-Process Evidence Only**:
   All verification herein was conducted using local subprocess execution (`python3 coordination/bus_cli.py --store <store> rpc`) and pluggable runners on a Linux host (Linux 6.8, Python 3.12).
3. **Network Execution Status**:
   Live two-host execution is authorized under read-only known_hosts and current resource safety rules; operational host network access / SSH host key admission remains the physical dependency.
4. **POSIX Remote Shell Scope Boundary**:
   Argument escaping via `shlex.quote()` is verified strictly for POSIX login shells (`sh`, `bash`, `dash`, `zsh`). Remote execution on Windows hosts (`cmd.exe` or `powershell.exe`) has incompatible argument passing semantics and remains HELD.

---

## 6. Run Instructions & Source Pin for Independent Reviewer (reviewer37)

The instructions and schemas below provide an illustrative integration template for the independent reviewer workflow, **not** a prefilled verdict or peer agreement. The enrolled independent reviewer (`reviewer37` or `reviewer259`) must independently inspect source commit `23b0742b...`, evaluate configuration, test local RPC usability against the ordinary local FileBus CLI baseline, and render an unconstrained verdict (`ACCEPTED`, `BOUNDED ACCEPTANCE`, or `REQUEST_CHANGES`).

### 6.1 Source Pin
- **Repository**: `.local/scratch/architect06-bus-integration/agent-bus` (or target integration remote)
- **Branch**: `feat/typed-ssh-filebus-rpc`
- **Commit SHA**: `23b0742b1f00ec027d830763e773577a807dbc39`
- **Base Commit**: `f3295f99e188719f5df9fccb22706d8a0e5bb8f8`

### 6.2 Reviewer Ingestion Workflow (Python API Template)
```python
import os
import sys
from pathlib import Path

# Add agent-bus to PYTHONPATH
sys.path.insert(0, "/home/alexey/git/cloudflare-agent-git/.local/scratch/architect06-bus-integration/agent-bus")

from coordination.ssh_rpc import SshFileBusClient
from coordination.envelope import new_idempotency_key

# Target local RPC runner or remote SSH FileBus store
client = SshFileBusClient(
    host="desktop-local",
    store_path="/path/to/store",
    bus_cli_path="/home/alexey/git/cloudflare-agent-git/.local/scratch/architect06-bus-integration/agent-bus/coordination/bus_cli.py",
)

# 1. Enroll reviewer identity (credentials returned securely over stdin/stdout RPC)
reviewer_id, reviewer_token = client.enroll(
    agent_name="reviewer37",
    device_id="desktop-local",
    project_id="agent-coordination",
    task_id="review-typed-ssh-filebus-rpc",
)

# 2. Ingest unread review tasks
pending_tasks = client.inbox(
    identity_id=reviewer_id,
    token=reviewer_token,
    unread_only=True,
)

# 3. Process task, acknowledge, and reply with independent findings
for task in pending_tasks:
    task_id = task["message_id"]
    sender = task["sender_id"]
    
    # Acknowledge receipt
    client.ack(
        identity_id=reviewer_id,
        token=reviewer_token,
        message_id=task_id,
    )
    
    # Submit independent review report / verdict (reviewer chooses freely based on evidence)
    client.reply(
        sender_id=reviewer_id,
        token=reviewer_token,
        message_id=task_id,
        body="<Independent findings summary from reviewer37>",
        data={
            "verdict": "<ACCEPTED | BOUNDED ACCEPTANCE | REQUEST_CHANGES>",
            "reviewer": "reviewer37",
            "commit_pin": "23b0742b1f00ec027d830763e773577a807dbc39",
            "evidence_digest": "<sha256_of_review_evidence>",
        },
        idempotency_key=new_idempotency_key(f"rev-{task_id}"),
    )
```

### 6.3 Reviewer CLI Run Instructions & Credential Hygiene
> [!IMPORTANT]
> **Credential Hygiene**: Passing `--token <token>` directly in command-line arguments can expose secrets to local process observation (`/proc`, `ps aux`). For production or multi-tenant execution, prefer storing credentials in a mode `0600` JSON file and using `--cred <cred_file>`, or communicating via structured JSON over stdin with `bus_cli.py rpc`.

```bash
# 1. Enroll reviewer37 and save credentials to mode 0600 file
python3 coordination/bus_cli.py --store /path/to/store enroll \
  --agent-name reviewer37 \
  --device-id desktop-local \
  --project-id agent-coordination \
  --task-id review-typed-ssh-filebus-rpc > /path/to/reviewer_cred.json
chmod 0600 /path/to/reviewer_cred.json

# 2. Fetch unread review tasks using credential file
python3 coordination/bus_cli.py --store /path/to/store inbox \
  --cred /path/to/reviewer_cred.json \
  --unread-only

# 3. Acknowledge and reply using credential file
python3 coordination/bus_cli.py --store /path/to/store ack \
  --cred /path/to/reviewer_cred.json \
  --message-id <task_message_id>

python3 coordination/bus_cli.py --store /path/to/store reply \
  --cred /path/to/reviewer_cred.json \
  --message-id <task_message_id> \
  --body "<Independent review findings and unconstrained verdict>"
```

---

## 7. Invariant Compliance Checklist

- [x] **Zero cargo / rustc invocations**: Verified zero calls. Standard Python 3.12 and Linux tools only.
- [x] **Canonical Isolation**: Canonical `/home/alexey/git/agent-bus/` remains 100% untouched.
- [x] **Scratch Root Isolation**: All work conducted within `/home/alexey/git/cloudflare-agent-git/.local/scratch/architect06-bus-integration/` (total size: 1.8 MB <= 512 MB limit).
- [x] **Host Storage Protection**: TMPDIR strictly set to scratch tmp (`.local/scratch/architect06-bus-integration/tmp/`, mode `0700`); zero writes to host `/tmp`.
- [x] **Memory Budget Compliance**: Process footprint well within <= 1500 MB cooperative pool.
- [x] **Publication Credential Guard**: Ran `python3 research/antigravity/tooling/publication_guard.py research/antigravity/recovery/REPORT-LOCAL-RPC-CONSUMER-INTEGRATION.md` with zero violations (exit code 0).
- [x] **Git Hygiene**: Committed exclusively to isolated scratch clone branch `feat/typed-ssh-filebus-rpc` (Commit SHA: `23b0742b1f00ec027d830763e773577a807dbc39`). Canonical repo untouched.
