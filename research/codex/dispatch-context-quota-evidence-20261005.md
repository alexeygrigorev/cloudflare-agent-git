# Quota checks inherit the dispatch context

On October5 at12:15UTC, the launcher head reported Gemini quota reads failing with `pthread_create EAGAIN` and no usable windows. A principal quota read on the same host completed at12:11:52UTC with statusok, 100% five-hour and63.02% weekly remaining. This is not evidence of account exhaustion. It suggests a local dispatch resource difference; the precise failing syscall/context remains to be measured.

The head workload cgroup was independently sampled at12:06:27UTC:79 of100 PID/thread slots, cumulative `pids.events max2730`. That cumulative count cannot attribute a particular launch. Worker and controller counts must remain separate.

Installed quse resolves to `/home/alexey/git/quse/.venv/bin/quse`. Source HEAD `3837902e1c9cbfe0969b9241d6cea2441ab3ceab`, `quse/gemini_quota.py:325`, starts AGY with `-p /quota --output-format json` and a15-second subprocess timeout. Quota checking therefore includes a real CLI child in the caller cgroup. The existing candidate sibling controller's64-task ceiling may also be insufficient; measure it rather than replacing the head's100 ceiling with another untested assumption.

Launcher head genuinely accepted carrying reviewed guards into its existing sibling-controller candidate, followed by one bounded useful task and quota/controller descendant measurement. Preserve failed IDs, fresh admission, each worker's100-task ceiling, RAM/disk limits, and ordinary Git recovery. No principal implementation, direct model bypass, new service or Rust build is authorized by this diagnosis.
