#!/usr/bin/env bash
set -u
set -o pipefail
cd /home/alexey/git/cloudflare-agent-git || exit 1
role="$1"
export PATH="$PWD/scripts/agent-bin:$PATH"
mkdir -p .local
for round in $(seq 1 12); do
  [ -f "coordination/$role.stop" ] && exit 0
  if [ "$role" = claude ] && [ "$round" -gt 1 ]; then exit 0; fi
  prompt="You are the $role principal in /home/alexey/git/cloudflare-agent-git. Read AGENTS.md, BRIEF.md, coordination/RESOURCE-POLICY.md, coordination/USER-STEERING.md, experiment/EXPERIMENT.md, your existing coordination file, peer outputs and aplexer inbox. This is execution round $round: advance the authorized research and debate autonomously. Start the required ZCode delegate early. Save incremental evidence, real source URLs and your own coordination/$role.md. Work with the other principal via durable acknowledged messages. Commit/push explicit owned paths under the git flock. Do not invent results, citations or peer agreement. Research/orchestrator inputs may arrive asynchronously. On later rounds resume from durable files instead of repeating research. After research consensus, continuously guide your ZCode team and independently validate your lane, periodically challenge peers and document decisions per USER-STEERING.md. Do not stop merely because research is complete. Print only a short final status."
  printf '%s round %s started %s\n' "$role" "$round" "$(date -Is)" >> ".local/$role-lifecycle.log"
  if [ "$role" = codex ]; then
    timeout 4h codex exec --sandbox danger-full-access -c approval_policy='"never"' -o ".local/$role-final-$round.md" "$prompt" 2>&1 | tee ".local/$role-$round.log"
  else
    timeout 4h claude -p --permission-mode auto --verbose --output-format stream-json "$prompt" 2>&1 | tee ".local/$role-$round.log"
  fi
  rc=$?
  printf '%s round %s exit %s %s\n' "$role" "$round" "$rc" "$(date -Is)" >> ".local/$role-lifecycle.log"
  [ -f "coordination/$role.stop" ] && exit 0
  [ "$rc" -eq 124 ] && exit "$rc"
  [ "$rc" -ne 0 ] && exit "$rc"
  sleep 120
done

[ -f "coordination/$role.stop" ] || exec bash scripts/principal-loop.sh "$role"
