import datetime
import hashlib
import json
import os
import pathlib
import tempfile
import unittest
import uuid

import scripts.supervision.service as service
from scripts.supervision.terminal_consumer import canonical_json_hash


class ActionableNotificationsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.root = pathlib.Path(self.tmp)
        self.private = self.root / "private"
        self.private.mkdir(parents=True, exist_ok=True)
        (self.private / "receipts").mkdir(parents=True, exist_ok=True)

        self.pinned = self.root / "aplexer"
        self.pinned.write_text("#!/bin/sh\nexit 0\n")
        self.pinned.chmod(0o755)

        # Team registry with an active head
        self.coordination_dir = self.root / "coordination"
        self.coordination_dir.mkdir(parents=True, exist_ok=True)
        self.registry = {
            "teams": [
                {
                    "id": "agent-branches",
                    "head_tag": "agent-branches-head",
                    "principal_tags": ["codex-principal"],
                }
            ]
        }
        (self.coordination_dir / "TEAM-REGISTRY.json").write_text(json.dumps(self.registry))

        # Real artifacts directory for receipt validation
        self.art_file = self.root / "artifact.txt"
        self.art_file.write_text("valid artifact payload")
        self.art_sha = hashlib.sha256(self.art_file.read_bytes()).hexdigest()

        # Save service globals
        self.real_cmd = service.command
        self.real_run = service.subprocess.run
        self.real_time = service.time
        self.real_root = service.ROOT
        self.real_priv = service.PRIVATE
        self.real_bin = service.BINARY
        self.real_defaults = service.recorded_send.__defaults__

    def tearDown(self):
        service.command = self.real_cmd
        service.subprocess.run = self.real_run
        service.time = self.real_time
        service.ROOT = self.real_root
        service.PRIVATE = self.real_priv
        service.BINARY = self.real_bin
        service.recorded_send.__defaults__ = self.real_defaults

    def _create_terminal_receipt(self, task_id="t-review-1", executor_tag="worker-exec-1"):
        return {
            "task_id": task_id,
            "project_id": "agent-branches",
            "phase": "execution",
            "status": "completed-awaiting-review",
            "completed_at": "2026-10-06T18:00:00Z",
            "executor": {
                "tag": executor_tag,
                "session_id": str(uuid.uuid4()),
                "engine": "codex",
            },
            "artifacts": [
                {"path": str(self.art_file), "sha256": self.art_sha}
            ],
            "first_tool_evidence": {
                "tool_name": "run_command",
                "args": "echo done",
                "output_summary": "done",
                "timestamp": "2026-10-06T17:59:00Z",
            },
        }

    def _create_review_receipt(self, term_receipt, verdict="REJECTED", reviewer_tag="reviewer-distinct"):
        term_sha = canonical_json_hash(term_receipt)
        return {
            "task_id": term_receipt["task_id"],
            "review_task_id": f"rev-{term_receipt['task_id']}",
            "target_receipt_sha256": term_sha,
            "verdict": verdict,
            "reviewed_at": "2026-10-06T18:05:00Z",
            "reviewer": {
                "tag": reviewer_tag,
                "session_id": str(uuid.uuid4()),
                "engine": "antigravity",
                "reason": "negative assertion failure" if verdict == "REJECTED" else "approved",
            },
            "review_evidence": {
                "exit_code": 1 if verdict == "REJECTED" else 0,
                "summary": "review completed",
            },
        }

    def test_review_required_notification_and_delivery_to_head(self):
        """Verify REVIEW_REQUIRED event generation and delivery to head when task finishes execution."""
        tasks = [
            {"id": "t-review-1", "project_id": "agent-branches", "status": "running", "owner_tag": "agent-branches-head"}
        ]
        (self.coordination_dir / "TASKS.json").write_text(json.dumps(tasks))

        # Worker finishes execution and persists terminal receipt
        term_receipt = self._create_terminal_receipt(task_id="t-review-1")
        (self.private / "receipts" / "terminal-t-review-1.json").write_text(json.dumps(term_receipt))

        # Pre-seed session state with 1 observation snapshot so cycle 1 hits snapshot count >= 2
        initial_state = {
            'agent-branches-head': {
                'session_id': 'sess-head-1',
                'ready_snapshot_count': 1,
            }
        }
        (self.private / 'state.json').write_text(json.dumps(initial_state))

        curr_time = [1000.0]
        sent_messages = []
        cycles = [0]
        delivered_calls = []

        def fake_cmd(args, timeout=20):
            words = [a for a in args[1:] if not a.startswith('-')]
            if words[:1] == ['whoami']:
                return json.dumps({'workspace': str(self.root), 'tag': 'experiment-supervision', 'id': 'sup-1'})
            if words[:1] == ['list']:
                cycles[0] += 1
                if cycles[0] >= 1:
                    (self.private / 'stop').write_text('stop')
                return json.dumps([
                    {'workspace': str(self.root), 'tag': 'agent-branches-head', 'id': 'sess-head-1', 'reported_state': 'idle', 'workload_pid': str(os.getpid())}
                ])
            if 'capture' in args:
                return '› \n'
            if words[:2] == ['message', 'send']:
                if '--help' in args:
                    return 'Usage: aplexer message send [OPTIONS] [BODY]...\n  --idempotency-key TEXT'
                body = args[-1]
                to_tag = args[args.index('--to')+1] if '--to' in args else 'unknown'
                sent_messages.append({'to': to_tag, 'body': body})
                return json.dumps({'id': 'm-review-1', 'delivery': 'inbox', 'body': body})
            if words[:2] == ['message', 'inbox']:
                return json.dumps([])
            return '{}'

        class R:
            def __init__(self, rc, out, err=''):
                self.returncode, self.stdout, self.stderr = rc, out, err

        def fake_run(args, **kwargs):
            if 'deliver' in args:
                delivered_calls.append(list(args))
                return R(0, json.dumps({'status': 'recipient-acked', 'delivery': 'recipient-acked'}))
            return R(0, '{}')

        service.command = fake_cmd
        service.subprocess.run = fake_run
        service.recorded_send.__defaults__ = (fake_cmd,)
        service.time = type('T', (), {'time': staticmethod(lambda: curr_time[0]), 'sleep': staticmethod(lambda s: None)})()
        service.ROOT, service.PRIVATE, service.BINARY = self.root, self.private, str(self.pinned)

        service.run()

        # Verify message sent to head with actionable notification format
        self.assertEqual(len(sent_messages), 1)
        msg = sent_messages[0]
        self.assertEqual(msg['to'], 'agent-branches-head')
        self.assertIn("Head agent-branches-head has actionable transitions:", msg['body'])
        self.assertIn("1 awaiting review (t-review-1)", msg['body'])
        self.assertTrue(msg['body'].startswith("SUPERVISION-"))

        # Verify delivery attempt occurred
        self.assertTrue(len(delivered_calls) >= 1)
        self.assertEqual(delivered_calls[0][3], 'm-review-1')

        # Verify state persistence
        st = json.loads((self.private / 'state.json').read_text())
        head_st = st['agent-branches-head']
        self.assertTrue(head_st.get('actionable_delta'))
        self.assertIn('t-review-1', head_st.get('actionable_task_ids', []))
        self.assertIsNotNone(head_st.get('actionable_fingerprint'))

    def test_task_rejected_notification_delivery_to_head(self):
        """Verify TASK_REJECTED event delivery to head when reviewer rejects output."""
        tasks = [
            {"id": "t-rejected-1", "project_id": "agent-branches", "status": "running", "owner_tag": "agent-branches-head"}
        ]
        (self.coordination_dir / "TASKS.json").write_text(json.dumps(tasks))

        # Terminal receipt + Review receipt (REJECTED)
        term_receipt = self._create_terminal_receipt(task_id="t-rejected-1")
        (self.private / "receipts" / "terminal-t-rejected-1.json").write_text(json.dumps(term_receipt))
        rev_receipt = self._create_review_receipt(term_receipt, verdict="REJECTED")
        (self.private / "receipts" / "review-t-rejected-1.json").write_text(json.dumps(rev_receipt))

        # Pre-seed session state with 1 observation snapshot so cycle 1 hits snapshot count >= 2
        initial_state = {
            'agent-branches-head': {
                'session_id': 'sess-head-1',
                'ready_snapshot_count': 1,
            }
        }
        (self.private / 'state.json').write_text(json.dumps(initial_state))

        curr_time = [1000.0]
        sent_messages = []
        cycles = [0]
        delivered_calls = []

        def fake_cmd(args, timeout=20):
            words = [a for a in args[1:] if not a.startswith('-')]
            if words[:1] == ['whoami']:
                return json.dumps({'workspace': str(self.root), 'tag': 'experiment-supervision', 'id': 'sup-1'})
            if words[:1] == ['list']:
                cycles[0] += 1
                if cycles[0] >= 1:
                    (self.private / 'stop').write_text('stop')
                return json.dumps([
                    {'workspace': str(self.root), 'tag': 'agent-branches-head', 'id': 'sess-head-1', 'reported_state': 'idle', 'workload_pid': str(os.getpid())}
                ])
            if 'capture' in args:
                return '› \n'
            if words[:2] == ['message', 'send']:
                if '--help' in args:
                    return 'Usage: aplexer message send [OPTIONS] [BODY]...\n  --idempotency-key TEXT'
                body = args[-1]
                to_tag = args[args.index('--to')+1] if '--to' in args else 'unknown'
                sent_messages.append({'to': to_tag, 'body': body})
                return json.dumps({'id': 'm-rejected-1', 'delivery': 'inbox', 'body': body})
            if words[:2] == ['message', 'inbox']:
                return json.dumps([])
            return '{}'

        class R:
            def __init__(self, rc, out, err=''):
                self.returncode, self.stdout, self.stderr = rc, out, err

        def fake_run(args, **kwargs):
            if 'deliver' in args:
                delivered_calls.append(list(args))
                return R(0, json.dumps({'status': 'recipient-acked', 'delivery': 'recipient-acked'}))
            return R(0, '{}')

        service.command = fake_cmd
        service.subprocess.run = fake_run
        service.recorded_send.__defaults__ = (fake_cmd,)
        service.time = type('T', (), {'time': staticmethod(lambda: curr_time[0]), 'sleep': staticmethod(lambda s: None)})()
        service.ROOT, service.PRIVATE, service.BINARY = self.root, self.private, str(self.pinned)

        service.run()

        # Verify rejection message sent to head
        self.assertEqual(len(sent_messages), 1)
        msg = sent_messages[0]
        self.assertEqual(msg['to'], 'agent-branches-head')
        self.assertIn("Head agent-branches-head has actionable transitions:", msg['body'])
        self.assertIn("1 rejected needing repair (t-rejected-1)", msg['body'])

        # Verify delivery attempt occurred
        self.assertTrue(len(delivered_calls) >= 1)
        self.assertEqual(delivered_calls[0][3], 'm-rejected-1')

        # Verify state persistence
        st = json.loads((self.private / 'state.json').read_text())
        head_st = st['agent-branches-head']
        self.assertTrue(head_st.get('actionable_delta'))
        self.assertIn('t-rejected-1', head_st.get('actionable_task_ids', []))
        rejected_events = [e for e in head_st.get('actionable_events', []) if e.get('type') == 'TASK_REJECTED']
        self.assertEqual(len(rejected_events), 1)
        self.assertEqual(rejected_events[0]['task_id'], 't-rejected-1')

    def test_duplicate_event_suppression(self):
        """Verify that identical actionable digest/fingerprint is suppressed without spamming the head."""
        tasks = [
            {"id": "t-review-1", "project_id": "agent-branches", "status": "running", "owner_tag": "agent-branches-head"}
        ]
        (self.coordination_dir / "TASKS.json").write_text(json.dumps(tasks))

        term_receipt = self._create_terminal_receipt(task_id="t-review-1")
        (self.private / "receipts" / "terminal-t-review-1.json").write_text(json.dumps(term_receipt))

        curr_time = [1000.0]
        sent_messages = []
        cycles = [0]

        def fake_cmd(args, timeout=20):
            words = [a for a in args[1:] if not a.startswith('-')]
            if words[:1] == ['whoami']:
                return json.dumps({'workspace': str(self.root), 'tag': 'experiment-supervision', 'id': 'sup-1'})
            if words[:1] == ['list']:
                cycles[0] += 1
                if cycles[0] >= 1:
                    (self.private / 'stop').write_text('stop')
                return json.dumps([
                    {'workspace': str(self.root), 'tag': 'agent-branches-head', 'id': 'sess-head-1', 'reported_state': 'idle', 'workload_pid': str(os.getpid())}
                ])
            if 'capture' in args:
                return '› \n'
            if words[:2] == ['message', 'send']:
                if '--help' in args:
                    return 'Usage: aplexer message send [OPTIONS] [BODY]...\n  --idempotency-key TEXT'
                body = args[-1]
                to_tag = args[args.index('--to')+1] if '--to' in args else 'unknown'
                sent_messages.append({'to': to_tag, 'body': body})
                return json.dumps({'id': f'm-{len(sent_messages)}', 'delivery': 'inbox', 'body': body})
            if words[:2] == ['message', 'inbox']:
                return json.dumps([])
            return '{}'

        class R:
            def __init__(self, rc, out, err=''):
                self.returncode, self.stdout, self.stderr = rc, out, err

        service.command = fake_cmd
        service.subprocess.run = lambda *a, **k: R(0, json.dumps({'status': 'recipient-acked', 'delivery': 'recipient-acked'}))
        service.recorded_send.__defaults__ = (fake_cmd,)
        service.time = type('T', (), {'time': staticmethod(lambda: curr_time[0]), 'sleep': staticmethod(lambda s: None)})()
        service.ROOT, service.PRIVATE, service.BINARY = self.root, self.private, str(self.pinned)

        # Cycle 1: First appearance of review event -> message sent
        service.run()
        self.assertEqual(len(sent_messages), 1)
        st = json.loads((self.private / 'state.json').read_text())
        head_st = st['agent-branches-head']
        first_fp = head_st['actionable_fingerprint']
        self.assertIsNotNone(first_fp)

        # Cycle 2: Head ACKs message, time advances. Receipt state is identical.
        sent_messages.clear()
        cycles[0] = 0
        (self.private / 'stop').unlink(missing_ok=True)
        st['agent-branches-head']['pending'] = None
        (self.private / 'state.json').write_text(json.dumps(st))
        curr_time[0] = 1300.0

        service.run()

        # Must be strictly suppressed!
        self.assertEqual(len(sent_messages), 0)
        st = json.loads((self.private / 'state.json').read_text())
        head_st = st['agent-branches-head']
        self.assertFalse(head_st.get('actionable_delta'))
        self.assertTrue(head_st.get('actionable_deduped'))
        self.assertEqual(head_st.get('last_notified_actionable_fingerprint'), first_fp)

        # Cycle 3: New rejection transition added -> fingerprint changes -> message sent!
        rev_receipt = self._create_review_receipt(term_receipt, verdict="REJECTED")
        (self.private / "receipts" / "review-t-review-1.json").write_text(json.dumps(rev_receipt))
        sent_messages.clear()
        cycles[0] = 0
        (self.private / 'stop').unlink(missing_ok=True)
        st['agent-branches-head']['pending'] = None
        (self.private / 'state.json').write_text(json.dumps(st))
        curr_time[0] = 1400.0

        service.run()

        self.assertEqual(len(sent_messages), 1)
        self.assertIn("1 rejected needing repair (t-review-1)", sent_messages[0]['body'])
        st = json.loads((self.private / 'state.json').read_text())
        self.assertTrue(st['agent-branches-head'].get('actionable_delta'))

    def test_busy_protected_draft_hold(self):
        """Verify busy / protected draft detection holds delivery and protects composer."""
        tasks = [
            {"id": "t-ready-1", "project_id": "agent-branches", "status": "ready", "owner_tag": "agent-branches-head"}
        ]
        (self.coordination_dir / "TASKS.json").write_text(json.dumps(tasks))

        curr_time = [1000.0]
        delivered_calls = []
        screen_holder = ["› git checkout -b test-branch\n  Context 45% left"]  # unsubmitted draft

        def fake_cmd(args, timeout=20):
            words = [a for a in args[1:] if not a.startswith('-')]
            if words[:1] == ['whoami']:
                return json.dumps({'workspace': str(self.root), 'tag': 'experiment-supervision', 'id': 'sup-1'})
            if words[:1] == ['list']:
                (self.private / 'stop').write_text('stop')
                return json.dumps([
                    {'workspace': str(self.root), 'tag': 'agent-branches-head', 'id': 'sess-head-1', 'reported_state': 'idle', 'workload_pid': str(os.getpid())}
                ])
            if 'capture' in args:
                return screen_holder[0]
            if words[:2] == ['message', 'send']:
                if '--help' in args:
                    return 'Usage: aplexer message send [OPTIONS] [BODY]...\n  --idempotency-key TEXT'
                return json.dumps({'id': 'm-draft-1', 'delivery': 'inbox'})
            if words[:2] == ['message', 'inbox']:
                return json.dumps([])
            return '{}'

        class R:
            def __init__(self, rc, out, err=''):
                self.returncode, self.stdout, self.stderr = rc, out, err

        def fake_run(args, **kwargs):
            if 'deliver' in args:
                delivered_calls.append(list(args))
                return R(0, json.dumps({'status': 'recipient-acked'}))
            return R(0, '{}')

        service.command = fake_cmd
        service.subprocess.run = fake_run
        service.recorded_send.__defaults__ = (fake_cmd,)
        service.time = type('T', (), {'time': staticmethod(lambda: curr_time[0]), 'sleep': staticmethod(lambda s: None)})()
        service.ROOT, service.PRIVATE, service.BINARY = self.root, self.private, str(self.pinned)

        # 1. Draft on screen: eligible returns 0 snapshots, deliver is NEVER invoked
        service.run()
        self.assertEqual(len(delivered_calls), 0)
        st = json.loads((self.private / 'state.json').read_text())
        head_st = st['agent-branches-head']
        self.assertEqual(head_st.get('composer'), 'draft')
        self.assertEqual(head_st.get('ready_snapshot_count'), 0)

        # 2. Busy screen: deliver is also NEVER invoked
        delivered_calls.clear()
        (self.private / 'stop').unlink(missing_ok=True)
        screen_holder[0] = "• Working (10s • esc to interrupt)\n› running test"
        service.run()
        self.assertEqual(len(delivered_calls), 0)
        st = json.loads((self.private / 'state.json').read_text())
        self.assertEqual(st['agent-branches-head'].get('composer'), 'busy')

        # 3. Screen was empty initially, but fresh_screen before deliver is draft
        (self.private / 'stop').unlink(missing_ok=True)
        st['agent-branches-head']['session_id'] = 'sess-head-1'
        st['agent-branches-head']['ready_snapshot_count'] = 2
        st['agent-branches-head']['pending'] = {
            'id': 'm-draft-1',
            'sender_id': 'sup-1',
            'delivery': 'inbox',
            'created_at': '2026-10-06T18:00:00Z',
        }
        (self.private / 'state.json').write_text(json.dumps(st))

        capture_count = [0]
        def fake_cmd_race(args, timeout=20):
            words = [a for a in args[1:] if not a.startswith('-')]
            if words[:1] == ['whoami']:
                return json.dumps({'workspace': str(self.root), 'tag': 'experiment-supervision', 'id': 'sup-1'})
            if words[:1] == ['list']:
                (self.private / 'stop').write_text('stop')
                return json.dumps([
                    {'workspace': str(self.root), 'tag': 'agent-branches-head', 'id': 'sess-head-1', 'reported_state': 'idle', 'workload_pid': str(os.getpid())}
                ])
            if 'capture' in args:
                capture_count[0] += 1
                if capture_count[0] == 1:
                    return '› \n'  # empty on initial eligible check
                return "› user started typing command\n  Context 50%"  # draft on fresh_screen!
            if words[:2] == ['message', 'send']:
                if '--help' in args:
                    return 'Usage: aplexer message send [OPTIONS] [BODY]...\n  --idempotency-key TEXT'
                return json.dumps({'id': 'm-draft-1', 'delivery': 'inbox'})
            return '{}'

        service.command = fake_cmd_race
        service.run()

        # Delivery must be aborted, draft protected with cooldown
        self.assertEqual(len(delivered_calls), 0)
        st = json.loads((self.private / 'state.json').read_text())
        self.assertTrue(st['agent-branches-head'].get('cooldown_until', 0) >= curr_time[0] + 60)

    def test_unknown_readiness_hold(self):
        """Verify unknown readiness handling (delivery status not-ready or send-uncertain enters diagnostic hold/cooldown)."""
        tasks = [
            {"id": "t-ready-1", "project_id": "agent-branches", "status": "ready", "owner_tag": "agent-branches-head"}
        ]
        (self.coordination_dir / "TASKS.json").write_text(json.dumps(tasks))

        curr_time = [1000.0]

        # Case A: Deliver returns not-ready
        def fake_cmd_a(args, timeout=20):
            words = [a for a in args[1:] if not a.startswith('-')]
            if words[:1] == ['whoami']:
                return json.dumps({'workspace': str(self.root), 'tag': 'experiment-supervision', 'id': 'sup-1'})
            if words[:1] == ['list']:
                (self.private / 'stop').write_text('stop')
                return json.dumps([
                    {'workspace': str(self.root), 'tag': 'agent-branches-head', 'id': 'sess-head-1', 'reported_state': 'idle', 'workload_pid': str(os.getpid())}
                ])
            if 'capture' in args:
                return '› \n'
            if words[:2] == ['message', 'send']:
                if '--help' in args:
                    return 'Usage: aplexer message send [OPTIONS] [BODY]...\n  --idempotency-key TEXT'
                return json.dumps({'id': 'm-not-ready', 'delivery': 'inbox'})
            return '{}'

        class R:
            def __init__(self, rc, out, err=''):
                self.returncode, self.stdout, self.stderr = rc, out, err

        def fake_run_not_ready(args, **kwargs):
            if 'deliver' in args:
                return R(0, json.dumps({'status': 'not-ready', 'detail': 'recipient not ready: subsequent PTY activity detected'}))
            return R(0, '{}')

        service.command = fake_cmd_a
        service.subprocess.run = fake_run_not_ready
        service.recorded_send.__defaults__ = (fake_cmd_a,)
        service.time = type('T', (), {'time': staticmethod(lambda: curr_time[0]), 'sleep': staticmethod(lambda s: None)})()
        service.ROOT, service.PRIVATE, service.BINARY = self.root, self.private, str(self.pinned)

        # Pre-seed state with ready_snapshot_count >= 2 and pending message ready for deliver
        initial_state = {
            'agent-branches-head': {
                'session_id': 'sess-head-1',
                'ready_snapshot_count': 2,
                'pending': {
                    'id': 'm-not-ready',
                    'sender_id': 'sup-1',
                    'delivery': 'inbox',
                    'created_at': '2026-10-06T18:00:00Z',
                }
            }
        }
        (self.private / 'state.json').write_text(json.dumps(initial_state))

        service.run()

        st = json.loads((self.private / 'state.json').read_text())
        head_st = st['agent-branches-head']
        self.assertEqual(head_st.get('diagnostic_hold'), 'resting-state-contradicted-by-pty')
        self.assertTrue(head_st.get('cooldown_until', 0) >= curr_time[0] + 180)
        self.assertEqual(head_st['pending'].get('delivery'), 'not-ready')

        # Case B: Send returns send-uncertain
        (self.private / 'stop').unlink(missing_ok=True)
        (self.private / 'state.json').unlink(missing_ok=True)

        def fake_cmd_b(args, timeout=20):
            words = [a for a in args[1:] if not a.startswith('-')]
            if words[:1] == ['whoami']:
                return json.dumps({'workspace': str(self.root), 'tag': 'experiment-supervision', 'id': 'sup-1'})
            if words[:1] == ['list']:
                (self.private / 'stop').write_text('stop')
                return json.dumps([
                    {'workspace': str(self.root), 'tag': 'agent-branches-head', 'id': 'sess-head-1', 'reported_state': 'idle', 'workload_pid': str(os.getpid())}
                ])
            if 'capture' in args:
                return '› \n'
            if words[:2] == ['message', 'send']:
                if '--help' in args:
                    return 'Usage: aplexer message send [OPTIONS] [BODY]...\n  --idempotency-key TEXT'
                return json.dumps({'delivery': 'send-uncertain', 'reason': 'timeout on lock'})
            return '{}'

        service.command = fake_cmd_b
        service.recorded_send.__defaults__ = (fake_cmd_b,)
        service.run()

        st = json.loads((self.private / 'state.json').read_text())
        head_st = st['agent-branches-head']
        self.assertEqual(head_st.get('diagnostic_hold'), 'send-uncertain')
        self.assertTrue(head_st.get('cooldown_until', 0) >= curr_time[0] + 60)


if __name__ == '__main__':
    unittest.main()
