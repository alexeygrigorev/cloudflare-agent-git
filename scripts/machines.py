#!/usr/bin/env python3
"""Team work machines: load the registry and select available hosts at run time.

Source of truth: coordination/MACHINES.json (no on/off status field).

Each machine records how it connects:
- ``inbound-ssh`` (Hetzner): available when an ssh BatchMode probe answers;
  work can be started there over ssh.
- ``outbound-bus`` (Win35, the founder's laptop): home-network machines that
  accept no inbound connections. Nothing ever ssh-es into them. They connect
  out to the Agent Bus on the hub (Hetzner) and are available iff they checked
  in on the bus within the freshness window. Work reaches them as bus messages
  they pull from their inbox; they talk to each other through the bus.

Check-ins are read from the bus's own records on the hub: the role authority
(port 8801) presence rows (agents.seen, live role leases) and the Agent Bus
FileBus store (messages sent, ack/accept/complete of messages addressed to the
machine's identities). Root (Grok Bot Cloudflare Root) coordinates; there is no
competing root.
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = ROOT / "coordination" / "MACHINES.json"
DEFAULT_CONNECT_TIMEOUT = 10
DEFAULT_CHECKIN_WINDOW = 900  # seconds; override with registry bus.checkin_window_seconds or env
CHECKIN_WINDOW_ENV = "MACHINES_CHECKIN_WINDOW_SECONDS"
BUS_STORE_ENV = "MACHINES_BUS_STORE"

INBOUND_SSH = "inbound-ssh"
OUTBOUND_BUS = "outbound-bus"
CONNECT_MODES = (INBOUND_SSH, OUTBOUND_BUS)
_STATUS_FIELDS = ("status", "online", "offline")


class RouteError(ValueError):
    """Raised when work would be routed over a path the machine does not accept."""


def load_registry(path: Optional[os.PathLike] = None) -> dict[str, Any]:
    reg_path = Path(path) if path else Path(os.environ.get("MACHINES_REGISTRY", DEFAULT_REGISTRY))
    with open(reg_path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict) or not isinstance(data.get("machines"), list):
        raise ValueError(f"machines registry must be an object with a machines list: {reg_path}")
    for m in data["machines"]:
        if not isinstance(m, dict) or "id" not in m:
            raise ValueError(f"each machine needs an id: {m!r}")
        if any(k in m for k in _STATUS_FIELDS):
            raise ValueError(f"machines registry must not carry on/off status fields: {m!r}")
        conn = m.get("connect")
        if not isinstance(conn, dict) or conn.get("mode") not in CONNECT_MODES:
            raise ValueError(f"machine {m['id']} needs connect.mode in {CONNECT_MODES}: {m!r}")
        if any(k in conn for k in _STATUS_FIELDS):
            raise ValueError(f"machines registry must not carry on/off status fields: {m!r}")
        if conn["mode"] == INBOUND_SSH and not conn.get("ssh"):
            raise ValueError(f"inbound-ssh machine {m['id']} needs connect.ssh")
        if conn["mode"] == OUTBOUND_BUS:
            if conn.get("ssh") or m.get("ssh"):
                raise ValueError(f"outbound-bus machine {m['id']} must not carry an ssh route")
            if not conn.get("bus_device_ids"):
                raise ValueError(f"outbound-bus machine {m['id']} needs connect.bus_device_ids")
    return data


def list_machines(path: Optional[os.PathLike] = None, roles: Optional[Sequence[str]] = None) -> List[dict[str, Any]]:
    machines = list(load_registry(path)["machines"])
    if roles is None:
        return machines
    wanted = set(roles)
    return [m for m in machines if wanted.intersection(m.get("roles") or [])]


def connect_mode(machine: dict[str, Any]) -> str:
    return str((machine.get("connect") or {}).get("mode") or "")


def ssh_alias(machine: dict[str, Any]) -> Optional[str]:
    """ssh alias for inbound-ssh machines; None for outbound-only machines."""
    if connect_mode(machine) != INBOUND_SSH:
        return None
    return (machine.get("connect") or {}).get("ssh")


def bus_device_ids(machine: dict[str, Any]) -> List[str]:
    return [str(d) for d in (machine.get("connect") or {}).get("bus_device_ids") or []]


def checkin_window(registry: Optional[dict[str, Any]] = None, override: Optional[float] = None) -> float:
    if override is not None:
        return float(override)
    env = os.environ.get(CHECKIN_WINDOW_ENV)
    if env:
        return float(env)
    bus = (registry or {}).get("bus") or {}
    return float(bus.get("checkin_window_seconds") or DEFAULT_CHECKIN_WINDOW)


def probe_ssh(
    alias: str,
    *,
    connect_timeout: int = DEFAULT_CONNECT_TIMEOUT,
    runner: Optional[Callable[..., subprocess.CompletedProcess]] = None,
) -> bool:
    """Return True when the ssh alias answers a BatchMode hostname probe."""
    run = runner or subprocess.run
    try:
        r = run(
            ["ssh", "-o", "BatchMode=yes", "-o", f"ConnectTimeout={connect_timeout}", alias, "hostname"],
            capture_output=True,
            text=True,
            timeout=connect_timeout + 5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return r.returncode == 0


# --- bus check-ins ---------------------------------------------------------

def _parse_ts(value: Any) -> Optional[datetime]:
    if not value or not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def summarize_checkins(
    identities: dict[str, Any],
    messages: Any,
    authority: Optional[dict[str, Any]] = None,
    *,
    now: Optional[datetime] = None,
) -> Dict[str, dict[str, Any]]:
    """Latest check-in per device_id from the bus's own records.

    Signals, all written by the machine's own actions:
    - role authority (port 8801) ``agents.seen``: the native observation time of
      an actor on that host;
    - role authority ``roles``: an unexpired lease held by an actor on that host
      (a lease stays live only while its holder keeps renewing it over mTLS) counts
      as a check-in at ``now``;
    - Agent Bus FileBus store: messages the device's identities sent, and
      ack/accept/complete of messages addressed to them.
    Identity registration alone is NOT a check-in: Hetzner-side enrollment code
    registers identities on a home machine's behalf.

    Returns {device_id: {"last_checkin", "latest_identity", "project_id"}}; never tokens.
    """
    now = now or datetime.now(timezone.utc)
    out: Dict[str, dict[str, Any]] = {}

    def entry(device: str) -> dict[str, Any]:
        return out.setdefault(device, {"last_checkin": None, "latest_identity": None, "project_id": None})

    def bump(device: str, ts: Any) -> None:
        dt = _parse_ts(ts)
        if not device or dt is None:
            return
        cur = entry(device)
        prev = _parse_ts(cur["last_checkin"])
        if prev is None or dt > prev:
            cur["last_checkin"] = dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    dev_of: Dict[str, str] = {}
    latest_reg: Dict[str, tuple] = {}
    for ident_id, ident in (identities or {}).items():
        if not isinstance(ident, dict):
            continue
        device = str(ident.get("device_id") or "")
        dev_of[ident_id] = device
        created = _parse_ts(ident.get("created_at"))
        if device and created is not None and (device not in latest_reg or created > latest_reg[device][0]):
            latest_reg[device] = (created, ident_id, ident.get("project_id"))
    msgs = messages.values() if isinstance(messages, dict) else (messages or [])
    for msg in msgs:
        if not isinstance(msg, dict):
            continue
        bump(dev_of.get(str(msg.get("sender_id")), ""), msg.get("created_at"))
        recipient_dev = dev_of.get(str(msg.get("recipient_id")), "")
        for field in ("acked_at", "accepted_at", "outcome_at"):
            bump(recipient_dev, msg.get(field))
    for agent in (authority or {}).get("agents") or []:
        seen = agent.get("seen")
        if isinstance(seen, (int, float)) and seen > 0:
            bump(str(agent.get("host") or ""), datetime.fromtimestamp(seen, timezone.utc).isoformat())
    for lease in (authority or {}).get("leases") or []:
        exp = lease.get("expires")
        if isinstance(exp, (int, float)) and exp > now.timestamp():
            bump(str(lease.get("host") or ""), now.isoformat())
    for device, (_dt, ident_id, project) in latest_reg.items():
        entry(device)["latest_identity"] = ident_id
        out[device]["project_id"] = project
    return out


def read_authority_presence(config_path: os.PathLike) -> dict[str, Any]:
    """Read-only presence rows from the role authority SQLite (agents.seen, live leases)."""
    import sqlite3

    with open(config_path, encoding="utf-8") as f:
        db_path = json.load(f)["authority_db"]
    con = sqlite3.connect(Path(db_path).as_uri() + "?mode=ro", uri=True)
    try:
        con.execute("PRAGMA query_only=ON")
        agents = [{"host": h, "seen": s} for h, s in con.execute("SELECT host, seen FROM agents")]
        leases = [
            {"host": h, "expires": e}
            for h, e in con.execute(
                "SELECT a.host, r.expires FROM roles r JOIN agents a ON a.id = r.holder WHERE r.holder IS NOT NULL"
            )
        ]
    finally:
        con.close()
    return {"agents": agents, "leases": leases}


def read_checkins_from_store(
    store: os.PathLike, authority_config: Optional[os.PathLike] = None
) -> Dict[str, dict[str, Any]]:
    store = Path(store)

    def load(name: str, default: Any) -> Any:
        p = store / name
        if not p.is_file():
            return default
        with open(p, encoding="utf-8") as f:
            return json.load(f)

    authority = None
    if authority_config and Path(authority_config).is_file():
        try:
            authority = read_authority_presence(authority_config)
        except Exception:  # presence is advisory; never break selection
            authority = None
    return summarize_checkins(load("identities.json", {}), load("messages.json", {}), authority)


_REMOTE_SUMMARY = r"""
import json, sqlite3, sys
from pathlib import Path
store = Path(sys.argv[1]).expanduser()
def load(n, d):
    p = store / n
    return json.loads(p.read_text(encoding='utf-8')) if p.is_file() else d
ids = load('identities.json', {})
msgs = load('messages.json', {})
ids = {k: {f: v.get(f) for f in ('device_id', 'created_at', 'project_id')} for k, v in ids.items() if isinstance(v, dict)}
it = msgs.values() if isinstance(msgs, dict) else msgs
fields = ('sender_id', 'recipient_id', 'created_at', 'acked_at', 'accepted_at', 'outcome_at')
msgs = [{f: m.get(f) for f in fields} for m in it if isinstance(m, dict)]
authority = None
if len(sys.argv) > 2 and Path(sys.argv[2]).expanduser().is_file():
    try:
        db = json.loads(Path(sys.argv[2]).expanduser().read_text(encoding='utf-8'))['authority_db']
        con = sqlite3.connect(Path(db).as_uri() + '?mode=ro', uri=True)
        con.execute('PRAGMA query_only=ON')
        authority = {
            'agents': [{'host': h, 'seen': s} for h, s in con.execute('SELECT host, seen FROM agents')],
            'leases': [{'host': h, 'expires': e} for h, e in con.execute(
                'SELECT a.host, r.expires FROM roles r JOIN agents a ON a.id = r.holder WHERE r.holder IS NOT NULL')],
        }
        con.close()
    except Exception:
        authority = None
print(json.dumps({'identities': ids, 'messages': msgs, 'authority': authority}))
"""


def read_checkins(
    registry: Optional[dict[str, Any]] = None,
    *,
    runner: Optional[Callable[..., subprocess.CompletedProcess]] = None,
    connect_timeout: int = DEFAULT_CONNECT_TIMEOUT,
) -> Dict[str, dict[str, Any]]:
    """Read check-ins from the bus records: locally when present, else read-only from the hub.

    On the hub (or with MACHINES_BUS_STORE pointing at a copy) the store is read
    directly. Elsewhere (root on the shared Linux computer) the hub is reached by
    its ssh alias and a read-only summary without tokens or bodies is returned.
    Any failure returns {} (no check-ins known), never raises.
    """
    registry = registry or load_registry()
    bus = registry.get("bus") or {}
    store = os.environ.get(BUS_STORE_ENV) or bus.get("store")
    authority_config = bus.get("role_authority_config")
    if not store:
        return {}
    # Paths in the registry are relative to the hub user's home ("~/..."): expand
    # locally only to test whether this process runs on the hub (or has a copy).
    local_store = Path(os.path.expanduser(str(store)))
    if local_store.is_dir():
        try:
            local_auth = os.path.expanduser(str(authority_config)) if authority_config else None
            return read_checkins_from_store(local_store, local_auth)
        except (OSError, ValueError):
            return {}
    hub = next((m for m in registry["machines"] if m.get("id") == bus.get("hub")), None)
    alias = ssh_alias(hub) if hub else None
    if not alias:
        return {}
    run = runner or subprocess.run
    cmd = ["ssh", "-o", "BatchMode=yes", "-o", f"ConnectTimeout={connect_timeout}", alias,
           "python3", "-c", shlex.quote(_REMOTE_SUMMARY), shlex.quote(str(store))]
    if authority_config:
        cmd.append(shlex.quote(str(authority_config)))
    try:
        r = run(cmd, capture_output=True, text=True, timeout=connect_timeout + 20, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return {}
    if r.returncode != 0:
        return {}
    try:
        snap = json.loads(r.stdout)
    except ValueError:
        return {}
    return summarize_checkins(snap.get("identities") or {}, snap.get("messages") or [], snap.get("authority"))


def last_checkin(machine: dict[str, Any], checkins: Dict[str, dict[str, Any]]) -> Optional[datetime]:
    best = None
    for dev in bus_device_ids(machine):
        dt = _parse_ts((checkins.get(dev) or {}).get("last_checkin"))
        if dt is not None and (best is None or dt > best):
            best = dt
    return best


def checked_in_recently(
    machine: dict[str, Any],
    checkins: Dict[str, dict[str, Any]],
    *,
    now: Optional[datetime] = None,
    window: float = DEFAULT_CHECKIN_WINDOW,
) -> bool:
    seen = last_checkin(machine, checkins)
    if seen is None:
        return False
    now = now or datetime.now(timezone.utc)
    age = (now - seen).total_seconds()
    return -60 <= age <= window  # tolerate small clock skew; future stamps beyond it are ignored


# --- selection -------------------------------------------------------------

def select_available(
    machines: Optional[Iterable[dict[str, Any]]] = None,
    *,
    probe: Optional[Callable[[str], bool]] = None,
    checkins: Optional[Dict[str, dict[str, Any]]] = None,
    now: Optional[datetime] = None,
    window: Optional[float] = None,
    connect_timeout: int = DEFAULT_CONNECT_TIMEOUT,
    path: Optional[os.PathLike] = None,
) -> List[dict[str, Any]]:
    """Return available machines; skip the rest.

    inbound-ssh machines: the ssh probe answers. outbound-bus machines: a bus
    check-in within ``window`` seconds; they are never probed over ssh. An
    unavailable machine is unknown, not dead. When nothing is available the
    list is empty.
    """
    registry = load_registry(path)
    pool = list(machines) if machines is not None else [
        m for m in registry["machines"] if "work" in (m.get("roles") or [])
    ]
    win = checkin_window(registry, window)
    check = probe or (lambda alias: probe_ssh(alias, connect_timeout=connect_timeout))
    available = []
    for m in pool:
        mode = connect_mode(m)
        if mode == INBOUND_SSH:
            alias = ssh_alias(m)
            if alias and check(str(alias)):
                available.append(m)
        elif mode == OUTBOUND_BUS:
            if checkins is None:
                checkins = read_checkins(registry, connect_timeout=connect_timeout)
            if checked_in_recently(m, checkins, now=now, window=win):
                available.append(m)
    return available


# Backwards-compatible name used by launch_gates and earlier callers.
select_reachable = select_available


def find_machine(key: str, *, path: Optional[os.PathLike] = None) -> Optional[dict[str, Any]]:
    k = str(key or "").strip().lower()
    if not k:
        return None
    for m in list_machines(path):
        candidates = {
            str(m.get("id") or "").lower(),
            str(m.get("hostname") or "").lower(),
            str(m.get("execution_target") or "").lower(),
            str(ssh_alias(m) or "").lower(),
        }
        candidates.update(d.lower() for d in bus_device_ids(m))
        candidates.discard("")
        if k in candidates:
            return m
    return None


def resolve_execution_target(
    device_id: Optional[str] = None,
    hostname: Optional[str] = None,
    *,
    path: Optional[os.PathLike] = None,
) -> str:
    """Map a device_id or hostname to the registry execution_target (or id)."""
    for key in (device_id, hostname):
        m = find_machine(key, path=path) if key else None
        if m:
            return str(m.get("execution_target") or m["id"])
    if device_id:
        return str(device_id)
    machines = list_machines(path)
    if machines:
        return str(machines[0].get("execution_target") or machines[0]["id"])
    return "unknown"


def work_route(
    machine: Any,
    *,
    checkins: Optional[Dict[str, dict[str, Any]]] = None,
    path: Optional[os.PathLike] = None,
) -> dict[str, Any]:
    """How to hand work to a machine.

    inbound-ssh -> {"transport": "ssh", "ssh": alias}.
    outbound-bus -> {"transport": "bus", ...}: post a bus message on the hub
    addressed to the machine's current bus identity; the machine pulls it from
    its inbox (/v1/inbox) and answers with ack/accept/complete. Never ssh.
    """
    registry = load_registry(path)
    m = machine if isinstance(machine, dict) else find_machine(str(machine), path=path)
    if not m:
        raise RouteError(f"unknown machine: {machine!r}")
    target = str(m.get("execution_target") or m["id"])
    mode = connect_mode(m)
    if mode == INBOUND_SSH:
        return {"machine": m["id"], "execution_target": target, "transport": "ssh", "ssh": ssh_alias(m)}
    bus = registry.get("bus") or {}
    recipient = None
    if checkins:
        best = None
        for dev in bus_device_ids(m):
            info = checkins.get(dev) or {}
            dt = _parse_ts(info.get("last_checkin"))
            if info.get("latest_identity") and (best is None or (dt and dt > best[0])):
                best = (dt or datetime.min.replace(tzinfo=timezone.utc), info["latest_identity"], dev, info.get("project_id"))
        if best:
            recipient = {"identity_id": best[1], "device_id": best[2], "project_id": best[3]}
    return {
        "machine": m["id"],
        "execution_target": target,
        "transport": "bus",
        "hub": bus.get("hub"),
        "store": bus.get("store"),
        "bus_device_ids": bus_device_ids(m),
        "recipient": recipient,
        "pull": "machine pulls /v1/inbox on the hub, then ack/accept/complete",
        "ssh": None,
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--registry", default=None, help="path to MACHINES.json")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="print the work-machine registry (no status)")
    p_list.add_argument("--json", action="store_true")

    for name in ("available", "reachable"):
        p = sub.add_parser(name, help="ssh-probe inbound machines, read bus check-ins for home machines")
        p.add_argument("--json", action="store_true")
        p.add_argument("--timeout", type=int, default=DEFAULT_CONNECT_TIMEOUT)
        p.add_argument("--window", type=float, default=None, help="check-in freshness window, seconds")

    p_route = sub.add_parser("route", help="print how work reaches a machine (ssh or bus)")
    p_route.add_argument("machine")

    args = ap.parse_args(argv)
    reg = load_registry(args.registry)
    if args.cmd == "list":
        payload = {"rule": reg.get("rule"), "root": reg.get("root"), "bus": reg.get("bus"), "machines": reg["machines"]}
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(reg.get("rule", ""))
            for m in reg["machines"]:
                host = m.get("hostname") or "-"
                how = f"ssh={ssh_alias(m)}" if connect_mode(m) == INBOUND_SSH else "bus=" + ",".join(bus_device_ids(m))
                print(f"{m['id']}\t{connect_mode(m)}\t{how}\thostname={host}\troles={','.join(m.get('roles') or [])}")
        return 0

    if args.cmd == "route":
        checkins = read_checkins(reg)
        print(json.dumps(work_route(args.machine, checkins=checkins, path=args.registry), indent=2, sort_keys=True))
        return 0

    checkins = read_checkins(reg, connect_timeout=args.timeout)
    avail = select_available(path=args.registry, connect_timeout=args.timeout, checkins=checkins, window=args.window)
    if args.json:
        seen = {m["id"]: (lambda d: d.strftime("%Y-%m-%dT%H:%M:%SZ") if d else None)(last_checkin(m, checkins))
                for m in reg["machines"] if connect_mode(m) == OUTBOUND_BUS}
        print(json.dumps({"available": avail, "reachable": avail, "count": len(avail),
                          "window_seconds": checkin_window(reg, args.window), "last_checkin": seen},
                         indent=2, sort_keys=True))
    else:
        if not avail:
            print("available: none (ssh probes failed and no fresh bus check-ins)", file=sys.stderr)
        for m in avail:
            print(m["id"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
