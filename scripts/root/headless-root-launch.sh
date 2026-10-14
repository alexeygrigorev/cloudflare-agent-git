#!/usr/bin/env bash
# systemd --user entry point: place the run in its own transient user scope
# (survives SSH logout; Linger=yes) with memory/pids limits.
set -euo pipefail
# --scope inherits the caller environment. Strip raw Hub values before even
# systemd-run is invoked; explicit nonsecret HR_HUB_* binding is retained.
for hub_env_key in ${!HUB_@}; do unset "$hub_env_key"; done
unset INVOCATION_ID  # Caller service invocation does not identify this scope.
here=$(cd "$(dirname "$0")" && pwd)
# Forward the Hub binding hooks only when the caller actually set them; an
# injected empty value would look "set but empty" to the run script's
# fail-closed validation. Validation itself stays in headless-root-run.sh, which
# remains the only owner of root.lock/state.json.
extra=()
for kv in HR_RUN_ID HR_HUB_JOB_ID HR_HUB_LEASE_EPOCH HR_HUB_HOST_ID \
          HR_HUB_LAUNCHER_TASK_ID HR_HUB_LAUNCHER_UNIT HR_HUB_FIRST_ACTION_FILE \
          HR_HUB_START_ACK_FILE HR_HUB_START_ACK_WAIT_SEC HR_PID_NAMESPACE_EXPECTED; do
  if [[ -n ${!kv:-} ]]; then extra+=("$kv=${!kv}"); fi
done
# A Hub-supplied unit name becomes the REAL scope name so the run script can
# compare it with the cgroup the manager actually put it in; otherwise generate one.
unit=${HR_HUB_LAUNCHER_UNIT:-headless-root-$(date +%Y%m%d%H%M%S)-$$}
if [[ ! $unit =~ ^[A-Za-z0-9][A-Za-z0-9._@-]{0,127}$ ]]; then
  printf 'headless-root-launch: invalid HR_HUB_LAUNCHER_UNIT: %s\n' "$unit" >&2
  exit 78
fi
# Raw Hub environment is stripped above; scope children inherit only public binding.
exec systemd-run --user --scope --collect --quiet \
  --unit="$unit" \
  -p MemoryMax=${HR_MEMORY:-2500M} -p TasksMax=${HR_PIDS:-512} \
  env -u APLEXER_SESSION_ID -u APLEXER_TAG -u APLEXER_WORKSPACE \
  ${extra[@]+"${extra[@]}"} "$here/headless-root-run.sh"
