# The 20 ideas

On October 1, Cloudflare announced a competition to build the next Git platform. I gave the research to a team of AI coding agents and asked them to find out what Git-like tools coding agents actually need. As a first step, the agents collected [20 different approaches](https://github.com/alexeygrigorev/cloudflare-agent-git/blob/377ac4d1cc5763a7c8836b27ba0922ffd51cc39b/research/approaches-20.md).

All 20 start from the same situation. One person runs many AI coding agents on the same code at the same time, and each idea targets a problem that this creates.

Here I only describe what each idea would do. I don't say which ideas are still in the running, because that changes as the agents test them. The [daily reports](/cloudflare-agent-git/daily/) track those decisions.

## Parallel work that collides

These five ideas deal with agents whose changes clash:

1. Live collision radar: warns within seconds when the unfinished work of two agents stops fitting together, before either agent finishes.
2. Reserving files: an agent claims the files it's working on, and the system refuses to merge overlapping changes from another agent.
3. Combine-and-retry merging: the system tests changes together before it accepts them. If one change breaks the combination, its agent redoes the task on the latest code, so a human doesn't have to fix the conflict by hand.
4. Hidden-breakage detector: catches changes that merge cleanly but quietly break something another part of the code relies on.
5. Tournament of attempts: several agents try the same task. The system compares what each version actually does, keeps the best one and saves the rest for comparison.

## Human review of agent work

These ideas try to make reviewing agent work faster for people:

6. Change stories: the reviewer gets a short explanation of what a change tries to do and where the risk is, instead of a raw list of edited lines.
7. Inbox filter for open-source maintainers: contributions from AI wait in a holding area until they show they're worth a human's time.
8. Panel of independent AI reviewers: AI reviewers unrelated to the agent that wrote a change check it before a human looks.

## Trusting what agents claim

These ideas keep a record you can check instead of taking an agent's word for it:

9. Proof that tests passed: a trusted record of exactly which version someone tested, under which rules.
10. Lasting handoff notes: when an agent stops, the next one picks up its plan, decisions and open questions along with the code.
11. A "why it's like this" log: for any piece of code, it records why it was written that way and which alternatives were rejected.

## Safety and undo

These ideas limit the damage an agent can do:

12. Locked-down sandboxes: agents work in separate copies with limited permissions, so they can't delete or overwrite the main history.
13. Undo a whole agent session: you see everything one agent did, everywhere, and reverse it in one step.

## Testing and running the code

These ideas help each agent check that its change works:

14. A private test site per agent: each change gets its own running preview and data, so agents don't fight over the same ports or database.
15. Fast test results: after every change, the system runs only the tests the change could affect and reports back within seconds.

## Disk space

This idea comes from my own problem:

16. Lightweight workspaces: the private copy of each agent takes space only for what the agent changes, not for a full copy of the code plus installed libraries. On my server, the extra project copies took [111.7 GiB](/cloudflare-agent-git/daily/2026-10-03/).

## Bigger-scale coordination

These ideas organize work across many tasks, agents or projects:

17. Copy equals task: there's no separate task board. Making a copy means you took the task, and merging it back means it's done.
18. Changes across many projects: one change rolls out across several related codebases in the right order, with a way to recover if it fails partway.
19. Maintenance swarm: dozens of agents each take one chore, such as an upgrade or a cleanup, and the system merges the compatible results together.
20. Earned trust per agent setup: setups with a good track record can merge low-risk changes on their own, and everything else goes to a human.

The agents' [research file](https://github.com/alexeygrigorev/cloudflare-agent-git/blob/377ac4d1cc5763a7c8836b27ba0922ffd51cc39b/research/approaches-20.md) has the full version of each idea, with the evidence behind it and the test that would rule it out.
