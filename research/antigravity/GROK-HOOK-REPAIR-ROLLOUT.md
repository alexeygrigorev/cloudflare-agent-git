# Grok-Head Hook Repair Rollout & Verification Plan

- **Author:** `antigravity-head` (`46fdb644`), Head of `a16-runtime-protocol`
- **Date:** 2026-10-03 11:05 UTC
- **Directives Addressed:**
  - Claude Principal (`01a1016e-132c-7ab1-b8f5-a7c7e9c539dc`, `01a1016e-c243-77b2-9942-c1183a81a5f7`)
  - Codex Principal C-1262, C-1263, C-1264 (`01a1016e-294c-7391-b05a-d92513d148c7`)
- **Base Proposal:** [`research/claude/grok-hook-repair-proposal.md`](file:///home/alexey/git/cloudflare-agent-git/research/claude/grok-hook-repair-proposal.md) (commit `166777f`)
- **Target Session:** `grok-head` (`d85e5cd8-c283-40c8-9e3c-ca745aec4710`, engine: `grok`)
- **Rollback File:** `~/.grok/hooks/aplexer.json.bak-20261003`

---

## 1. Pinned Binary & Target Hook Specification

### Pinned Binary Identity
- **Absolute Path:** `/home/alexey/git/cloudflare-agent-git/.local/supervision/bin/aplexer-installed`
- **SHA256:** `8d49a216d43c70843bc07705f4c11eb13f3eb51646d5c6fc204ce0796ce618c4`
- **File Mode:** `0500` (`-r-x------`, read & execute by owner `alexey` only)
- **Status:** Existing private immutable copy of the installed release CLI. Completely immune to `cargo build` / `cargo clean` drift in `cloudflare-aplexer-protocol`.

### Invariant & Operational Rule: No `a init`
> [!CAUTION]
> **NOBODY RUNS `a init` OR `a init --engine grok` FROM INSTALLED `8d49a216`!**  
> Empirical testing in proposal §3.3 proved that `8d49a216`'s built-in `GROK_EVENTS` table predates the upstream fix (`36829c4`), so running `a init` from it would rewrite the grok file back to the broken five-event table (`Notification -> waiting`).

---

## 2. Bounded Tradeoff & Negative Gate Analysis

- **Upstream Intent:** Exclude `Notification` entirely from Grok's hook table (src/hooks/mod.rs:150-158) to eliminate the 60-second `idle_prompt` heartbeat poisoning the authentic `idle` state.
- **Bounded Tradeoff:** Without `Notification`, Grok loses automated reporting of `waiting` during interactive permission prompts.
- **Negative Gate Requirement:**
  A permission prompt, active new turn, or running child process must NOT be falsely classified as deliverable `idle`. The receiver delivery classifier (`aplexer message deliver`) and runner composer classifier must continue enforcing active child process checks and non-empty composer checks before allowing message injection.

---

## 3. Exact Diff & Checksum Verification

### Checksum Ledger
- **Original File:** `~/.grok/hooks/aplexer.json`
  - SHA256: `df3d7ce9d8d82535fbc5814494f9e299d5680d89ae37af41003eb9a9e69fbd3b`
  - Size: 1,337 bytes
- **Target File:**
  - SHA256: `0419c4c6b744b55ed9ad553ac21aab26dbefe52e66274ddd3971d2a72421034d`
  - Size: 1,140 bytes

### Unified Diff vs Installed (`df3d7ce9`)
```diff
--- ~/.grok/hooks/aplexer.json (df3d7ce9...)
+++ ~/.grok/hooks/aplexer.json (target 0419c4c6...)
@@ -1,20 +1,10 @@
 {
   "hooks": {
-    "Notification": [
-      {
-        "hooks": [
-          {
-            "command": "/home/alexey/git/cloudflare-aplexer-protocol/target/debug/aplexer state-report waiting || true",
-            "type": "command"
-          }
-        ]
-      }
-    ],
     "PostToolUse": [
       {
         "hooks": [
           {
-            "command": "/home/alexey/git/cloudflare-aplexer-protocol/target/debug/aplexer context hook --engine grok 2>/dev/null || true # aplexer-managed-awareness-hook-v1",
+            "command": "/home/alexey/git/cloudflare-agent-git/.local/supervision/bin/aplexer-installed context hook --engine grok 2>/dev/null || true # aplexer-managed-awareness-hook-v1",
             "timeout": 5,
             "type": "command"
           }
@@ -25,7 +15,7 @@
       {
         "hooks": [
           {
-            "command": "/home/alexey/git/cloudflare-aplexer-protocol/target/debug/aplexer state-report working || true",
+            "command": "/home/alexey/git/cloudflare-agent-git/.local/supervision/bin/aplexer-installed state-report working || true",
             "type": "command"
           }
         ]
@@ -35,7 +25,7 @@
       {
         "hooks": [
           {
-            "command": "/home/alexey/git/cloudflare-aplexer-protocol/target/debug/aplexer state-report idle || true",
+            "command": "/home/alexey/git/cloudflare-agent-git/.local/supervision/bin/aplexer-installed state-report idle || true",
             "type": "command"
           }
         ]
@@ -45,7 +35,7 @@
       {
         "hooks": [
           {
-            "command": "/home/alexey/git/cloudflare-aplexer-protocol/target/debug/aplexer state-report working || true",
+            "command": "/home/alexey/git/cloudflare-agent-git/.local/supervision/bin/aplexer-installed state-report working || true",
             "type": "command"
           }
         ]
```

---

## 4. Atomic Rollout & Mid-Session Reload Protocol

1. **Private Backup:**
   ```bash
   cp -p ~/.grok/hooks/aplexer.json ~/.grok/hooks/aplexer.json.bak-20261003
   chmod 0600 ~/.grok/hooks/aplexer.json.bak-20261003
   ```
2. **Atomic Write:**
   Write target content (`0419c4c6...`) to `~/.grok/hooks/aplexer.json.tmp`, verify sha256 matches `0419c4c6b744b55ed9ad553ac21aab26dbefe52e66274ddd3971d2a72421034d`, and `mv` atomically to `~/.grok/hooks/aplexer.json`.
3. **Mid-Session Hook Reload (Grok User Guide 10-hooks.md §580/612):**
   - Verify `grok-head` is at resting idle twice (empty composer, no active child processes).
   - In Grok TUI, trigger hotkey reload (`r` in Hooks tab) via aplexer UI attach/keystroke boundary.
   - Zero model prompting, zero shell command injection into the pane, zero manual idle state forging.
   - Preserves conversation `d85e5cd8-c283-40c8-9e3c-ca745aec4710`.
4. **Verification & Proof of Recovery:**
   - Verify loaded hook table shows `Notification` absent.
   - **Recovery Proof Gate:** Deliver queued message `01a10140-b223-7673-8b0a-101f824d27c0` via native aplexer delivery.
   - Gate passes ONLY when:
     1. Delivery exits `0`.
     2. `grok-head` processes message, sends an authentic ACK via aplexer, and executes its first useful tool action.
     3. `Stop` hook fires and settles cleanly into `reported_state: "idle"` without subsequent expiration into `waiting`.
