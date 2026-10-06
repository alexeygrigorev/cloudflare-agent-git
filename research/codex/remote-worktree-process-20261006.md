# Remote worktree development process — 6 October 2026

The codex-zcode development process is implemented and independently reviewed at
[commit 63f03b79f9720226af770533daa8bdc868719d63](https://github.com/alexeygrigorev/codex-zcode/commit/63f03b79f9720226af770533daa8bdc868719d63),
on preserved branch `process/storagebox-development`. Remote branch SHA was verified.
Changed files: `ABOUT.md`, `AGENTS.md`, `scripts/storagebox-dev.sh`,
`scripts/build-zcode-bundle.sh`. The clean integration [PR #56](https://github.com/alexeygrigorev/codex-zcode/pull/56)
was independently accepted and merged through the normal GitHub route. Fork main
is `555e784fc36753ff777a35b1e4bffaaa8c35de68`, verified by `git ls-remote`;
its tree `79f78aaa20be8438b65512c64a80deae1f820853` matches the reviewed tree.
Every other base path/blob/mode was independently verified preserved.
Original PR #55 was closed because its source ancestry included an unrelated
test commit; the correction applied only the accepted four-file commit to
current main. Both source branches remain preserved.

The actual wrapper selects the existing `~/storagebox` SSHFS mount, fails closed
when absent or unusable, places new worktrees under
`~/storagebox/worktrees/codex-zcode/TASK`, and selects per-task output under
`~/storagebox/targets/codex-zcode/TASK`, `~/storagebox/tmp/codex-zcode/TASK`,
and `~/storagebox/build-output/codex-zcode/TASK`. A local per-task lock rejects
concurrent commands targeting the same output. The default server workflow is
in the startup instructions and Quick Build process; independent direct local/CI
commands retain normal Cargo behavior.

```bash
scripts/storagebox-dev.sh worktree TASK HEAD
cd ~/storagebox/worktrees/codex-zcode/TASK
scripts/storagebox-dev.sh paths
# Only after resource/build admission permits compilation:
scripts/storagebox-dev.sh run sh -c 'cd codex-rs && cargo build --profile dev-small -p codex-cli --bin zcodex'
```

A genuine tiny linked worktree used remote source and a tiny shell executable
in the remote target while retaining Git metadata locally. Independent review
verified that executable and Git integrity, plus 17 mock/negative cases covering
mount absence, wrong filesystem, target selection, relative bundle paths,
missing artifacts, path traversal/symlink escape, timeout and writer exclusion.
Bash syntax and shellcheck passed. A private 26,936-byte `/usr/bin/true` copy also executed from the remote target:
ELF64 PIE, matching source SHA, exit code zero in 0.0204 seconds. Only the owned
proof file was removed. This is executable-mapping evidence, not build timing.
No Rust compilation, real provider call,
full-size performance, reboot or forced mount outage was tested.

`just fmt` delegates to the whole-repository formatter, including DotSlash and
`uv run` commands which may download tools/dependencies and modify unowned Rust,
Bazel and Python files. It was inspected but not run under the task's no-download
and owned-file boundaries. No Rust source changed.

[Remote drive setup was added to the existing gist](https://gist.github.com/alexeygrigorev/5c1135fdfce97d3938a24c0f3dcc0ab2#file-09-remote-drive-md).
Fetched remote content verified the addition's SHA256
`1493699e3ce30e2b122a26a14de72a4558a08275ed1d2d1a1b678309249075f5`
and all ten existing files and the description unchanged.

Existing worktrees, target caches, installed local launcher/runtime and healthy
mount service remain preserved. SSHFS can slow metadata-heavy builds and
interrupt writes; remote capacity does not lift existing build/resource holds.
The local launcher and ordinary Git backup remain the recovery paths.
Independent acceptance: [review record](remote-worktree-process-review-20261006.md).


## Integration checkpoint awaiting final review

The fork main advanced to `71d987c3e0ec1a9915b4f4f26c63df97df9e05cf`. [PR55](https://github.com/alexeygrigorev/codex-zcode/pull/55) is open for the reviewed process branch; the conflict-free candidate merge tree is `e26ae7d9bdda58e7501fcefb3d531481c64252bf`. Separate final integration review and ordinary merge remain pending at this checkpoint. Source-branch acceptance and the published setup guide do not yet establish default-main integration.

A further worker-reported bounded check copied the existing 26,936-byte `/usr/bin/true` ELF64 PIE to its owned remote target, verified equal hashes, ran it with exit0 in0.0204s and removed only that copied proof file. This demonstrates this tiny executable can run from the remote target; it is not a Rust build, full-size performance result or runtime relocation.
