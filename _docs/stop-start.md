# Stopping and starting the root systems

Status as of 15 Oct 2026: both roots are stopped. Only ever run one root.

## Hetzner headless root (systemd user timer)

The single command `scripts/root/rootctl stop|start|status` (run from the repo) also handles this timer, plus the hub scheduling flag once the hub has one.

Runs `scripts/root/headless-root-run.sh` every 30 min (:07 and :37). Unit files: `headless-root.service` and `headless-root.timer` in the `scripts/root/` folder. State is in `~/.local/state/headless-root/`.

- Stop: `systemctl --user disable --now headless-root.timer`
- Start: `systemctl --user link ~/git/cloudflare-agent-git/scripts/root/headless-root.service ~/git/cloudflare-agent-git/scripts/root/headless-root.timer && systemctl --user enable --now headless-root.timer`
- Status: `systemctl --user list-timers headless-root.timer`

Stopped 15 Oct 06:27 Berlin. Disabling removes the linked unit files, so starting needs the `link` step again.

## Win35 root guardian (Windows Task Scheduler)

Task `\Win35Root-Guardian` was created 8 Oct 2026 during the Win35 root bootstrap. It runs as the user every minute (start 2026-10-08 17:32, no end). Each run:

1. checks the SHA-256 of `opencode_guardian_runtime.py` under `C:\Users\User\git\cloudflare-agent-git\.local\win35-root-bootstrap\operational-runtime1\channel-drain-succession121\factory-domain-shortstore-r9\operator-r9\source20\`;
2. checks the SHA-256 of the uv CPython 3.14.8 `python.exe`;
3. runs `python.exe -I -S opencode_guardian_runtime.py Guard <pinned hash>`, which keeps the old Win35 OpenCode root and supervisor alive.

The rest of the bootstrap is in `.local\win35-root-bootstrap\` on Win35. It is local only and not in git.

- Stop: `schtasks /end /tn "\Win35Root-Guardian"; schtasks /change /tn "\Win35Root-Guardian" /disable`
- Start: `schtasks /change /tn "\Win35Root-Guardian" /enable` (it starts within a minute)
- Status: `schtasks /query /tn "\Win35Root-Guardian" /fo list`

Disabled 15 Oct 08:35 Berlin.

## Other things still running on Hetzner

These were not stopped:
- `principal-ping.timer`
- `supervision-watcher-{1,2}.timer`
- `desktop-orchestrator-watchdog.timer`
- the aplexer principal and head sessions

Stop any of them with `systemctl --user disable --now <name>.timer`.
