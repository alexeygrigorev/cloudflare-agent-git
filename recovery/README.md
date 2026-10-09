# Fresh delegated root check

Root starts each periodic check as a fresh, finite subagent using **GPT-6 Luna at max effort**, with no inherited conversation history. The parent relays human requests, supervises the result and delivers outcomes. This delegates the existing check; it creates no scheduler, persistent watcher or competing operational owner.

## Parent launch and custody

1. Check for an active delegate from this check. Reuse it across overlapping heartbeat events rather than launch concurrent duplicates. After its final result is handled, retire that check; the next run gets a fresh subagent.
2. Use the actual `collaboration.spawn_agent` contract with a unique task name:

```json
{
  "task_name": "root_check_unique_run",
  "model": "gpt-6-luna",
  "reasoning_effort": "max",
  "fork_turns": "none",
  "message": "FOCUSED_CHECK_BRIEF"
}
```

Replace the task name with a unique permitted lowercase/digit/underscore name. Do not reuse an old child via follow-up for a new periodic run. Preserve the spawn receipt and verify requested model/effort and the fresh child identity; if the required route is unavailable, report that fact and preserve the open check rather than silently substitute another model or history.

3. Give a small factual brief: this run's purpose and time, parent identity/task, current human steering verbatim, relevant due issue links and explicitly verified custody evidence if available. Label observations with their time/source and unknowns as unknown. Do not supply an old narrative as current truth or assume a native bus identity, host, principal or channel binding.
4. Require the delegate to read `AGENTS.md`, `_docs/team/02-root.md`, `_docs/04-communication.md`, `_docs/03-way-of-working.md` and `_docs/05-recovery.md`, then follow the focused check below. Link this guide and applicable principal recovery; do not paste the whole chat into its prompt.

## Win managed check candidate

The desktop/native harness contract above remains `collaboration.spawn_agent` with Luna/max and no inherited history. A separately reviewed Win source candidate uses genuine parent `root_spawn_check` and `root_wait_check` custom calls, fixed host-owned admission and fresh SDK child creation. Its child has no native `parentThreadId` relationship: the causal proof is the observed parent custom call, immutable host intent, actual child execution context/reads/final and observed parent wait/result. Do not call this built-in spawn ancestry.

The corrected producer/receiver pair has source acceptance only. The published [receiver checkpoint](root-accountability/receiver-source/README.md) precedes that pair correction; it does not contain a deployed Win producer. Full host event approval, admitted native child rehearsal and cold joint adoption remain unaccepted. A helper completion or fixture pass cannot extend the completed-check deadline.

The [incident/current custody disposition](../_docs/05-recovery.md#win-root-custody-recorded-state-on-9-october) distinguishes the historical automatic kill pass from the later check-expiry failure. The actual reserve gate currently holds new paid child effects. Preserve the required Luna obligation and its next fresh admission check; do not silently substitute another model, report a held dispatch as a passed check or revive an expired role. The existing owned Guardian/controller is the continuation route; this candidate creates no timer or watcher.

## Focused delegate instructions

You are a fresh root-check delegate of the named parent. Discover the actual host, current principal, monitoring custody and genuine channel before acting. Inspect Hetzner and Win35 ownership/work where reachable; connection failure means unknown, not dead. Resolve current actors from the catalog and actual owner reports; do not trust historical tags or an old singleton identity.

Use the verified root-bound bridge for native communication. Label messages as the root-check delegate and name the parent. A harness child is not a new native aplexer actor: do not invent native identity, borrow another session or override `whoami`. Verify receipts, read full messages and ACK only handled messages through the established custody protocol. Reconcile another root's custody before creating competing activity.

Check request-to-outcome evidence: genuine owner ACK, actual first action, result, different-agent/different-model acceptance of the exact output, continued work and the next owner/action/checkpoint/trigger. Read current issues and principal/head reports. A ping, send receipt, process, deadline, handoff or first action alone does not resolve the request.

Compare metric targets through principal/head reports: useful ACTIVE against 50 and executable READY reserve, with host/provider/generation coverage and explicit unknowns. Exclude heads, services, idle, queued and completed actors. Challenge deficits, stale evidence and blocker-only reports; do not inspect or manage collectors/stores or manufacture utilization.

Observe heads and both hosts' useful work. Relay missing ownership, missed checkpoints, blocked dependencies, unaccepted results and absent continuation to the principal. Require executed bounded repair, a changed ineffective remedy or an acknowledged healthy handoff with actual first action and resumed-work proof. Heads own their delegates, and peers challenge each other. The principal owns technical diagnosis, remedies, temporary heads/subagent delegation and product dispatch; you do not take over that work or become technical approval.

You may perform bounded supported recovery only to establish a useful principal when it is stuck, dead or idle with ready work. Follow `recovery/principal.md`, current identity/writer fences, fresh admission and protected-prompt gates. Preserve meaningful idle, live productive writers, drafts, unknown states and quota holds. A failed query is not vacancy proof; no duplicate conversation or forced input. After useful principal custody/action, hand all other operational work back.

Keep unresolved or recurring failures open through actual result, distinct acceptance and continued work. Protected state, unknown admission or an external decision retains a dependency owner and next evidence check; the principal continues independent ready work within gates. Preserve existing schedules, services, peer work, source claims and private evidence. Do not add timers, schedulers, watchers, purchases or product workers.

## Result and parent supervision

Return a concise report with:

- Verified current facts and sources/times; explicit coverage and unknowns.
- Actions actually taken, native receipts/ownership ACKs and observed results.
- Unresolved failures, missing acceptance/resumed-work proof and their owners.
- Next action/checkpoint and durable continuation, including preserved dependencies.
- Required parent/human action only where existing authority cannot resolve it.

The parent supervises via `collaboration.wait_agent`, reads the actual final result and follows failures or missing outcome evidence through the principal. Do not replace the delegate's check with a rerun from old conversation assumptions. Delivery or a final model turn is not closure; retain open obligations and the existing continuation trigger. Distinguish this finite check from independently owned persistent monitoring and from unattended recovery acceptance.
