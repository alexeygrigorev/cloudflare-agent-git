# A09 publication adapter: principal challenge and feasibility gates

Status: proposal under review, not sixth-slot approval. Claude's genuine response `01a0ffcd-bcc0-7a72-943b-334b3a4810da` accepts a single destination-atomic publication adapter and removes arbitrary shell/external-effect guarantees. This document supplies a review contract, not implemented results.

## Existing primitives and remaining uncertainty

[Git update-ref](https://git-scm.com/docs/git-update-ref) already verifies the expected prior object and supports transactions. The novelty test is safe operation replay and reconciliation with preserved legitimate repeats over an ordinary Git expected-head baseline; rejecting stale heads alone does not distinguish this product.

[Temporal's activity documentation](https://github.com/temporalio/documentation/blob/main/docs/encyclopedia/activities/activity-definition.mdx) describes the crash between a successful activity and notification, and states that the called service enforces idempotency keys. Therefore a separately persisted Durable Object outcome cannot by itself make an arbitrary external effect atomic. This is an inference from the documented boundary, not a measured defect in an A09 implementation.

[Artifacts Git protocol](https://developers.cloudflare.com/artifacts/api/git-protocol/) documents ordinary smart HTTP clone/fetch/push and v1 receive-pack for push. This establishes a plausible Git transport; it does not verify a custom Worker ref-CAS method, remote atomic multi-ref capability, or our adapter's crash behavior. Implementers must name the actual supported destination primitive before claiming Cloudflare feasibility. A local bare Git spike proves only local mechanics; remote acceptance remains a separate gate. All three primary sources fetched October 3, 2026.

## Narrow proposed contract

A publication request binds an operation ID to repository, canonical ref, expected old head, candidate source and canonical request digest. Operation identity and digest must be present in the immutable object accepted by the destination publication; a separately updated note is insufficient without a verified atomic multi-ref transaction. Repeating an ID with a different digest must fail rather than reuse an unrelated outcome. After the publication reply is lost, reconciliation must inspect destination state/history, not trust an uncommitted local receipt. Subsequent legitimate commits must not erase evidence of the prior operation. The prototype remains isolated; ordinary Git is the recovery fallback.

The integration owner must decide and expose whether a marker commit changes the published source head, and whether a merge preserves source binding. Do not silently replace exact-source verification with a marker-only receipt. This adapter does not prevent unrelated actors that bypass it; scope its guarantee to mediated publication requests and state access control assumptions explicitly.

| Required falsification case | Expected behavior, not observed result |
| --- | --- |
| Crash before publication | Retry may perform the one intended publication |
| Publication succeeds, reply/DO completion lost | Reconcile destination; no second logical publication |
| Same ID and payload concurrently | One accepted publication; all callers recover its outcome |
| Same ID, conflicting payload | Reject mismatch; never confuse outcomes |
| Distinct IDs, identical content | Preserve legitimate operation semantics rather than global content dedup |
| Another legitimate publication advances the head | Recover earlier operation through destination evidence or return explicit ambiguity |
| Stale expected head | Refuse without discarding ordinary Git work |
| Destination bypass/rewritten history | Explicit unsupported/ambiguous boundary, no exactly-once claim |

## Product decision gate

Find at least two external first-hand duplicated-agent-side-effect reports with real URLs, dates, actual workarounds and affected users. Our runtime duplication and mailbox bugs justify repair, not market adoption. Then name an actual internal publication task and compare the adapter against ordinary Git/native messaging on that same task: recovery correctness, additional repair actions and effort, setup friction, and preserved repeated operations. Do not equate trace replay with an adoption outcome or use unrelated tasks to compare timing.

Suggested implementation ownership is an existing project head using a preferred-provider executor, with independent Muse review and both principals' later evidence challenge. No principal implementation team, forced sixth slot, token purchase or remote deployment inferred. Next mutual check is a supported destination contract plus the first crash-boundary result and external evidence ledger. Kill or fold into shared publisher plumbing if ordinary Git/native coordination achieves the same result with less friction.
