#!/usr/bin/env bash
set -u
cd /home/alexey/git/cloudflare-agent-git || exit 1
role="$1"
mkdir -p ".local/$role" "research/$role"
round=0
failures=0
while [ ! -f "coordination/$role.stop" ]; do
  round=$((round+1))
  prompt="You are $role, an independently responsible peer in /home/alexey/git/cloudflare-agent-git. User explicitly requested your engine to run, challenge the goal/task, improve the approach, coordinate with other agents, continuously validate viability and later guide ZCode teams. Read AGENTS.md, CLAUDE.md, BRIEF.md, coordination/USER-STEERING.md and experiment/EXPERIMENT.md; latest user steering supersedes earlier stop-after-research assumptions. Read your durable research and aplexer inbox as your true identity. Round $round. You own research/$role/ and coordination/$role.md; do not edit peers' paths. First write an independent challenge of the mission/selection/architecture and improvements with real evidence, tradeoffs and kill tests; send compact durable critiques to claude-principal and codex-principal and obtain responses. Later evolve into your assigned lane or comparative-review role and guide scoped ZCode executors in isolated worktrees. Read ~/git/.agents/skills/external-model-agents/SKILL.md, a2a-communication/SKILL.md and telegram-writing-assistant social research guide. Do not confuse research ideas with proven viability. Save progress incrementally and publish sanitized owned files under flock .local/git.lock with explicit paths. Append major decisions/events under flock .local/events.lock. Seek adversarial peer review at material milestones and at least daily; work between daily standups. No unbounded spawning, secrets, purchases, unrelated infra changes or final competition submission. Print only a short status; next rounds resume from files instead of repeating completed work. If blocked, write exact blocker and useful independent work remaining."
  printf '%s round %s started %s\n' "$role" "$round" "$(date -Is)" >> ".local/$role/lifecycle.log"
  case "$role" in
    grok) timeout 4h grok --cwd "$PWD" --permission-mode auto -p "$prompt" > ".local/$role/round-$round.log" 2>&1 ;;
    antigravity) timeout 4h env -u GEMINI_API_KEY -u GOOGLE_API_KEY agy --dangerously-skip-permissions --effort high --print-timeout 0 --output-format json -p "$prompt" > ".local/$role/round-$round.json" 2> ".local/$role/round-$round.log" ;;
    space-bunny) timeout 4h opencode run --auto --model opencode/space-bunny-free --format json --title "Cloudflare experiment Space Bunny round $round" "$prompt" > ".local/$role/round-$round.log" 2>&1 ;;
    muse) timeout 4h opencode run --auto --model opencode/muse-spark-1.3-contributor-free --format json --title "Cloudflare experiment Muse 1.3 round $round" "$prompt" > ".local/$role/round-$round.log" 2>&1 ;;
    zcode) timeout 4h zcodex exec --sandbox danger-full-access -c approval_policy='"never"' -o ".local/$role/final-$round.md" "$prompt" > ".local/$role/round-$round.log" 2>&1 ;;
    *) exit 2 ;;
  esac
  rc=$?
  printf '%s round %s exit %s %s\n' "$role" "$round" "$rc" "$(date -Is)" >> ".local/$role/lifecycle.log"
  if [ "$rc" -ne 0 ]; then
    failures=$((failures+1))
    printf 'CLI round %s failed with exit %s; failures %s. Inspect private .local/%s logs.\n' "$round" "$rc" "$failures" "$role" > "coordination/$role-runtime.md"
    # Avoid hammering rate limits or failed auth. Daily standup can recover configuration.
    sleep 1800
  else
    failures=0
    sleep 120
  fi
done
