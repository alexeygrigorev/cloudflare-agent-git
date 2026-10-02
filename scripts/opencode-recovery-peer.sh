#!/usr/bin/env bash
# opencode-recovery-peer.sh — bounded headless OpenCode peer launcher (opencode-recovery owner)
# Workaround route: installed baseline executable + isolated XDG data/config + --pure
# + authenticated opencode-go models (unauth opencode/*-free route hung; see
# coordination/opencode-recovery.md). Bounded retry loop with backoff; stops on
# coordination/<role>.stop. Shared orchestrator scripts/peer-loop.sh intentionally NOT edited.
set -u
set -o pipefail
REPO=/home/alexey/git/cloudflare-agent-git
cd "$REPO" || exit 1
role="$1"
case "$role" in
  muse-reviewer)    model="opencode-go/muse-spark-1.3-contributor"; logdir=".local/muse" ;;
  space-bunny-head) model="opencode-go/space-bunny-free";          logdir=".local/space-bunny" ;;
  *) echo "unknown role $role" >&2; exit 2 ;;
esac
prompt_file=".local/opencode-recovery/prompts/$role.txt"
oc="/home/alexey/.nvm/versions/node/v24.13.1/lib/node_modules/opencode-ai/node_modules/opencode-linux-x64-baseline/bin/opencode"
export XDG_DATA_HOME="$REPO/.local/opencode-isolated"
export XDG_CONFIG_HOME="$REPO/.local/opencode-config"
mkdir -p "$logdir" "research/${role%-*}" 2>/dev/null
max_attempts=3
for attempt in 1 2 3; do
  [ -f "coordination/$role.stop" ] && { echo "$role stop file present; exiting" ; exit 0; }
  printf '%s recovered round %s started %s model=%s\n' "$role" "$attempt" "$(date -Is)" "$model" >> "$logdir/recovered-lifecycle.log"
  label="$role recovered round $attempt"
  timeout 100m "$oc" run --pure --print-logs --format json --auto \
    --title "$label" --model "$model" \
    "$(cat "$prompt_file")" 2>&1 | tee "$logdir/recovered-round-$attempt.log"
  rc=${PIPESTATUS[0]}
  printf '%s recovered round %s exit %s %s\n' "$role" "$attempt" "$rc" "$(date -Is)" >> "$logdir/recovered-lifecycle.log"
  if [ "$rc" -eq 0 ]; then
    exit 0
  fi
  {
    printf '%s recovered round %s failed exit %s at %s; bounded backoff before retry.\n' \
      "$role" "$attempt" "$rc" "$(date -Is)"
  } >> "$logdir/recovered-lifecycle.log"
  sleep $((120 * attempt))
done
printf '%s all %s attempts failed; see %s/recovered-lifecycle.log\n' "$role" "$max_attempts" "$logdir" \
  >> "$logdir/recovered-lifecycle.log"
exit 1
