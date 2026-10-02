# Protocol Repair: Native Ergonomics & Cross-Host Design

## 1. Challenge & Critique
The initial orchestrator script (`orchestrator-channel.py`) faced a critical issue: a crash between sending an aplexer message and recording the receipt caused duplicate messages and un-correlated responses. Instead of building a full new broker, we challenged the requirements to leverage aplexer's native durable message primitives over existing SSH channels.

## 2. Implemented Approach: Idempotency Keys
We have introduced native idempotency tracking directly into `aplexer message send` and `aplexer message reply`:
- Messages can now carry an `--idempotency-key <KEY>`.
- The idempotency key is durably stored in the `MessageEnvelope` schema.
- Before writing a new message, `aplexer` checks the target inbox for an existing message with the same idempotency key from the same sender workflow.
- If a duplicate is found, the CLI returns successfully with the JSON of the existing envelope instead of writing a new one.

This seamlessly closes the crash-after-send window for the desktop orchestrator without introducing any long-running daemon processes or network daemons. The desktop can simply run:
`ssh hetzner aplexer message send --workspace ... --idempotency-key <req-id> ...`
And it is guaranteed to either send once or return the existing sent envelope on a retry.

## 3. Logs & Headless Visibility
To solve the "blank sessions" issue for orchestrators, the experiment launchers were already corrected to use `tee` for logs. The aplexer repair branch is now focusing strictly on robust durable coordination via the implemented idempotency key.

## 4. Testing & Validation
- Added `idempotency_key` to `MessageEnvelope` struct and `serde` representation.
- Added `test-idempotency.sh` to validate that repeated sends with the same `--idempotency-key` yield the exact same `id` instead of generating duplicates.
- All code modifications were isolated in the `cloudflare-aplexer-protocol` worktree to prevent disrupting the dirty package/coordination work.
