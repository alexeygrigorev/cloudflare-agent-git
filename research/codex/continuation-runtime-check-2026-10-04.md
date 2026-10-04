# Head continuation and bounded runtime recovery

## Two independently observed callback cycles

Ant scheduled native callbacks rather than a headless principal loop. Principal independently inspected bounded metadata from the head's private native transcript, without exporting message bodies or credentials:

| Callback | Native SYSTEM event created | Following actual tools |
|---|---|---|
| task35367 | 2026-10-04T04:49:53Z, step35401 | run_command35402/35405/35408 read the native inbox |
| task35459 | 2026-10-04T04:53:06Z, step35511 | run_command35512/35515/35518/35521 |

These establish two scheduled callback-to-tool cycles in this head. They do not repair every engine's prompt readiness or establish uninterrupted productive work. Earlier idle misses remain in coordination history. Head reports another callback35588 and rearmed35772; those additional events have not been independently inspected here.

A second genuine safe idle delivery of existing C1677 occurred after two empty captures and native idle. Submission briefly appeared as pasted text; principal did not press Enter or retry. The head then natively acknowledged, read the report and fetched the primary article. Corrected A07 evidence was published as [b053c2d](https://github.com/alexeygrigorev/cloudflare-agent-git/commit/b053c2d).

## Virtual memory failure and a tested mitigation

ZCode observed Node24.13.1 native fetch failing to allocate WebAssembly memory under virtual-address limit1500000 KiB. [Node's official documentation](https://nodejs.org/download/release/v24.15.0/docs/api/cli.html#--disable-wasm-trap-handler) explains large virtual reservations for WebAssembly trap-handler bounds checks and documents a flag that instead uses inline checks. This is a performance tradeoff, not permission to exceed physical RAM budgets.

Ant reported a bounded empirical comparison on the installed version with the same virtual limit: unflagged allocation exited1, flagged allocation exited0; a local native-fetch probe returned200. Reported peak RSS was59516 KiB. These are head test results; principal did not execute an implementation harness. The complete live Git/SDK workflow remains a separate gate.

Principal independently read the worker's PID files and process cgroups: sidecar3630847 and coordinator3759540 both belonged to the genuine4abc workload scope, whose `memory.max` was1572864000 bytes. This is **1500 MiB shared total**, including the backend, not1500 MiB per process. This snapshot verifies that the worker's removed-virtual-limit variant remained inside the physical cap at inspection time; it does not certify later processes or the entire host.

## Forensic scope and next owner

The audit in [1c7c905](https://github.com/alexeygrigorev/cloudflare-agent-git/blob/1c7c905/research/antigravity/audit/INVOCATION-LINEAGE-RETRY-DIAGNOSTIC.md) explains the duplicate trace through two logging statements and contrasts a reported repository409 with recorded201. Principal required narrowing claims: a repeatable substitution does not identify its second invocation or exclude all outer retries. The second insertion toolcall/payload remains unknown; older incidents require separate evidence.

Ant owns callback rearming, resource admission and replenishment. ZCode owns its current live-stack checkpoint and the queued CLI credential task; a genuinely separate reviewer owns the ensuing source/HTTP checks. A real consumer/integration job with an ordinary Git fallback is requested through the head, not yet claimed as running. Final shortlist consensus and deployment remain held.
