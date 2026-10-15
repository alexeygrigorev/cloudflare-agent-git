# Demo feedback and follow-up

These notes consolidate the demo discussion on 15 October 2026. The recording and submission are complete; the founder then authorized implementation of the follow-up improvements. Preserve the recorded presentation and distinguish later fixes from what the submitted video demonstrates.

## Main idea

I'm not building a better Git. I'm building a coordination layer on top of Git. Git stores and merges changes; Agent Branches helps agents coordinate their work.

Git worktrees already provide separate working directories and branches. The additional value is knowing who is changing what, identifying overlapping work early, checking current combinations and telling the agents what needs attention. Remove vague comparisons such as “whether that beats worktrees depends on the workflow.”

The opening can retain the personal context: running out of disk space was solved with a 1 TB network drive for €3 a month. Coordination is the problem this project addresses.

Keep these two capabilities distinct:

- Current demonstration: agents publish commits to their separate forks, then an authenticated client checks them before integration into canonical `main`.
- Desired earlier coordination: warn about overlapping intended or in-progress work before agents spend substantial effort on it, ideally before a push is necessary. A remote service cannot see unpublished local edits unless a client reports them. An overlap warning is not proof of a merge conflict or failing combined tests.

The benefit of an early warning is time to act: agree ownership of a shared file, adjust overlapping tasks, rebase a change and check the updated commits again.

The user's central critique is that plain Git can already perform the conflict check shown in this demo, so the demonstration does not establish why another layer is needed. The added workflow should automatically check pushed changes, store version-specific results and expose the warning through status; do not present Git's existing merge preview as a new product capability. The user clarified that committing and pushing should be enough: the next status read should show the result without a separate manual check step. Earlier coordination before substantial overlapping work remains another intended benefit to test. Describe the actual workflow rather than a proven improvement over plain Git.

## Current status and verification boundary

The accepted post-recording release is on `main` in commits `b24ea10b`, `1689f47c` and `985f7567`. It includes the filesystem-installed `uv run branches` CLI, private server-bound configuration, an independently running checker and persistent run-owned cleanup. Independent review accepted the exact source. Verification covered 162 Worker tests, 75 Node tests, 16 real-Git sidecar tests and 56 combined Python tests. A separate real-Git integration started the checker before independent pushes and verified clean results, combined-test failure, repair, textual conflict, planned overlap and safe publication to the task's own fork.

The original smoke client was repaired and rerun against its explicit mock: 14 checks passed with 26 simulated operations and owned cleanup. This does not replace the original failed report or establish new live Cloudflare proof. The historical 13 October live run remains separate evidence.

Task creation from a fresh directory is now accepted and pushed in `2651cc64`: omitted Git context comes from the coordinator, and an explicit base on one task does not freeze the base for later tasks. Focused CLI and real-service integration tests passed. The dashboard's planned-overlap display was independently accepted and pushed in `6b1f4bf7`; all 83 UI tests passed after correcting malformed-overlap and first-load failure handling. Actual browser checks covered warnings before any push, removing a declared overlap, task-specific warnings, escaped filenames, and a 390-pixel viewport without horizontal overflow. A failed status update labels the previous overlap as historical and current plans as unknown.

The current deployed Worker still needs the newer APIs deployed; the existing contest head owns deployment admission. A read-only account inspection did not establish an aggregate preventive dollar bound or Artifacts allowance. No optional live write run is authorized by a passing local test or an application operation allowance alone.

- Implemented in the demo source: explicit local/Cloudflare backend selection, Space or Enter progression for displayed commands or logical blocks, descriptive titles and visible block separators, task-registration explanations and sanitized response output, and automatic checks after the demo's pushes. Fetch/comparison/report transport stays internal by default; the next status read exposes the recorded result.
- The final presentation revision completed an actual Windows terminal run: descriptive block titles, Space before execution, output held until Space reveals the next command, one passing combined test, a stale result after new pushes, a conflict warning naming both agents and `shared.txt`, unchanged canonical main and successful cleanup. Cloudflare read-only startup and cancellation before sending setup also passed; this is not a live write run.
- The final CLI integration passed a complete local run, including optional planned-path warnings before the conflicting edits. The current backend passed 39 core/router/plan tests, and nine targeted Python CLI/client tests passed. An actual CLI status request to the deployed Worker also succeeded without writes. Optional `--plans` needs the new backend deployed on Cloudflare; it is available locally now.
- The local/Cloudflare visible-flow correction is implemented and independently reviewed: one common preparation action, then the same task, edit, push and status sequence. Two offline parity tests and a real local interactive run passed. Offline cloud transports are not evidence of a live Cloudflare write run.
- A live Cloudflare write run of the post-recording changes has not been established. Local success is not Cloudflare proof.
- The original smoke report failed at the seed push, so its later checks also failed. Do not replace that evidence with a blanket “all checks passed” statement; diagnose or rerun that path separately if it is used as submission evidence.
- The website title/image stacking and centering have been reviewed on desktop and mobile. The daily-report update has been accepted and deployed: eleven `Day X: ...` titles and distinct day-specific illustrations. Preserve that work rather than regenerate it unnecessarily.
- The demo article and architecture illustrations are committed in `985f7567` and available on GitHub. Publication of the website is separate from deploying the latest Worker code.

## Priority 0: finish the submission presentation

### Pause at commands and logical blocks

The user needs time to explain each action. Pausing only after an entire compatible/conflict case is too late.

Acceptance criteria:

- Display an explanation and the command or meaningful block, then wait for Space before executing it. Enter may also advance.
- Give every block a short descriptive action title, for example `Block 3: Register Agent A` or `Block 12: Check both agents' current changes`; a bare block number is not enough.
- Use two distinct pauses: read the command and press Space to execute; review its output and press Space to reveal the next command. Do not display the next command while the presenter is still explaining the previous output. Separate blocks with blank lines and a clear divider such as `=====`.
- Treat the two concurrent pushes as a related block so the example still demonstrates concurrency.
- Group internal fetches, credentials and check-report transport into one audience-facing “check these two agents” action. Detailed commands can be optional verbose output.
- Show actual concise evidence: registered agent/task IDs and fork, current check state, combined test result for compatible changes, conflicting file and warning for the second case. Never print bearer tokens.
- Verify that the final version responds to a single Space without requiring Enter, retains both result screens for explanation, and cleans up after normal completion and Ctrl+C.

### Explain task registration and fork pushes

For `POST /tasks`, explain that an agent registers its intended work; the coordinator creates a task and a separate fork and returns scoped write access. Show useful returned fields, with credentials redacted.

Keep registration short: the user explicitly removed branch and SHA flags from the demo command. Supply the canonical repository context through configuration rather than requiring long URLs and commit hashes in routine task registration. Explicit options must still override configured defaults.

The name `main` in an agent's fork caused confusion. State the destination clearly: a push to Agent A's fork does not merge into canonical `main`. The present example detects a checked conflict after fork publication and before canonical integration. Do not describe it as detecting unpublished changes before their push.

`git merge-tree` also caused confusion: it previews the combined tree without updating either branch. Explain that distinction plainly. This uses Git's existing conflict detection; it does not implement the earlier warning about agents starting overlapping work.

The user asked to remove this manual command from the demo, then clarified that committing and pushing should trigger the check automatically. Present the pushes followed by a status read and its result, with the comparison running internally. Do not claim that hiding the command removes the need for the comparison or proves early overlap detection. The helper automates checks after its observed push sequence; the separately verified `branches watch` client reacts to independent external pushes. Checks are asynchronous. A status read before current evidence arrives must show unknown or stale evidence, rather than promise an immediate completed check.

Keep one continuous example with the same two agents: first compatible checkout settings, then conflicting values in `shared.txt`. The audience should see what changed, what was checked and why the warning appeared.

### Make the backend explicit

Use the ordinary uv project and commands from `prototype/`:

```bash
uv run python demo/pair-example.py --backend local --interactive
```

```bash
uv run python demo/pair-example.py --backend cloudflare --interactive
```

The user wants Cloudflare for the recording. State the actual selected backend and distinguish local rehearsal from live Worker/Artifacts evidence. Keep credentials in private configuration. Use `jq` for JSON, and avoid `uv run --no-project --python ...` boilerplate.

The local and Cloudflare demonstrations must follow exactly the same visible setup, task registration, edit, push and status sequence. The extra initial commit commands in the Cloudflare flow were explicitly rejected. Keep backend initialization and establishing the canonical baseline inside one common setup action, with the same block titles, commands and pauses afterward. Different endpoint URLs and generated IDs are data, not reasons to present a different workflow. Verify visible parity without disguising offline tests as live Cloudflare proof.

Before a later live Cloudflare run, resolve the existing review findings:

- The original cleanup used the application's global repository inventory. An initial empty-inventory check did not protect repositories created concurrently by somebody else. The accepted implementation records run-owned names before provider calls, serializes creation and cleanup, preserves unrelated repositories, and retains incomplete runs for retry. The updated API must be deployed before a new live demo.
- Preserve strict gateway-path validation, including rejection of encoded and dot-segment paths. The demo's validation was narrowed during the final verification pass.
- An early read-only cancellation exposed a Windows temporary-log sharing error. A bounded cleanup retry was implemented and the final read-only cancellation test passed.
- Record live results only after the real run, including canonical-head preservation, owned cleanup and applicable operation limits. Do not claim that an allowance is a verified account-wide dollar spending cap.

## Priority 1: improve the existing CLI/API after submission

We already have a Branches CLI, but the initial demonstration used raw Git and API calls. It was located at the repository root: the `agent-branches` entrypoint and `agent_branches/cli.py`. It already supports task registration, status, push-event notification and check submission. The user explicitly asked to use it in the demo, with real operations behind the nicer interface, rather than inventing commands to implement later. That integration and the status-display corrections are now implemented and verified locally. The reason it was bypassed earlier remains unverified; do not invent one. Its `push` command registers an event and must not be presented as a Git push.

The desired interaction is closer to “these two agents are changing the same file; coordinate their work” than a sequence of authenticated fetch commands.

The CLI is now packaged as a local filesystem dependency of the uv project with a `branches` console entry point. The requested invocation is `uv run branches ...`, replacing `uv run python ../agent-branches ...`. It reuses the existing implementation. Fresh-install tests execute task registration and status without a global installation or manual `PYTHONPATH`. This change followed the recording, as requested.

Acceptance criteria:

- Reuse or extend the existing CLI for task registration, publishing work, checking a pair and reading warnings. Document any missing capability that requires an extension.
- Explain each action in terms of agents and their work. Keep transport details out of the normal path.
- Return a concise result naming the agents, overlapping paths, checked commit versions, evidence freshness and a suggested next action. Missing evidence remains unknown.
- Provide an explicit local/Cloudflare choice without making users assemble gateway URLs or bearer headers for routine actions.
- Test a fresh-user walkthrough using the CLI rather than raw `curl`/`GIT_CONFIG_*` plumbing.

## Priority 1: coordinate before substantial overlapping work

Investigate reporting intended files or areas when registering a task, followed by changed-path updates while an agent works. Choose and test the reporting mechanism rather than assuming the server sees local edits.

The optional declared-path mechanism is now implemented: owner/admin requests persist `plannedPaths` on a task, and status derives `plannedOverlaps` without changing branch heads or Git check results. It distinguishes undeclared plans from explicitly empty plans. The local `--plans` demonstration verifies an overlap before edits and commits. Automatic observation of arbitrary unpublished edits remains future work.

Acceptance criteria:

- When Agent B declares or begins work overlapping Agent A, both can receive an understandable warning before committing extensive work.
- Identify the shared files or areas and the participating tasks. Distinguish planned overlap, observed edits, a checked textual conflict and a combined-test failure.
- Support a response: agree ownership, split the task, update the plan or rebase and recheck. Avoid promising automatic coordination unless implemented and demonstrated.
- Retain exact-commit check freshness: new changes invalidate earlier passing evidence, and a lost push remains unknown.
- Compare the observed benefit with a worktree workflow using a small real task; do not assume fork isolation alone establishes a coordination advantage.

## Documentation and diagrams

Keep `_docs/demo-recording-script.md` as an article: `## Demo`, descriptive `###` sections and proper code blocks. Remove “Say,” presenter instructions, bold emphasis and comments such as “the diagram shows.” Describe the behavior directly.

Link the [hypotheses page](https://alexeygrigorev.com/cloudflare-agent-git/hypotheses/) early and briefly explain the relevant ideas: Live Integration Radar, exact-commit verification, scoped forks/tokens and change-story review. Brief problem descriptions should make the research understandable without prior context.

Use “authenticated client” and “check,” not “trusted runner” or “trusted check.” Explain Artifacts as Git repository storage, the Worker as the Git gateway and coordination API, the SQLite Durable Object as the coordinator's state, and the authenticated client as the computer that runs checks and submits reports. The coordinator does not execute agent code.

Illustrations must match those responsibilities. A generic merge-and-test diagram alone does not explain the coordination layer. Show separately scoped agent writes through the Worker to Artifacts forks, and show who reports work, checks combinations and receives warnings. Keep PNGs visible inline and retain editable sources.

Keep the demo focused. The user removed live-budget/status exposition, refused-request/security demonstrations and the multiple fixture tour. Explain budget reservation only where needed to understand why the demo limits operations; do not make it a recording section.

If operation counters appear elsewhere, label used operations and remaining allowance distinctly. A value such as `utcDayOps: 0` must not be presented as exhausted allowance without checking its actual schema meaning. Budget reservations exist to bound service use before an operation, not to demonstrate the coordination benefit.

For local UI instructions, use the correct `prototype/` working directory. A static server started from the wrong directory produced 404s; the live UI also needs a running coordinator and the correct `?api=` endpoint. Verify the documented command from the stated directory.

## Website and daily-report requirements

- Put the problem on each hypothesis card, separately from the proposed solution. Preserve the user's concrete wording where applicable: “Stop two agents from silently doing overlapping work.”
- Put each project image below its title/status/caption and center it within the page. Check both a narrow mobile viewport and desktop; avoid horizontal overflow.
- For each daily report, use `Day X: ...` with a title about that day's actual result. Confirm the numbering against the existing experiment timeline rather than inventing dates.
- Give each report a distinct illustration specific to that day's events, using the established visual style. Conceptual art must not imply unverified product behavior or measurements.
- Verify the deployed page and image, not just the source or a local screenshot. Preserve independently accepted titles, illustrations and layout fixes already delivered.

The user discussed showing the desired behavior now and completing it overnight. A demonstrated real CLI does not need a prototype label; an unimplemented or simulated capability must not be presented as verified live behavior. Continue actual implementation and verification rather than manufacture demo evidence.

The post-recording implementation adds the filesystem-installed CLI, private configuration, an independently running authenticated checker and run-owned cleanup. Their verification and release are tracked in [the post-demo issue](https://github.com/alexeygrigorev/cloudflare-agent-git/issues/114). Automatic observation of unreported local edits remains future work. No additional demo scenario or broad styling pass is implied by this note.
