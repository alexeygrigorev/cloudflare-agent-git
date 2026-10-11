#!/usr/bin/env python3
"""Team work machines: load the registry and select reachable hosts at run time.

Source of truth: coordination/MACHINES.json (no on/off status field).
Rule: if a machine is on and reachable, work runs on it; otherwise work runs
on the machines that are reachable. Root (Grok Bot Cloudflare Root) reaches
them by ssh from Alexey's shared Linux computer; there is no competing root.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Iterable, List, Optional, Sequence

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = ROOT / "coordination" / "MACHINES.json"
DEFAULT_CONNECT_TIMEOUT = 10


def load_registry(path: Optional[os.PathLike] = None) -> dict[str, Any]:
    reg_path = Path(path) if path else Path(os.environ.get("MACHINES_REGISTRY", DEFAULT_REGISTRY))
    with open(reg_path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict) or not isinstance(data.get("machines"), list):
        raise ValueError(f"machines registry must be an object with a machines list: {reg_path}")
    for m in data["machines"]:
        if not isinstance(m, dict) or "id" not in m or "ssh" not in m:
            raise ValueError(f"each machine needs id and ssh: {m!r}")
        if "status" in m or "online" in m or "offline" in m:
            raise ValueError(f"machines registry must not carry on/off status fields: {m!r}")
    return data


def list_machines(path: Optional[os.PathLike] = None, roles: Optional[Sequence[str]] = None) -> List[dict[str, Any]]:
    machines = list(load_registry(path)["machines"])
    if roles is None:
        return machines
    wanted = set(roles)
    return [m for m in machines if wanted.intersection(m.get("roles") or [])]


def probe_ssh(
    ssh_alias: str,
    *,
    connect_timeout: int = DEFAULT_CONNECT_TIMEOUT,
    runner: Optional[Callable[..., subprocess.CompletedProcess]] = None,
) -> bool:
    """Return True when the ssh alias answers a BatchMode hostname probe."""
    run = runner or subprocess.run
    try:
        r = run(
            [
                "ssh",
                "-o", "BatchMode=yes",
                "-o", f"ConnectTimeout={connect_timeout}",
                ssh_alias,
                "hostname",
            ],
            capture_output=True,
            text=True,
            timeout=connect_timeout + 5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return r.returncode == 0


def select_reachable(
    machines: Optional[Iterable[dict[str, Any]]] = None,
    *,
    probe: Optional[Callable[[str], bool]] = None,
    connect_timeout: int = DEFAULT_CONNECT_TIMEOUT,
    path: Optional[os.PathLike] = None,
) -> List[dict[str, Any]]:
    """Return machines that answer the probe; skip unreachable ones.

    A failed probe means unknown/unreachable, not dead permanently. Callers
    run work on the returned list. When every probe fails, the list is empty.
    """
    pool = list(machines) if machines is not None else list_machines(path, roles=["work"])
    check = probe or (lambda alias: probe_ssh(alias, connect_timeout=connect_timeout))
    reachable = []
    for m in pool:
        alias = m.get("ssh")
        if not alias:
            continue
        if check(str(alias)):
            reachable.append(m)
    return reachable


def resolve_execution_target(
    device_id: Optional[str] = None,
    hostname: Optional[str] = None,
    *,
    path: Optional[os.PathLike] = None,
) -> str:
    """Map a device_id or hostname to the registry execution_target (or id)."""
    machines = list_machines(path)
    keys = []
    if device_id:
        keys.append(str(device_id).strip().lower())
    if hostname:
        keys.append(str(hostname).strip().lower())
    for m in machines:
        candidates = {
            str(m.get("id") or "").lower(),
            str(m.get("hostname") or "").lower(),
            str(m.get("execution_target") or "").lower(),
            str(m.get("ssh") or "").lower(),
        }
        candidates.discard("")
        if any(k in candidates for k in keys):
            return str(m.get("execution_target") or m["id"])
    if device_id:
        return str(device_id)
    if machines:
        return str(machines[0].get("execution_target") or machines[0]["id"])
    return "unknown"


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--registry", default=None, help="path to MACHINES.json")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="print the work-machine registry (no status)")
    p_list.add_argument("--json", action="store_true")

    p_reach = sub.add_parser("reachable", help="probe ssh and print reachable machines")
    p_reach.add_argument("--json", action="store_true")
    p_reach.add_argument("--timeout", type=int, default=DEFAULT_CONNECT_TIMEOUT)

    args = ap.parse_args(argv)
    reg = load_registry(args.registry)
    if args.cmd == "list":
        payload = {"rule": reg.get("rule"), "root": reg.get("root"), "machines": reg["machines"]}
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(reg.get("rule", ""))
            for m in reg["machines"]:
                host = m.get("hostname") or "-"
                print(f"{m['id']}\tssh={m['ssh']}\thostname={host}\troles={','.join(m.get('roles') or [])}")
        return 0

    reached = select_reachable(path=args.registry, connect_timeout=args.timeout)
    if args.json:
        print(json.dumps({"reachable": reached, "count": len(reached)}, indent=2, sort_keys=True))
    else:
        if not reached:
            print("reachable: none (all probes failed or unknown)", file=sys.stderr)
        for m in reached:
            print(m["id"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
