"""SAME8801 Host-Recovery Server Adapter.

Bounded pure server protocol operating over the existing RoleAuthority SQLite database.
Enforces constructor-installed typed callbacks, atomic CAS drain, durable factory fencing,
and at-most-once held enrollment with canonical binding digest handoff.
Only the separate privileged, source-pinned caretaker may submit kernel observations; root/model credentials cannot.
"""
from __future__ import annotations

import hashlib
import json
import math
import secrets
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Tuple, Union

try:
    from coordination.role_failover import RoleAuthority, Fenced
except ImportError:
    try:
        from role_failover import RoleAuthority, Fenced
    except ImportError:
        RoleAuthority = None  # type: ignore

        class Fenced(RuntimeError):  # type: ignore
            pass


class HostRecoveryError(Exception):
    """Base exception for host recovery errors."""
    pass


class HostRecoveryFenced(HostRecoveryError, Fenced):
    """Raised when an operation is fenced (e.g. CAS conflict, stale lease, invalid epoch)."""
    pass


class HostRecoveryIdempotencyConflict(HostRecoveryError):
    """Raised when an idempotent operation conflicts with prior recorded state."""
    pass


@dataclass(frozen=True)
class OwnerBaseline:
    """Frozen baseline representation of the incumbent project role owner."""
    project: str
    role: str
    actor: str
    generation: str
    epoch: int
    digest: str

    def as_dict(self) -> Dict[str, Any]:
        return {
            "project": self.project,
            "role": self.role,
            "actor": self.actor,
            "generation": self.generation,
            "epoch": self.epoch,
            "digest": self.digest,
        }


@dataclass(frozen=True)
class VerifiedDrain:
    """Typed verification proof bound to baseline, nonce, kernel proof, and job status."""
    baseline: OwnerBaseline
    nonce: str
    receipt_ref: str
    kernel_proof_ref: str
    native_owner_all_dead: bool
    job_active_zero: bool
    drain_time: float
    mode: str = "automatic"
    historical_receipt_sha256: Optional[str] = None


@dataclass(frozen=True)
class VerifiedSuccessor:
    """Typed verification proof of successor native identity and pinned factory source."""
    baseline: OwnerBaseline
    nonce: str
    proof_ref: str
    new_actor: str
    new_generation: str
    kernel_identity: str
    factory_source: str
    verified_time: float


class HostRecoveryAdapter:
    """Server-side host-recovery protocol adapter operating over existing RoleAuthority DB.

    Trust boundary:
    - Callers provide ONLY opaque receipt references and authentication credentials.
    - All verification is delegated to constructor-installed typed callbacks.
    - Callbacks default to deny (fail closed).
    - Database transitions use strict SQLite transactions and atomic CAS operations.
    - No background daemon or HTTP socket listener is started ("serve nothing").
    """

    VALID_PHASES = {
        "challenged",
        "drained",
        "factory-pending",
        "factory-receipted",
        "enrollment-pending",
        "held-completed",
        "uncertain",
    }

    def __init__(
        self,
        authority: Any,
        *,
        select_baseline: Optional[Callable[[str, str, Any], OwnerBaseline]] = None,
        verify_drain: Optional[Callable[[str, OwnerBaseline, str], Optional[VerifiedDrain]]] = None,
        factory_dispatch: Optional[Callable[[str, OwnerBaseline], Any]] = None,
        verify_successor: Optional[Callable[[str, OwnerBaseline, str], Optional[VerifiedSuccessor]]] = None,
        hold_enroll: Optional[Callable[[VerifiedSuccessor], Any]] = None,
        host_credential: Optional[str] = None,
        default_project: Optional[str] = None,
        default_role: Optional[str] = None,
        operator_receipt_sha256: str = "a86f6bd1eab93c1b758f84a5027b8cc07a3803ff560efe3920361c61a39e42f2",
    ):
        if authority is None:
            raise ValueError("authority instance is required")
        if (not isinstance(operator_receipt_sha256, str) or len(operator_receipt_sha256) != 64
                or any(c not in "0123456789abcdef" for c in operator_receipt_sha256)):
            raise ValueError("constructor-installed operator digest required")
        self._operator_receipt_sha256 = operator_receipt_sha256
        self.authority = authority
        self._select_baseline_cb = select_baseline
        self._verify_drain_cb = verify_drain
        self._factory_dispatch_cb = factory_dispatch
        self._verify_successor_cb = verify_successor
        self._hold_enroll_cb = hold_enroll
        self.host_credential = host_credential
        self.default_project = default_project
        self.default_role = default_role

        self._init_db()

    def _init_db(self) -> None:
        """Create host_recovery_attempts table in the existing authority DB."""
        with self.authority._tx() as db:
            db.execute("CREATE TABLE IF NOT EXISTS reply_tombstones(actor TEXT,generation TEXT,created REAL,PRIMARY KEY(actor,generation))")
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS host_recovery_attempts (
                    attempt_key TEXT PRIMARY KEY,
                    project TEXT NOT NULL,
                    role TEXT NOT NULL,
                    old_actor TEXT NOT NULL,
                    old_generation TEXT NOT NULL,
                    old_epoch INTEGER NOT NULL,
                    baseline_sha TEXT NOT NULL,
                    nonce TEXT UNIQUE NOT NULL,
                    phase TEXT NOT NULL,
                    baseline_json TEXT NOT NULL,
                    drain_receipt_ref TEXT,
                    kernel_proof_ref TEXT,
                    factory_proof_ref TEXT,
                    new_actor TEXT,
                    new_generation TEXT,
                    binding_digest TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    UNIQUE(project, role, old_actor, old_generation, old_epoch, baseline_sha)
                )
                """
            )
            db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_recovery_nonce ON host_recovery_attempts(nonce)")

    @staticmethod
    def _compute_digest(project: str, role: str, actor: str, generation: str, epoch: int) -> str:
        canonical = f"{project}:{role}:{actor}:{generation}:{epoch}"
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def challenge(self, project: str, role: str, *, key: Optional[str] = None) -> Dict[str, Any]:
        """Issue or retrieve challenge for the specified configured project role."""
        if not project or not role:
            raise ValueError("project and role required")

        with self.authority._tx() as db:
            row = self.authority._get(db, project, role)

            # Check if an attempt is currently in-flight for this project and role
            active = db.execute(
                "SELECT * FROM host_recovery_attempts WHERE project=? AND role=? AND phase NOT IN ('held-completed')",
                (project, role),
            ).fetchone()

            if not row["holder"]:
                if active:
                    attempt_key = active["attempt_key"]
                    if key is not None and key != attempt_key and key != active["baseline_sha"]:
                        raise HostRecoveryIdempotencyConflict(
                            f"idempotency key mismatch: expected {attempt_key}, got {key}"
                        )
                    baseline_dict = json.loads(active["baseline_json"])
                    return {
                        "v": 1,
                        "state": active["phase"],
                        "challenge": active["nonce"],
                        "baseline": baseline_dict,
                    }
                raise HostRecoveryFenced(f"role {project}/{role} has no configured or active holder to recover")

            if self._select_baseline_cb is None:
                raise HostRecoveryFenced("default deny: select_baseline callback not installed")

            baseline = self._select_baseline_cb(project, role, row)
            if type(baseline) is not OwnerBaseline:
                raise HostRecoveryFenced("select_baseline callback must return frozen OwnerBaseline instance")

            if (
                baseline.project != project
                or baseline.role != role
                or baseline.actor != row["holder"]
                or baseline.generation != row["generation"]
                or baseline.epoch != row["epoch"]
            ):
                raise HostRecoveryFenced("selected baseline mismatch with current role authority row")

            attempt_key = f"{baseline.project}:{baseline.role}:{baseline.actor}:{baseline.generation}:{baseline.epoch}:{baseline.digest}"
            if key is not None and key != attempt_key and key != baseline.digest:
                raise HostRecoveryIdempotencyConflict(f"idempotency key mismatch: expected {attempt_key}, got {key}")

            if active:
                if active["attempt_key"] != attempt_key:
                    raise HostRecoveryFenced(
                        f"concurrent recovery attempt already in flight for {project}/{role} (nonce: {active['nonce']})"
                    )
                baseline_dict = json.loads(active["baseline_json"])
                return {
                    "v": 1,
                    "state": active["phase"],
                    "challenge": active["nonce"],
                    "baseline": baseline_dict,
                }

            existing = db.execute(
                "SELECT * FROM host_recovery_attempts WHERE attempt_key=?", (attempt_key,)
            ).fetchone()

            if existing:
                if (
                    existing["project"] != baseline.project
                    or existing["role"] != baseline.role
                    or existing["old_actor"] != baseline.actor
                    or existing["old_generation"] != baseline.generation
                    or existing["old_epoch"] != baseline.epoch
                    or existing["baseline_sha"] != baseline.digest
                ):
                    raise HostRecoveryIdempotencyConflict("challenge idempotency conflict with existing attempt")

                return {
                    "v": 1,
                    "state": existing["phase"],
                    "challenge": existing["nonce"],
                    "baseline": baseline.as_dict(),
                }

            nonce = secrets.token_hex(24)
            now = float(self.authority.clock())
            baseline_json = json.dumps(baseline.as_dict(), sort_keys=True)

            db.execute(
                """
                INSERT INTO host_recovery_attempts (
                    attempt_key, project, role, old_actor, old_generation, old_epoch,
                    baseline_sha, nonce, phase, baseline_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'challenged', ?, ?, ?)
                """,
                (
                    attempt_key,
                    project,
                    role,
                    baseline.actor,
                    baseline.generation,
                    baseline.epoch,
                    baseline.digest,
                    nonce,
                    baseline_json,
                    now,
                    now,
                ),
            )

            self.authority._event(
                db,
                project,
                role,
                "recovery_challenged",
                baseline.epoch,
                {"nonce": nonce, "baseline": baseline.as_dict()},
            )

            return {
                "v": 1,
                "state": "challenged",
                "challenge": nonce,
                "baseline": baseline.as_dict(),
            }

    def drain(self, nonce: str, receipt_ref: str) -> Dict[str, Any]:
        """Perform verified drain of predecessor using atomic CAS on the roles table."""
        if not isinstance(nonce, str) or not nonce.strip():
            raise ValueError("nonce required")
        if not isinstance(receipt_ref, str) or not receipt_ref.strip():
            raise ValueError("receipt_ref required")

        with self.authority._tx() as db:
            attempt = db.execute(
                "SELECT * FROM host_recovery_attempts WHERE nonce=?", (nonce,)
            ).fetchone()
            if attempt is None:
                raise HostRecoveryError("unknown challenge nonce")

            # Check if drain was already successfully performed
            if attempt["phase"] in (
                "drained",
                "factory-pending",
                "factory-receipted",
                "enrollment-pending",
                "held-completed",
            ):
                if attempt["drain_receipt_ref"] and attempt["drain_receipt_ref"] != receipt_ref:
                    raise HostRecoveryIdempotencyConflict("conflicting drain receipt reference")
                return {
                    "v": 1,
                    "state": attempt["phase"],
                    "challenge": nonce,
                    "kernel_proof_ref": attempt["kernel_proof_ref"],
                }

            if attempt["phase"] != "challenged":
                raise HostRecoveryFenced(f"cannot execute drain in phase '{attempt['phase']}'")

            baseline_dict = json.loads(attempt["baseline_json"])
            baseline = OwnerBaseline(**baseline_dict)

            if self._verify_drain_cb is None:
                raise HostRecoveryFenced("default deny: verify_drain callback not installed")

            proof = self._verify_drain_cb(receipt_ref, baseline, nonce)
            if type(proof) is not VerifiedDrain:
                raise HostRecoveryFenced("drain verification failed: proof must be typed VerifiedDrain")

            if proof.baseline != baseline:
                raise HostRecoveryFenced("drain verification failed: baseline mismatch")
            if proof.nonce != nonce:
                raise HostRecoveryFenced("drain verification failed: nonce mismatch")
            if proof.receipt_ref != receipt_ref:
                raise HostRecoveryFenced("drain verification failed: receipt reference mismatch")
            if proof.native_owner_all_dead is not True:
                raise HostRecoveryFenced("drain verification failed: native owner not dead")
            if proof.mode == "automatic":
                if proof.job_active_zero is not True or proof.historical_receipt_sha256 is not None:
                    raise HostRecoveryFenced("fresh retained exact Job zero proof required")
            elif proof.mode == "operator-bootstrap":
                if (proof.job_active_zero is not False or proof.historical_receipt_sha256 !=
                        self._operator_receipt_sha256):
                    raise HostRecoveryFenced("explicit fixed historical drain proof required; no fresh Job claim")
            else:
                raise HostRecoveryFenced("unknown drain proof mode")
            if not isinstance(proof.kernel_proof_ref, str) or not proof.kernel_proof_ref.strip():
                raise HostRecoveryFenced("drain verification failed: non-empty kernel proof reference required")

            now = float(self.authority.clock())
            if not math.isfinite(proof.drain_time) or proof.drain_time > now:
                raise HostRecoveryFenced("drain verification failed: invalid drain timestamp")

            # Execute atomic CAS: exactly one execution succeeds
            cas_res = db.execute(
                """
                UPDATE roles 
                SET holder=NULL, generation=NULL, epoch=epoch+1, expires=0, activation_due=0, suspect_since=NULL 
                WHERE project=? AND role=? AND holder=? AND generation=? AND epoch=?
                """,
                (
                    baseline.project,
                    baseline.role,
                    baseline.actor,
                    baseline.generation,
                    baseline.epoch,
                ),
            )
            if cas_res.rowcount != 1:
                raise HostRecoveryFenced(
                    "concurrent drain CAS failed: role already modified, transferred, or revoked"
                )

            # Tombstone old predecessor incarnation only
            db.execute(
                "INSERT OR IGNORE INTO reply_tombstones VALUES(?,?,?)",
                (baseline.actor, baseline.generation, now),
            )

            # Persist audit event preserving all unrelated roles, claims, and history
            self.authority._event(
                db,
                baseline.project,
                baseline.role,
                "recovery_drain",
                baseline.epoch + 1,
                {
                    "nonce": nonce,
                    "actor": baseline.actor,
                    "generation": baseline.generation,
                    "kernel_proof_ref": proof.kernel_proof_ref,
                    "preserve_claims": True,
                    "preserve_history": True,
                    "preserve_tokens": True,
                    "preserve_candidates": True,
                },
            )

            db.execute(
                """
                UPDATE host_recovery_attempts 
                SET phase='drained', drain_receipt_ref=?, kernel_proof_ref=?, updated_at=? 
                WHERE nonce=?
                """,
                (receipt_ref, proof.kernel_proof_ref, now, nonce),
            )

            return {
                "v": 1,
                "state": "drained",
                "challenge": nonce,
                "kernel_proof_ref": proof.kernel_proof_ref,
            }

    def dispatch_factory(self, nonce: str) -> Dict[str, Any]:
        """Dispatch native factory once-per-incarnation. Marks factory-pending durable before call."""
        if not isinstance(nonce, str) or not nonce.strip():
            raise ValueError("nonce required")

        baseline: OwnerBaseline
        with self.authority._tx() as db:
            attempt = db.execute(
                "SELECT * FROM host_recovery_attempts WHERE nonce=?", (nonce,)
            ).fetchone()
            if attempt is None:
                raise HostRecoveryError("unknown challenge nonce")

            if attempt["phase"] == "uncertain":
                raise HostRecoveryFenced(
                    "attempt in uncertain phase: factory dispatch cannot be replayed; original nonce requires explicit reconcile with typed factory proof"
                )
            if attempt["phase"] in (
                "factory-pending",
                "factory-receipted",
                "enrollment-pending",
                "held-completed",
            ):
                raise HostRecoveryFenced(
                    f"factory dispatch already performed for nonce {nonce}; repeat permits forbidden"
                )
            if attempt["phase"] != "drained":
                raise HostRecoveryFenced(f"cannot dispatch factory in phase '{attempt['phase']}'")

            baseline = OwnerBaseline(**json.loads(attempt["baseline_json"]))
            now = float(self.authority.clock())

            # Mark factory-pending durable in DB BEFORE external caretaker side-effect
            db.execute(
                "UPDATE host_recovery_attempts SET phase='factory-pending', updated_at=? WHERE nonce=?",
                (now, nonce),
            )

        # External factory callback execution
        failed = False
        factory_res = None
        try:
            if self._factory_dispatch_cb is None:
                raise HostRecoveryFenced("default deny: factory_dispatch callback not installed")
            factory_res = self._factory_dispatch_cb(nonce, baseline)
            if not factory_res:
                failed = True
        except Exception:
            failed = True

        now = float(self.authority.clock())
        if failed:
            with self.authority._tx() as db:
                db.execute(
                    "UPDATE host_recovery_attempts SET phase='uncertain', updated_at=? WHERE nonce=?",
                    (now, nonce),
                )
            raise HostRecoveryFenced(
                "factory dispatch failed or disconnected: attempt marked uncertain; no replay permitted"
            )

        proof_ref = (
            factory_res
            if isinstance(factory_res, str)
            else factory_res.get("proof_ref", str(factory_res))
            if isinstance(factory_res, dict)
            else str(factory_res)
        )

        with self.authority._tx() as db:
            db.execute(
                "UPDATE host_recovery_attempts SET phase='factory-receipted', factory_proof_ref=?, updated_at=? WHERE nonce=?",
                (proof_ref, now, nonce),
            )

        return {
            "v": 1,
            "state": "factory-receipted",
            "challenge": nonce,
            "factory_proof_ref": proof_ref,
        }

    def reconcile(self, nonce: str, receipt_ref: str) -> Dict[str, Any]:
        """Reconcile recovery with opaque receipt reference. Handles drain or successor verification."""
        if not isinstance(nonce, str) or not nonce.strip():
            raise ValueError("nonce required")
        if not isinstance(receipt_ref, str) or not receipt_ref.strip():
            raise ValueError("receipt_ref required")

        with self.authority._tx() as db:
            attempt = db.execute(
                "SELECT * FROM host_recovery_attempts WHERE nonce=?", (nonce,)
            ).fetchone()
            if attempt is None:
                raise HostRecoveryError("unknown challenge nonce")

            # Check if already held-completed: idempotent return
            if attempt["phase"] == "held-completed":
                if attempt["factory_proof_ref"] and attempt["factory_proof_ref"] != receipt_ref:
                    raise HostRecoveryIdempotencyConflict(
                        "reconcile receipt conflict with already held-completed enrollment"
                    )
                return {
                    "v": 1,
                    "state": "held-completed",
                    "challenge": nonce,
                    "binding_digest": attempt["binding_digest"],
                }

        # If currently in 'challenged' phase, attempt drain first
        if attempt["phase"] == "challenged":
            drain_result = self.drain(nonce, receipt_ref)
            # If factory dispatch is configured, dispatch factory to advance phase
            if self._factory_dispatch_cb is not None:
                try:
                    self.dispatch_factory(nonce)
                except Exception:
                    pass
            return drain_result

        # Successor verification & Enrollment flow
        baseline = OwnerBaseline(**json.loads(attempt["baseline_json"]))

        if self._verify_successor_cb is None:
            raise HostRecoveryFenced("default deny: verify_successor callback not installed")

        proof = self._verify_successor_cb(receipt_ref, baseline, nonce)
        if type(proof) is not VerifiedSuccessor:
            raise HostRecoveryFenced(
                "successor verification failed: proof must be typed VerifiedSuccessor"
            )

        if proof.baseline != baseline:
            raise HostRecoveryFenced("successor verification failed: baseline mismatch")
        if proof.nonce != nonce:
            raise HostRecoveryFenced("successor verification failed: nonce mismatch")
        if proof.proof_ref != receipt_ref:
            raise HostRecoveryFenced("successor verification failed: proof reference mismatch")
        if not isinstance(proof.new_actor, str) or not proof.new_actor.strip():
            raise HostRecoveryFenced("successor verification failed: new_actor required")
        if not isinstance(proof.new_generation, str) or not proof.new_generation.strip():
            raise HostRecoveryFenced("successor verification failed: new_generation required")
        if not isinstance(proof.kernel_identity, str) or not proof.kernel_identity.strip():
            raise HostRecoveryFenced("successor verification failed: kernel_identity required")
        if not isinstance(proof.factory_source, str) or not proof.factory_source.strip():
            raise HostRecoveryFenced("successor verification failed: factory_source required")

        # Reject same expired actor revival
        if proof.new_actor == baseline.actor and proof.new_generation == baseline.generation:
            raise HostRecoveryFenced("forbidden: same expired actor revival")

        now = float(self.authority.clock())
        if not math.isfinite(proof.verified_time) or proof.verified_time > now:
            raise HostRecoveryFenced("successor verification failed: invalid verified timestamp")

        # Mark enrollment-pending durable in DB BEFORE hold_enroll callback
        with self.authority._tx() as db:
            fresh = db.execute("SELECT phase,new_actor FROM host_recovery_attempts WHERE nonce=?", (nonce,)).fetchone()
            if (fresh["phase"] not in ("factory-pending", "factory-receipted", "uncertain")
                    or (fresh["phase"] == "uncertain" and fresh["new_actor"] is not None)):
                raise HostRecoveryFenced("enrollment already pending/ambiguous or factory permit absent")
            changed = db.execute(
                """UPDATE host_recovery_attempts
                SET phase='enrollment-pending', factory_proof_ref=?, new_actor=?, new_generation=?, updated_at=?
                WHERE nonce=? AND phase=? AND new_actor IS NULL""",
                (receipt_ref, proof.new_actor, proof.new_generation, now, nonce, fresh["phase"]),
            )
            if changed.rowcount != 1:
                raise HostRecoveryFenced("enrollment CAS lost; no duplicate callback")

        # Call hold_enroll
        failed = False
        enroll_res = None
        try:
            if self._hold_enroll_cb is None:
                raise HostRecoveryFenced("default deny: hold_enroll callback not installed")
            enroll_res = self._hold_enroll_cb(proof)
            if not enroll_res:
                failed = True
        except Exception:
            failed = True

        now = float(self.authority.clock())
        if failed:
            with self.authority._tx() as db:
                db.execute(
                    "UPDATE host_recovery_attempts SET phase='uncertain', updated_at=? WHERE nonce=?",
                    (now, nonce),
                )
            raise HostRecoveryFenced(
                "hold_enroll callback failed: attempt marked uncertain (at most once partial hold)"
            )

        # Extract binding digest ONLY (never output tokens)
        if isinstance(enroll_res, dict):
            binding_digest = enroll_res.get("binding_digest") or enroll_res.get("digest")
            if not binding_digest:
                binding_digest = hashlib.sha256(
                    json.dumps(enroll_res, sort_keys=True).encode("utf-8")
                ).hexdigest()
        else:
            binding_digest = str(enroll_res)

        with self.authority._tx() as db:
            db.execute(
                """
                UPDATE host_recovery_attempts 
                SET phase='held-completed', binding_digest=?, updated_at=? 
                WHERE nonce=?
                """,
                (binding_digest, now, nonce),
            )
            self.authority._event(
                db,
                baseline.project,
                baseline.role,
                "recovery_held_completed",
                baseline.epoch + 1,
                {
                    "nonce": nonce,
                    "new_actor": proof.new_actor,
                    "new_generation": proof.new_generation,
                    "binding_digest": binding_digest,
                },
            )

        return {
            "v": 1,
            "state": "held-completed",
            "challenge": nonce,
            "binding_digest": binding_digest,
        }

    def handle_wire_request(self, req: Union[Dict[str, Any], str]) -> Dict[str, Any]:
        """Handle wire JSON protocol requests for CHALLENGE and RECONCILE."""
        if isinstance(req, str):
            try:
                req = json.loads(req)
            except Exception as e:
                raise HostRecoveryError(f"invalid JSON payload: {e}")
        if not isinstance(req, dict):
            raise HostRecoveryError("wire request must be a JSON object")

        if req.get("v") != 1:
            raise HostRecoveryError("unsupported protocol version: expected v=1")

        # Host authentication check
        if self.host_credential is not None:
            cred = req.get("credential")
            if not cred or not secrets.compare_digest(str(cred), str(self.host_credential)):
                raise HostRecoveryError("unauthorized: invalid host scope credential")
        else:
            raise HostRecoveryError("default deny: host_credential not configured")

        op = req.get("op")
        if op == "challenge":
            project = req.get("project") or self.default_project
            role = req.get("role") or self.default_role
            if not project or not role:
                raise HostRecoveryError("project and role required for challenge")
            key = req.get("key")
            return self.challenge(project, role, key=key)
        elif op == "reconcile":
            nonce = req.get("challenge")
            receipt = req.get("receipt")
            if nonce is None or receipt is None:
                raise HostRecoveryError("challenge nonce and receipt reference required for reconcile")
            if not isinstance(nonce, str) or not nonce.strip():
                raise HostRecoveryError("challenge nonce required for reconcile")
            if not isinstance(receipt, str) or not receipt.strip():
                raise HostRecoveryError("opaque receipt reference required; arbitrary observations denied")
            return self.reconcile(nonce, receipt)
        else:
            raise HostRecoveryError(f"unsupported operation '{op}'")


class HostRecoveryWire:
    """Fixed privileged caretaker wire; caller cannot select source, store or role.

    This credential is provisioned only to the reviewed outside-root producer.
    mTLS plus this separate device key authenticate that producer, never a root
    Bus credential. Its installed kernel/task source is verified at adoption.
    This does not claim to fence arbitrary OS access by the computer's user.
    """
    OPERATOR_SHA = "a86f6bd1eab93c1b758f84a5027b8cc07a3803ff560efe3920361c61a39e42f2"

    def __init__(self, authority, config_path, plan):
        from role_fence_cli import pinned_file
        # Only the private installed plan controls this privileged source.
        # There is no runtime/client "verified" flag.
        pinned_file(plan['producer_source_path'],plan['guardian']['source_sha256'])
        self.authority, self.config_path, self.plan = authority, config_path, plan
        if plan.get("scope") != "fixed-host-caretaker":
            raise HostRecoveryFenced("fixed host scope required")
        self._receipts = {}
        self._successors = {}
        self._lock = __import__('threading').RLock()
        self.held_enrollment=self._held_enrollment
        self.read_handoff=self._read_handoff
        with authority._tx() as db:
            db.execute("CREATE TABLE IF NOT EXISTS host_kernel_baselines(owner_key TEXT PRIMARY KEY,payload TEXT NOT NULL)")
        self.adapter = HostRecoveryAdapter(authority, select_baseline=self._select,
            verify_drain=self._drain, factory_dispatch=self._permit_intent,
            verify_successor=self._successor, hold_enroll=self._enroll,
            operator_receipt_sha256=self._operator_sha() if "operator" in self.plan else self.OPERATOR_SHA)

    @staticmethod
    def digest(value):
        return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

    def _config(self):
        from role_fence_cli import private_json
        return private_json(self.config_path)

    def _fixed(self, name):
        from role_fence_cli import pinned_file, private_json
        entry = self.plan['operator'][name]
        pinned_file(entry['path'],entry['sha256'])
        return private_json(entry['path'])

    def _operator_sha(self):
        mode = self.plan['operator'].get('mode', 'historical-activated')
        if mode == 'historical-activated':
            return self.OPERATOR_SHA
        if mode != 'fixed-unactivated-cold-repair':
            raise HostRecoveryFenced('unknown fixed operator disposition')
        value = self.plan['operator']['kill']['sha256']
        if not isinstance(value, str) or len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
            raise HostRecoveryFenced('fixed reviewed operator digest required')
        return value

    def _unactivated_operator(self, row, owner, kill, model, checkpoint):
        # This is a provisioner-pinned cold repair, not activation or renewal.
        # No caller can select these files, owner, mode or source hashes.
        operator = self.plan['operator']
        if (operator.get('mode') != 'fixed-unactivated-cold-repair'
                or operator.get('expected_owner') != owner
                or row['expires'] > self.authority.clock()
                or row['activation_due'] <= 0
                or row['activation_due'] > self.authority.clock()):
            raise HostRecoveryFenced('exact expired unactivated operator owner required')
        with __import__('sqlite3').connect(__import__('pathlib').Path(self.authority.path).as_uri()+'?mode=ro', uri=True) as db:
            if db.execute('SELECT 1 FROM activation_receipts WHERE project=? AND role=? AND epoch=?',
                          (owner['project'], owner['role'], owner['epoch'])).fetchone():
                raise HostRecoveryFenced('activated owner cannot use unactivated repair')
        config = self._config()
        binding = config['bindings'].get(owner['actor'])
        history = self._fixed('history')
        thread = history.get('history', {}).get('thread', {})
        turns = thread.get('turns')
        if (not binding or binding.get('retired') or binding.get('generation') != owner['generation']
                or model.get('model', {}).get('native_actor') != owner['actor']
                or history.get('owner') != owner or checkpoint.get('owner') != owner
                or checkpoint.get('runtime_flags_changed') is not False
                or checkpoint.get('profile_sha256') != operator['profile_sha256']
                or kill.get('proof_sha256') != operator['model']['sha256']
                or kill.get('source_sha256') != operator['kill_source_sha256']
                or thread.get('id') != checkpoint['thread_id'] or thread.get('historyMode') != 'legacy'
                or not isinstance(turns, list) or not turns or not isinstance(turns[-1], dict)
                or turns[-1].get('status') != 'completed'):
            raise HostRecoveryFenced('fixed native completed-history repair custody mismatch')
        # Original activation evidence is deliberately absent. Completed SDK
        # history/proof plus the exact reviewed held-handle kill source establish
        # this fixed operator disposition; fresh automatic Job gates unchanged.

    def authenticate(self, credential, fingerprint):
        import hmac
        if (not isinstance(credential,dict) or set(credential)!={'identity_id','token'}
            or not all(isinstance(v,str) and 1<=len(v)<=4096 for v in credential.values())):
            raise HostRecoveryFenced("separate caretaker credential required")
        if (not hmac.compare_digest(fingerprint,self.plan['tls_fingerprint'])
            or not hmac.compare_digest(credential['identity_id'],self.plan['credential_id'])
            or not hmac.compare_digest(hashlib.sha256(credential['token'].encode()).hexdigest(),self.plan['token_sha256'])):
            raise HostRecoveryFenced("device/caretaker scope mismatch")

    @staticmethod
    def _owner(row):
        return dict(project=row['project'],role=row['role'],actor=row['holder'],generation=row['generation'],epoch=row['epoch'])

    def _guardian(self, value):
        expected=self.plan['guardian']
        if not isinstance(value,dict) or any(value.get(k)!=v for k,v in expected.items()):
            raise HostRecoveryFenced("fixed installed caretaker source/task/SID/session required")
        for k in ('pid','creation_filetime'):
            if type(value.get(k)) is not int or value[k]<=0:
                raise HostRecoveryFenced("current caretaker kernel incarnation missing")

    @staticmethod
    def _process(value):
        if (not isinstance(value,dict) or type(value.get('pid')) is not int or value['pid']<=0
            or type(value.get('creation_filetime')) is not int or value['creation_filetime']<=0):
            raise HostRecoveryFenced("exact native PID/FILETIME required")
        return {k:value[k] for k in ('pid','creation_filetime')}

    @staticmethod
    def _checkpoint(value):
        if (not isinstance(value,dict) or value.get('provider_turn_state')!='completed'
            or type(value.get('pending_tool_count')) is not int or value['pending_tool_count']!=0
            or value.get('protected_state')!='clear'
            or not isinstance(value.get('thread_id'),str) or not value['thread_id']
            or not isinstance(value.get('history_receipt_sha256'),str) or len(value['history_receipt_sha256'])!=64):
            raise HostRecoveryFenced("completed exact provider/history checkpoint required")

    def observe(self, baseline):
        from role_fence import Owner
        from role_fence_cli import active_model
        config=self._config(); owner=baseline.get('owner',{})
        if owner.get('role')!='root' or owner.get('project')!=self.plan['project']:
            raise HostRecoveryFenced("fixed root scope only")
        self._guardian(baseline.get('guardian'))
        self._checkpoint(baseline.get('checkpoint'))
        if not isinstance(baseline.get('profile_sha256'),str) or len(baseline['profile_sha256'])!=64:
            raise HostRecoveryFenced('current producer API profile digest required')
        with self.authority._tx() as db:
            row=self.authority._get(db,owner['project'],'root')
            if self._owner(row)!=owner:
                raise HostRecoveryFenced("actual authority owner mismatch")
            self.authority._valid(db,*Owner(**owner).args())
            binding=config['bindings'].get(owner['actor'])
            if not binding or binding.get('retired') or binding['generation']!=owner['generation'] or baseline.get('host')!=binding['host']:
                raise HostRecoveryFenced("current configured native binding required")
            if active_model(config,Owner(**owner))!=baseline['checkpoint']['thread_id']:
                raise HostRecoveryFenced("immutable activation CID mismatch")
            native=baseline['native'];model=baseline['model']
            if native.get('id')!=owner['actor'] or model.get('owner')!=owner:
                raise HostRecoveryFenced("native/model owner mismatch")
            values=[self._process(native[n]) for n in ('worker','workload','host_process')]+[self._process(model['backend'])]
            if owner['generation']!='win32:'+str(values[2]['pid'])+':'+str(values[2]['creation_filetime']):
                raise HostRecoveryFenced("native kernel generation mismatch")
            if baseline['guardian']['pid'] in {x['pid'] for x in values} or model['job'].get('session_id')!=2 or not model['job'].get('name'):
                raise HostRecoveryFenced("caretaker/root Job boundary mismatch")
            db.execute("INSERT OR REPLACE INTO host_kernel_baselines VALUES(?,?)",(self.digest(owner),json.dumps(baseline,sort_keys=True,allow_nan=False)))
        return {'status':'baseline_observed','baseline_sha256':self.digest(baseline)}

    def _select(self, project, role, row):
        owner=self._owner(row)
        if project!=self.plan['project'] or role!='root':raise HostRecoveryFenced("fixed root role only")
        with __import__('sqlite3').connect(self.authority.path) as db:
            saved=db.execute('SELECT payload FROM host_kernel_baselines WHERE owner_key=?',(self.digest(owner),)).fetchone()
        if saved: rich=json.loads(saved[0])
        else:
            kill=self._fixed('kill');model=self._fixed('model');cp=self._fixed('checkpoint')
            if (kill.get('owner')!=owner or model.get('owner')!=owner or kill.get('cid')!=cp.get('thread_id')
                or model['model'].get('thread_id')!=cp.get('thread_id') or kill.get('phase')!='killed-awaiting-automatic-recovery'
                or kill.get('job_drained')!={'active_processes':0,'source':'QueryInformationJobObject'}
                or self.plan['operator']['kill']['sha256']!=self._operator_sha()):
                raise HostRecoveryFenced("fixed operator baseline mismatch")
            self._checkpoint(cp)
            from role_fence import Owner
            from role_fence_cli import active_model
            if self.plan['operator'].get('mode') == 'fixed-unactivated-cold-repair':
                self._unactivated_operator(row, owner, kill, model, cp)
            elif active_model(self._config(),Owner(**owner))!=cp['thread_id']:
                raise HostRecoveryFenced('immutable operator activation CID mismatch')
            rich={'owner':owner,'host':self._config()['bindings'][owner['actor']]['host'],'mode':'operator-bootstrap',
                'kill':kill,'checkpoint':cp,'profile_sha256':self.plan['operator']['profile_sha256']}
        baseline=OwnerBaseline(project,role,owner['actor'],owner['generation'],owner['epoch'],self.digest(rich))
        self._selected=rich
        return baseline

    def _baseline(self, nonce):
        # Verification runs inside the drain transaction. A second writer
        # connection would deadlock; these immutable selections are committed.
        with __import__('sqlite3').connect(__import__('pathlib').Path(self.authority.path).as_uri()+"?mode=ro",uri=True) as db:
            db.row_factory=__import__('sqlite3').Row
            row=db.execute('SELECT baseline_json FROM host_recovery_attempts WHERE nonce=?',(nonce,)).fetchone()
            if not row:raise HostRecoveryFenced('unknown server nonce')
            base=OwnerBaseline(**json.loads(row[0]))
            stored=db.execute('SELECT payload FROM host_wire_selected WHERE nonce=?',(nonce,)).fetchone()
            if not stored:raise HostRecoveryFenced('selected native baseline missing')
            return base,json.loads(stored[0])

    def _drain(self, reference, baseline, nonce):
        rich=self._receipts[reference];selected=self._baseline(nonce)[1]
        owner=dict(project=baseline.project,role=baseline.role,actor=baseline.actor,generation=baseline.generation,epoch=baseline.epoch)
        if rich.get('v')!=1 or rich.get('challenge')!=nonce or rich.get('owner')!=owner or rich.get('host')!=selected['host']:
            raise HostRecoveryFenced('nonce/owner/host mismatch')
        self._guardian(rich.get('guardian'));self._checkpoint(rich.get('checkpoint'))
        if rich['checkpoint']!=selected['checkpoint']:raise HostRecoveryFenced('completed history changed')
        observed=rich.get('observed_at')
        if type(observed) not in (float,int) or not math.isfinite(observed) or not -1 <= self.authority.clock()-observed <= 30:
            raise HostRecoveryFenced('fresh native observation required')
        operator=selected.get('mode')=='operator-bootstrap'
        if operator:
            if (rich.get('mode')!='operator-bootstrap' or rich.get('operator_receipt_sha256')!=self._operator_sha()
                or rich.get('operator_receipt')!=selected['kill'] or rich.get('current_exact_family_dead') is not True
                or rich.get('job')!={'queried':False,'historical_receipt_sha256':self._operator_sha()}):
                raise HostRecoveryFenced('explicit fixed operator drain only; no fresh Job claim')
        else:
            if rich.get('mode') not in (None,'automatic') or rich.get('factory_attempt','missing') is not None:
                raise HostRecoveryFenced('automatic factory state unknown')
            if any(rich['guardian'].get(k)!=v for k,v in selected['guardian'].items()) or rich['guardian'].get('state')!='alive' or rich['guardian'].get('outside_owned_jobs') is not True:
                raise HostRecoveryFenced('exact outside-root caretaker incarnation required')
            for name in ('worker','workload','host_process'):
                if self._process(rich['native'].get(name))!=selected['native'][name] or rich['native'][name].get('state')!='dead':raise HostRecoveryFenced('actual exact native family death required')
            if (rich['native'].get('id')!=owner['actor'] or rich['model'].get('owner')!=owner
                or self._process(rich['model'].get('backend'))!=selected['model']['backend'] or rich['model']['backend'].get('state')!='dead'):
                raise HostRecoveryFenced('actual exact model death required')
            expected=dict(selected['model']['job'],queried=True,active_processes=0)
            if rich['model'].get('job')!=expected or type(rich['model']['job']['active_processes']) is not int:
                raise HostRecoveryFenced('fresh retained exact Job zero query required')
        return VerifiedDrain(baseline,nonce,reference,self.digest(rich),True,not operator,float(self.authority.clock()),
            'operator-bootstrap' if operator else 'automatic',self._operator_sha() if operator else None)

    def _permit_intent(self, nonce, baseline):
        return 'factory-permit:'+nonce

    def _successor(self, reference, baseline, nonce):
        s=self._successors[reference];owner=dict(project=baseline.project,role=baseline.role,actor=baseline.actor,generation=baseline.generation,epoch=baseline.epoch)
        if not isinstance(s.get('actor'),str) or s['actor']==baseline.actor:
            raise HostRecoveryFenced('genuine successor/new actor required')
        k=self._process(s.get('kernel'));generation='win32:'+str(k['pid'])+':'+str(k['creation_filetime'])
        if s.get('generation')!=generation or s.get('whoami',{}).get('id')!=s['actor'] or s['whoami'].get('tag')!=s.get('root_tag'):
            raise HostRecoveryFenced('actual successor WHOAMI/kernel mismatch')
        key=hashlib.sha256(nonce.encode()).hexdigest()
        if (s.get('actual_leaf_verified') is not True
            or s.get('root_tag')!='win35-root-capsule-api-recovery-'+key[:16]
            or s.get('state_dir','').replace(chr(92),'/')!=self.plan['win_state_root'].rstrip('/')+'/recovery-'+key
            or s.get('host')!=self._baseline(nonce)[1]['host']
            or not isinstance(s.get('leaf_sha256'),str) or len(s['leaf_sha256'])!=64
            or not isinstance(s.get('holding_profile_sha256'),str) or len(s['holding_profile_sha256'])!=64):
            raise HostRecoveryFenced('fixed nonce-derived actual factory/leaf proof required')
        return VerifiedSuccessor(baseline,nonce,reference,s['actor'],generation,self.digest(k),self.plan['factory_sha256'],self.authority.clock())

    def _enroll(self, proof):
        # Server-owned profile callback is installed by the accepted one-writer
        # adoption plan. It receives only this verified fixed successor object.
        callback=getattr(self,'held_enrollment',None)
        if callback is None:raise HostRecoveryFenced('held enrollment adapter not installed')
        return callback(proof,self._successors[proof.proof_ref])

    def handle(self, request, fingerprint):
        self.authenticate(request.get('credential'),fingerprint)
        if request.get('v')!=1 or set(request)-{'v','credential','op','baseline','challenge','receipt','successor'}:
            raise HostRecoveryFenced('strict host protocol required')
        with self._lock:
            op=request.get('op')
            if op=='observe-baseline':return self.observe(request['baseline'])
            if op=='challenge':
                result=self.adapter.challenge(self.plan['project'],'root')
                nonce=result['challenge']
                with self.authority._tx() as db:
                    db.execute('CREATE TABLE IF NOT EXISTS host_wire_selected(nonce TEXT PRIMARY KEY,payload TEXT NOT NULL)')
                    if not db.execute('SELECT 1 FROM host_wire_selected WHERE nonce=?',(nonce,)).fetchone():
                        db.execute('INSERT INTO host_wire_selected VALUES(?,?)',(nonce,json.dumps(self._selected,sort_keys=True,allow_nan=False)))
                selected=self._baseline(nonce)[1]
                response={'challenge':nonce,'baseline':selected,'mode':selected.get('mode','automatic')}
                if response['mode']=='operator-bootstrap':response['operator_receipt_sha256']=self._operator_sha()
                return response
            if op!='reconcile':raise HostRecoveryFenced('fixed host operation required')
            nonce=request['challenge'];baseline,selected=self._baseline(nonce)
            if 'receipt' in request:
                receipt=request['receipt'];reference=self.digest(receipt);self._receipts[reference]=receipt
                self.adapter.drain(nonce,reference)
                self.adapter.dispatch_factory(nonce)
                owner=selected['owner'];profile=selected['profile_sha256']
                expected={'challenge':nonce,'owner':owner,'profile_sha256':profile}
                return {'permit':dict(expected,v=1,operation='fixed-native-factory'),'expected':expected}
            if 'successor' in request:
                reference=self.digest(request['successor']);self._successors[reference]=request['successor']
                result=self.adapter.reconcile(nonce,reference)
                callback=getattr(self,'read_handoff',None)
                if result['state']!='held-completed' or callback is None:raise HostRecoveryFenced('private held handoff unavailable')
                return callback(nonce,result['binding_digest'])
            raise HostRecoveryFenced('exact receipt or successor required')


    def _held_enrollment(self, proof, successor):
        """One fixed privileged recovery adapter, under the existing writer locks.

        The retired root is already CAS-fenced. Never call its live-role action
        interface or invent a native sender. Only the actual new native leaf is
        registered in the maintained Bus; every new observation remains held.
        """
        import pathlib,fcntl,uuid
        from role_fence_cli import private_json
        from role_fence_enrollment import atomic_profile
        from coordination.bus import FileBus
        path=pathlib.Path(self.config_path)
        with open(path.parent/'install.lock','a') as install, open(path.parent/'profile.lock','a') as profile_lock:
            fcntl.flock(install,fcntl.LOCK_EX);fcntl.flock(profile_lock,fcntl.LOCK_EX)
            config=private_json(path)
            old_actor=proof.baseline.actor; actor=proof.new_actor
            if str(uuid.UUID(actor))!=actor:raise HostRecoveryFenced('canonical genuine native UUID required')
            binding=config['bindings'][old_actor]
            if (binding['project']!=proof.baseline.project or binding['role']!='root'
                or binding['generation']!=proof.baseline.generation or binding['host']!=successor['host']
                or successor['whoami'].get('workspace','').replace(chr(92),'/').lower()!=self.plan['win_workspace'].lower()):
                raise HostRecoveryFenced('actual native workspace/host/predecessor mismatch')
            key=proof.nonce
            recorded=config.get('host_successors',{}).get(key)
            if recorded:
                if recorded['actor']!=actor or recorded['generation']!=proof.new_generation:
                    raise HostRecoveryFenced('private held record conflict')
                raise HostRecoveryFenced('partial enrollment already recorded; controlled exact reconciliation required')
            with self.authority._tx() as db:
                row=self.authority._get(db,proof.baseline.project,'root')
                if row['holder'] is not None or row['epoch']!=proof.baseline.epoch+1:
                    raise HostRecoveryFenced('expected fenced vacant epoch required; no current-owner overwrite')
                if (actor in config['bindings'] or db.execute('SELECT 1 FROM agents WHERE id=?',(actor,)).fetchone()
                    or db.execute('SELECT 1 FROM candidates WHERE agent=?',(actor,)).fetchone()):
                    raise HostRecoveryFenced('new leaf already has authority custody')
                old=db.execute('SELECT priority FROM agents WHERE id=?',(old_actor,)).fetchone()
                if not old:raise HostRecoveryFenced('predecessor admission metadata missing')
                bus=FileBus(config['bus_store']); name='win35-root-native:'+actor
                identities=bus._read(bus._identities,{})
                matches=[i for i in identities.values() if i.get('agent_name')==name]
                if len(matches)>1:raise HostRecoveryFenced('ambiguous native enrollment')
                if matches:
                    ident=matches[0]
                    if (ident['device_id'],ident['project_id'])!=(binding['host'],binding['project']):
                        raise HostRecoveryFenced('native identity scope conflict')
                    identity_id=ident['identity_id'];token=bus._read(bus._tokens,{}).get(identity_id)
                    if not token:raise HostRecoveryFenced('incomplete native enrollment remains held')
                else:
                    ident,token=bus.register(agent_name=name,device_id=binding['host'],project_id=binding['project'])
                    identity_id=ident.identity_id
                new_binding=dict(project=binding['project'],role='root',host=binding['host'],generation=proof.new_generation,
                    bus_identity=identity_id,capsule_tag_prefix=binding.get('capsule_tag_prefix','win35-root-capsule-'))
                binding['retired']=True; config['bindings'][actor]=new_binding
                for scope in config['tls_clients'].values():
                    scopes=scope.get('actors',[scope])
                    if any(x.get('actor')==old_actor and x.get('bus_identity')==binding['bus_identity'] for x in scopes):
                        if 'actors' not in scope:
                            previous=dict(scope);scope.clear();scope['actors']=[previous]
                        scope['actors'].append(dict(actor=actor,role='root',project=binding['project'],bus_identity=identity_id))
                handoff=dict(status='enrolled_held_api_candidate',actor=actor,generation=proof.new_generation,
                    root_tag=successor['root_tag'],project=binding['project'],role='root',owner_is_candidate_context_only=True,
                    owner=dict(project=binding['project'],role='root',actor=actor,generation=proof.new_generation,epoch=1),
                    credential=dict(identity_id=identity_id,token=token))
                digest=self.digest(handoff)
                config.setdefault('host_successors',{})[key]=dict(handoff=handoff,binding_digest=digest,
                    actor=actor,generation=proof.new_generation,leaf_sha256=successor['leaf_sha256'],predecessor=old_actor)
                # Persist exact private expected after-state before the held DB
                # transaction commits. Ambiguous crashes remain held, never
                # replay factory/register or overwrite another role owner.
                atomic_profile(path,config)
                db.execute('UPDATE agents SET ready=0,draft=1,quota=0 WHERE id=?',(old_actor,))
                db.execute('INSERT INTO agents VALUES(?,?,?,?,?,?,?,?)',
                    (actor,binding['host'],proof.new_generation,self.authority.clock(),0,1,0,old[0]))
                db.execute('INSERT INTO candidates VALUES(?,?,?)',(binding['project'],'root',actor))
                self.authority._event(db,binding['project'],'root','host_successor_registered_held',row['epoch'],
                    {'actor':actor,'generation':proof.new_generation,'predecessor':old_actor})
                return {'binding_digest':digest}

    def _read_handoff(self, nonce, digest):
        record=self._config().get('host_successors',{}).get(nonce)
        if not record or record['binding_digest']!=digest or self.digest(record['handoff'])!=digest:
            raise HostRecoveryFenced('exact private held handoff required')
        return record['handoff']
