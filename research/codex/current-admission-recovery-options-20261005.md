# Admission recovery options — 5 October 2026

Read-only ad hoc discovery for Codex principal; no mailbox access, code review, model launch, process control, cleanup, copies or service changes. Measurements at 14:57:02 UTC. Owner of this evidence: safe_admission_alternatives native helper; implementation/custody remains with project heads.

## Measured storage

| Location | Available GiB | Meaning |
| --- | ---: | --- |
| Root `/` | 48.382 | Below mandatory 50 GiB root floor |
| `/data` | 13.407 | Separate ext4 filesystem, insufficient floor |
| `/tmp` | 13.407 | Bind on the same `/data` filesystem; not another capacity pool |
| `/dev/shm` | 31.358 | RAM-backed, does not restore root floor |
| `/run/user/1000` | 6.272 | RAM-backed, does not restore root floor |

`findmnt` shows root `/dev/nvme0n1p3`, `/data` `/dev/nvme1n1`, and `/tmp` a subdirectory bind from the latter. No measured alternative authorizes bypassing the global root floor. No unrelated mounted/container contents were inspected.

Project-owned allocated-byte measurements from bounded `du -sx -B1`: `.local/scratch` 730,009,600; `.local/tmp` 1,363,968; `.local/journal` 87,232,512; `.local/metrics` 204,627,968; `.local/supervision` 11,661,312. Launcher scale50 subtree 14,131,200; AgentBus local 258,048; AgentCoordination local 1,527,808. These are subtree allocation measurements, not proof of safe disposal, and not a unique whole-project sum.

Root needs approximately 1.618 GiB restored before admission. Even removing all measured scratch/journal/metrics/supervision/tmp would recover only about 0.964 GiB. Such removal is forbidden and would destroy retained evidence; the calculation disproves that this limited scope alone is a sufficient recovery plan.

## Bounded next action and owner

Antigravity integration/retention head can perform a read-only custody reconciliation now: map the 730 MB scratch tree to closed task owners, identify generated disposable artifacts separately from Git worktrees, credentials, retained receipts/history and review evidence, and produce an exact path/bytes preservation manifest plus owner releases. Existing task registry names Antigravity ownership for scratch review/dogfood lanes, including bus-ssh-rpc-snapshot, metrics audits and filebus reviews; this is not a blanket deletion authorization. Largest measured immediate child `uprt-concurrent-trial` is 120,504,320 B, but disposal eligibility is UNKNOWN. `node-compile-cache` is only 4,231,168 B; its name does not establish safe release. No closed-task disposal manifest or acknowledged release was found in the targeted current policy/task search.

That reconciliation can enforce the scratch budget and propose safe cleanup; it cannot plausibly restore the current root deficit alone. Do not launch new workers or move files to /tmp/RAM as a substitute. Preserve the healthy metrics collector and supervision history.

If broader recovery is needed, the actual storage owner must name a bounded authorized root-filesystem retention target large enough to restore the floor with operating margin, with private preservation and independent confirmation. Permission is missing specifically for unrelated/private storage cleanup or policy reduction, not for ordinary project task dispatch. Do not ask for general project approval, kill unknown processes, install/build, or claim a repaired gate.

## Supported execution alternative

`coordination/OPERATING-MODEL.md` explicitly states the maintained launcher has no trustworthy remote-host execution contract; unsupported remains explicit until accepted. Existing user-owned computers/Hetzner are authorized execution locations in principle, but no second host with measured resources, fresh quotas, authenticated worker identity, supported admission and actual first tool was established here. Buying capacity or inventing remote availability is not an option. A second mount is not a second host.

## Verification / trigger

Next event: Ant head exact custody manifest and safe owner release, or actual storage-owner restoration. Principal then remeasures root >=50 GiB, RAM >=10 GiB, scratch <=512 MiB, and fresh provider/admission evidence before allowing head-owned first useful worker. Independent recovery reviewer validates retained receipts/worktrees, source pins and actual before/after bytes. No ACK, cleanup, remote-host acceptance or gate restoration is claimed by this discovery.

Sources: `coordination/RESOURCE-POLICY.md` (Grok5/50-worker physical ceilings), `coordination/OPERATING-MODEL.md` (metrics retention and fourth-product launcher host boundary), current `coordination/TASKS.json` scratch ownership records, native `findmnt`, `statvfs` and bounded project-scoped `du`. No external citation or fabricated agreement.
