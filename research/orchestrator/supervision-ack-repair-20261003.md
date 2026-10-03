# Supervision ACK reconciliation — 3 October 2026

The supervisor retained an old pending request after its sender session changed. The recipient had already acknowledged that exact request in native aplexer consumer state. The current supervisor could not safely deliver a predecessor's message, and an empty recipient inbox alone would not prove acknowledgment.

The repair reads the existing native mailbox under its nonblocking shared mailbox lock. It checks workspace metadata, the retained envelope's original sender, resolved recipient and tag, and the recipient's **exact** acknowledged message ID. It records hashes of the envelope and cursor. Missing, pruned, malformed, oversized, locked or inconsistent evidence remains unresolved; a legacy high-water value alone is insufficient. The helper never sends an ACK, changes a cursor, impersonates a sender or delivers a predecessor's envelope.

All 35 supervision and retention tests passed, including 13 new cases covering changed supervisor identity, genuinely unacknowledged messages, wrong sender/recipient/workspace, legacy-only evidence, missing files, symlinks, oversized/malformed files, contention and unchanged native file contents. The desktop orchestrator independently reran the suite.

At the owned graceful service checkpoint, the old process exited before replacement. The replacement verified its genuine experiment-supervision identity and retained the previously approved immutable installed CLI digest. Its first real polling cycle reconciled the old request from persisted exact native ACK evidence and preserved that request and its provenance in last_request. A separate new task-revision request remained pending; reconciliation does not imply task agreement or completion. Principals were busy, so this recovery did not inject input into their panes. Private evidence and archives remain private and preserved.

This repairs a stale bookkeeping blocker. It does not establish unattended progress across every team, safe readiness for every engine, or a cross-host transport guarantee.
