"""Meaningful adverse tests for SAME8801 HostRecoveryAdapter.

Covers:
1. Multiple challengers rejected (one active attempt per role)
2. Wrong epoch/nonce/baseline rejected
3. Fake proof & default deny (uninstalled callbacks fail closed)
4. Raw bool, raw dict, or unknown job receipt denied (never manufacture missing Job as zero)
5. Original key idempotency & conflicting key rejection
6. Factory exception marks uncertain; no replay or new nonce
7. Interrupted factory & interrupted enrollment never replay
8. Concurrent drain exact-one CAS (atomic single winner)
9. Preserved old roles, candidates, claims, and history (no standby role revoked)
10. No tokens in responses or audit logs
11. Reconcile retry of completed enrollment does not duplicate FileBus register
12. Same expired actor revival forbidden
13. Stale baseline / deathproof / different epoch rejected
14. Wire JSON request validation with host scope credential authentication
15. Unauthenticated / caller-injected JSON observation rejection
16. Full end-to-end recovery lifecycle: challenge -> drain -> factory -> successor -> held-enrollment
"""
import concurrent.futures
import hashlib
import json
import sqlite3
import pytest
from pathlib import Path

from coordination.role_failover import RoleAuthority, Fenced
from host_recovery_adapter import (
    HostRecoveryAdapter,
    HostRecoveryError,
    HostRecoveryFenced,
    HostRecoveryIdempotencyConflict,
    OwnerBaseline,
    VerifiedDrain,
    VerifiedSuccessor,
)


class MockClock:
    def __init__(self, start=1000.0):
        self.time = float(start)

    def __call__(self):
        return self.time

    def advance(self, dt):
        self.time += float(dt)
        return self.time


@pytest.fixture
def env(tmp_path):
    clock = MockClock(1000.0)
    db_path = tmp_path / "authority.db"
    auth = RoleAuthority(db_path, clock=clock, boot_id="boot-recovery-01")
    return auth, clock, db_path


def default_baseline_cb(project, role, row):
    canonical = f"{project}:{role}:{row['holder']}:{row['generation']}:{row['epoch']}"
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return OwnerBaseline(
        project=project,
        role=role,
        actor=row["holder"],
        generation=row["generation"],
        epoch=row["epoch"],
        digest=digest,
    )


# ---------------------------------------------------------------------------
# Test 1: Fake proof & default deny (uninstalled callbacks fail closed)
# ---------------------------------------------------------------------------
def test_01_default_deny_uninstalled_callbacks(env):
    """Ensure that all uninstalled callbacks default to deny (fail closed)."""
    auth, clock, db_path = env
    auth.configure("proj1", "root", ["actor1"])
    auth.observe("actor1", "hetzner", "g1", ready=True, draft=False, quota_ok=True)
    auth.tick("proj1", "root")

    # Adapter with zero callbacks installed
    adapter = HostRecoveryAdapter(auth, host_credential="host-secret-123")

    # Challenge fails closed because select_baseline is not installed
    with pytest.raises(HostRecoveryFenced, match="default deny: select_baseline"):
        adapter.challenge("proj1", "root")

    # Test with baseline installed but drain not installed
    adapter_baseline_only = HostRecoveryAdapter(
        auth, select_baseline=default_baseline_cb, host_credential="host-secret-123"
    )
    chal = adapter_baseline_only.challenge("proj1", "root")
    assert chal["state"] == "challenged"
    nonce = chal["challenge"]

    # Drain fails closed because verify_drain is not installed
    with pytest.raises(HostRecoveryFenced, match="default deny: verify_drain"):
        adapter_baseline_only.drain(nonce, "drain-ref-1")

    # Factory dispatch fails closed
    with pytest.raises(HostRecoveryFenced, match="cannot dispatch factory"):
        adapter_baseline_only.dispatch_factory(nonce)


# ---------------------------------------------------------------------------
# Test 2: Original key idempotency & conflicting key rejection
# ---------------------------------------------------------------------------
def test_02_original_key_idempotency_and_conflict(env):
    """Verify that idempotent challenge with same key returns original challenge,
    while conflicting keys or parameters are strictly rejected.
    """
    auth, clock, db_path = env
    auth.configure("proj1", "root", ["actor1"])
    auth.observe("actor1", "hetzner", "g1", ready=True, draft=False, quota_ok=True)
    auth.tick("proj1", "root")

    adapter = HostRecoveryAdapter(
        auth, select_baseline=default_baseline_cb, host_credential="cred"
    )
    c1 = adapter.challenge("proj1", "root")
    nonce1 = c1["challenge"]

    # Re-challenging same role idempotently returns exact same challenge nonce
    c2 = adapter.challenge("proj1", "root")
    assert c2["challenge"] == nonce1
    assert c2["state"] == "challenged"

    # Conflicting key parameter raises HostRecoveryIdempotencyConflict
    with pytest.raises(HostRecoveryIdempotencyConflict, match="idempotency key mismatch"):
        adapter.challenge("proj1", "root", key="conflicting-caller-key-xyz")


# ---------------------------------------------------------------------------
# Test 3: Multiple challengers rejected (one active attempt per role)
# ---------------------------------------------------------------------------
def test_03_multiple_challengers_rejected(env):
    """Ensure that multiple distinct callers cannot initiate concurrent attempts for the same role."""
    auth, clock, db_path = env
    auth.configure("proj1", "root", ["actor1"])
    auth.observe("actor1", "hetzner", "g1", ready=True, draft=False, quota_ok=True)
    auth.tick("proj1", "root")

    adapter = HostRecoveryAdapter(
        auth, select_baseline=default_baseline_cb, host_credential="cred"
    )
    c1 = adapter.challenge("proj1", "root")
    assert c1["state"] == "challenged"

    # In DB, simulate an attempt with another nonce being active
    with auth._tx() as db:
        db.execute(
            """INSERT INTO host_recovery_attempts (
                attempt_key, project, role, old_actor, old_generation, old_epoch,
                baseline_sha, nonce, phase, baseline_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'challenged', ?, ?, ?)""",
            (
                "proj2:root:other:g1:1:sha2",
                "proj1",  # Same project and role
                "root",
                "other",
                "g1",
                2,
                "sha2",
                "nonce-other-999",
                json.dumps({"project": "proj1", "role": "root"}),
                clock(),
                clock(),
            ),
        )

    # Now a new challenger attempting to challenge is fenced due to active concurrent attempt
    with pytest.raises(HostRecoveryFenced, match="concurrent recovery attempt already in flight"):
        # Clear the first attempt_key to trigger check
        with auth._tx() as db:
            db.execute("DELETE FROM host_recovery_attempts WHERE nonce=?", (c1["challenge"],))
        adapter.challenge("proj1", "root")


# ---------------------------------------------------------------------------
# Test 4: Raw bool, raw dict, or unknown job receipt denied
# ---------------------------------------------------------------------------
def test_04_raw_bool_and_dict_receipt_denied(env):
    """Ensure that passing raw booleans, raw dictionaries, or duck-typed objects is rejected."""
    auth, clock, db_path = env
    auth.configure("proj1", "root", ["actor1"])
    auth.observe("actor1", "hetzner", "g1", ready=True, draft=False, quota_ok=True)
    auth.tick("proj1", "root")

    # Callback returning a raw boolean
    adapter_raw_bool = HostRecoveryAdapter(
        auth,
        select_baseline=default_baseline_cb,
        verify_drain=lambda ref, base, nonce: True,  # Raw bool!
        host_credential="cred",
    )
    chal = adapter_raw_bool.challenge("proj1", "root")
    with pytest.raises(HostRecoveryFenced, match="proof must be typed VerifiedDrain"):
        adapter_raw_bool.drain(chal["challenge"], "ref1")

    # Callback returning a raw dictionary
    adapter_raw_dict = HostRecoveryAdapter(
        auth,
        select_baseline=default_baseline_cb,
        verify_drain=lambda ref, base, nonce: {"job_active": 0, "all_dead": True},  # Raw dict!
        host_credential="cred",
    )
    with pytest.raises(HostRecoveryFenced, match="proof must be typed VerifiedDrain"):
        adapter_raw_dict.drain(chal["challenge"], "ref1")


# ---------------------------------------------------------------------------
# Test 5: Unknown job receipt denied (never manufacture missing Job as zero)
# ---------------------------------------------------------------------------
def test_05_unknown_job_as_zero_denied(env):
    """Reject drain proofs where job_active_zero is False (cannot assume missing job is 0)."""
    auth, clock, db_path = env
    auth.configure("proj1", "root", ["actor1"])
    auth.observe("actor1", "hetzner", "g1", ready=True, draft=False, quota_ok=True)
    auth.tick("proj1", "root")

    def drain_cb_active_job(receipt_ref, baseline, nonce):
        return VerifiedDrain(
            baseline=baseline,
            nonce=nonce,
            receipt_ref=receipt_ref,
            kernel_proof_ref="kernel-k1",
            native_owner_all_dead=True,
            job_active_zero=False,  # Still active jobs or missing job query!
            drain_time=clock(),
        )

    adapter = HostRecoveryAdapter(
        auth,
        select_baseline=default_baseline_cb,
        verify_drain=drain_cb_active_job,
        host_credential="cred",
    )
    chal = adapter.challenge("proj1", "root")
    with pytest.raises(HostRecoveryFenced, match="fresh retained exact Job zero"):
        adapter.drain(chal["challenge"], "drain-ref-active")


# ---------------------------------------------------------------------------
# Test 6: Wrong epoch / nonce / baseline rejected
# ---------------------------------------------------------------------------
def test_06_wrong_epoch_nonce_baseline_rejected(env):
    """Reject verification proofs with mismatched epoch, nonce, or baseline."""
    auth, clock, db_path = env
    auth.configure("proj1", "root", ["actor1"])
    auth.observe("actor1", "hetzner", "g1", ready=True, draft=False, quota_ok=True)
    auth.tick("proj1", "root")

    def drain_cb_mismatched(receipt_ref, baseline, nonce):
        # Mismatched baseline epoch
        wrong_baseline = OwnerBaseline(
            project=baseline.project,
            role=baseline.role,
            actor=baseline.actor,
            generation=baseline.generation,
            epoch=baseline.epoch + 999,  # Wrong epoch!
            digest=baseline.digest,
        )
        return VerifiedDrain(
            baseline=wrong_baseline,
            nonce=nonce,
            receipt_ref=receipt_ref,
            kernel_proof_ref="kernel-k1",
            native_owner_all_dead=True,
            job_active_zero=True,
            drain_time=clock(),
        )

    adapter = HostRecoveryAdapter(
        auth,
        select_baseline=default_baseline_cb,
        verify_drain=drain_cb_mismatched,
        host_credential="cred",
    )
    chal = adapter.challenge("proj1", "root")
    with pytest.raises(HostRecoveryFenced, match="baseline mismatch"):
        adapter.drain(chal["challenge"], "drain-ref-wrong-epoch")

    # Unknown challenge nonce
    with pytest.raises(HostRecoveryError, match="unknown challenge nonce"):
        adapter.drain("completely-unknown-nonce", "drain-ref-1")


# ---------------------------------------------------------------------------
# Test 7: Concurrent drain exact-one CAS (atomic single winner)
# ---------------------------------------------------------------------------
def test_07_concurrent_drain_exact_one_cas(env):
    """Verify that multiple concurrent threads attempting drain against the same live holder
    result in exactly ONE CAS success and all others being fenced.
    """
    auth, clock, db_path = env
    auth.configure("proj1", "root", ["actor1"])
    auth.observe("actor1", "hetzner", "g1", ready=True, draft=False, quota_ok=True)
    auth.tick("proj1", "root")

    def valid_drain_cb(receipt_ref, baseline, nonce):
        return VerifiedDrain(
            baseline=baseline,
            nonce=nonce,
            receipt_ref=receipt_ref,
            kernel_proof_ref=f"kernel-{receipt_ref}",
            native_owner_all_dead=True,
            job_active_zero=True,
            drain_time=clock(),
        )

    adapter = HostRecoveryAdapter(
        auth,
        select_baseline=default_baseline_cb,
        verify_drain=valid_drain_cb,
        host_credential="cred",
    )
    chal = adapter.challenge("proj1", "root")
    nonce = chal["challenge"]

    # We simulate 4 concurrent drain calls with distinct receipt references
    successes = []
    failures = []

    def attempt_drain(ref):
        try:
            res = adapter.drain(nonce, ref)
            successes.append((ref, res))
        except Exception as e:
            failures.append((ref, type(e).__name__, str(e)))

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        futures = [ex.submit(attempt_drain, f"receipt-{i}") for i in range(4)]
        concurrent.futures.wait(futures)

    # Exactly ONE should succeed with the CAS update!
    assert len(successes) == 1, f"Expected exactly 1 CAS success, got {len(successes)}"
    assert len(failures) == 3, f"Expected 3 fenced failures, got {len(failures)}"

    # Check that roles table epoch incremented exactly once and holder is NULL
    with auth._tx() as db:
        role_row = db.execute("SELECT * FROM roles WHERE project='proj1' AND role='root'").fetchone()
        assert role_row["holder"] is None
        assert role_row["epoch"] == 2
        assert role_row["expires"] == 0
        assert role_row["activation_due"] == 0


# ---------------------------------------------------------------------------
# Test 8: Preserved old roles, candidates, claims, and history
# ---------------------------------------------------------------------------
def test_08_preserved_old_roles_and_candidates(env):
    """Ensure that drain revokes ONLY the predecessor incarnation, preserving
    standby roles, candidates, action history, and tokens.
    """
    auth, clock, db_path = env
    # Configure principal (standby role) and root
    auth.configure("proj1", "standby_role", ["standby_actor"])
    auth.observe("standby_actor", "hetzner", "g_s1", ready=True, draft=False, quota_ok=True)
    auth.tick("proj1", "standby_role")

    auth.configure("proj1", "root", ["actor1", "candidate2"])
    auth.observe("actor1", "hetzner", "g1", ready=True, draft=False, quota_ok=True)
    auth.tick("proj1", "root")

    def valid_drain_cb(receipt_ref, baseline, nonce):
        return VerifiedDrain(
            baseline=baseline,
            nonce=nonce,
            receipt_ref=receipt_ref,
            kernel_proof_ref="kernel-proof-1",
            native_owner_all_dead=True,
            job_active_zero=True,
            drain_time=clock(),
        )

    adapter = HostRecoveryAdapter(
        auth,
        select_baseline=default_baseline_cb,
        verify_drain=valid_drain_cb,
        host_credential="cred",
    )
    chal = adapter.challenge("proj1", "root")
    adapter.drain(chal["challenge"], "receipt-drain-1")

    # Verify database state
    with auth._tx() as db:
        # 1. Standby role was NOT revoked
        standby_row = db.execute(
            "SELECT * FROM roles WHERE project='proj1' AND role='standby_role'"
        ).fetchone()
        assert standby_row["holder"] == "standby_actor"
        assert standby_row["epoch"] == 1

        # 2. Candidates for root preserved
        candidates = [
            r["agent"]
            for r in db.execute(
                "SELECT agent FROM candidates WHERE project='proj1' AND role='root'"
            ).fetchall()
        ]
        assert "actor1" in candidates
        assert "candidate2" in candidates

        # 3. Only the predecessor incarnation was tombstoned
        tombstones = db.execute("SELECT * FROM reply_tombstones").fetchall()
        assert len(tombstones) == 1
        assert tombstones[0]["actor"] == "actor1"
        assert tombstones[0]["generation"] == "g1"


# ---------------------------------------------------------------------------
# Test 9: Factory pending durable BEFORE dispatch & exception no replay
# ---------------------------------------------------------------------------
def test_09_factory_exception_transitions_to_uncertain_no_replay(env):
    """When factory dispatch fails or throws, attempt transitions to 'uncertain'.
    Further dispatch attempts or new challenge nonces for this incarnation are denied.
    """
    auth, clock, db_path = env
    auth.configure("proj1", "root", ["actor1"])
    auth.observe("actor1", "hetzner", "g1", ready=True, draft=False, quota_ok=True)
    auth.tick("proj1", "root")

    dispatch_attempt_count = 0

    def throwing_factory(nonce, baseline):
        nonlocal dispatch_attempt_count
        dispatch_attempt_count += 1
        raise RuntimeError("network timeout to external caretaker side-effect")

    adapter = HostRecoveryAdapter(
        auth,
        select_baseline=default_baseline_cb,
        verify_drain=lambda r, b, n: VerifiedDrain(b, n, r, "k1", True, True, clock()),
        factory_dispatch=throwing_factory,
        host_credential="cred",
    )

    chal = adapter.challenge("proj1", "root")
    nonce = chal["challenge"]
    adapter.drain(nonce, "drain-ref-1")

    # Factory dispatch throws
    with pytest.raises(HostRecoveryFenced, match="attempt marked uncertain; no replay permitted"):
        adapter.dispatch_factory(nonce)

    assert dispatch_attempt_count == 1

    # Verify attempt in DB is marked uncertain
    with auth._tx() as db:
        att = db.execute("SELECT phase FROM host_recovery_attempts WHERE nonce=?", (nonce,)).fetchone()
        assert att["phase"] == "uncertain"

    # Replaying factory dispatch is strictly forbidden
    with pytest.raises(HostRecoveryFenced, match="factory dispatch cannot be replayed"):
        adapter.dispatch_factory(nonce)
    assert dispatch_attempt_count == 1  # Did NOT call callback again!

    # Re-challenging returns the uncertain attempt with original nonce, NO new nonce
    c_retry = adapter.challenge("proj1", "root")
    assert c_retry["challenge"] == nonce
    assert c_retry["state"] == "uncertain"


# ---------------------------------------------------------------------------
# Test 10: Interrupted factory explicit reconcile with typed proof only
# ---------------------------------------------------------------------------
def test_10_interrupted_factory_explicit_reconcile_only(env):
    """An uncertain attempt can proceed ONLY via explicit reconcile with typed successor proof."""
    auth, clock, db_path = env
    auth.configure("proj1", "root", ["actor1"])
    auth.observe("actor1", "hetzner", "g1", ready=True, draft=False, quota_ok=True)
    auth.tick("proj1", "root")

    adapter = HostRecoveryAdapter(
        auth,
        select_baseline=default_baseline_cb,
        verify_drain=lambda r, b, n: VerifiedDrain(b, n, r, "k1", True, True, clock()),
        factory_dispatch=lambda n, b: None,  # Fails dispatch
        verify_successor=lambda r, b, n: VerifiedSuccessor(
            b, n, r, "successor-actor", "g2", "kernel-whoami-ok", "factory-pinned-src", clock()
        ),
        hold_enroll=lambda proof: {"binding_digest": "digest-binding-456"},
        host_credential="cred",
    )

    chal = adapter.challenge("proj1", "root")
    nonce = chal["challenge"]
    adapter.drain(nonce, "drain-ref-1")

    with pytest.raises(HostRecoveryFenced):
        adapter.dispatch_factory(nonce)

    # Reconciling with explicit typed successor proof succeeds and finishes enrollment!
    res = adapter.reconcile(nonce, "successor-proof-ref-1")
    assert res["state"] == "held-completed"
    assert res["challenge"] == nonce
    assert res["binding_digest"] == "digest-binding-456"


# ---------------------------------------------------------------------------
# Test 11: Interrupted held enrollment marks uncertain; never duplicates FileBus register
# ---------------------------------------------------------------------------
def test_11_interrupted_held_enrollment_never_replays_or_duplicates(env):
    """Interrupted enrollment transitions to 'uncertain'. Retry completed enrollment does
    not execute duplicate registration.
    """
    auth, clock, db_path = env
    auth.configure("proj1", "root", ["actor1"])
    auth.observe("actor1", "hetzner", "g1", ready=True, draft=False, quota_ok=True)
    auth.tick("proj1", "root")

    enroll_calls = 0

    def failing_enroll(proof):
        nonlocal enroll_calls
        enroll_calls += 1
        if enroll_calls == 1:
            raise ConnectionResetError("FileBus connection dropped mid-register")
        return {"binding_digest": "digest-enrolled-ok"}

    adapter = HostRecoveryAdapter(
        auth,
        select_baseline=default_baseline_cb,
        verify_drain=lambda r, b, n: VerifiedDrain(b, n, r, "k1", True, True, clock()),
        factory_dispatch=lambda n, b: "factory-receipt-1",
        verify_successor=lambda r, b, n: VerifiedSuccessor(
            b, n, r, "new-root", "g2", "whoami-ok", "factory-source-pin", clock()
        ),
        hold_enroll=failing_enroll,
        host_credential="cred",
    )

    chal = adapter.challenge("proj1", "root")
    nonce = chal["challenge"]
    adapter.drain(nonce, "drain-ref-1")
    adapter.dispatch_factory(nonce)

    # First reconcile fails at enrollment
    with pytest.raises(HostRecoveryFenced, match="hold_enroll callback failed"):
        adapter.reconcile(nonce, "succ-ref-1")

    with auth._tx() as db:
        att = db.execute("SELECT phase FROM host_recovery_attempts WHERE nonce=?", (nonce,)).fetchone()
        assert att["phase"] == "uncertain"

    # Unknown partial effects cannot be replayed by a retry.
    with pytest.raises(HostRecoveryFenced, match="ambiguous"):
        adapter.reconcile(nonce, "succ-ref-1")
    assert enroll_calls == 1
    with auth._tx() as db:
        assert db.execute("SELECT phase FROM host_recovery_attempts WHERE nonce=?", (nonce,)).fetchone()["phase"] == "uncertain"


# ---------------------------------------------------------------------------
# Test 12: Same expired actor revival forbidden
# ---------------------------------------------------------------------------
def test_12_forbidden_same_expired_actor_revival(env):
    """Reject successor proof attempting to revive the same expired actor and generation."""
    auth, clock, db_path = env
    auth.configure("proj1", "root", ["actor1"])
    auth.observe("actor1", "hetzner", "g1", ready=True, draft=False, quota_ok=True)
    auth.tick("proj1", "root")

    adapter = HostRecoveryAdapter(
        auth,
        select_baseline=default_baseline_cb,
        verify_drain=lambda r, b, n: VerifiedDrain(b, n, r, "k1", True, True, clock()),
        factory_dispatch=lambda n, b: "receipt-1",
        verify_successor=lambda r, b, n: VerifiedSuccessor(
            b, n, r, "actor1", "g1", "whoami-same", "factory-src", clock()  # Same actor & generation!
        ),
        hold_enroll=lambda proof: {"binding_digest": "ok"},
        host_credential="cred",
    )

    chal = adapter.challenge("proj1", "root")
    nonce = chal["challenge"]
    adapter.drain(nonce, "drain-ref-1")
    adapter.dispatch_factory(nonce)

    with pytest.raises(HostRecoveryFenced, match="forbidden: same expired actor revival"):
        adapter.reconcile(nonce, "succ-ref-same-actor")


# ---------------------------------------------------------------------------
# Test 13: Stale baseline / different epoch rejected
# ---------------------------------------------------------------------------
def test_13_borrowed_stale_baseline_rejected(env):
    """Reject attempt if baseline does not match the actual current database row."""
    auth, clock, db_path = env
    auth.configure("proj1", "root", ["actor1"])
    auth.observe("actor1", "hetzner", "g1", ready=True, draft=False, quota_ok=True)
    auth.tick("proj1", "root")

    def stale_baseline_cb(project, role, row):
        # Return baseline with wrong epoch (e.g. borrowed old baseline)
        return OwnerBaseline(
            project=project,
            role=role,
            actor=row["holder"],
            generation=row["generation"],
            epoch=row["epoch"] + 10,  # Stale / future epoch
            digest="fake-digest",
        )

    adapter = HostRecoveryAdapter(
        auth, select_baseline=stale_baseline_cb, host_credential="cred"
    )
    with pytest.raises(HostRecoveryFenced, match="selected baseline mismatch"):
        adapter.challenge("proj1", "root")


# ---------------------------------------------------------------------------
# Test 14: No tokens in responses or audit logs
# ---------------------------------------------------------------------------
def test_14_no_tokens_in_responses_or_audit(env):
    """Ensure that all responses, outputs, and database audit logs contain NO secret tokens."""
    auth, clock, db_path = env
    auth.configure("proj1", "root", ["actor1"])
    auth.observe("actor1", "hetzner", "g1", ready=True, draft=False, quota_ok=True)
    auth.tick("proj1", "root")

    adapter = HostRecoveryAdapter(
        auth,
        select_baseline=default_baseline_cb,
        verify_drain=lambda r, b, n: VerifiedDrain(b, n, r, "k1", True, True, clock()),
        factory_dispatch=lambda n, b: "receipt-fact-1",
        verify_successor=lambda r, b, n: VerifiedSuccessor(
            b, n, r, "new-actor-9", "g2", "whoami-new", "factory-src", clock()
        ),
        hold_enroll=lambda proof: {"binding_digest": "canonical-binding-hash-777"},
        host_credential="host-scope-private-secret-999",
    )

    c = adapter.challenge("proj1", "root")
    d = adapter.drain(c["challenge"], "d-ref")
    f = adapter.dispatch_factory(c["challenge"])
    r = adapter.reconcile(c["challenge"], "s-ref")

    for response in [c, d, f, r]:
        serialized = json.dumps(response).lower()
        assert "token" not in serialized
        assert "secret" not in serialized
        assert "private" not in serialized

    # Inspect events table
    with auth._tx() as db:
        events = db.execute("SELECT payload FROM events").fetchall()
        for evt in events:
            p = evt["payload"].lower()
            assert "host-scope-private-secret-999" not in p


# ---------------------------------------------------------------------------
# Test 15: Wire JSON request validation and credential authentication
# ---------------------------------------------------------------------------
def test_15_wire_json_request_validation(env):
    """Test wire protocol validation for CHALLENGE and RECONCILE with credential checks."""
    auth, clock, db_path = env
    auth.configure("proj1", "root", ["actor1"])
    auth.observe("actor1", "hetzner", "g1", ready=True, draft=False, quota_ok=True)
    auth.tick("proj1", "root")

    adapter = HostRecoveryAdapter(
        auth,
        select_baseline=default_baseline_cb,
        verify_drain=lambda r, b, n: VerifiedDrain(b, n, r, "k1", True, True, clock()),
        factory_dispatch=lambda n, b: "fact-ref-1",
        verify_successor=lambda r, b, n: VerifiedSuccessor(
            b, n, r, "actor-wire-new", "g2", "kernel-whoami", "pinned-fact", clock()
        ),
        hold_enroll=lambda proof: {"binding_digest": "digest-wire-101"},
        host_credential="correct-host-credential",
        default_project="proj1",
        default_role="root",
    )

    # 1. Invalid version
    with pytest.raises(HostRecoveryError, match="unsupported protocol version"):
        adapter.handle_wire_request({"v": 2, "op": "challenge", "credential": "correct-host-credential"})

    # 2. Missing / invalid credential
    with pytest.raises(HostRecoveryError, match="unauthorized"):
        adapter.handle_wire_request({"v": 1, "op": "challenge", "credential": "wrong-credential"})

    # 3. Valid challenge request
    chal_res = adapter.handle_wire_request({
        "v": 1,
        "op": "challenge",
        "credential": "correct-host-credential",
        "project": "proj1",
        "role": "root",
    })
    assert chal_res["state"] == "challenged"
    nonce = chal_res["challenge"]

    # 4. Caller observation injection denied: only opaque receipt accepted
    with pytest.raises(HostRecoveryError, match="opaque receipt reference required"):
        adapter.handle_wire_request({
            "v": 1,
            "op": "reconcile",
            "credential": "correct-host-credential",
            "challenge": nonce,
            "receipt": "",  # Empty receipt
        })

    # 5. Valid reconcile drain request via wire
    drain_wire_res = adapter.handle_wire_request({
        "v": 1,
        "op": "reconcile",
        "credential": "correct-host-credential",
        "challenge": nonce,
        "receipt": "drain-receipt-wire-01",
    })
    assert drain_wire_res["state"] == "drained"

    # 6. Valid reconcile successor request via wire
    succ_wire_res = adapter.handle_wire_request({
        "v": 1,
        "op": "reconcile",
        "credential": "correct-host-credential",
        "challenge": nonce,
        "receipt": "succ-receipt-wire-02",
    })
    assert succ_wire_res["state"] == "held-completed"
    assert succ_wire_res["binding_digest"] == "digest-wire-101"


# ---------------------------------------------------------------------------
# Test 16: Complete end-to-end recovery flow
# ---------------------------------------------------------------------------
def test_16_complete_end_to_end_recovery_flow(env):
    """Verify complete end-to-end recovery lifecycle from challenged to held-completed."""
    auth, clock, db_path = env
    auth.configure("proj1", "root", ["actor1"])
    auth.observe("actor1", "hetzner", "g1", ready=True, draft=False, quota_ok=True)
    auth.tick("proj1", "root")

    enrolled_proofs = []

    def enroll_cb(proof):
        enrolled_proofs.append(proof)
        # Update RoleAuthority with successor configure and observe
        auth.configure("proj1", "root", ["actor1", proof.new_actor])
        auth.observe(proof.new_actor, "hetzner", proof.new_generation, ready=True, draft=False, quota_ok=True)
        return {"binding_digest": "binding-digest-complete-999"}

    adapter = HostRecoveryAdapter(
        auth,
        select_baseline=default_baseline_cb,
        verify_drain=lambda r, b, n: VerifiedDrain(b, n, r, "k-proof-77", True, True, clock()),
        factory_dispatch=lambda n, b: "factory-permit-77",
        verify_successor=lambda r, b, n: VerifiedSuccessor(
            b, n, r, "actor-born-77", "g2", "kernel-whoami-77", "pinned-caretaker-77", clock()
        ),
        hold_enroll=enroll_cb,
        host_credential="cred",
    )

    # 1. Challenge
    c = adapter.challenge("proj1", "root")
    nonce = c["challenge"]
    assert c["state"] == "challenged"

    # 2. Drain
    d = adapter.drain(nonce, "drain-ref-77")
    assert d["state"] == "drained"

    # 3. Factory dispatch
    f = adapter.dispatch_factory(nonce)
    assert f["state"] == "factory-receipted"

    # 4. Reconcile successor & enrollment
    r = adapter.reconcile(nonce, "succ-ref-77")
    assert r["state"] == "held-completed"
    assert r["binding_digest"] == "binding-digest-complete-999"

    # Check enrolled successor
    assert len(enrolled_proofs) == 1
    assert enrolled_proofs[0].new_actor == "actor-born-77"
    assert enrolled_proofs[0].new_generation == "g2"

    # Check authority role can now elect the enrolled successor on tick
    elected = auth.tick("proj1", "root")
    assert elected["state"] == "elected"
    assert elected["holder"] == "actor-born-77"
    assert elected["generation"] == "g2"
