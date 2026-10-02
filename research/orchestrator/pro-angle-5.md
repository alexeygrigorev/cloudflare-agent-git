# Completed browser ChatGPT Pro investigation 5

Captured 2026-10-02. Model-generated research; citations require independent verification. No benchmark was performed by this conversation.

Angle 5: reduce the cost of runnable agent workspaces—not merely Git forks

Research date: October 2, 2026.

The reported problem is worth pursuing, but the unit to optimize is an independently editable, buildable, testable workspace over its lifetime. A cheaper repository fork, faster checkout, or smaller-looking directory is not necessarily a solution.

The public experiment’s storage-pain note correctly treats the problem as firsthand qualitative evidence: the workload, baseline size, and measured amplification are still unknown. I have not run a disk benchmark for this report. The findings below distinguish documented mechanisms, practitioner reports, and proposed designs and acceptance criteria.

1. What actually multiplies
Git already shares history; it does not share ordinary checked-out files

Linked Git worktrees share the repository’s object database and much repository metadata, while maintaining separate checked-out files and per-worktree state such as HEAD and the index. Creating another linked worktree is therefore not equivalent to downloading another complete repository history. 
Git

Git also does not automatically copy all ignored and untracked files from the existing workspace. Dependencies, generated assets, build outputs, and application caches can appear because an agent’s setup hook copies them, a package manager installs them, or a build recreates them. Worktrunk’s separate command for copying ignored dependencies and build caches illustrates this distinction. 
Worktrunk

A useful baseline accounting model, not a measured result, is:

𝑃
ordinary
(
𝑁
,
𝑡
)
≈
𝐺
+
𝐶
shared
+
∑
𝑖
=
1
𝑁
(
𝑆
𝑖
+
𝐷
𝑖
+
𝐵
𝑖
+
𝐶
𝑖
)
+
𝑀
P
ordinary
	​

(N,t)≈G+C
shared
	​

+
i=1
∑
N
	​

(S
i
	​

+D
i
	​

+B
i
	​

+C
i
	​

)+M

Here, 
𝐺
G is shared Git storage; 
𝑆
S, checked-out sources; 
𝐷
D, installed dependencies; 
𝐵
B, build/test outputs; 
𝐶
𝑖
C
i
	​

, private caches; and 
𝑀
M, filesystem metadata. The categories must be made non-overlapping when implementing the accounting.

Under reflinks, snapshots, or shared immutable layers, physical accounting instead requires the union of referenced extents, not a sum of directory sizes. Btrfs explicitly distinguishes total, exclusive, and “set shared” space for this reason. 
BTRFS Documentation

Consequently, source-checkout optimization has a ceiling. If sources are a small fraction of post-build storage, even eliminating almost all repeated source bytes cannot substantially reduce the total. Conversely, a source-heavy monorepo with small task-specific access sets may strongly favor sparse or lazy workspaces. That is an inference to test, not a diagnosis of this user’s machine.

Public evidence supports the pain, but not a universal amplification factor
Evidence	What it establishes—and what it does not
A 2026 Reddit user reported approximately 200 GB associated with worktrees and asked whether deleting sessions was necessary.	A concrete capacity complaint. The thread does not establish the number of workspaces, category breakdown, or whether the number represents unique physical allocation. 
Reddit

A practitioner’s January 28, 2026 account described a disk warning after accumulating nine worktrees with node_modules.	Dependency setup and lifecycle management deserve measurement, rather than assuming Git history is responsible. This is a reported experience, not a controlled benchmark. 
Dan Malone Apps

A September 2026 HN discussion debated COW copies, filesystem migration, clean baselines, copied secrets, and worktree-management tools.	There is demand, but also meaningful resistance to changing filesystems or abandoning familiar workflows. It does not establish COW as the universally preferred solution. 
Hacker News

pnpm issue #14782, opened September 10, reported a fresh-install failure when auto did not fall back after hardlinks were refused. The issue is now closed.	Filesystem/package-manager combinations require actual capability tests and version pinning. This is not evidence that current pnpm generally fails.

These are useful recruitment and test-case sources, not a representative market survey. Some proposed community shortcuts—particularly shared writable dependency directories—should not be accepted merely because they appear in successful anecdotes.

2. Five differentiated, viable approaches

These approaches target different terms in the storage model. They can be combined, but should first be benchmarked separately to identify where each helps.

Approach 1 — Task-scoped sparse workspaces

Concept: Materialize the task’s source scope and its dependency closure, rather than the full repository.

The underlying substitute already exists: Git sparse checkout selects which tracked paths are present, and its configuration can be worktree-specific. Cone mode includes additional ancestor-level files, so “one selected directory” is not always exactly the materialized set. Sparse-index support also has external-tool compatibility caveats. 
Git

Proposed product: A scope-aware workspace allocator that derives an initial path set from the task and build graph, includes configuration and transitive dependencies, and expands the checkout when needed. It should explain scope decisions and record expansions, rather than silently treating missing files as nonexistent.

For a fresh workspace, configure sparsity before full checkout, avoiding a temporary full-copy peak. Partial clone is complementary: it reduces which Git objects must be acquired, whereas sparse checkout reduces materialized working files. Neither, by itself, eliminates installed dependencies or build outputs. 
Git
+1

Best fit: Large, modular repositories where tasks and their required tests touch a small portion of the tree.

Adoption friction: Relatively low filesystem friction; potentially substantial build-graph and tool-compatibility work. Hidden configuration dependencies, cross-package code generation, and repository-wide tooling must be tested.

Differentiation: Reliable scope inference, transparent expansion, and test-equivalence guarantees—not another wrapper around git sparse-checkout.

Failure condition: Most real tasks rapidly expand to the whole tree, or sparse operation misses required tests. In that case, retain sparse mode only for suitable tasks rather than forcing it universally.

Approach 2 — Immutable dependencies with private writable environments

Concept: Share dependency content, not a mutable installation directory.

Proposed design: Maintain a content-addressed package store, then construct each task’s environment using either enforced read-only references or independently writable COW copies. Keep editable packages, installation metadata, generated files, runtime caches, and build outputs private unless a particular component has an explicit safe-sharing contract.

Current defaults matter. pnpm’s documentation now says auto tries hardlinks before clones on Linux, while macOS and Windows try clones first. It explicitly warns that editing a hardlinked package changes the shared store and other projects. For writable agent environments, clone-or-copy avoids that particular hardlink fallback; on unsupported filesystems, the safe fallback consumes full-copy space. 
pnpm

uv currently documents clone mode by default on macOS/Linux and hardlinks on Windows. Its cache supports concurrent uv operations and environment-install locks, but that is not a guarantee that arbitrary agent commands can safely mutate a shared environment. Inspect actual installation behavior rather than inferring safety from the package-manager name. 
Astral Docs
+1

Existing substitutes: Yarn Plug’n’Play can reference cached packages without a conventional node_modules tree, but introduces loader/IDE integration requirements; its documentation identifies React Native/Expo as requiring ordinary node_modules. Bazel’s remote action cache and content-addressed output store address repeated build work, although restored outputs still need somewhere to live. 
yarnpkg.com
+1

Proposed compatibility key: Lockfile and package hashes, platform, architecture, runtime/compiler versions, install flags, and relevant lifecycle-script inputs. A lockfile alone is insufficient for a reusable prepared environment.

Best fit: Small source trees with large, largely identical dependencies.

Differentiation: Safe environment construction and invalidation across agents and operating systems. Do not build another package manager before determining whether configuring existing ones solves the problem.

Approach 3 — Native COW worktree factories

Concept: Prepare a clean workspace once, then create independent files that share physical blocks until modified.

Reflinks are materially different from hardlinks: they share data blocks while preserving independent file identity and modification behavior. They require filesystem support; Btrfs does not permit cross-filesystem reflinks. 
BTRFS Documentation

Proposed design: A trusted controller builds a seed at a pinned commit and environment key, stops its writers, then clones the approved source/dependency/build state. Each destination must receive correct independent Git worktree metadata, index, and branch state. Blindly copying a linked worktree’s .git pointer is not an adequate implementation.

Seed construction should use an allowlist. Copying a developer’s live directory risks inheriting dirty files, secrets, stale generated state, or partially written build databases. Path-sensitive environments require reconstruction or validation; Python virtual environments are a notable relocation concern. 
Worktrunk

Direct substitutes already exist:

stol creates reflinked copies of template worktrees. Its documented setup is Linux-oriented, tested on XFS, and can use a mounted filesystem image or dedicated disk.
Worktrunk reflinks ignored dependencies and build caches on supported filesystems, while leaving tracked files untouched. It falls back to full copies on ext4/NTFS and reports which occurred. 
Worktrunk

Best fit: Workspaces with large reusable installed/build state on an existing COW-capable volume.

Adoption friction: Low where native COW already works; high where adoption requires a new filesystem, mounted image, administrator involvement, or repository relocation.

Differentiation: Seed correctness, trustworthy physical accounting, quotas, recovery, and backend selection. “Fast reflink copying” alone is already supplied.

Failure condition: Install/build rewrites eliminate sharing, or per-file metadata and initialization dominate creation latency. Neither “only a few source lines changed” nor “COW copy succeeded” proves a small post-build footprint.

Approach 4 — Shared-base overlay and lazy workspace runtime

Concept: Present a complete filesystem view without independently materializing all content for every task.

Two mechanisms should be distinguished:

Overlay sharing places an immutable prepared tree beneath each task’s private writable layer. Lazy hydration fetches or materializes file contents only as required. A design can use either or both.

Linux OverlayFS permits shared lower layers but requires distinct, non-overlapping upper/work directories. Writes can trigger file copy-up; it should not be assumed that an overlay stores only the changed byte ranges. The lower layer must remain stable while in use. 
Linux Kernel Documentation
+1

Important existing substitute: ArtifactFS already provides a Git-backed FUSE working tree, lazy/background hydration, and a writable overlay. It works with ordinary Git remotes, not only Cloudflare Artifacts. Its README documents Linux and macOS prerequisites and labels the release beta.

Do not infer additional capabilities from that description. In particular, bounded cache eviction, cross-workspace cache sharing, crash guarantees, and sustained low disk occupancy need explicit verification. Background hydration may optimize time-to-first-use without preserving a small long-lived footprint. 
Cloudflare Docs

EdenFS is another architectural precedent, but Sapling’s current repository still describes external EdenFS use as unsupported experimentation—not a frictionless production substitute. 
GitHub

Best fit: Large repositories, short-lived tasks, Linux sandbox fleets, and workloads whose access sets remain narrow.

Adoption friction: Highest local-runtime complexity: mounts, FUSE permissions, file watching, rename/locking behavior, Git integration, and recovery.

Differentiation: Shared bounded hydration caches, dependency layers, quota enforcement, and robust persistence. A repository-wide content search or build is an essential adversarial workload: it may erase lazy-materialization savings even when shared-base savings remain.

Approach 5 — Remote execution with durable task state and bounded active workspaces

Concept: Keep runnable workspaces remote, return patches/results locally, and avoid allocating a live environment for every queued or parked task.

Proposed architecture: A controller stores task state and leases a sandbox only while execution is needed. Many tasks can exist as versioned source plus recoverable dirty-state checkpoints, while a smaller number of sandboxes are active. Remote source/dependency layers can then use approaches 2–4.

Cloudflare already documents a repo-per-sandbox integration: a Worker creates or reuses an Artifacts repository and sandbox, then supplies a scoped Git remote to the sandbox. This supplies useful orchestration primitives; it does not establish an optimized workspace-storage implementation. 
Cloudflare Docs

The local-saving mechanism is remote execution without a full local checkout. A cheap server-side fork followed by a full local checkout and dependency installation does not solve local amplification. Nor does creating twenty remote repositories prove that twenty remote execution environments share storage.

Existing substitute: A managed remote runner or ordinary remote host with bounded workspace slots may be enough. Artifacts should earn its place through versioning, scoped access, lifecycle integration, and recovery—not through an assumed local-disk benefit.

Best fit: Teams already accepting remote execution, constrained laptops, or workloads that need stronger isolation and centralized lifecycle control.

Adoption friction: Network dependence, interactive debugging, credentials, operating-system parity, data residency, remote cost, and provider limits.

Current Cloudflare constraints are material. Artifacts entered open beta on October 1, 2026. Current limits include 1 GB storage per repository and 32 MB per individual blob. Large dependencies/build outputs therefore need a separate storage strategy, and some large-history repositories will not fit this backend unchanged. 
Cloudflare Docs
+1

Billing starts October 14, 2026, with operations and stored data charged separately on the Workers Paid plan. The economic model must also account for execution and retained runtime storage; free current experimentation is not a long-term cost result. 
Cloudflare Docs

3. Platform limits and concurrent safety
Support must be established per volume and application
Environment	Practical interpretation
Linux, ext4	Sparse checkout and overlay-based designs are options. Ordinary reflink copying is not. Package-store sharing must not silently become unsafe writable hardlinks. Worktrunk documents full-copy fallback here. 
Worktrunk
+1

Linux, Btrfs / reflink-capable XFS	Strong COW candidates. Probe the actual volume, mount arrangement, file attributes, and copying implementation rather than relying on the filesystem’s name. 
BTRFS Documentation
+1

macOS, APFS	Native cloned-file approaches are available through supporting tools. ArtifactFS additionally requires macFUSE; that is a different installation and compatibility burden. 
Worktrunk

Windows, NTFS	Do not promise ReFS-style block cloning. Use sparse/materialization reduction or safe copies unless another explicitly validated mechanism is available. 
Microsoft Learn

Windows, ReFS / Dev Drive	Block cloning preserves independent writes, but source and destination must share a ReFS volume, and the application must use a supported operation. Merely placing Git on ReFS does not prove checkout sharing. 
Microsoft Learn

WSL2 or filesystem images	Measure both guest filesystem usage and host backing-file allocation. WSL’s virtual capacity and actual Windows disk consumption are different quantities. A Dev Drive underneath a WSL virtual disk is not automatically a COW Linux workspace solution. 
Microsoft Learn
+1
Three different isolation requirements

File independence: Mutable sources and outputs must not share writable inodes. Use genuine COW, independent copies, or private writable overlays—not hardlinked sources.

Build independence: Give each task compatible dependency state and private mutable outputs. Namespace ports, databases, temporary directories, and writable runtime caches as part of the proposed runtime contract. A separate checkout alone does not supply these guarantees.

Security isolation: Git worktrees are not a hostile-agent boundary: common repository state remains shared. Distinct branches and indices support ordinary parallel development, but an untrusted process also needs an appropriate sandbox and restricted access to shared Git administration, credentials, and cache writers. 
Git

For the proposed dependency service, “immutable” must be enforced outside the agent’s writable authority. A hash identifies content; it does not prove the producer was trustworthy. Partition cache-write privileges by trust domain and test attempted mutation, not just cooperative use.

4. Reproducible benchmark design

The benchmark should answer:

At equal task correctness and useful throughput, how much filesystem capacity does each approach consume at 1, 5, 10, and 20 workspaces—before, during, and after real work?

A. Publish the experiment manifest

Each run must include repository commit IDs, lockfile digests, exact create/install/build/test commands, tool versions, environment variables, OS/kernel, filesystem and mount options, storage hardware, CPU/RAM limits, compression settings, network conditions, and retention policy.

Define N as task workspaces, excluding the administrative repository and seed from the count—but including their storage in the total.

Use a disposable test volume or isolated test directory. Never discover and delete existing user worktrees as part of the benchmark.

B. Use two classes of fixtures
Fixture	Purpose
Deterministic synthetic filesystem fixture	Separate byte-copy, metadata, COW divergence, and lazy hydration effects. A concrete v1 could contain 32,768 × 4 KiB files and 128 × 1 MiB files, with content generated as SHAKE256("angle5:v1:" + path). Add separately identified dependency/output trees and fixed mutation scripts. This is a mechanism test, not an application-build benchmark.
Pinned real workloads	At least one dependency-heavy JavaScript repository, one Python project with native/package-environment concerns, and one Rust/C++ project with substantial compiled output. Add a representative affected user workload when available. Freeze actual commands and expected tests before comparing backends.

Include both narrow tasks and repository-wide tasks. A tiny research-notes repository is not a sufficient representative workload for this problem.

C. Compare credible baselines

The baseline should be ordinary linked worktrees with the project’s normal package-manager caches, not deliberately wasteful independent downloads.

Compare it against each of the five approaches, relevant configured substitutes such as Worktrunk/stol, and the most promising combination. Unsupported combinations should be recorded as unsupported—not silently replaced by full copies and labelled “COW.”

Run a separate scheduling experiment comparing twenty persistent task environments with twenty tasks using a bounded active pool. That tests a different hypothesis from filesystem deduplication and should not be blended into its results.

D. Measure the complete lifecycle
Stage	Required operation and observation
Preparation	Acquire the repository; prepare dependency stores, images, seeds, and remote state. Record one-time time, network, and storage costs.
Creation at N = 1/5/10/20	Measure serial creation and simultaneous fan-out separately. Record metadata-visible time and genuinely usable workspace time.
Install / clean build / test	Record each phase independently, including peak storage and the same required test suite.
Warm incremental work	Apply deterministic distinct edits per task; rebuild and retest. Measure sharing retained after useful work.
Divergence	Change dependencies in selected tasks, regenerate large outputs, rename/delete files, and run a broad refactor/search workload.
Retention / reuse	Park tasks, remove half the workspaces, recreate them, and measure warm reuse plus retained seed/cache cost.
Recovery / GC	Kill workers/controllers at defined points, restore state, expire eligible leases, collect garbage, and verify actual reclamation.

A directory appearing immediately is not enough to count a lazy workspace as ready. The ready metric must include a successful required read/command and the necessary environment setup.

E. Record three different size concepts

Apparent size describes logical file lengths. Allocated-per-file size describes referenced allocation but may count shared COW extents repeatedly. Unique physical allocation and capacity consumption require filesystem-aware accounting.

These GNU commands are useful diagnostics, not interchangeable physical measurements:

Bash
du --apparent-size --count-links -s -B1 "$ROOT"
du -s -B1 "$ROOT"
df -B1 "$MOUNT"

# Btrfs only:
btrfs filesystem du --raw -s "$ROOT"

GNU du distinguishes apparent size and hardlink counting; ordinary results should not be relabelled as unique reflink allocation. Btrfs’s native command uses FIEMAP and explicitly accounts for overlapping shared extents. 
man7.org
+1

Use a quiescent dedicated volume and record filesystem usage/free-space changes, cross-checked with native metadata, compression, and allocation-profile accounting. Report unique data extents separately from total capacity consumed, including metadata. On virtual or thin-provisioned storage, include the host layer.

Charge all repository objects, seeds, dependency stores, hydration caches, container layers, outputs, logs, and checkpoints. For remote backends, report local usage, observable remote usage, and provider-billed storage separately. Mark inaccessible physical metrics unknown, not zero.

Do not accidentally hydrate the benchmark while measuring it. Whole-tree hashing can defeat lazy materialization. Use metadata/backend counters during performance runs; perform exhaustive content validation in a separate correctness run or an explicitly charged final phase.

F. Timing and repeatability

Run cold and warm experiments separately, distinguishing package-cache warmth from OS page-cache warmth. Keep total CPU, memory, and build-job limits equal across backends at each N.

Use at least five randomized repetitions initially; report medians and ranges rather than presenting an unreliable p95. Record creation, install, clean build, incremental build, test, recovery, and GC durations, plus network transfer, peak memory, and filesystem writes.

The principal metrics should include:

Savings
(
𝑁
,
𝑡
)
=
1
−
𝑃
candidate
(
𝑁
,
𝑡
)
𝑃
baseline
(
𝑁
,
𝑡
)
Savings(N,t)=1−
P
baseline
	​

(N,t)
P
candidate
	​

(N,t)
	​

Marginal growth
1
→
20
=
𝑃
(
20
,
𝑡
)
−
𝑃
(
1
,
𝑡
)
19
Marginal growth
1→20
	​

=
19
P(20,t)−P(1,t)
	​


Also report peak capacity, storage byte-hours, completed correct tasks per hour, and bytes actually reclaimed after retirement. These prevent a design from “winning” by excluding its base cache or retaining expensive state indefinitely.

G. Recovery and isolation must be pass/fail tests

Test concurrent dependency divergence and independent edits, including in-place writes, truncation, rename, deletion, permission changes, and large-output regeneration. Verify that untouched workspaces and shared bases remain unchanged.

Inject termination during creation, installation, hydration, checkpointing, and garbage collection. Add quota exhaustion and unavailable/corrupted cache entries. Recovery must preserve staged, unstaged, and relevant untracked work—not merely the last commit.

A proposed safe retirement sequence is: stop writers, establish a durable checkpoint, verify restoration, retire the workspace, then collect unreferenced cache state. Secrets require separate handling; do not automatically commit every ignored file.

Git’s worktree prune removes stale administrative records, not the large contents of still-existing workspaces. Package caches also need their supported cleanup paths: uv explicitly warns against direct cache modification and provides coordinated cleanup operations. 
Git
+1

5. Falsification criteria and where to focus

The following are proposed preregistered product gates, not observed results:

Hypothesis	Evidence that should reject or narrow it
Storage improvement is material	At N=10 and N=20, post-build and post-divergence physical savings fail a chosen target—suggest 50% for a substantial new runtime—after charging seeds, caches, and metadata.
Savings survive useful work	Benefits appear only immediately after creation, then disappear through hydration, installation, or rebuilds. Reclassify as startup acceleration rather than sustained storage reduction.
Performance remains acceptable	Suggest rejecting configurations with more than 20% median end-to-end slowdown, unless users explicitly prefer that capacity tradeoff.
Isolation and recovery are correct	Any cross-workspace mutation, wrong dependency selection, missed required test, or unrecoverable acknowledged checkpoint is a hard failure.
A new product adds value	Correctly configured existing tools solve the problem with comparable savings and less operational burden. Integrate or contribute upstream instead.
Remote execution improves economics	Local savings merely shift a larger cost to persistent remote sandboxes, duplicated remote outputs, or operational overhead. Report the shift, not a global storage win.
Challenge the goal before committing to infrastructure

Twenty tasks do not necessarily require twenty simultaneously resident build environments. The Reddit discussion itself includes a bounded-worktree reuse strategy. A lifecycle manager may address much of the pain without inventing another filesystem. 
Reddit

Similarly, minimizing bytes is not the ultimate objective. Aggressively deleting caches can produce expensive rebuilds; retaining everything can exhaust storage. Optimize correct task throughput under a storage budget, with predictable recovery and low user effort.

Recommended focus

Near term: a storage-budget controller over existing workspace tools. Start with a category census and trustworthy physical accounting; then select sparse scopes, safe dependency import, or COW preparation based on the actual workload and volume. Add bounded active workspaces, explicit fallback reporting, and recoverable cleanup. Worktrunk and stol should be benchmark competitors and possible integration points, not ignored substitutes. 
Worktrunk

Longer term: a hardened layered workspace runtime. Pursue shared immutable dependency/build layers, bounded hydration, quotas, and crash-safe private state only if measured workloads show durable benefits beyond configured existing tools. ArtifactFS lowers the novelty of lazy Git mounting; the opportunity is making the entire runnable environment economical and dependable.

Competition-shaped MVP: remote task leases with explicit local-disk avoidance. Workers can coordinate task state, Artifacts can version source, and sandboxes can execute. Demonstrate bounded active environments, recoverable parking, and a transparent local/remote storage ledger. Keep the backend replaceable and reject out-of-limit repositories explicitly.

Bottom line: The strongest opportunity is not “Git forks that are cheap.” It is independent agent workspaces whose total storage cost stays bounded after installation, builds, edits, failures, and cleanup. Prove that property against existing tools before building a new platform.

## Captured citation links

- [Git](https://git-scm.com/docs/git-worktree.html)
- [Worktrunk](https://worktrunk.dev/step/)
- [BTRFS Documentation](https://btrfs.readthedocs.io/en/latest/btrfs-filesystem.html)
- [Reddit](https://www.reddit.com/r/ClaudeCode/comments/1qokhp0/holy_disk_space_wtf/)
- [Dan Malone Apps](https://www.dan-malone.com/blog/ralph-wiggum-orchestrating-ai-agents?utm_source=chatgpt.com)
- [Hacker News](https://news.ycombinator.com/item?id=49606281)
- [Git](https://git-scm.com/docs/git-sparse-checkout)
- [Git +1](https://git-scm.com/docs/git-worktree.html)
- [pnpm](https://pnpm.io/settings/node-modules)
- [Astral Docs +1](https://docs.astral.sh/uv/reference/settings/)
- [yarnpkg.com +1](https://yarnpkg.com/features/pnp)
- [BTRFS Documentation](https://btrfs.readthedocs.io/en/latest/Reflink.html)
- [Worktrunk](https://worktrunk.dev/step/)
- [Worktrunk](https://worktrunk.dev/step/)
- [Linux Kernel Documentation +1](https://docs.kernel.org/filesystems/overlayfs.html)
- [Cloudflare Docs](https://developers.cloudflare.com/artifacts/guides/artifact-fs/)
- [GitHub](https://github.com/facebook/sapling)
- [Cloudflare Docs](https://developers.cloudflare.com/artifacts/examples/sandbox-sdk-artifacts/)
- [Cloudflare Docs +1](https://developers.cloudflare.com/artifacts/platform/changelog/)
- [Cloudflare Docs](https://developers.cloudflare.com/artifacts/platform/pricing/)
- [Worktrunk +1](https://worktrunk.dev/step/)
- [BTRFS Documentation +1](https://btrfs.readthedocs.io/en/latest/Reflink.html)
- [Worktrunk](https://worktrunk.dev/step/)
- [Microsoft Learn](https://learn.microsoft.com/en-us/windows/win32/fileio/block-cloning)
- [Microsoft Learn](https://learn.microsoft.com/en-us/windows/win32/fileio/block-cloning)
- [Microsoft Learn +1](https://learn.microsoft.com/en-us/windows/wsl/disk-space)
- [Git](https://git-scm.com/docs/git-worktree.html)
- [man7.org +1](https://man7.org/linux/man-pages/man1/du.1.html)
- [Git +1](https://git-scm.com/docs/git-worktree.html)
- [Reddit](https://www.reddit.com/r/ClaudeCode/comments/1qokhp0/holy_disk_space_wtf/)
- [Worktrunk](https://worktrunk.dev/step/)
