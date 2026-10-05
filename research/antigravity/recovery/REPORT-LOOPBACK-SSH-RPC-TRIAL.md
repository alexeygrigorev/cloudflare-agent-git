# REPORT: Loopback OpenSSH FileBus RPC Integration Trial (C2214 / C2217)

- **Author / Parent**: `antigravity-head` (aplexer session `46fdb644-9b58-4e2f-aab3-9be5e1e33337`, conversation ID `245c7bba-9a7b-45c1-87a7-4537f289f9a5`)
- **Executor**: `architect06` (`06ecf158-e51f-411c-89b8-083fc9fb3dd6`)
- **Directives**: Codex Principal Directives C2166, C2196, C2201, C2214, C2217; human steering (`experiment/human-cross-computer-product-20261004.txt`)
- **Software Sibling Pin**: Commit `23b0742b1f00ec027d830763e773577a807dbc39` atop `f3295f99` (`feat/typed-ssh-filebus-rpc`)
- **Date**: 2026-10-05T03:17:00+02:00 (Europe/Berlin)
- **Status**: **SELF-HOST OPENSSH RPC LIFECYCLE VERIFIED; DISTINCT TWO-PHYSICAL-MACHINE EXECUTION UNKNOWN/HELD**
- **Compiler Invariant**: Exactly 0 cargo / rustc invocations executed in this trial interval and environment under human hold

---

## 1. Executive Summary & Verification Scope

Under Codex Principal Directives C2214 and C2217, the default OpenSSH subprocess runner in `SshFileBusClient` was empirically tested through a complete multi-agent communication lifecycle using the verified sibling implementation commit `23b0742b1f00ec027d830763e773577a807dbc39`.

### Key Outcomes:
1. **Default OpenSSH Subprocess Runner Verified**:
   - `SshFileBusClient` executed all commands through the default OpenSSH runner invoking `ssh -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=5 hetzner "python3 <bus_cli> --store <store> rpc"`.
   - No mock or in-memory runner replacements were utilized.
2. **Secret Stdin Piping & Command Hygiene**:
   - Credentials, tokens, request envelopes (`RpcRequest`), and message payloads were piped strictly via stdin JSON streams.
   - Command-line arguments (`sys.argv`) contained zero secrets or user message payloads.
3. **Multi-Agent Lifecycle Executed**:
   - Full 8-step lifecycle (enroll Alice -> enroll Bob -> send message -> inbox read -> acknowledge -> verify empty unread inbox -> reply -> verify correlated reply) passed with 100% assertion success in **3.019 seconds**.
4. **Physical Topology & Epistemic Demarcation**:
   - The SSH alias `hetzner` connects to a self-host OpenSSH endpoint on the local host `RMTHZ`.
   - True distinct two-physical-machine cross-network execution remains designated **`UNKNOWN/HELD`** pending reverse desktop SSH endpoint inputs.

---

## 2. OpenSSH Invocation & Command Construction

Each operation performed by `SshFileBusClient` constructs a hardened OpenSSH command line:

```text
ssh \
  -o BatchMode=yes \
  -o StrictHostKeyChecking=yes \
  -o ConnectTimeout=5 \
  -- \
  hetzner \
  'python3 /home/alexey/git/cloudflare-agent-git/.local/scratch/architect06-bus-integration/agent-bus/coordination/bus_cli.py --store /home/alexey/git/cloudflare-agent-git/.local/scratch/loopback-ssh-trial/store rpc'
```

### Security Properties Verified:
- **`--` Delimiter**: Placed immediately prior to the destination host operand to defeat destination option injection.
- **Mandatory Policy Flags**: Enforces `-o BatchMode=yes` and `-o StrictHostKeyChecking=yes`.
- **Zero Command-Line Secret Leakage**: Stdin streams JSON payloads:
  `{"op": "<operation>", "request_id": "<uuid>", "params": {...}}`
- **Decoupled Exception Chaining**: All internal transport exceptions suppress `__cause__` and `__context__` via `raise ... from None`.

---

## 3. Empirical Test Execution Receipts

- **Test Script**: `.local/scratch/architect06-bus-integration/verify_loopback_ssh_rpc.py`
- **Store Directory**: `.local/scratch/loopback-ssh-trial/store/` (mode `0700`)
- **Execution Log**:

```text
======================================================================
STARTING LOOPBACK SSH FILEBUS RPC INTEGRATION TRIAL (C2214)
======================================================================

[Step 1] Enrolling Alice over loopback SSH RPC...
  [OK] Enrolled Alice: id=7141c340-2319-47a1-a90f-1811bbc69990 in 0.434s

[Step 2] Enrolling Bob over loopback SSH RPC...
  [OK] Enrolled Bob: id=34192145-81ac-4896-9f2c-22fa6df5f891 in 0.396s

[Step 3] Sending message Alice -> Bob over loopback SSH RPC...
  [OK] Sent message: msg_id=81068d4e-f5d5-4c7b-b657-70f3d6e6d561 in 0.396s

[Step 4] Bob reading unread inbox over loopback SSH RPC...
  [OK] Bob retrieved message: "Hello Bob from Alice over loopback SSH FileBus RPC" in 0.329s

[Step 5] Bob acknowledging message over loopback SSH RPC...
  [OK] Bob acknowledged message: acked_at=2026-10-05T01:16:47Z in 0.362s
  [OK] Verified Bob unread inbox is empty after ACK

[Step 7] Bob replying to Alice over loopback SSH RPC...
  [OK] Bob replied: reply_id=af7c22f6-3450-4369-8f93-2a33aad69ef3 in 0.406s

[Step 8] Alice verifying reply in inbox over loopback SSH RPC...
  [OK] Alice verified reply: "Handshake acknowledged and verified by Bob over loopback SSH FileBus RPC" in 0.346s

======================================================================
ALL LOOPBACK SSH FILEBUS RPC CHECKS PASSED in 3.019s
======================================================================
```

---

## 4. Latency & Timing Breakdown

| Operation | Protocol Op | Transport | Latency | Result |
|---|---|---|---|---|
| Enroll Alice | `enroll` | OpenSSH (`hetzner`) | 0.434s | `id=7141c340...` |
| Enroll Bob | `enroll` | OpenSSH (`hetzner`) | 0.396s | `id=34192145...` |
| Send Message | `send` | OpenSSH (`hetzner`) | 0.396s | `msg_id=81068d4e...` |
| Inbox Query | `inbox` | OpenSSH (`hetzner`) | 0.329s | 1 message retrieved |
| Acknowledge | `ack` | OpenSSH (`hetzner`) | 0.362s | `acked_at: 2026-10-05T01:16:47Z` |
| Inbox Verification | `inbox` | OpenSSH (`hetzner`) | 0.350s* | 0 unread messages |
| Correlated Reply | `reply` | OpenSSH (`hetzner`) | 0.406s | `reply_id=af7c22f6...` |
| Inbox Verification | `inbox` | OpenSSH (`hetzner`) | 0.346s | Reply verified |
| **Total Cycle** | 8 RPC calls | OpenSSH (`hetzner`) | **3.019s** | **100% PASS** |

*\*Note on Step 6 Timing (per C2230/C2236 audit)*: Unlike the other 7 operations which recorded discrete `time.monotonic()` deltas, Step 6 ("Inbox Verification") did not measure an isolated delta in `verify_loopback_ssh_rpc.py`. The reported latency of `0.350s` represents an **inferred residual duration** ($3.019\text{s} - 2.669\text{s} = 0.350\text{s}$) capturing Step 6 execution along with subprocess cleanup, garbage collection, and script teardown overhead. Individual step inbox latency was not discretely isolated for Step 6.

---

## 5. Epistemic Demarcation & Input Requests

1. **Topology Classification**:
   - The test demonstrated verified OpenSSH command serialization, argument validation, stdin streaming, and fail-closed parsing against a live OpenSSH daemon.
   - Because `hetzner` connects to the local host `RMTHZ`, this evidence proves **self-host OpenSSH transport integration**.
   - Distinct two-physical-machine cross-network execution across separate physical hosts remains designated **`UNKNOWN/HELD`**.
2. **Reverse Desktop Host Input Request**:
   - To advance to true cross-computer execution across distinct physical machines, an authorized reverse endpoint or SSH configuration for the desktop node is required as an **input dependency** from `desktop-orchestrator` / root.
   - This request does not seek permission or approval for authorized product scope; it identifies physical network connectivity inputs required to execute multi-machine trials.
3. **Windows Platform Surface**:
   - Windows execution (`cmd.exe`/`powershell.exe`) remains strictly designated **`UNKNOWN/HELD`** pending authentic native Windows platform availability.
4. **Invariant Compliance**:
   - Exactly **0** `cargo` / `rustc` invocations executed in this trial interval and environment under human hold.
   - Scratch usage confined to `.local/scratch/` (size < 5 MB $\le$ 512 MB, zero net `/tmp` growth).
   - Canonical workspace `/home/alexey/git/agent-bus` remained strictly read-only.
