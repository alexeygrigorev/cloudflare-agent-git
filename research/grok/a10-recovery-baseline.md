# A10 plain-file recovery baseline

2026-10-03. Author: grok-head `eb20adc0-48cf-405e-ab35-dcfde4303d0e`. This file is the first artifact after the E1 resume. It is the ordinary Git and file record. It is not a scored passport comparison and not an executor run.

## Identity

`aplexer whoami --json` with no `--from` and no identity environment overrides returned:

- tag `grok-head`
- id `eb20adc0-48cf-405e-ab35-dcfde4303d0e`
- engine `grok`
- workspace and cwd `/home/alexey/git/cloudflare-agent-git`
- parent session `0d04303a-34d6-49ef-bcc7-3ebd971f5491`
- resume conversation `01a0fe00-6ecd-7c73-a852-e9862578d192`
- phase `running`, reported state `working`

This seat is not `8840df13`. Codex handoff `01a10002-98c9` said the native list resolved `0000ea93`. That id is not this process. Usage counters are absent on whoami, so usage is null, not zero. `quse status` is not a valid invocation here, so provider quota was not sampled. Free space on `/` was 110527299584 bytes. No executor was launched.

## What was read

- Handoff `01a10002-98c9` from codex-principal to grok-head.
- Claude `01a0fffc-81d1` is addressed to antigravity-head. It asks the executor to resume this conversation. It is not a task assignment to this seat.
- `coordination/TASKS.json`: `prospective-review-task` and `recoverable-task-handoff`, both `ready`, owner `grok-head`, team `a06-a10`, assignment ack previously pending.
- Durable originals: `01a0ffcd-0fe9` (`C-REAL-A10-NEXT`) and `01a0ffdd-a8f5` (`C-HUMAN31-GROK-OWNERSHIP`).

## Crash and restart

Prior grok-head id `8840df13` is stopped. The saved conversation `01a0fe00` was resumed under `eb20adc0`. Repo HEAD at this reading was `347155f95b0977f467b09337811c94546b210b0d`. No A10 passport prototype exists under `research/grok/`. Earlier challenges in `challenge-r3.md` through `challenge-r5.md` still say a side manifest must beat a plan file in the same commit. Those notes are not this restart's evidence.

## Preregistered question

After this restart, does the next actor recover owner, task, code SHA, dependency, crash point, and next action from Git plus `TASKS.json` plus the native handoff, with the same access a passport file would have?

Baseline fields present now: owner `grok-head`, tasks above, code SHA `347155f`, dependency on the saved conversation and aplexer whoami, crash point as the UUID change `8840df13` to `eb20adc0`, next action as this file. Missing from the plain record before this file: a single place that bound the new UUID to the old conversation. Whoami supplies that binding. A passport that only repeats these fields has no adoption case yet.

Kill criterion: if an independent reader, using only the commit that contains this file, `TASKS.json`, and the handoff ids, can name the next action without asking the stopped session, do not adopt a second store from this one restart. One exposed recovery does not establish a rate. No A01 fixture is scored. Source-guard work is not evidence of an unattended scheduler.

Next actor: Muse reviews this baseline against the same messages. Grok does not edit Muse's files. No consumer executor until that review names a missing field the baseline cannot carry.
