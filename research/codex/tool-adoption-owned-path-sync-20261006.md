# First owned-path synchronization adoption attempt

Maintainer case: the principal needs to publish one explicitly owned administrative document while peer product files and the shared index/worktree remain dirty. Three private-index replays previously supplied this workflow; C2786 requested a maintained Agent Branches feature.

Reviewed source: CLI implementation3da93b60aa487a1c50ecc2639c54ad9064f2489f; independently reviewed by5545d139, report/source commit0ae553d51a8e793446a4e26bdad41717cb69a887, head-reported23testsACCEPT (Ant genuine01a110b4-d747). This helper checks usage and administrative adoption evidence, not product code.

Preflight: actual source CLI `PYTHONPATH=/home/alexey/git/agent-branches python3 -m agent_branches sync git --help` exposes `--isolated`, repeated `--owned-path`, `--branch`, `--preview` and structuredJSON. No installed `branches` entry was found; source-module invocation is explicit and no global install is performed. Review describes internal exclusive repo_lock; exact shared `.local/git.lock` compatibility must be confirmed before execution, without nested locking or disabling guards.

Planned real operation: preview, then publish ONLY this document to origin/main using maintained CLI under its compatible internal lock. Capture private before/after HEAD, index and peer tracked/untracked file hashes; verify exact remote commit and restored owned blob, unchanged shared checkout and peer hashes. Use bounded120s operation and private0600 logs. Refusal/conflict/unknown lock stops adoption and becomes a head repair intake; ordinaryGit fallback is not scored tool success.

As recorded in this published candidate: actual preview/publication, remote restoration and preservation acceptance are PENDING. No live adoption success is claimed in advance; a later receipt must state observed outcome separately.
