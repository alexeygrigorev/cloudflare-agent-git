# Inotify Resource Diagnosis & Bounded Holder Analysis (C-1144)

- **Timestamp:** 2026-10-03 09:41:00 UTC
- **Host System Limit:** `/proc/sys/fs/inotify/max_user_instances` = 128
- **Current Total User Inotify Instances:** 125 / 128 (97.7% saturation)
- **Observed Symptom:** `aplexer message wait --timeout 30` exits 1 with `create mailbox watch Too many open files (os error 24)` (`EMFILE`).
- **Standard Inbox Status:** Polling fallback (`aplexer message inbox`) uses ordinary directory/file reads without inotify, and continues functioning normally.

---

## 1. Distribution of Inotify File Descriptors by Process Category

| Category | Process Command / Binary | Approx. Processes | Instances Each | Subtotal Instances |
|---|---|---|---|---|
| **Antigravity CLI** | `agy` (antigravity-head PID 560857, public-journal-site PID 2807007) | 2 | 7 | 14 |
| **ZCodex / z.ai** | `zcodex` (PIDs 1126222, 1276412, 1293050, 1667913, 2021902, 2224513, 2309373, 2592137, 2775643, 2805504, 3204742, 3836235, 4090369) | 13 | 1–2 | ~24 |
| **OpenAI Codex** | `codex` musl binaries / app-server daemon (PIDs 86249, 316048, 495949, 1801181, 2450657, 2729786, 2988922, 3182821, 3277101, 3689905, 3709598, 3924122, 3974734) | 13 | 2–3 | ~32 |
| **Grok** | `grok` (PIDs 1032321, 1359382, 1795016) | 3 | 3 | 9 |
| **OpenCode** | `opencode` (PIDs 1036995, 3299323, 3551342) | 3 | 2–3 | 8 |
| **Claude Code** | `claude` (PIDs 1395685, 1741398, 2758199) | 3 | 2 | 6 |
| **Background / External** | tsx / vite dev-server (dataops), openclaw gateway, dbus-daemon, adb, gvfsd | ~10 | 1–2 | ~15 |
| **Total** | | | | **125** |

---

## 2. Root Cause Analysis

1. Each CLI harness (Codex, ZCodex, OpenCode, Claude, Grok, AGY) initializes between 2 and 7 inotify instances for file watching, workspace change detection, or IPC sockets upon boot.
2. Across multiple autonomous recovery sessions and background delegate processes, 30+ separate AI CLI processes remain running simultaneously in the user session.
3. Because Linux sets `fs.inotify.max_user_instances = 128` per UID by default, the aggregate count reached 125.
4. Any new process attempting to call `inotify_init1()` (such as `aplexer message wait` when creating a mailbox inotify watcher) exceeds the 128 instance cap and fails immediately with `os error 24 (EMFILE)`.

---

## 3. Recommended Non-Destructive Resolution Protocol

Per Codex C-1144 directives (no global sysctl mutation, no indiscriminate process killing, no worktree deletion):
1. **Durable Inbox Fallback:** All heads and executors should rely on lightweight polling `aplexer message inbox` at natural boundaries rather than spawning `aplexer message wait` watches until instance headroom is restored.
2. **Lifecycle Reclamation of Completed Executors:**
   - Coordinate with project heads to gracefully terminate completed delegate sessions whose turns have finished and whose artifacts are committed.
   - For example, retired zcodex and codex test sessions from earlier rounds that are no longer active can be exited cleanly via their respective parent sessions.
   - Reclaiming even 10 completed executor processes will release 20–30 inotify instances, dropping total usage to <95 / 128.
