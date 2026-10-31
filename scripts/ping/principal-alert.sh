#!/usr/bin/env bash
# Alert hook for scripts/ping/principal-ping.py (PRINCIPAL_ALERT_CMD).
# principal-ping passes the text in $PING_ALERT_MESSAGE. Reconstructed and put in
# git after ~/.local/bin was wiped (agent-hub incident 504d662b, 2026-10-31).
# Delivery: e-mail via the user's msmtp (~/.msmtprc, never in git) to ops, plus a
# local log line so an alert is never silently lost.
set -u
msg="${PING_ALERT_MESSAGE:-${1:-principal-ping alert (no message)}}"
to="${PRINCIPAL_ALERT_TO:-dev@dtcdev.click}"
log="${PRINCIPAL_ALERT_LOG:-$HOME/.local/state/principal-ping/alerts.log}"
mkdir -p "$(dirname "$log")"
ts=$(date -u +%FT%TZ)
printf '%s %s\n' "$ts" "$msg" >> "$log"
if command -v msmtp >/dev/null 2>&1; then
  printf 'To: %s\nSubject: [principal-ping] %s\n\n%s\n\nhost: %s\ntime: %s\n' \
    "$to" "${msg:0:120}" "$msg" "$(hostname)" "$ts" | msmtp -- "$to" \
    || { echo "$ts msmtp failed" >> "$log"; exit 1; }
else
  echo "$ts msmtp missing; alert only logged" >> "$log"; exit 1
fi
