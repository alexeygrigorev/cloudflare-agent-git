# Product 4: Desktop Orchestrator Hand-off Specification

**Document Version**: 1.0.0 (Concrete Windows Physical Execution Package)  
**Date**: 2026-10-06  
**Author**: Coordination Head (`coord-917-custody-resume-20261006`, session `3138b062`)  
**Directives**: C2991, C2994, C3000  
**Target Recipient**: `desktop-orchestrator` (session `79ffb8c7`)  

---

## 1. Overview & Principal Authorization

In accordance with Codex Principal Directive **C3000**, the reviewed v2.1.0 standalone AgentBus transport and Windows client contract is formally handed off to the Desktop Orchestrator for physical Windows execution.

> **Principal Authorization (Directive C3000)**:  
> *"Desktop runs physical client after concrete safe contract; do not wait for another principal approval for this authorized handoff."*

This specification provides the exact full source commits, file hashes, authenticated SSH pinned entrypoint, dedicated cryptographic enrollments, cursor separation, and minimal useful handshake payload.

---

## 2. Canonical Source Commits & Artifact Integrity

| Component | Repository / Location | Pinned Commit / Hash | File Path |
| :--- | :--- | :--- | :--- |
| **Canonical Source** | `agent-coordination` (`origin/codex/role-failover-20261006`) | `b3ca77650bdf34c9c3cbd361f1d99253ee71cd44` | `adapters/agent_bus_client.py` (SHA-256: `ae05c344...`) |
| **Unit Test Suite** | `agent-coordination` | `b3ca77650bdf34c9c3cbd361f1d99253ee71cd44` | `tests/test_agent_bus_client.py` (12/12 passed) |
| **Contract v2.1.0** | `cloudflare-agent-git` (`main`) | `45a032a` | `research/coordination/WINDOWS-CLIENT-STANDALONE-INTEGRATION-CONTRACT-20261006.md` |
| **Dry Run Evidence** | `cloudflare-agent-git` (`main`) | `2355b89` | `research/coordination/evidence/LITERAL-COMMAND-CONTRACT-DRY-RUN-20261006.md` |
| **Review Report** | `cloudflare-agent-git` (`main`) | `d5c724a` | `research/coordination/REV-COMMAND-CONTRACT-DRY-RUN-C2991.md` (Verdict: `ACCEPT`) |
| **Launcher Receipt** | `state.db` | Receipt ID `35` | `t-coord-command-contract-dryrun-c2991` |

---

## 3. Dedicated FileBus Cryptographic Enrollments (Non-Fixture)

Dedicated production enrollments have been provisioned in the live Hetzner store (`/home/alexey/git/agent-bus/.local/bus_store`) under mode `0600` permissions. Neither uses synthetic aplexer sessions (`session_id=None` strictly enforced):

### 3.1. Enrolled Hetzner Recipient Sink
- **Agent Name**: `coord-primary-sink`
- **Device ID**: `hetzner-rmthz`
- **Project ID**: `cross-computer-coordination`
- **Enrolled Identity ID**: `6a24d8fc-93c7-40c8-8087-99d357f0c3d7`
- **Credentials Path**: `/home/alexey/.local/agent_bus_credentials/coord_primary_sink.cred.json` (mode `0600`)

### 3.2. Enrolled Windows Desktop Client
- **Agent Name**: `windows-desktop-worker`
- **Device ID**: `windows-desktop`
- **Project ID**: `cross-computer-coordination`
- **Enrolled Identity ID**: `7e636034-6c0f-4d31-8f0f-4961652bff9d`
- **Credentials Path**: `/home/alexey/.local/agent_bus_credentials/windows_desktop_worker.cred.json` (mode `0600`)

*(Note: Raw token values are stored strictly in private local filesystem files with mode `0600` and are never broadcast in public Git or aplexer logs).*

---

## 4. Pinned Remote SSH Stdin RPC Entrypoint

Whenever executing bus commands over SSH from Windows, the command string MUST pin remote working directory and `PYTHONPATH` to ensure deterministic execution:

```bash
ssh hetzner-rmthz "cd /home/alexey/git/agent-coordination && PYTHONPATH=/home/alexey/git/agent-coordination:/home/alexey/git/agent-bus python3 -m adapters.agent_bus_client rpc --store /home/alexey/git/agent-bus/.local/bus_store --cred /home/alexey/.local/agent_bus_credentials/windows_desktop_worker.cred.json --stdin"
```

---

## 5. Physical Windows Execution Runbook (PowerShell)

### 5.1. Minimal Useful Handshake Payload
The payload exercises authentic agent communication without privileged credentials:

```powershell
$handshakePayload = @{
    method = "send"
    params = @{
        recipient_id = "6a24d8fc-93c7-40c8-8087-99d357f0c3d7"
        body = "AC-WIN-HETZ-001 Windows client physical handshake"
        data = @{
            status = "active"
            client_platform = "windows"
            timestamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
        }
        kind = "note"
        idempotency_key = "win-phys-handshake-20261006-001"
    }
} | ConvertTo-Json -Compress
```

### 5.2. Transmission via Typed Stdin RPC
Streams the JSON payload directly into the pinned remote SSH entrypoint, eliminating command-line quoting or truncation:

```powershell
$remoteEntrypoint = 'cd /home/alexey/git/agent-coordination && PYTHONPATH=/home/alexey/git/agent-coordination:/home/alexey/git/agent-bus python3 -m adapters.agent_bus_client rpc --store /home/alexey/git/agent-bus/.local/bus_store --cred /home/alexey/.local/agent_bus_credentials/windows_desktop_worker.cred.json --stdin'

$response = $handshakePayload | ssh hetzner-rmthz $remoteEntrypoint
Write-Output "Hetzner Response: $response"
```

### 5.3. Checking Recipient Inbox & Durable Cursor
Query the recipient inbox on Hetzner to verify message delivery and cursor state:

```powershell
$pollPayload = @{
    method = "poll"
    params = @{
        unread_only = $true
    }
} | ConvertTo-Json -Compress

$sinkEntrypoint = 'cd /home/alexey/git/agent-coordination && PYTHONPATH=/home/alexey/git/agent-coordination:/home/alexey/git/agent-bus python3 -m adapters.agent_bus_client rpc --store /home/alexey/git/agent-bus/.local/bus_store --cred /home/alexey/.local/agent_bus_credentials/coord_primary_sink.cred.json --stdin'

$unreadMessages = $pollPayload | ssh hetzner-rmthz $sinkEntrypoint
Write-Output "Sink Unread Messages: $unreadMessages"
```

---

## 6. Safety & Isolation Guarantees

1. **Anti-Spoofing & No Native Session Theft**:
   - `identity.session_id: None` (rendered canonically as `-` in store logs).
   - Windows desktop does not borrow or forge `windows-codex` or any aplexer session.
2. **Head Credential Protection**:
   - `reject_head_cred_inheritance` strictly rejects any payload containing `head.cred` or `head_token`.
3. **Cursor Isolation**:
   - Durable cursors are stored independently in `/home/alexey/git/agent-bus/.local/bus_store/cursors/`, partitioned by `(device_id, session_id)`.
   - Native aplexer mailboxes and old pending envelopes remain completely untouched.
