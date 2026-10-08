"""Trusted host callback enrollment; one authority and existing FileBus only."""
import fcntl
import json
import os
from pathlib import Path
import uuid


def owner_dict(owner):
    return dict(zip(("project", "role", "actor", "generation", "epoch"), owner.args()))


def successor_key(owner):
    return "successor:" + ":".join(map(str, owner.args()))


def atomic_profile(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + "." + str(uuid.uuid4()) + ".tmp")
    fd = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if temporary.exists():
            temporary.unlink()


def enroll_successor(config_path, authority, incumbent, receipt):
    """Called only with the fixed authenticated native sink's durable receipt.

    The caller request supplies no identity, eligibility or credential. Lost
    responses recover from the private owner profile, never another launch key.
    """
    from role_fence_cli import private_json
    from coordination.bus import FileBus
    if incumbent.role != "root":
        raise PermissionError("production principal enrollment is outside bootstrap")
    exact = owner_dict(incumbent)
    if receipt.get("key") != successor_key(incumbent):
        raise PermissionError("exact once-per-predecessor operation key required")
    if (receipt.get("v"), receipt.get("owner"), receipt.get("operation"), receipt.get("payload"), receipt.get("state")) != (
            1, exact, "root-native-successor", {}, "completed"):
        raise PermissionError("exact fixed native successor receipt required")
    successor = receipt.get("evidence", {}).get("successor", {})
    death = successor.get("owned_model_exit", {})
    whoami, kernel = successor.get("whoami", {}), successor.get("kernel", {})
    actor = successor.get("actor")
    if (not isinstance(actor, str) or str(uuid.UUID(actor)) != actor or actor == incumbent.actor
            or whoami.get("id") != actor or successor.get("predecessor_owner") != exact
            or death.get("verified_dead") is not True or death.get("owner") != exact
            or type(kernel.get("pid")) is not int or kernel["pid"] <= 0
            or type(kernel.get("creation_filetime")) is not int or kernel["creation_filetime"] <= 0):
        raise PermissionError("genuine new WHOAMI/kernel and exact managed Job death required")
    generation = "win32:" + str(kernel["pid"]) + ":" + str(kernel["creation_filetime"])
    if successor.get("generation") != generation:
        raise PermissionError("kernel-derived execution incarnation required")
    path = Path(config_path)
    lock_fd = os.open(path.parent / "profile.lock", os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        config = private_json(path)
        key = successor_key(incumbent)
        recorded = config.get("successors", {}).get(key)
        if recorded:
            if recorded["actor"] != actor or recorded["generation"] != generation:
                raise PermissionError("successor intent conflict")
            # The private profile can survive an authority transaction crash.
            # Reconcile only its exact held enrollment, never repeat the host
            # launch or reset a lease/activation/working successor observation.
            with authority._tx() as db:
                previous = db.execute("SELECT priority FROM agents WHERE id=?", (incumbent.actor,)).fetchone()
                existing = db.execute("SELECT host,generation FROM agents WHERE id=?", (actor,)).fetchone()
                host = config["bindings"][actor]["host"]
                if existing and (existing["host"], existing["generation"]) != (host, generation):
                    raise PermissionError("authority enrollment conflict")
                if db.execute("SELECT 1 FROM candidates WHERE agent=? AND NOT(project=? AND role='root')", (actor, incumbent.project)).fetchone():
                    raise PermissionError("successor has foreign role custody")
                if db.execute("SELECT 1 FROM roles WHERE holder=? AND NOT(project=? AND role='root')", (actor, incumbent.project)).fetchone():
                    raise PermissionError("successor already holds a foreign role")
                db.execute("UPDATE agents SET ready=0,draft=1,quota=0 WHERE id=?", (incumbent.actor,))
                db.execute("INSERT OR IGNORE INTO agents VALUES(?,?,?,?,?,?,?,?)",
                    (actor, host, generation, authority.clock(), 0, 1, 0, previous[0]))
                db.execute("INSERT OR IGNORE INTO candidates VALUES(?,?,?)", (incumbent.project, "root", actor))
            return recorded
        binding = config["bindings"][incumbent.actor]
        if successor.get("host") != binding["host"]:
            raise PermissionError("enrolled host scope required")
        root_tag = successor.get("root_tag")
        if (not isinstance(root_tag, str) or not 1 <= len(root_tag) <= 128
                or not root_tag.startswith(binding.get("capsule_tag_prefix", "win35-root-capsule-"))
                or whoami.get("tag") != root_tag):
            raise PermissionError("actual owned native capsule tag required")
        if actor in config["bindings"]:
            raise PermissionError("new native actor already has another binding")
        bus = FileBus(config["bus_store"])
        with authority._tx() as db:
            authority._valid(db, *incumbent.args())
            if (db.execute("SELECT 1 FROM agents WHERE id=?", (actor,)).fetchone()
                    or db.execute("SELECT 1 FROM roles WHERE holder=?", (actor,)).fetchone()
                    or db.execute("SELECT 1 FROM candidates WHERE agent=?", (actor,)).fetchone()):
                raise PermissionError("native actor already belongs to the shared authority")
            priority = db.execute("SELECT priority FROM agents WHERE id=?", (incumbent.actor,)).fetchone()[0]
            # Recovery from a profile-write crash reuses one unambiguous native
            # enrollment, including its owner-private token, rather than duplicating.
            name = "win35-root-native:" + actor
            identities = bus._read(bus._identities, {})
            matches = [i for i in identities.values() if i.get("agent_name") == name]
            if len(matches) > 1:
                raise PermissionError("ambiguous existing native enrollment")
            if matches:
                identity = matches[0]
                if (identity["device_id"], identity["project_id"]) != (binding["host"], incumbent.project):
                    raise PermissionError("existing enrollment scope mismatch")
                identity_id = identity["identity_id"]
                token = bus._read(bus._tokens, {}).get(identity_id)
                if not token:
                    raise PermissionError("incomplete existing enrollment remains held")
            else:
                identity, token = bus.register(agent_name=name, device_id=binding["host"], project_id=incumbent.project)
                identity_id = identity.identity_id
            new_binding = {"project": incumbent.project, "role": "root", "host": binding["host"],
                "generation": generation, "bus_identity": identity_id,
                "capsule_tag_prefix": binding.get("capsule_tag_prefix", "win35-root-capsule-")}
            config["bindings"][actor] = new_binding
            binding["retired"] = True
            for scope in config["tls_clients"].values():
                scopes = scope.get("actors", [scope])
                if any((s.get("actor"), s.get("role"), s.get("project"), s.get("bus_identity")) ==
                       (incumbent.actor, "root", incumbent.project, binding["bus_identity"]) for s in scopes):
                    config_scope = {"actor": actor, "role": "root", "project": incumbent.project, "bus_identity": identity_id}
                    if "actors" not in scope:
                        previous = dict(scope)
                        scope.clear()
                        scope["actors"] = [previous]
                    scope["actors"].append(config_scope)
            record = {"actor": actor, "generation": generation, "project": incumbent.project, "role": "root",
                "root_tag": root_tag,
                "credential": {"identity_id": identity_id, "token": token}, "predecessor_owner": exact,
                "status": "enrolled_held_pending_admission_and_election"}
            config.setdefault("successors", {})[key] = record
            atomic_profile(path, config)
            # Insert held observations in the same maintained transaction. Profile
            # may precede commit on crash; replay must reconcile held state.
            now = authority.clock()
            db.execute("UPDATE agents SET ready=0,draft=1,quota=0 WHERE id=?", (incumbent.actor,))
            db.execute("INSERT INTO agents VALUES(?,?,?,?,?,?,?,?)",
                (actor, binding["host"], generation, now, 0, 1, 0, priority))
            db.execute("INSERT OR IGNORE INTO candidates VALUES(?,?,?)", (incumbent.project, "root", actor))
            authority._event(db, incumbent.project, "root", "native_successor_enrolled_held", incumbent.epoch,
                {"actor": actor, "generation": generation, "previous": incumbent.actor})
            return record
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)


def reconcile_successors(config_path, authority):
    """Owner-server startup reconciliation; no remote stale-actor write route."""
    from role_fence_cli import private_json
    from role_fence import Owner
    import sqlite3
    config = private_json(config_path)
    for key, record in config.get("successors", {}).items():
        old = record["predecessor_owner"]
        owner = Owner(*(old[k] for k in ("project", "role", "actor", "generation", "epoch")))
        if key != successor_key(owner):
            raise PermissionError("private successor key conflict")
        with sqlite3.connect(config["sink_journal"]) as db:
            row = db.execute("SELECT body,result FROM sink_receipts WHERE key=?", (key,)).fetchone()
        if not row or not row[1]:
            raise PermissionError("durable native successor receipt unavailable")
        intent, receipt = json.loads(row[0]), json.loads(row[1])
        if intent != {"v": 1, "key": key, "operation": "root-native-successor", "owner": owner_dict(owner), "payload": {}}:
            raise PermissionError("durable successor intent conflict")
        enroll_successor(config_path, authority, owner, receipt)
