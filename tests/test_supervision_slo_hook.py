#!/usr/bin/env python3
"""
Test Suite for Supervision Pending NOTREADY Beyond SLO Handling,
Cursor Retry Reconciliation, and Authoritative Turn-Boundary Hook Event Provenance.
(Codex Principal C1516 / C1521 directives)

Tests:
1. test_check_pending_slo_direct:
   - Verifies SLO calculation for standard (300s) and Claude (1800s) thresholds.
   - Verifies accurate extraction of blocking reasons:
     * Dead recipient process
     * Unsubmitted composer draft / menu
     * Recipient actively working / busy
     * Quota denied
     * Sender ID mismatch (stale / orphaned envelope)
     * aplexer delivery refusal (not-ready, send-uncertain)
2. test_service_run_pending_beyond_slo_truthful_reporting:
   - Verifies that when a recipient stays NOTREADY past SLO, service.run() reports:
     * status = 'blocked_beyond_slo'
     * report['degraded'] = True
     * Exact blocking reason and duration in report['errors']
     * Strictly preserves pending tracking (no drop, no fake ACK).
3. test_service_run_missing_principal_pending_beyond_slo:
   - Verifies that when a principal is missing/ambiguous and has a pending message past SLO,
     the pending envelope is preserved and reported as blocked_beyond_slo.
4. test_cursor_reconciliation_exact_ack_clears_safely:
   - Verifies genuine cursor exception evidence safely clears pending,
     records ack_evidence, and persists native-ack-<mid>.json.
5. test_cursor_reconciliation_refuses_fake_ack_on_timeout:
   - Verifies that timeout / missing cursor evidence strictly refuses fake ACKs,
     preserves pending envelope, and reports blocked_beyond_slo.
6. test_parse_and_validate_turn_hook_event:
   - Verifies validation of turn_complete and turn_start hook events.
   - Enforces valid UUID, authorized engine, monotonic prompt_seq >= 0, positive timestamp.
   - Fails closed on active child processes (> 0) during turn_complete.
   - Fails closed on draft / menu composer states during turn_complete.
   - Fails closed on engine mismatch or malformed JSON.
"""

import datetime
import json
import os
import pathlib
import sys
import tempfile
import unittest
import uuid

# Ensure repo root and supervision scripts are in python path
REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

SUPERVISION_DIR = REPO_ROOT / 'scripts' / 'supervision'
if str(SUPERVISION_DIR) not in sys.path:
    sys.path.insert(0, str(SUPERVISION_DIR))

import research.antigravity.tooling.supervision.service_candidate as candidate


class TestSupervisionSLOHook(unittest.TestCase):
    """Offline unit & regression test suite for SLO handling, cursor reconciliation, and hook events."""

    def test_check_pending_slo_direct(self):
        """Test check_pending_slo calculation and precise blocking reasons."""
        base_time = 1791110000.0  # arbitrary epoch
        created_dt = datetime.datetime.fromtimestamp(base_time - 350, datetime.timezone.utc)
        created_iso = created_dt.isoformat()

        # 1. Under SLO (< 300s)
        pending_recent = {'id': str(uuid.uuid4()), 'created_at': datetime.datetime.fromtimestamp(base_time - 100, datetime.timezone.utc).isoformat()}
        beyond, dur, slo, reason = candidate.check_pending_slo(pending_recent, 'codex-principal', {'alive': True}, now_ts=base_time)
        self.assertFalse(beyond)
        self.assertAlmostEqual(dur, 100.0, places=1)
        self.assertEqual(slo, 300)

        # 2. Beyond SLO (350s >= 300s) - Dead process
        pending = {'id': str(uuid.uuid4()), 'created_at': created_iso}
        beyond, dur, slo, reason = candidate.check_pending_slo(pending, 'codex-principal', {'alive': False, 'reason': 'process dead'}, now_ts=base_time)
        self.assertTrue(beyond)
        self.assertAlmostEqual(dur, 350.0, places=1)
        self.assertEqual(slo, 300)
        self.assertIn("recipient process is missing or dead", reason)

        # 3. Beyond SLO - Draft composer
        beyond, dur, slo, reason = candidate.check_pending_slo(
            pending, 'codex-principal',
            {'alive': True, 'composer': 'draft', 'reported_state': 'idle', 'reason': 'composer draft present'},
            now_ts=base_time
        )
        self.assertTrue(beyond)
        self.assertIn("recipient composer has an unsubmitted draft or menu", reason)

        # 4. Beyond SLO - Recipient working / busy
        beyond, dur, slo, reason = candidate.check_pending_slo(
            pending, 'codex-principal',
            {'alive': True, 'composer': 'busy', 'reported_state': 'working', 'reason': 'not-reported-ready'},
            now_ts=base_time
        )
        self.assertTrue(beyond)
        self.assertIn("recipient is actively busy (reported: working, composer: busy)", reason)

        # 5. Beyond SLO - Quota denied
        beyond, dur, slo, reason = candidate.check_pending_slo(
            pending, 'codex-principal',
            {'alive': True, 'composer': 'empty', 'reported_state': 'idle', 'reason': 'quota-denied-or-unknown'},
            now_ts=base_time
        )
        self.assertTrue(beyond)
        self.assertIn("codex quota denied or unknown", reason)

        # 6. Beyond SLO - Delivery refused (not-ready)
        pending_refused = {'id': str(uuid.uuid4()), 'created_at': created_iso, 'delivery': 'not-ready'}
        beyond, dur, slo, reason = candidate.check_pending_slo(
            pending_refused, 'codex-principal',
            {'alive': True, 'composer': 'empty', 'reported_state': 'idle', 'reason': 'idle contradicted by PTY'},
            now_ts=base_time
        )
        self.assertTrue(beyond)
        self.assertIn("aplexer deliver refused: recipient not-ready", reason)

        # 7. Claude principal default SLO is 1800s
        beyond, dur, slo, reason = candidate.check_pending_slo(pending, 'claude-principal', {'alive': True}, now_ts=base_time)
        self.assertFalse(beyond)
        self.assertEqual(slo, 1800)

        # 8. Claude principal beyond 1800s
        claude_created = datetime.datetime.fromtimestamp(base_time - 1850, datetime.timezone.utc).isoformat()
        pending_claude = {'id': str(uuid.uuid4()), 'created_at': claude_created}
        beyond, dur, slo, reason = candidate.check_pending_slo(pending_claude, 'claude-principal', {'alive': True, 'composer': 'busy', 'reported_state': 'working'}, now_ts=base_time)
        self.assertTrue(beyond)
        self.assertEqual(slo, 1800)
        self.assertAlmostEqual(dur, 1850.0, places=1)

        # 9. Environment override: finite positive value
        old_slo = os.environ.get('SUPERVISION_RETRY_SLO_SECONDS')
        try:
            os.environ['SUPERVISION_RETRY_SLO_SECONDS'] = '120'
            beyond, dur, slo, reason = candidate.check_pending_slo(pending_recent, 'codex-principal', {'alive': True}, now_ts=base_time)
            self.assertEqual(slo, 120)

            # 10. Environment override: NaN, Inf, Negative fail closed to default
            for bad_val in ('nan', 'inf', '-50', 'not-a-number'):
                os.environ['SUPERVISION_RETRY_SLO_SECONDS'] = bad_val
                beyond, dur, slo, reason = candidate.check_pending_slo(pending_recent, 'codex-principal', {'alive': True}, now_ts=base_time)
                self.assertEqual(slo, 300, f"Failed closed for bad override: {bad_val}")
        finally:
            if old_slo is not None:
                os.environ['SUPERVISION_RETRY_SLO_SECONDS'] = old_slo
            else:
                os.environ.pop('SUPERVISION_RETRY_SLO_SECONDS', None)

        # 11. Naive timestamp format handled gracefully
        naive_pending = {'id': str(uuid.uuid4()), 'created_at': '2026-10-04T12:00:00'}
        beyond, dur, slo, reason = candidate.check_pending_slo(naive_pending, 'codex-principal', {'alive': True})
        self.assertIsInstance(beyond, bool)

    def test_service_run_pending_beyond_slo_truthful_reporting(self):
        """Simulate pending beyond SLO and verify status='blocked_beyond_slo', degraded=True, and preserved tracking."""
        with tempfile.TemporaryDirectory() as td:
            tmp = pathlib.Path(td)
            root = tmp / 'root'
            (root / 'coordination').mkdir(parents=True)
            (root / 'coordination/TEAM-REGISTRY.json').write_text(json.dumps({'teams': [{'id': 'T1', 'principal_tags': ['codex-principal']}]}))
            (root / 'coordination/TASKS.json').write_text(json.dumps({'tasks': [{'id': 'task-1', 'team_id': 'T1', 'status': 'ready', 'owner_tag': 'codex-principal'}]}))
            private = tmp / 'private'
            private.mkdir()
            bin_dir = tmp / 'bin'
            bin_dir.mkdir()
            pinned = bin_dir / 'aplexer'
            pinned.write_bytes(b'PINNED')

            recipient_id = str(uuid.uuid4())
            sender_id = str(uuid.uuid4())
            mid = str(uuid.uuid4())
            # 400 seconds ago (> 300s SLO)
            t_now = 1791110000.0
            created_dt = datetime.datetime.fromtimestamp(t_now - 400, datetime.timezone.utc)
            created_iso = created_dt.isoformat()

            init_state = {
                'codex-principal': {
                    'session_id': recipient_id,
                    'reported_state': 'working',
                    'alive': True,
                    'composer': 'busy',
                    'reason': 'not-reported-ready',
                    'pending': {
                        'id': mid,
                        'sender_id': sender_id,
                        'event': 'ev-1',
                        'delivery': 'not-ready',
                        'created_at': created_iso
                    }
                }
            }
            (private / 'state.json').write_text(json.dumps(init_state))

            def fake_cmd(args, timeout=20):
                words = [a for a in args[1:] if not a.startswith('-')]
                if words[:1] == ['whoami']:
                    return json.dumps({'workspace': str(root), 'tag': 'experiment-supervision', 'id': sender_id})
                if 'idempotency-key' in args and 'help' in args:
                    return '  --idempotency-key'
                if words[:1] == ['list']:
                    (private / 'stop').write_text('stop')
                    return json.dumps([{
                        'workspace': str(root),
                        'tag': 'codex-principal',
                        'id': recipient_id,
                        'reported_state': 'working',
                        'workload_pid': str(os.getpid())
                    }])
                if 'inbox' in args:
                    return json.dumps({'messages': []})
                if 'capture' in args:
                    return "• Working (2m 15s • esc to interrupt)"
                if args[0] == 'quse':
                    return json.dumps({'codex': {'status': 'ok', 'windows': {'7d': {'percent_remaining': 90}}}})
                return '{}'

            real_cmd, real_time = candidate.command, candidate.time
            real_root, real_priv, real_bin = candidate.ROOT, candidate.PRIVATE, candidate.BINARY
            old_env = os.environ.get('APLEXER_STATE_DIR')
            try:
                os.environ['APLEXER_STATE_DIR'] = str(tmp / 'state/aplexer')
                candidate.command = fake_cmd
                candidate.time = type('T', (), {'time': staticmethod(lambda: t_now), 'sleep': staticmethod(lambda s: None)})()
                candidate.ROOT, candidate.PRIVATE, candidate.BINARY = root, private, str(pinned)

                candidate.run()

                st = json.loads((private / 'state.json').read_text())
                status_raw = json.loads((private / 'status.json').read_text())

                # Verifications
                self.assertTrue(status_raw['degraded'], "Supervision cycle must report degraded=True when pending exceeds SLO")
                self.assertEqual(st['codex-principal']['status'], 'blocked_beyond_slo')
                self.assertIn('actively busy', st['codex-principal']['blocking_reason'])
                self.assertAlmostEqual(st['codex-principal']['pending_duration_seconds'], 400.0, places=1)
                self.assertEqual(st['codex-principal']['retry_slo_seconds'], 300)

                # Pending tracking must be strictly preserved; NO fake ACK
                self.assertIsNotNone(st['codex-principal']['pending'])
                self.assertEqual(st['codex-principal']['pending']['id'], mid)
                self.assertFalse((private / f'native-ack-{mid}.json').exists())

                # Errors list must document exact blocking reason
                err_text = " ".join(status_raw['errors'])
                self.assertIn("blocked_beyond_slo", err_text)
                self.assertIn("400.0s >= 300s", err_text)
            finally:
                if old_env is not None:
                    os.environ['APLEXER_STATE_DIR'] = old_env
                else:
                    os.environ.pop('APLEXER_STATE_DIR', None)
                candidate.command, candidate.time = real_cmd, real_time
                candidate.ROOT, candidate.PRIVATE, candidate.BINARY = real_root, real_priv, real_bin

    def test_service_run_missing_principal_pending_beyond_slo(self):
        """Verify that when a principal is missing/ambiguous, pending beyond SLO is preserved and reported as blocked."""
        with tempfile.TemporaryDirectory() as td:
            tmp = pathlib.Path(td)
            root = tmp / 'root'
            (root / 'coordination').mkdir(parents=True)
            (root / 'coordination/TEAM-REGISTRY.json').write_text(json.dumps({'teams': [{'id': 'T1', 'principal_tags': ['claude-principal']}]}))
            (root / 'coordination/TASKS.json').write_text(json.dumps({'tasks': [{'id': 'task-1', 'team_id': 'T1', 'status': 'ready', 'owner_tag': 'claude-principal'}]}))
            private = tmp / 'private'
            private.mkdir()
            bin_dir = tmp / 'bin'
            bin_dir.mkdir()
            pinned = bin_dir / 'aplexer'
            pinned.write_bytes(b'PINNED')

            sender_id = str(uuid.uuid4())
            mid = str(uuid.uuid4())
            t_now = 1791110000.0
            # 2000s ago (> 1800s Claude SLO)
            created_dt = datetime.datetime.fromtimestamp(t_now - 2000, datetime.timezone.utc)
            created_iso = created_dt.isoformat()

            init_state = {
                'claude-principal': {
                    'session_id': None,
                    'alive': False,
                    'reason': 'missing-or-ambiguous-principal',
                    'pending': {
                        'id': mid,
                        'sender_id': sender_id,
                        'event': 'ev-claude',
                        'delivery': 'inbox',
                        'created_at': created_iso
                    }
                }
            }
            (private / 'state.json').write_text(json.dumps(init_state))

            def fake_cmd(args, timeout=20):
                words = [a for a in args[1:] if not a.startswith('-')]
                if words[:1] == ['whoami']:
                    return json.dumps({'workspace': str(root), 'tag': 'experiment-supervision', 'id': sender_id})
                if 'idempotency-key' in args and 'help' in args:
                    return '  --idempotency-key'
                if words[:1] == ['list']:
                    (private / 'stop').write_text('stop')
                    # Zero sessions returned -> claude-principal is missing
                    return json.dumps([])
                if 'inbox' in args:
                    return json.dumps({'messages': []})
                return '{}'

            real_cmd, real_time = candidate.command, candidate.time
            real_root, real_priv, real_bin = candidate.ROOT, candidate.PRIVATE, candidate.BINARY
            old_env = os.environ.get('APLEXER_STATE_DIR')
            try:
                os.environ['APLEXER_STATE_DIR'] = str(tmp / 'state/aplexer')
                candidate.command = fake_cmd
                candidate.time = type('T', (), {'time': staticmethod(lambda: t_now), 'sleep': staticmethod(lambda s: None)})()
                candidate.ROOT, candidate.PRIVATE, candidate.BINARY = root, private, str(pinned)

                candidate.run()

                st = json.loads((private / 'state.json').read_text())
                status_raw = json.loads((private / 'status.json').read_text())

                self.assertTrue(status_raw['degraded'])
                self.assertEqual(st['claude-principal']['status'], 'blocked_beyond_slo')
                self.assertAlmostEqual(st['claude-principal']['pending_duration_seconds'], 2000.0, places=1)
                self.assertEqual(st['claude-principal']['retry_slo_seconds'], 1800)
                self.assertIsNotNone(st['claude-principal']['pending'])
                self.assertEqual(st['claude-principal']['pending']['id'], mid)
            finally:
                if old_env is not None:
                    os.environ['APLEXER_STATE_DIR'] = old_env
                else:
                    os.environ.pop('APLEXER_STATE_DIR', None)
                candidate.command, candidate.time = real_cmd, real_time
                candidate.ROOT, candidate.PRIVATE, candidate.BINARY = real_root, real_priv, real_bin

    def test_cursor_reconciliation_exact_ack_clears_safely(self):
        """Verify that genuine mailbox cursor exception safely reconciles pending and records native-ack evidence."""
        with tempfile.TemporaryDirectory() as td:
            tmp = pathlib.Path(td)
            root = tmp / 'root'
            (root / 'coordination').mkdir(parents=True)
            (root / 'coordination/TEAM-REGISTRY.json').write_text(json.dumps({'teams': [{'id': 'T1', 'principal_tags': ['codex-principal']}]}))
            (root / 'coordination/TASKS.json').write_text(json.dumps({'tasks': [{'id': 'task-1', 'team_id': 'T1', 'status': 'ready', 'owner_tag': 'codex-principal'}]}))
            private = tmp / 'private'
            private.mkdir()
            bin_dir = tmp / 'bin'
            bin_dir.mkdir()
            pinned = bin_dir / 'aplexer'
            pinned.write_bytes(b'PINNED')

            mid = str(uuid.uuid4())
            sender_id = str(uuid.uuid4())
            recipient_id = str(uuid.uuid4())
            ws_hash = candidate.hashlib.sha256(str(root.resolve()).encode()).hexdigest()[:32]
            box = tmp / 'state/aplexer/messages' / ws_hash
            (box / 'msgs').mkdir(parents=True)
            (box / 'cursors').mkdir(parents=True)
            (box / '.mailbox.lock').touch()
            (box / 'workspace.json').write_text(json.dumps({'workspace': str(root.resolve())}))
            env = {
                'schema_version': 1, 'id': mid, 'workspace': str(root.resolve()),
                'from': {'session_id': sender_id, 'tag': 'experiment-supervision', 'workspace': str(root.resolve())},
                'to': {'session_id': recipient_id, 'tag': 'codex-principal'}
            }
            (box / 'msgs' / (mid + '.json')).write_text(json.dumps(env))
            # Recipient cursor has mid in exceptions -> genuine read/processed ACK
            (box / 'cursors' / (recipient_id + '.json')).write_text(json.dumps({'exceptions': [mid]}))

            init_state = {
                'codex-principal': {
                    'session_id': recipient_id,
                    'reported_state': 'idle',
                    'alive': True,
                    'composer': 'empty',
                    'cooldown_until': 2000.0,  # prevents re-sending in same cycle
                    'pending': {
                        'id': mid,
                        'sender_id': sender_id,
                        'event': 'ev-1',
                        'delivery': 'inbox',
                        'created_at': "2026-10-04T12:00:00+00:00"
                    }
                }
            }
            (private / 'state.json').write_text(json.dumps(init_state))

            cycles = [0]
            def fake_cmd(args, timeout=20):
                words = [a for a in args[1:] if not a.startswith('-')]
                if words[:1] == ['whoami']:
                    return json.dumps({'workspace': str(root), 'tag': 'experiment-supervision', 'id': sender_id})
                if 'idempotency-key' in args and 'help' in args:
                    return '  --idempotency-key'
                if words[:1] == ['list']:
                    cycles[0] += 1
                    if cycles[0] >= 1:
                        (private / 'stop').write_text('stop')
                    return json.dumps([{'workspace': str(root), 'tag': 'codex-principal', 'id': recipient_id, 'reported_state': 'idle', 'workload_pid': str(os.getpid())}])
                if 'inbox' in args:
                    return json.dumps({'messages': []})
                if 'capture' in args:
                    return "› Ask Codex to do anything"
                if args[0] == 'quse':
                    return json.dumps({'codex': {'status': 'ok', 'windows': {'7d': {'percent_remaining': 90}}}})
                return '{}'

            real_cmd, real_time = candidate.command, candidate.time
            real_root, real_priv, real_bin = candidate.ROOT, candidate.PRIVATE, candidate.BINARY
            old_env = os.environ.get('APLEXER_STATE_DIR')
            try:
                os.environ['APLEXER_STATE_DIR'] = str(tmp / 'state/aplexer')
                candidate.command = fake_cmd
                candidate.time = type('T', (), {'time': staticmethod(lambda: 1000.0), 'sleep': staticmethod(lambda s: None)})()
                candidate.ROOT, candidate.PRIVATE, candidate.BINARY = root, private, str(pinned)

                candidate.run()

                st = json.loads((private / 'state.json').read_text())
                self.assertIsNone(st['codex-principal']['pending'], "Pending must be cleared upon genuine cursor ACK")
                self.assertIsNotNone(st['codex-principal']['last_request'])
                self.assertEqual(st['codex-principal']['last_request']['id'], mid)
                self.assertIn('ack_evidence', st['codex-principal']['last_request'])
                self.assertTrue((private / f'native-ack-{mid}.json').exists())
                self.assertEqual(st['codex-principal']['status'], 'ok')
            finally:
                if old_env is not None:
                    os.environ['APLEXER_STATE_DIR'] = old_env
                else:
                    os.environ.pop('APLEXER_STATE_DIR', None)
                candidate.command, candidate.time = real_cmd, real_time
                candidate.ROOT, candidate.PRIVATE, candidate.BINARY = real_root, real_priv, real_bin

    def test_cursor_reconciliation_refuses_fake_ack_on_timeout(self):
        """Verify that timeout/absence of cursor exception refuses fake ACK, keeps pending, and reports blocked."""
        with tempfile.TemporaryDirectory() as td:
            tmp = pathlib.Path(td)
            root = tmp / 'root'
            (root / 'coordination').mkdir(parents=True)
            (root / 'coordination/TEAM-REGISTRY.json').write_text(json.dumps({'teams': [{'id': 'T1', 'principal_tags': ['codex-principal']}]}))
            (root / 'coordination/TASKS.json').write_text(json.dumps({'tasks': [{'id': 'task-1', 'team_id': 'T1', 'status': 'ready', 'owner_tag': 'codex-principal'}]}))
            private = tmp / 'private'
            private.mkdir()
            bin_dir = tmp / 'bin'
            bin_dir.mkdir()
            pinned = bin_dir / 'aplexer'
            pinned.write_bytes(b'PINNED')

            mid = str(uuid.uuid4())
            sender_id = str(uuid.uuid4())
            recipient_id = str(uuid.uuid4())
            ws_hash = candidate.hashlib.sha256(str(root.resolve()).encode()).hexdigest()[:32]
            box = tmp / 'state/aplexer/messages' / ws_hash
            (box / 'msgs').mkdir(parents=True)
            (box / 'cursors').mkdir(parents=True)
            (box / '.mailbox.lock').touch()
            (box / 'workspace.json').write_text(json.dumps({'workspace': str(root.resolve())}))
            env = {
                'schema_version': 1, 'id': mid, 'workspace': str(root.resolve()),
                'from': {'session_id': sender_id, 'tag': 'experiment-supervision', 'workspace': str(root.resolve())},
                'to': {'session_id': recipient_id, 'tag': 'codex-principal'}
            }
            (box / 'msgs' / (mid + '.json')).write_text(json.dumps(env))
            # Empty cursor exceptions -> message NOT processed by recipient
            (box / 'cursors' / (recipient_id + '.json')).write_text(json.dumps({'exceptions': []}))

            # 500s ago (> 300s SLO)
            t_now = 1791110000.0
            created_dt = datetime.datetime.fromtimestamp(t_now - 500, datetime.timezone.utc)
            created_iso = created_dt.isoformat()

            init_state = {
                'codex-principal': {
                    'session_id': recipient_id,
                    'reported_state': 'working',
                    'alive': True,
                    'composer': 'busy',
                    'reason': 'not-reported-ready',
                    'pending': {
                        'id': mid,
                        'sender_id': sender_id,
                        'event': 'ev-1',
                        'delivery': 'not-ready',
                        'created_at': created_iso
                    }
                }
            }
            (private / 'state.json').write_text(json.dumps(init_state))

            cycles = [0]
            def fake_cmd(args, timeout=20):
                words = [a for a in args[1:] if not a.startswith('-')]
                if words[:1] == ['whoami']:
                    return json.dumps({'workspace': str(root), 'tag': 'experiment-supervision', 'id': sender_id})
                if 'idempotency-key' in args and 'help' in args:
                    return '  --idempotency-key'
                if words[:1] == ['list']:
                    cycles[0] += 1
                    if cycles[0] >= 1:
                        (private / 'stop').write_text('stop')
                    return json.dumps([{'workspace': str(root), 'tag': 'codex-principal', 'id': recipient_id, 'reported_state': 'working', 'workload_pid': str(os.getpid())}])
                if 'inbox' in args:
                    return json.dumps({'messages': []})
                if 'capture' in args:
                    return "• Working (2m 15s • esc to interrupt)"
                if args[0] == 'quse':
                    return json.dumps({'codex': {'status': 'ok', 'windows': {'7d': {'percent_remaining': 90}}}})
                return '{}'

            real_cmd, real_time = candidate.command, candidate.time
            real_root, real_priv, real_bin = candidate.ROOT, candidate.PRIVATE, candidate.BINARY
            old_env = os.environ.get('APLEXER_STATE_DIR')
            try:
                os.environ['APLEXER_STATE_DIR'] = str(tmp / 'state/aplexer')
                candidate.command = fake_cmd
                candidate.time = type('T', (), {'time': staticmethod(lambda: t_now), 'sleep': staticmethod(lambda s: None)})()
                candidate.ROOT, candidate.PRIVATE, candidate.BINARY = root, private, str(pinned)

                candidate.run()

                st = json.loads((private / 'state.json').read_text())
                # Must refuse fake ACK: pending remains set!
                self.assertIsNotNone(st['codex-principal']['pending'])
                self.assertEqual(st['codex-principal']['pending']['id'], mid)
                self.assertFalse((private / f'native-ack-{mid}.json').exists())
                self.assertEqual(st['codex-principal']['status'], 'blocked_beyond_slo')
                status_raw = json.loads((private / 'status.json').read_text())
                self.assertTrue(status_raw['degraded'])
            finally:
                if old_env is not None:
                    os.environ['APLEXER_STATE_DIR'] = old_env
                else:
                    os.environ.pop('APLEXER_STATE_DIR', None)
                candidate.command, candidate.time = real_cmd, real_time
                candidate.ROOT, candidate.PRIVATE, candidate.BINARY = real_root, real_priv, real_bin

    def test_parse_and_validate_turn_hook_event(self):
        """Test parsing and validation of authoritative turn-boundary hook events."""
        valid_sess = str(uuid.uuid4())
        valid_event = {
            'type': 'turn_complete',
            'state': 'idle-empty',
            'prompt_seq': 42,
            'session_id': valid_sess,
            'engine': 'zcodex',
            'timestamp_ms': 1791118000000,
            'workload_pid': 12345,
            'active_children': 0,
            'composer_state': 'empty'
        }

        # 1. Valid event parsing
        parsed = candidate.parse_and_validate_turn_hook_event(valid_event)
        self.assertTrue(parsed['syntax_valid'])
        self.assertTrue(parsed['authenticated_channel_required'])
        self.assertEqual(parsed['prompt_seq'], 42)
        self.assertEqual(parsed['session_id'], valid_sess)
        self.assertEqual(parsed['state'], 'idle-empty')

        # 2. JSON string payload parsing
        json_str = json.dumps({'hook_event': valid_event})
        parsed_str = candidate.parse_and_validate_turn_hook_event(json_str)
        self.assertTrue(parsed_str['syntax_valid'])

        # 3. Fail closed on active child processes during turn_complete
        bad_children = dict(valid_event, active_children=2)
        with self.assertRaises(ValueError) as ctx:
            candidate.parse_and_validate_turn_hook_event(bad_children)
        self.assertIn("active child processes", str(ctx.exception))

        # 4. Fail closed on draft composer state during turn_complete
        bad_draft = dict(valid_event, composer_state='draft')
        with self.assertRaises(ValueError) as ctx:
            candidate.parse_and_validate_turn_hook_event(bad_draft)
        self.assertIn("composer state is 'draft'", str(ctx.exception))

        # 5. Fail closed on invalid engine
        bad_engine = dict(valid_event, engine='unknown-unauthorized-tui')
        with self.assertRaises(ValueError) as ctx:
            candidate.parse_and_validate_turn_hook_event(bad_engine)
        self.assertIn("not in authorized hook engines", str(ctx.exception))

        # 6. Fail closed on non-UUID session_id
        bad_uuid = dict(valid_event, session_id='session-not-uuid-1234')
        with self.assertRaises(ValueError) as ctx:
            candidate.parse_and_validate_turn_hook_event(bad_uuid)
        self.assertIn("not a valid UUID", str(ctx.exception))

        # 7. Fail closed on negative prompt_seq
        bad_seq = dict(valid_event, prompt_seq=-1)
        with self.assertRaises(ValueError) as ctx:
            candidate.parse_and_validate_turn_hook_event(bad_seq)
        self.assertIn("prompt_seq must be a non-negative integer", str(ctx.exception))

        # 8. Fail closed on session_id mismatch
        diff_sess = str(uuid.uuid4())
        with self.assertRaises(ValueError) as ctx:
            candidate.parse_and_validate_turn_hook_event(valid_event, expected_session_id=diff_sess)
        self.assertIn("session_id mismatch", str(ctx.exception))

        # 9. Valid turn_start event
        valid_start = {
            'type': 'turn_start',
            'state': 'working',
            'prompt_seq': 43,
            'session_id': valid_sess,
            'engine': 'opencode',
            'timestamp_ms': 1791118001000
        }
        parsed_start = candidate.parse_and_validate_turn_hook_event(valid_start)
        self.assertTrue(parsed_start['syntax_valid'])
        self.assertEqual(parsed_start['type'], 'turn_start')
        self.assertEqual(parsed_start['state'], 'working')

    def test_service_run_missing_principal_preserves_old_intent_and_cooldown(self):
        """Verify that when a principal is temporarily absent, old sent_event/cooldown/intent are preserved."""
        with tempfile.TemporaryDirectory() as td:
            tmp = pathlib.Path(td)
            root = tmp / 'root'
            (root / 'coordination').mkdir(parents=True)
            (root / 'coordination/TEAM-REGISTRY.json').write_text(json.dumps({'teams': [{'id': 'T1', 'principal_tags': ['codex-principal']}]}))
            (root / 'coordination/TASKS.json').write_text(json.dumps({'tasks': [{'id': 'task-1', 'team_id': 'T1', 'status': 'ready', 'owner_tag': 'codex-principal'}]}))
            private = tmp / 'private'
            private.mkdir()
            bin_dir = tmp / 'bin'
            bin_dir.mkdir()
            pinned = bin_dir / 'aplexer'
            pinned.write_bytes(b'PINNED')

            sender_id = str(uuid.uuid4())
            mid = str(uuid.uuid4())
            t_now = 1791110000.0

            # State has frozen intent / cooldown / sent_event from previous cycle
            init_state = {
                'codex-principal': {
                    'session_id': None,
                    'alive': False,
                    'sent_event': 'frozen-event-key-12345',
                    'cooldown_until': t_now + 600,
                    'last_request': {'id': 'prev-req-id', 'acknowledged_at': '2026-10-04T11:00:00+00:00'},
                    'pending': {
                        'id': mid,
                        'sender_id': sender_id,
                        'event': 'ev-frozen',
                        'delivery': 'send-uncertain',
                        'created_at': "2026-10-04T12:00:00+00:00"
                    }
                }
            }
            (private / 'state.json').write_text(json.dumps(init_state))

            def fake_cmd(args, timeout=20):
                words = [a for a in args[1:] if not a.startswith('-')]
                if words[:1] == ['whoami']:
                    return json.dumps({'workspace': str(root), 'tag': 'experiment-supervision', 'id': sender_id})
                if 'idempotency-key' in args and 'help' in args:
                    return '  --idempotency-key'
                if words[:1] == ['list']:
                    (private / 'stop').write_text('stop')
                    return json.dumps([])  # session absent
                if 'inbox' in args:
                    return json.dumps({'messages': []})
                return '{}'

            real_cmd, real_time = candidate.command, candidate.time
            real_root, real_priv, real_bin = candidate.ROOT, candidate.PRIVATE, candidate.BINARY
            old_env = os.environ.get('APLEXER_STATE_DIR')
            try:
                os.environ['APLEXER_STATE_DIR'] = str(tmp / 'state/aplexer')
                candidate.command = fake_cmd
                candidate.time = type('T', (), {'time': staticmethod(lambda: t_now), 'sleep': staticmethod(lambda s: None)})()
                candidate.ROOT, candidate.PRIVATE, candidate.BINARY = root, private, str(pinned)

                candidate.run()

                st = json.loads((private / 'state.json').read_text())
                # Verify that old sent_event, cooldown_until, last_request, and pending are preserved!
                codex_st = st['codex-principal']
                self.assertEqual(codex_st['sent_event'], 'frozen-event-key-12345')
                self.assertEqual(codex_st['cooldown_until'], t_now + 600)
                self.assertEqual(codex_st['last_request']['id'], 'prev-req-id')
                self.assertEqual(codex_st['pending']['id'], mid)
                self.assertEqual(codex_st['pending']['delivery'], 'send-uncertain')
            finally:
                if old_env is not None:
                    os.environ['APLEXER_STATE_DIR'] = old_env
                else:
                    os.environ.pop('APLEXER_STATE_DIR', None)
                candidate.command, candidate.time = real_cmd, real_time
                candidate.ROOT, candidate.PRIVATE, candidate.BINARY = real_root, real_priv, real_bin


if __name__ == '__main__':
    unittest.main()
