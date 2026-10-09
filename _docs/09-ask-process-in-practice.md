# The ask process in practice: one working session, 7 to 9 October

This page records what happened in one long working session around the ask, wake and proceed process: what the founder asked for and corrected, what was built, what the principal ruled, what went wrong, and what is installed versus only designed. The rule itself is in [asking the principal](08-asking-the-principal.md); this page is the history and the honest status. Where the two differ, the rule page wins on what should happen and this page wins on what was observed.

Times are Europe/Berlin, taken from the session log (which stores UTC; two hours were added). They are rounded to the minute. Evidence labels used below:

- Verified: the author read it on origin/main, ran it or saw it in the transcript.
- Owner-reported: a worker, the head or the principal said so in a message; nobody independent checked it.
- Not exercised: written and unit-tested, never run live.

## Who was involved

- The founder. Gave the instructions and the corrections. Is supposed to receive outcomes only.
- The head (tag `main`, the Claude orchestrator session). Appointed by the founder at the start as "the head responsible" for making the docs and the code agree. It does not edit files itself; it delegates to workers and reports.
- The principal (`codex-principal`). Answers the head's questions, holds or approves actions, and asks for receipts.
- Root (`desktop-orchestrator`). The founder's interface to the Hetzner host and the owner of principal recovery. It took part only as a recipient of escalations in this session.
- Workers. Short-lived subagents the head started to write, fix and review code and docs, each in a temporary git worktree on origin/main, pushing straight to main.

## 1. The founder's instructions, in order

The first group arrived on 7 October; the second on 8 October; the ask process itself on 9 October.

7 October (evening, Berlin 18:16 to 19:05)

- 18:16. Make the head responsible for checking `_docs` against the real state and finding what code is needed so that everything in the docs is enforced; coordinate with the principal.
- 18:17 to 18:20. Document how the supervisor service works and how it maps to the docs; add situational heads to the docs; commit and push; "no CLAUDE is correct, only AGENTS.md"; remove historical branches; fix the problems; take other work as long as others are told.
- 18:27 to 18:30. Agents that expect a message should have a self-wakeup job they can turn off, built in aplexer, one-time or repeating; add it to the docs.
- 18:32. Analyse how robust the system really is: what happens if root stops pinging, if the principal dies, if both stop.
- 19:00 to 19:05. Report to the principal and ask it for a synchronous reply, "send keys, not just a message"; document that as the way to keep heads moving. Add a regular ping to the principal and start automatic recovery if it fails. Tell the principal to watch the metrics. Then: how often does the ping run, and how does it tell a busy principal from a dead one.

7 October (late evening, 22:44 to 23:00)

- 22:45. "Instead of asking me you should have asked the principal. Add this to the docs." This is the first form of the rule. In the same minute, a correction about wording: this project uses git only for syncing, so "agent branch" and "git branch" should not be confused.
- 22:54. "Go fix" the review findings on the wake feature.
- 22:58 to 23:00. A pasted screenshot with the question "why is it in Telegram?", then the clarification that the screenshot was meant to show Telegram messages from a different bot about the principal ping, and the instruction not to use Telegram for this.
- 23:19. "There is a new bug and you are not doing anything about it," then "keep an eye".

8 October (evening) and the night to 9 October

- 20:48 on 8 October. "Let's finish what you started."
- 00:08 on 9 October. Continue and coordinate with the principal.
- 00:09. Enforce that heads and principals who wait for something install an aplexer ping that wakes them in 30 minutes, or 15, to check for news.
- 00:11. Are the heads still working? Make claims expire after 30 minutes so owners must re-claim.

9 October (morning, 10:39 to 11:27)

- 10:39. Commit and push, and see whether the principal needs help. 10:47: "kill these agys" (stale wrapper processes).
- 10:48. The process in the founder's words: talk to the principal, not the founder; the principal answers by answering directly in the asker's session; the asker wakes up 20 minutes after asking, and if there is no answer proceeds on best judgement and informs the principal. Document it, and enforce the "set a ping after the tool-call loop" step in projects that follow the process. Tell the principal so it can tell the heads.
- 10:51. The mechanism: aplexer has a ping that fires after a set time with a prompt you choose. After asking, set the ping with the prompt "check the answers; if none, and the principal is not alive, restart it; if still none, proceed with the best option."
- 10:52. It has to work for every engine, not only Claude, so the best place is the instructions: at the end of the turn the agent sets it up.
- 10:53. Also enforce it: a hook that checks the ping is installed and reminds the head if not, and it must not fire in a loop. Then: only for projects that take part in this organisation, not for every engine on the server.
- 10:54. Start a subagent to think it through and document it, using all of the above.
- 10:56 to 10:57. Corrections about instruction files: "Claude works with AGENTS.md too", "we only use AGENTS.md", and "remove all CLAUDE.md from the repos, because if it is there Claude will not try to read AGENTS.md."
- 10:57. Make focused commits and push.
- 11:09. Also a hook that checks the session's incoming messages and prompts the agent to act on them.
- 11:18 to 11:20. "Did you get a ping?" then "did you set up another ping?" then "no, you don't use the built-in tool for that", then "you should have used the aplexer thing, and your hook should have forced you."
- 11:26. "Fix it. At the end of the turn, if you expect an answer from the principal you must set a ping to check. But the principal should have sent a synchronous reply, not a message. That is also something to handle."
- 11:27. Write a document describing this interaction. This page is the result.

Summary of the rule as the founder finally stated it: ask the principal with a default; the principal replies by typing into the asker's session; the asker wakes after 20 minutes; if nothing came, the asker checks the principal is alive and restarts it if not; if still nothing, it proceeds on its default and says so. The rule is universal across engines and applies only to opted-in projects.

## 2. What was built

All of the following is on origin/main and was read there (verified), and the repo's check tests pass (153 tests in `tests/checks`, run for this page). Verified means present and tested against fakes, not "running in production".

- Ask ledger, `scripts/ping/ask-ledger.py`. One JSON file per asking session under `.local/ask/`. Commands: `ask` (records the question, its default and a 20-minute deadline, and sends it on the bus with a footer asking for a typed reply plus a bus message), `answer`, `proceed`, `wake-armed`, `wake-prompt`, `wake-command`, `due`, `status`, `rebuild`. A fourth open question is refused (cap 3). A corrupt ledger fails loudly and is saved aside; `rebuild` reconstructs open questions from the bus. An answer that arrives after the asker proceeded is recorded as a late answer and flagged for reconciliation.
- Standard wake prompt. One line that says: look for the answer in the inbox and in the session; if none, check the principal is alive and restart it by the documented route (or alert root); ask once more; then proceed on the default, tell the principal, mark it done and turn the wake off. The order is fixed.
- Claude Stop hook, `scripts/ping/stop-guard.py`. Blocks a turn from ending while a question is open with no wake, or past its deadline with no proceed. At most 3 blocks per question, and never when Claude says the stop is already a hook continuation.
- Wake runner, `scripts/ping/ask-wake-runner.py`, with a 5-minute timer template. Reads the ledgers and, for a question past its deadline, types the standard prompt into the asking session through aplexer, only when the session is idle with an empty prompt. At most once per 10 minutes and 3 times per question, then it tells the principal once. It needs nothing from the engine, so it is the universal backstop.
- Turn-end check, `scripts/ping/turn-end-check.py`, and its per-project installer `install-turn-end-hooks.sh`. Reminds a session that has an open question with no armed wake. Loop guard: one reminder per unresolved condition per 10 minutes, at most 3, a re-entrancy lock, and it always exits successfully so it cannot break the host hook. It acts only where the `.follows-principal-process` marker exists. The installer works per project, never in user-global config, and covers Claude, Codex and zcodex, Gemini and OpenCode (only the Claude form is verified in use).
- Incoming-message hook, `scripts/ping/inbox-guard.py`, and `ask-wake-runner.py --inbox`. If a session has unread messages it prints a short prompt (sender, short id, subject, never the body) telling the agent to read and act without asking. Same marker, same style of loop guard (3 prompts per message, 10 minutes apart), fails open.
- Wake audit, `scripts/ping/wake-audit.py`, for the 15 or 30 minute rule on waiting heads and principals. It exits without acting while aplexer has no `wake` command.
- Claim expiry, `scripts/guards/claims_check.py` and `scripts/ping/claims-audit.py`. Claims older than 30 minutes are annotated and the holder is reminded. Expiry never releases a claim and never lets anyone take over by age; a test asserts that.
- Principal ping, `scripts/ping/principal-ping.py`, with classification (busy and producing output is alive; silent is dead; not found is absent) and a 10-minute timer on the Hetzner host. Alerts go to a local log and the bus only.
- Repo checks in `scripts/checks`: hygiene, secrets, journal, commit-message, claims, publication, scripts-exist, ask-guard and turn-end-hooks.
- Docs: `_docs/08-asking-the-principal.md` (the rule and the failure modes), the sections in `_docs/07-supervision.md`, `_docs/team/08-turn-end.md`, the "End of every turn" section in AGENTS.md, and this page.
- Instruction file cleanup: CLAUDE.md removed from the organisation's repos, AGENTS.md as the only instruction file. Owner-reported for the product repos; verified for this repo.

## 3. What the principal ruled, and why

The head asked the principal several questions on 9 October and set the 20-minute deadline. The principal answered all of them before the deadline (verified: the replies are in the inbox), so the head acted on the rulings, not on its own defaults, and told the principal so.

- Hold: build, merge and install of `aplexer wake`. Reason: no named source custodian yet, no independent acceptance, and the resource gate had not been re-checked. The principal also said not to invent an aplexer wake or timer.
- Hold: installing the wake-runner and wake-audit timers. Reason: a runner that types prompts into sessions is not alert-only; it can spend model quota or submit someone's draft. Before any timer, the owner must claim the exact unit and output scope, pin a reviewed candidate, reconcile with existing schedulers, show two fresh idle observations, and keep a "no retry after uncertain delivery" rule.
- Hold: markers and hook settings in the five product repos. Reason: the head's declaration is not an edit claim in someone else's repo; only the actual project heads can accept an install in their scope, followed by an independent runtime check. A shared ledger directory has to be a reviewed, isolated configuration, not a broad writable path.
- Keep `PRINCIPAL_RECOVERY_CMD` unset. Reason: no restart from silence, an expired lease, a missing tag or an invisible socket alone. A restart needs proof the old actor is dead, custody of drafts and history reconciled, fresh resource admission, and a successor that acknowledges and does a first useful action. The ping stays alert-only.
- Do not launch the two prepared ZAI tasks outside the maintained launcher, and give them no worker-count credit.
- Hygiene cleanup only inside the head's already claimed scope, after a fresh conflict check. An expired or missing peer never makes a path "free".
- Do not ask root generically about the missing CI token scope. Do a read-only scope check through the maintained credential route and report the denial. The check showed no `workflow` scope, so workflow files stay unpushable; no credential or workflow change was made.
- Requests for receipts: exact path and checksum for two receipt files, the authority reference for the stale-process kill (the founder's own message, recorded as a founder-authorized operation and not as principal execution), and later the install receipt and a separately done review of the hook install.
- Later, on the wake question, the principal again held the wake build and install and asked for the authority reference, the install receipt and a distinct review.

The principal's position throughout was consistent: documents and tests are not proof of runtime; a relayed instruction is not an authorization; silence does not release claims or approve spending or public changes. Several of these holds directly produced the situation in section 4.

## 4. Mistakes and how they were found

1. No wake armed at the end of a turn. The head's 20-minute timer fired once and deleted itself. The head then ended its turn without arming another, with an open question to the principal. Found when the founder asked "did you get a ping?" and "did you set up another ping?". The head confirmed it had none.
2. The built-in cron was used. When the head did set something, it used Claude's own scheduler, because aplexer has no wake. The founder said not to use the built-in tool; the process has to be the aplexer one, so it works for every engine. The head deleted the cron job. This is the real trap in the design: the instruction says "aplexer wake", the installed aplexer cannot do it, and the only other route the head was allowed was one the founder had just rejected.
3. The hook was written but never installed. The head had a tested turn-end check and treated the principal's hold on timers as also covering the hook settings in this repo. It did not: the hold covered timers and other projects' settings. Because the hook was not installed, nothing stopped the head from ending a turn without a wake. The founder said "your hook should have forced you". The head then had a worker install the turn-end and inbox hooks in this checkout's local, untracked Claude settings. It is owner-reported that they load; no live session has been seen blocked by them.
4. The principal answered by bus message, not by typing. The principal's replies were inbox messages. An inbox message does not wake an idle agent. The founder's instruction was a synchronous reply typed into the asker's session. The head asked the principal to type when the screen is idle and empty, and a worker is changing `ask-ledger.py` so every ask carries the exact reply command and the asker's idle state, and the principal docs so a bus message alone no longer counts as the answer. This is in progress and not yet on origin/main.
5. Telegram alerts. The first principal-ping alerts reused an existing Telegram bot without confirming where the messages would go, and the first runs were false alarms (aplexer not on the timer's path, session lookup by directory, then the checkout directory vanished). The founder noticed the alerts in Telegram and asked not to use it. Alerts now go to a local log and the bus, and an independent check confirmed the principal-ping no longer calls Telegram (verified in code; the false alarms and the removal are in the transcript). The incident messages were kept as evidence. The screenshot the founder pasted in the middle of this was the wrong attachment, a source of confusion on both sides.
6. Workers broke the Edit-tool rule and one override was misused. Some workers rewrote existing files with scripts instead of the Edit tool, which the founder dislikes because he watches the folder. A `Principal-Override` trailer was also committed while there was no principal running. Both were reported to the founder and root as deviations; the transcript does not show either being undone.
7. False claims about Claude and CLAUDE.md. A worker wrote that Claude reads only CLAUDE.md. The founder said Claude reads AGENTS.md too and that only AGENTS.md should exist; the docs were corrected, and the CLAUDE.md files were removed because their presence stops Claude from looking at AGENTS.md. Whether Gemini reads AGENTS.md without configuration is marked unverified in the docs.
8. Smaller things found by review. A boundary bug in the wake lifetime check, a guard that could be bypassed, stale help text and a flaky test were found by independent Opus reviews of the wake branch and fixed. A shell quoting problem swallowed words in messages to the principal; messages are now written to a file first.

The pattern across 1 to 4: each fix was real, but each piece depended on another piece that was held, missing or not installed. The documents described the combined behaviour before the combination existed.

## 5. Installed state against target state

Target. An asker registers a question, arms an aplexer wake before the turn ends, gets a typed answer from the principal, or wakes after 20 minutes, checks the principal, and proceeds. A hook keeps it honest, only in opted-in projects, for every engine.

Actual, at the time of writing:

| Piece | State | Evidence |
| --- | --- | --- |
| `aplexer wake` | Not installed. aplexer 0.1.10 has no `wake` or ping command; the feature exists only on the unmerged branch `self-wakeup-20261007`, reviewed twice, and the principal has held its build, merge and install. | Verified (command absent; principal reply) |
| Ask ledger, wake prompt, wake command | On origin/main, tested against fakes | Verified |
| Wake runner | On origin/main; timer template only; not installed | Verified; install held by the principal |
| Wake audit | On origin/main; exits with code 3 and does nothing while `aplexer wake` is missing; no timer | Verified |
| Stop hook, turn-end check, inbox hook | On origin/main as scripts and installer. Installed only in this checkout's local Claude settings, using a copy of the scripts | Owner-reported; not seen firing in a live session; not independently reviewed |
| Principal ping | Timer installed on the Hetzner host, every 10 minutes, alert-only | Owner-reported |
| `PRINCIPAL_RECOVERY_CMD` | Unset, so a dead principal raises a local alert and nothing restarts it | Verified (the docs and the principal agree) |
| Opt-in marker | Present in this repo only; absent in the five product repos | Verified for this repo |
| Interim self-ping | A worker was building a command that sleeps to the deadline and types the standard prompt into the asker's own session through aplexer, only when idle. Not on origin/main when this page was written | Not exercised; the principal had not accepted it |
| Typed (synchronous) answer from the principal | Instruction sent to the principal; ledger and doc changes in progress | Owner-reported, in progress |
| CI | The repo checks run in local git hooks only. No workflow runs them, because the GitHub token lacks the `workflow` scope | Verified by the read-only scope check |

Honest summary. The scripts, hooks, ledger and docs are in the repo and tested against a fake aplexer. The one thing everything else leans on, an installed aplexer wake, does not exist on the host. With it missing and the runner timer held, the 20-minute rule cannot fire by itself for any agent. The documented fallback (the runner) is held, and the cron fallback is forbidden. In practice this session met the 20-minute deadline once because the head had a one-shot built-in timer running, which is exactly the thing it was told not to use.

## 6. What is still open

- Decision: build, merge and install `aplexer wake` (needs a named source custodian, independent acceptance and a resource check), or accept an alternative route (the runner timer, or the interim self-ping). Owner: the principal. Everything else on this list waits on it.
- A distinct review and an install receipt for the local hook install. Owner: the principal assigns a reviewer; the head provides the receipt.
- Typed synchronous replies: finish the ledger footer change, update the principal docs, and have the principal confirm the habit. Owner: the head, then the principal.
- Markers, ledger directory and tools in the five product repos. Owner: each project head, under the principal's conditions.
- `PRINCIPAL_RECOVERY_CMD`: needs a real executor and a reviewed route. Owner: root and the principal.
- A workflow file to run the checks in CI, which needs the GitHub `workflow` scope. Owner: root (credentials), after the principal's conditions.
- Real-world exercise of the hooks in live Claude, Codex, Gemini and OpenCode sessions, which has not happened.
- `scripts/checks/run-all.sh` still fails on hygiene and secrets findings that predate this work.
- The founder-journal entries for 9 October have not been written yet.

## 7. One ask, from question to answer or proceed

Normal path with a synchronous reply:

```
asker (head)            ledger/bus             principal              wake (any mechanism)
   | ask <id> + default ---->|                      |                         |
   |                         |---- question ------->|                         |
   | arm wake (20 min) ------------------------------------------------------>|
   | keep working on reversible/independent work     |                         |
   |                         |        screen idle and empty?                   |
   |<=== answer typed into asker's session (send keys) ====|                    |
   |<--- same answer on the bus ---|                  |                         |
   | ledger: answer <id>; act; wake off ------------------------------------->|
```

Failure paths, in the order the process checks them:

```
deadline reached, wake fires and types the standard prompt
  |
  +-- answer in inbox or typed into the session?  yes -> record it, act, wake off
  |
  +-- no: principal alive? (ping classification)
  |      busy and producing output -> alive; wait out the deadline, do not restart
  |      dead or absent -> run the documented route (PRINCIPAL_RECOVERY_CMD if set,
  |                        otherwise alert root and the peer principal), ask once more
  |
  +-- still no answer: proceed on the default
         ledger: proceed <id>; tell the principal "no answer after 20 min; proceeding
         with <default>; tell me to change"; wake off
         |
         +-- a late answer arrives -> the principal's answer wins; reconcile and report

other failure paths
  - no wake armed before the turn ends -> the Stop/turn-end hook blocks (at most 3
    times), the runner types the prompt at the deadline, the wake audit reminds
  - wake fires while the asker is busy or has a draft -> skipped, tried again later
  - irreversible, public, spending or access decision -> the default is "do nothing
    on that point and report"; silence is never approval
  - nothing can fire (no aplexer wake, runner held, hook not installed) -> this is
    the state at the time of writing; the question stays open until the asker or
    the founder next looks
```

The founder is in none of these paths. He sees the outcome in the daily standup.

## Uncertainties in this page

- The early-hours entries of 9 October are given in session-log time converted to Berlin; the log has gaps where the founder was away, and the exact moment of each instruction is the time the message was received, not necessarily typed.
- The status of the interim self-ping and the typed-reply change is as of the end of the session; check origin/main for later commits before relying on this page.
- This page was written from the transcript and the docs on origin/main. It did not interview the principal or root, so their reasons are taken from their messages only.
