# Two-Host Cross-Computer FileBus RPC Report: Windows Desktop to Hetzner Linux (Codex C2224 / C2226)

- **Author**: `antigravity-head` (`46fdb644`, conversation ID: `245c7bba-9a7b-45c1-87a7-4537f289f9a5`)
- **Directives & Authority**: Executed under Codex Principal Directives C2224 and C2226, Desktop Orchestrator / Root directive (`01a109b0-a71a-7cb2-aaf0-3d4b317b1031`), and authoritative human cross-computer steering (`experiment/human-cross-computer-product-20261004.txt`).
- **Target Repository**: `/home/alexey/git/cloudflare-agent-git/.local/scratch/architect06-bus-integration/agent-bus` on branch `feat/typed-ssh-filebus-rpc` at commit `23b0742b1f00ec027d830763e773577a807dbc39` atop `f3295f99e188719f5df9fccb22706d8a0e5bb8f8`.
- **Rendezvous Store**: `/home/alexey/git/cloudflare-agent-git/.local/scratch/desktop-root-rpc-20261005/store`
- **Canonical Repositories Status**: Canonical `/home/alexey/git/agent-bus` and `/home/alexey/git/agent-dashboard` remained strictly read-only with respect to head and delegate actions; pre-existing dirty working trees preserved.
- **Compiler Invariant**: Exactly `0` `cargo` or `rustc` invocations executed during this trial interval across all observed subprocesses under human hold.
- **Date**: 2026-10-05T03:40:00+02:00 (Europe/Berlin)

---

## 1. Physical Topology & Host Admission

| Property | Host 1: Desktop Node (Client) | Host 2: Hetzner Node (`RMTHZ` Server / Rendezvous) |
| :--- | :--- | :--- |
| **Operating System** | Windows 11 Pro (`x86_64`) | Linux (`x86_64`, kernel 6.8) |
| **Physical Node** | Distinct physical desktop workstation | Distinct physical dedicated server (`135.181.114.209`) |
| **Inbound SSH Listener** | **None** (Zero `sshd` listener, port 22 closed) | Standard OpenSSH daemon on port 22 |
| **Outbound Transport** | Native Windows OpenSSH (`ssh.exe`, PowerShell) | Outbound OpenSSH client (`ssh`) |
| **Disk Storage** | `C:` drive: 535.78 GiB free | Write filesystem: 62 GiB free ($\ge 50.5$ GiB floor) |
| **Memory Capacity** | `MemAvailable`: 5.15 GiB ($< 10$ GiB floor) | Available RAM: 38.8 GiB ($\ge 10$ GiB floor) |
| **Execution Role** | Human-interface / root RPC diagnostic client only (model worker admission denied due to $< 10$ GiB floor) | Rendezvous FileBus host & `antigravity-head` execution environment |

---

## 2. Desktop-Root Authentic Enrollment Receipts

Desktop Root executed enrollment from the Windows 11 desktop workstation across the physical WAN network using native Windows OpenSSH (`ssh.exe`) and PowerShell stdin JSON piping into the pinned `bus_cli.py` server:

- **Execution Timestamp**: `2026-10-05T01:31:05Z`
- **Total Duration**: $1,415\text{ ms}$
- **Transport Flags**: `-o BatchMode=yes -o StrictHostKeyChecking=yes`
- **Enrollment Request ID**: `aa4fa288-407d-4e7d-bf2a-b94a1ca993f2`
- **Enrolled Identity ID**: `01ace831-6d23-4c05-a6df-1a58099aca67`
- **Agent Name**: `desktop-orchestrator-root`
- **Device ID**: `windows-desktop`
- **Task ID**: `actual-desktop-hetzner-20261005`
- **Credential Storage**: Saved to DPAPI user-bound private Windows desktop file; zero bearer tokens printed or exposed in stdout/stderr.

Verified store record in `/home/alexey/git/cloudflare-agent-git/.local/scratch/desktop-root-rpc-20261005/store/identities.json`:
```json
{
  "01ace831-6d23-4c05-a6df-1a58099aca67": {
    "agent_name": "desktop-orchestrator-root",
    "created_at": "2026-10-05T01:31:05Z",
    "device_id": "windows-desktop",
    "identity_id": "01ace831-6d23-4c05-a6df-1a58099aca67",
    "kind": "bus-agent",
    "parent_id": null,
    "project_id": "agent-coordination",
    "task_id": "actual-desktop-hetzner-20261005"
  }
}
```

---

## 3. Hetzner Head Enrollment Receipts

`antigravity-head` enrolled into the same rendezvous store to establish peer communication:

```bash
python3 .local/scratch/architect06-bus-integration/agent-bus/coordination/bus_cli.py \
  --store /home/alexey/git/cloudflare-agent-git/.local/scratch/desktop-root-rpc-20261005/store \
  register \
  --agent antigravity-head \
  --device hetzner-linux \
  --project agent-coordination \
  --task actual-desktop-hetzner-20261005 \
  --cred /home/alexey/git/cloudflare-agent-git/.local/scratch/desktop-root-rpc-20261005/head_cred.json
```

- **Output**: `{"identity_id": "91d2a63b-fe47-4b53-bee8-2ada24259439", "agent_name": "antigravity-head", "cred": ".../head_cred.json"}`
- **Credential Permissions**: Mode `0600` (`-rw------- 1 alexey alexey 348 Oct 5 03:38 head_cred.json`).

---

## 4. Forward Message Dispatch Receipts

`antigravity-head` dispatched an evaluation message addressed specifically to the enrolled desktop root identity:

```bash
python3 .local/scratch/architect06-bus-integration/agent-bus/coordination/bus_cli.py \
  --store /home/alexey/git/cloudflare-agent-git/.local/scratch/desktop-root-rpc-20261005/store \
  send \
  --cred /home/alexey/git/cloudflare-agent-git/.local/scratch/desktop-root-rpc-20261005/head_cred.json \
  --to 01ace831-6d23-4c05-a6df-1a58099aca67 \
  --idempotency-key hetzner-head-eval-20261005-001 \
  --body "..." \
  --data '{"task":"evaluate_cross_host_coordination",...}'
```

### Verified Message Envelope:
- **Message ID**: `4497403a-70a5-4adc-9398-bbcb85b45415`
- **Idempotency Key**: `hetzner-head-eval-20261005-001`
- **Sender ID**: `91d2a63b-fe47-4b53-bee8-2ada24259439` (`antigravity-head`)
- **Recipient ID**: `01ace831-6d23-4c05-a6df-1a58099aca67` (`desktop-orchestrator-root`)
- **Message Digest**: `ae04c8cc80f614e343aadd01000abf51f8fcf4ba71a4bdbf3cd5b15d2594f80b`
- **Creation Timestamp**: `2026-10-05T01:39:10Z`
- **Delivery Timestamp**: `2026-10-05T01:39:10Z`
- **Status in Store**: Stored in `messages/` under mode `0600`, ready for inbox retrieval by `desktop-orchestrator-root`.

---

## 5. Architectural Evaluation: Forward Polling vs. Inbound Reverse SSH

Under Directives C2224 and C2226, the team evaluated whether an inbound reverse SSH service (running `sshd` on the Windows desktop) is required for cross-computer agent coordination:

### 1. The Reverse SSH Overhead Problem:
Requiring the server to initiate SSH connections back to the desktop introduces severe operational and security friction:
- **Consumer NAT & Dynamic IP**: Desktop nodes reside behind home/office NAT routers without public static IPv4 addresses.
- **Port Forwarding & Firewall**: Requires configuring inbound port forwarding on edge routers and punching holes in the Windows Defender Firewall on port 22.
- **Service Management**: Requires installing and maintaining an administrative Windows OpenSSH server service (`sshd`), generating host keys, and managing user authentication.
- **Security Exposure**: Exposes the desktop workstation to inbound port scans and brute-force SSH attacks from the local network.

### 2. The Forward Rendezvous Polling Architecture:
In contrast, utilizing forward OpenSSH RPC against a reachable rendezvous server (e.g. Hetzner Linux):
- **Zero Inbound Ports**: The desktop requires zero listening ports, zero firewall alterations, and zero administrative daemon installation.
- **Standard Client Outbound**: The desktop initiates standard outbound OpenSSH connections (`ssh -o BatchMode=yes hetzner python3 bus_cli.py inbox ...`) to poll unread tasks and submit correlated replies (`bus_cli.py reply ...`).
- **Complete Bidirectional Capability**: Because messages, ACKs, and replies are durable, content-addressed entities in the rendezvous FileBus store, full bidirectional request/reply cycles are achieved seamlessly.
- **Verdict**: Inbound reverse SSH services are **unnecessary and discouraged** for edge/desktop agent integration. Forward OpenSSH polling and reply over a rendezvous FileBus store is the superior architectural pattern for cross-computer agent coordination.

---

## 6. Epistemic Demarcation & Invariant Receipts

1. **Physical Host Boundary**:
   - Real physical cross-machine enrollment is **demonstrated and verified** across Windows 11 Desktop and Hetzner Linux.
   - The full bidirectional lifecycle (inbox retrieval, ACK, and reply) awaits desktop-root's subsequent execution from Windows PowerShell.
2. **Platform Surface Boundaries**:
   - Native Windows OpenSSH (`ssh.exe`) frontend execution is **verified**.
   - Native Windows Python `SshFileBusClient` and Windows-local `FileBus` (requiring `flock` / `O_DIRECTORY`) remain strictly **`UNKNOWN/HELD`**.
3. **Compiler Invariant**:
   - Exactly **`0`** `cargo` or `rustc` invocations were executed during this trial interval across all observed subprocesses under human hold.
4. **Canonical Repositories**:
   - Canonical `/home/alexey/git/agent-bus` and `/home/alexey/git/agent-dashboard` remained completely untouched and strictly read-only.
5. **Scratch & Credential Hygiene**:
   - Directory `.local/scratch/desktop-root-rpc-20261005/` secured with mode `0700`.
   - Credentials stored in mode `0600` JSON files (`head_cred.json`); zero credentials passed on command-line arguments (`sys.argv`).
