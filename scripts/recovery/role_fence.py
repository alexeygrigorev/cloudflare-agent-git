"""Managed coordinator mutation boundary over the maintained RoleAuthority.

Install inside the existing authenticated authority adapter, not as a second
service. Authentication, native observations and sink idempotency are injected
by that adapter. Unmigrated raw OS/native commands are outside this boundary.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Owner:
    project: str
    role: str
    actor: str
    generation: str
    epoch: int

    def args(self):
        if self.role not in ("root", "principal"):
            raise ValueError("root and principal are distinct managed roles")
        if not all((self.project, self.actor, self.generation)):
            raise ValueError("exact native actor and incarnation required")
        if type(self.epoch) is not int or self.epoch < 1:
            raise ValueError("positive fencing epoch required")
        return self.project, self.role, self.actor, self.generation, self.epoch


class CoordinatorFence:
    """No cached authorization; every effect is inside the election transaction.

    authenticate(credential, owner) must verify enrollment and exact native
    session/host/incarnation, not accept caller-supplied observation booleans.
    Operations are fixed owner-installed callbacks, and must durably deduplicate
    the supplied key. They enqueue bounded control operations; long-lived work
    must validate the epoch again at its own mutation sink.
    """
    def __init__(self, authority, authenticate, operations, verify_handover):
        self.authority = authority
        self.authenticate = authenticate
        self.operations = dict(operations)
        self.verify_handover = verify_handover

    def _identity(self, credential, owner):
        args = owner.args()
        if self.authenticate(credential, owner) is not True:
            raise PermissionError("native binding authentication failed")
        return args

    def renew(self, credential, owner, *, ttl=180):
        args = self._identity(credential, owner)
        if not 1 <= ttl <= 180:
            raise ValueError("lease TTL outside maintained bound")
        self.authority.renew(*args, ttl=ttl)
        return self.authority.role_state(owner.project, owner.role)

    def execute(self, credential, owner, key, operation, payload):
        args = self._identity(credential, owner)
        if not isinstance(key, str) or not key or len(key) > 256:
            raise ValueError("durable bounded effect key required")
        entry = self.operations.get((owner.role, operation))
        if entry is None:
            raise PermissionError("operation not installed for this role")
        validate, effect = entry
        if validate(payload) is not True:
            raise ValueError("invalid operation payload")
        receipt = self.authority.activation(*args)
        if not receipt.get("role_ack") or not receipt.get("first_action"):
            raise PermissionError("semantic role ACK and first action required")
        body = {"operation": operation, "payload": payload}
        return self.authority.guarded_effect(
            *args, key, body, lambda k, p: effect(k, p["payload"], owner))

    def handback(self, credential, owner, successor, evidence, *, ttl=180):
        """CAS transfer after trusted semantic checkpoint and successor ACK.

        This moves role authority only; file claims and native writers require
        their separate acknowledged handoff. Epoch increments before the old
        actor can make another managed mutation. Successor activation is pending.
        """
        args = self._identity(credential, owner)
        if not 1 <= ttl <= 180:
            raise ValueError("lease TTL outside maintained bound")
        if (successor.project, successor.role) != (owner.project, owner.role):
            raise ValueError("cross-role handback forbidden")
        successor.args()
        if successor.epoch != owner.epoch + 1:
            raise ValueError("successor epoch must be next generation")
        if self.verify_handover(owner, successor, evidence) is not True:
            raise PermissionError("trusted checkpoint and successor ACK required")
        evidence = {k: evidence[k] for k in ("checkpoint", "ack")}
        a = self.authority
        # Version-pinned authority transaction extension: the new control-plane
        # owner reviews it with the exact maintained authority source. It changes
        # no peer-owned authority module or existing production role/store.
        with a._tx() as db:
            old = a._valid(db, *args)
            candidate = db.execute(
                "SELECT a.* FROM agents a JOIN candidates c ON c.agent=a.id "
                "WHERE c.project=? AND c.role=? AND a.id=?",
                (owner.project, owner.role, successor.actor)).fetchone()
            now = a.clock()
            if (candidate is None or candidate["generation"] != successor.generation
                    or candidate["seen"] <= now - 60 or not candidate["ready"]
                    or candidate["draft"] or not candidate["quota"]):
                raise PermissionError("successor lacks trusted fresh eligibility")
            occupied = db.execute(
                "SELECT 1 FROM roles WHERE holder=? AND expires>? "
                "AND role IN ('root','principal') AND NOT(project=? AND role=?)",
                (successor.actor, now, owner.project, owner.role)).fetchone()
            if occupied:
                raise PermissionError("successor already owns another coordinator role")
            if (successor.actor, successor.generation) == (owner.actor, owner.generation):
                raise ValueError("handback requires another execution incarnation")
            db.execute(
                "UPDATE roles SET holder=?,generation=?,epoch=?,expires=?,"
                "activation_due=?,suspect_since=NULL WHERE project=? AND role=?",
                (successor.actor, successor.generation, successor.epoch, now + ttl,
                 now + 300, owner.project, owner.role))
            a._event(db, owner.project, owner.role, "handback", successor.epoch,
                     {"previous": old["holder"], "holder": successor.actor,
                      "generation": successor.generation, "evidence": evidence})
            return {"holder": successor.actor, "generation": successor.generation,
                    "epoch": successor.epoch, "activation": "pending"}
