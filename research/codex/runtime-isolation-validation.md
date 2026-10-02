# A14 resource-binding comparison: mechanism reproduced, no product advantage

2026-10-02, interactive continuation. Source: [fixture](runtime-isolation-fixture.py), [recorded measurements](runtime-isolation-measurements.json). Standard-library Python, local HTTP and SQLite only; no installation, Cloudflare call, Git branch integration or coding-agent run. MIT source under this repository's license.

Run from the repository: `timeout 30s python3 -B research/codex/runtime-isolation-fixture.py`. The command prints sanitized JSON. It creates disposable SQLite files, starts loopback-only servers on automatically assigned ports, stops its own children and removes its scratch directory. Its cap is 8 MiB, below the 512 MiB policy; it checks the 8 GiB free floor on both the repository and scratch filesystems. These are different mounts here. Recorded allocated regular-file blocks before cleanup: 86,016 bytes. Free-space changes include unrelated host activity and are not a storage-saving estimate.

## Controlled comparison

Both servers execute the same handler. Task A writes `value-A`, then task B writes `value-B` at the same logical row ID. Both processes remain live; requests are deliberately ordered, not simultaneous or randomized. Separate resource bindings are the only changed variable.

| Arm | Task A's subsequent read | Task B's subsequent read | Interpretation |
|---|---|---|---|
| Independent fresh-data checks | value-A | value-B | Both pass when tested alone |
| Two live runtimes, shared database | value-B | value-B | A observes B's write |
| Explicit separate task databases | value-A | value-B | Isolation mechanism works |
| Ordinary separate-resource control | value-A | value-B | Same result without a new platform |

This reproduces a configuration hazard that fresh isolated tests miss. It does not establish that merged-tree tests cannot detect it: a test using the real binding configuration can. The proposed arm and ordinary control intentionally use identical isolation mechanics. There is no measured adoption, orchestration or review advantage. Returned task/resource labels are handler-supplied diagnostics, not independently attested deployment identities. Same-user processes can access these files; this is not a hostile-code security boundary. No provision/cleanup latency or managed-service semantics were measured.

## Stronger existing baseline, independently opened

E-X023: [Workers Previews resources](https://developers.cloudflare.com/workers/previews/resources/), updated September22, documents automatic per-Preview Durable Object and Container isolation. D1/KV isolate through distinct resource bindings. [Workflow comparison](https://developers.cloudflare.com/workers/previews/compare-workflows/) distinguishes full Previews from Version URLs, which use production resources. Our earlier generic use of “preview” obscured that distinction.

[Previews overview](https://developers.cloudflare.com/workers/previews/) documents branch commands, fixed deployment URLs, public-by-default access and deletion. These are incumbent capabilities, not implementations verified on this host. Agent/task-to-source attestation, data provisioning and feedback automation could still matter, but must beat this baseline.

Verdict: A14 no longer deserves priority merely for resource isolation. Retain its unapproved slot for a focused falsification test; recommend folding it into A01 verification unless actual agent workflow advantages emerge. Do not automatically replace it with A12/A18. First next experiment is A01 live uptake, after genuine session binding; remote A14 comparison uses Workers Previews, not deliberately misconfigured Version URLs.
