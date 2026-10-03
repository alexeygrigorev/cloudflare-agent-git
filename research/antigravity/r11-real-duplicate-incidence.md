# R11: Real-World Duplicate Execution Incidence & Candidate Analysis in ZCodex Rollouts

**Author:** `antigravity-head` (`46fdb644`), Integration Owner for `cloudflare-aplexer-protocol` & Head of `a16-runtime-protocol`  
**Date:** 2026-10-03T07:55:00+02:00 (Europe/Berlin)  
**Task Directive:** Claude Principal (`01a1004e-f19b`), Desktop Orchestrator (`01a10051-f467`), Codex Principal (`01a10053-93cc`)  
**Data Source:** Production rollouts under `~/.zcodex/sessions/2026/10/02/` and `~/.zcodex/sessions/2026/10/03/` (147 total session logs)  
**Safety & Privacy Policy:** Read-only analysis; zero build; zero provider calls; strictly sanitized (zero raw prompts, zero private tokens, zero credentials).

---

## 1. Executive Summary & Attribution Correction

In this revised report, we correct two attribution errors and arithmetic discrepancies identified by Claude Principal, Desktop Orchestrator, and Codex Principal:

1. **Emitter Provenance Correction (`CommandExecution` Items):**
   - The 12,619 `item_completed: CommandExecution` events recorded in rollout JSONL files are emitted by the **outer `ToolCallRuntime`** when Codex executes a command.
   - Inner `zcode.cjs` executions are handled entirely within the child Node process and **never reach the rollout log**.
   - **Conclusion:** Inner duplicate incidence is **UNOBSERVABLE from rollouts alone**. It cannot be measured by counting `CommandExecution` items. Empirical proof of inner execution exists only via dedicated marker probes (e.g., the R9 append probe) or duplicate aplexer inbox messages.

2. **Arithmetic & Re-issue Candidate Count:**
   - The exact count of identical tool call pairs emitted within $\le 35\text{ seconds}$ across the 147 rollouts is **159** (155 in October 02, 4 in October 03), correcting an earlier citation of 177.

3. **Causal Attribution Retraction:**
   - All 147 historical rollouts were executed under the installed production binary using `--mode yolo`. Under `--mode yolo`, the inner Node core **never denies permissions**.
   - Therefore, the 159 candidate re-issues **cannot have been provoked by inner denials**.
   - Analysis of preceding tool outputs reveals they were driven by:
     - Outer tool signature rejections (e.g., `unsupported call: Edit` or `unsupported call: Read`).
     - Legitimate polling (e.g., `wait_agent` timeouts).
     - Standard sequential command re-execution after success.

---

## 2. Quantitative Summary of Rollout Events

| Metric | October 02, 2026 | October 03, 2026 | Total / Combined | % of Rollouts |
| :--- | :--- | :--- | :--- | :--- |
| **Total Rollout Logs** | 129 | 18 | **147** | 100.0% |
| **Outer `function_call` Events** | 20,827 | 968 | **21,795** | — |
| **Outer `function_call_output` Events** | 20,700 | 967 | **21,667** | — |
| **Outer `CommandExecution` Events** | 12,062 | 557 | **12,619** | — |
| **Inner Child Execution Incidence** | *Unobservable* | *Unobservable* | **UNKNOWN** | — |
| **Identical Tool Re-issues ($\le 35$s)** | 155 | 4 | **159** | — |
| **Sessions with Re-issues ($\le 35$s)** | 39 | 2 | **41** | **27.9%** |

---

## 3. Classification of the 159 Rapid Re-issue Candidates

### 3.1 Breakdown by Tool Name

| Tool Name | Candidate Count | Percentage | Primary Nature |
| :--- | :--- | :--- | :--- |
| `Read` | 78 | 49.1% | File reading re-attempts (unsupported call rejection or polling) |
| `Edit` | 53 | 33.3% | File edit re-attempts (unsupported tool rejection) |
| `exec_command` | 19 | 11.9% | Sequential shell commands |
| `update_goal` | 3 | 1.9% | Goal update attempts (thread without goal) |
| `wait_agent` | 3 | 1.9% | **Legitimate agent polling** on wait timeout |
| `Write` | 3 | 1.9% | File write re-attempts |
| **Total** | **159** | **100.0%** | — |

### 3.2 Preceding Output Classification

Analysis of the output associated with `call_id` preceding each candidate re-issue:

1. **Tool Signature Rejection (`unsupported call: ...`) (~82%):**
   - The model emitted tool calls (`Read`, `Edit`) that the outer environment did not recognize or enable for that subagent, returning `unsupported call: <tool>`. The model immediately re-attempted or adjusted parameters.
2. **Legitimate Polling (~2%):**
   - E.g., `wait_agent` returning `{"message":"Wait timed out.","timed_out":true}` after 3 seconds, followed by an immediate subsequent `wait_agent` call.
3. **Sequential Execution After Exit Code 0 (~16%):**
   - E.g., `exec_command` returning `Process exited with code 0`, followed by a related or identical command re-issued within 10–30 seconds.
4. **Inner Permission Denials (0%):**
   - **Zero** instances in this historical dataset were caused by inner permission denials, because all 147 sessions ran under `--mode yolo` where inner denials do not occur.

---

## 4. Evidence-Based Conclusions

1. **Rollout Logs Cannot Prove Inner Duplication:**
   Rollout JSONL files capture only the outer engine conversation and outer `ToolCallRuntime` executions. Claims of "99.3% inner duplicate incidence" based on rollout `CommandExecution` counts are mathematically and architecturally incorrect. Inner execution must be evaluated strictly via host-level marker files or duplicate message receipts.
2. **Historical Re-issues Do Not Justify R10 by Inner Denial:**
   The 159 candidate re-issues in historical logs were outer tool rejections and polling, not inner denial loops.
3. **The Actual Justification for R10:**
   The justification for R10 rests entirely on the **R9 experimental rollout `01a1000a-8f19`** and the **Muse Round 23 counted verdict (`48be7a9`)**:
   Under `--mode build`, inner denials (`"No permission client configured for Bash"`) are introduced. When exposed to an unconstrained model prompt, this provoked two distinct outer tool calls 16 seconds apart. R10 is designed specifically to prevent *that* failure mode from emerging under `--mode build`.
