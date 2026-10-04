#!/usr/bin/env python3
"""Comprehensive unit test suite for conversation-aware usage event matching in collect.py.

Verifies:
1. Exact Conversation Match (Test 1):
   Session with conversation_id C1 matches event with C1, ignores event with C2
   even if tag and team_id are identical.
2. Tag Reused Negative Check (Test 2):
   Two distinct conversations C1 and C2 for tag "worker-alpha" / team "a16".
   Verify C1 receives C1 tokens, C2 receives C2 tokens; neither receives max(C1, C2).
3. Legacy Fallback (Test 3):
   Session and event without conversation_id fall back to tag match with truthful scope.
   Events with conversation_id NEVER bind to sessions without conversation_id.
4. Deterministic Reconciliation (Test 4):
   Multiple snapshots for same conversation pick latest timestamp regardless of file order.
5. Multi-Source Authentic Conversation ID resolution:
   Extracts conversation_id from harness_conversation_id, s.engine_session_id,
   s.conversation_id, disk transcript.json, disk session.json, and telemetry.
"""
import datetime as dt
import json
import os
import pathlib
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

# Ensure scripts/metrics and repo root are on sys.path
REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
METRICS_DIR = REPO_ROOT / 'scripts/metrics'
if str(METRICS_DIR) not in sys.path:
    sys.path.insert(0, str(METRICS_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import collect
from collect import (
    authentic_conversation_id,
    match_usage_event,
    parse_entry_timestamp,
)


class TestCollectConversationScope(unittest.TestCase):
    """Unit test suite for conversation-aware usage matching in collect.py."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp_dir.name)
        self.store = self.root / '.local/metrics'
        self.store.mkdir(parents=True, exist_ok=True)
        self.events_path = self.store / 'usage-events.jsonl'
        self.aplexer_state = self.root / 'state/aplexer/sessions'
        self.aplexer_state.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _write_events(self, events):
        with self.events_path.open('w', encoding='utf-8') as f:
            for e in events:
                f.write(json.dumps(e) + '\n')

    # --------------------------------------------------------------------------
    # Test 1: Exact Conversation Match
    # --------------------------------------------------------------------------
    def test_01_exact_conversation_match(self):
        """Test 1: Session with conversation_id C1 matches event with C1,

        ignores event with C2 even if tag and team_id are identical.
        """
        tag = 'worker-alpha'
        team_id = 'a16'
        c1 = '01a0fe3c-aa6f-7ba0-ad72-03498623a6d2'
        c2 = '01a0fe3c-ab7e-7e52-ab06-b1a9289d445c'

        # Events written with C1 (1200 tokens) and C2 (4500 tokens)
        self._write_events([
            {
                'event_id': 'ev-c2',
                'conversation_id': c2,
                'tag': tag,
                'team_id': team_id,
                'provider': 'gemini',
                'model': 'gemini-2.5-pro',
                'total_tokens': 4500,
                'at': '2026-10-04T08:05:00Z',
            },
            {
                'event_id': 'ev-c1',
                'conversation_id': c1,
                'tag': tag,
                'team_id': team_id,
                'provider': 'gemini',
                'model': 'gemini-2.5-pro',
                'total_tokens': 1200,
                'at': '2026-10-04T08:00:00Z',
            },
        ])

        found, is_fallback = match_usage_event(self.events_path, tag, team_id, session_cid=c1)
        self.assertIsNotNone(found)
        self.assertFalse(is_fallback)
        self.assertEqual(found['conversation_id'], c1)
        self.assertEqual(found['event_id'], 'ev-c1')
        self.assertEqual(found['total_tokens'], 1200)

        # Negative check: C2 must be completely ignored for session C1
        self.assertNotEqual(found['conversation_id'], c2)
        self.assertNotEqual(found['total_tokens'], 4500)

    # --------------------------------------------------------------------------
    # Test 2: Tag Reused Negative Check
    # --------------------------------------------------------------------------
    def test_02_tag_reused_negative_check(self):
        """Test 2: Two distinct conversations C1 and C2 for tag 'worker-alpha' / team 'a16'.

        Verify C1 receives C1 tokens, C2 receives C2 tokens; neither receives max(C1, C2).
        """
        tag = 'worker-alpha'
        team_id = 'a16'
        c1 = 'conv-run-1'
        c2 = 'conv-run-2'

        # C1 has 150 tokens, C2 has 900 tokens.
        # Under greedy max matching defect, C1 would erroneously receive 900 (max(150, 900)).
        self._write_events([
            {
                'event_id': 'ev-1',
                'conversation_id': c1,
                'tag': tag,
                'team_id': team_id,
                'provider': 'zcode',
                'model': 'glm-5.3-flash',
                'total_tokens': 150,
                'at': '2026-10-04T08:00:00Z',
            },
            {
                'event_id': 'ev-2',
                'conversation_id': c2,
                'tag': tag,
                'team_id': team_id,
                'provider': 'zcode',
                'model': 'glm-5.3-flash',
                'total_tokens': 900,
                'at': '2026-10-04T08:05:00Z',
            },
        ])

        found_c1, fallback_c1 = match_usage_event(self.events_path, tag, team_id, session_cid=c1)
        found_c2, fallback_c2 = match_usage_event(self.events_path, tag, team_id, session_cid=c2)

        self.assertIsNotNone(found_c1)
        self.assertFalse(fallback_c1)
        self.assertEqual(found_c1['conversation_id'], c1)
        self.assertEqual(found_c1['total_tokens'], 150)
        # Crucial invariant: C1 does NOT receive max(150, 900)
        self.assertNotEqual(found_c1['total_tokens'], 900)

        self.assertIsNotNone(found_c2)
        self.assertFalse(fallback_c2)
        self.assertEqual(found_c2['conversation_id'], c2)
        self.assertEqual(found_c2['total_tokens'], 900)
        self.assertNotEqual(found_c2['total_tokens'], 150)

    def test_02_tag_reused_end_to_end_collect(self):
        """End-to-end collect() test for Test 2:

        Two sessions registered under the same tag 'worker-alpha' and team 'a16'
        with distinct harness_conversation_ids C1 and C2.
        Verify both are attributed their own tokens and aggregate is C1 + C2.
        """
        c1 = 'conv-worker-alpha-run1'
        c2 = 'conv-worker-alpha-run2'
        (self.root / 'coordination').mkdir(parents=True, exist_ok=True)
        (self.root / 'coordination/TEAM-REGISTRY.json').write_text(json.dumps({
            'teams': [{
                'id': 'a16',
                'agents': [
                    {'tag': 'worker-alpha', 'role': 'executor', 'session_id': 's1', 'harness_conversation_id': c1},
                    {'tag': 'worker-alpha', 'role': 'executor', 'session_id': 's2', 'harness_conversation_id': c2},
                ],
            }],
        }))
        (self.root / 'coordination/TASKS.json').write_text(json.dumps({'tasks': []}))

        self._write_events([
            {
                'event_id': 'ev-alpha-1',
                'conversation_id': c1,
                'tag': 'worker-alpha',
                'team_id': 'a16',
                'provider': 'gemini',
                'model': 'gemini-2.5-pro',
                'total_tokens': 150,
                'at': '2026-10-04T08:00:00Z',
            },
            {
                'event_id': 'ev-alpha-2',
                'conversation_id': c2,
                'tag': 'worker-alpha',
                'team_id': 'a16',
                'provider': 'gemini',
                'model': 'gemini-2.5-pro',
                'total_tokens': 900,
                'at': '2026-10-04T08:05:00Z',
            },
        ])

        catalog = [
            {'id': 's1', 'tag': 'worker-alpha', 'workspace': str(self.root), 'workload_pid': 101, 'reported_state': 'idle'},
            {'id': 's2', 'tag': 'worker-alpha', 'workspace': str(self.root), 'workload_pid': 102, 'reported_state': 'idle'},
        ]

        with patch.object(collect, 'quotas', return_value={}), \
             patch.object(collect, 'ROOT', self.root), \
             patch.object(collect, 'STORE', self.store), \
             patch.object(collect, 'APLEXER_STATE', self.aplexer_state), \
             patch.object(collect.subprocess, 'run', return_value=types.SimpleNamespace(returncode=0, stdout=json.dumps(catalog))), \
             patch.object(collect, 'proc', return_value={'alive': True}), \
             patch.object(collect, 'native_usage', return_value=None):
            snap = collect.collect()

        sessions = snap['sessions']
        self.assertEqual(len(sessions), 2)
        sess_map = {s['id']: s for s in sessions}

        s1_usage = sess_map['s1']['usage']
        s2_usage = sess_map['s2']['usage']

        self.assertIsNotNone(s1_usage)
        self.assertIsNotNone(s2_usage)
        self.assertEqual(s1_usage['conversation_id'], c1)
        self.assertEqual(s1_usage['total_tokens'], 150)
        self.assertEqual(s2_usage['conversation_id'], c2)
        self.assertEqual(s2_usage['total_tokens'], 900)

        # Aggregate known_conversation_tokens must sum both distinct conversations (150 + 900 = 1050)
        self.assertEqual(snap['aggregate']['known_conversation_tokens'], 1050)
        self.assertEqual(snap['aggregate']['usage_observed_conversations'], 2)

    # --------------------------------------------------------------------------
    # Test 3: Legacy Fallback
    # --------------------------------------------------------------------------
    def test_03_legacy_fallback(self):
        """Test 3: Session and event without conversation_id fall back to tag match.

        Also verifies:
        - Truthful fallback scope label.
        - Events with conversation_id NEVER bind to sessions without conversation_id.
        - Events without conversation_id NEVER bind to sessions with conversation_id.
        """
        tag = 'legacy-worker'
        team_id = 'a16'

        # Event with no conversation_id
        self._write_events([
            {
                'event_id': 'ev-legacy',
                'tag': tag,
                'team_id': team_id,
                'provider': 'opencode',
                'model': 'glm-5.3-flash',
                'total_tokens': 320,
                'at': '2026-10-04T08:00:00Z',
            },
        ])

        # Session without conversation_id -> matches under legacy fallback
        found, is_fallback = match_usage_event(self.events_path, tag, team_id, session_cid=None)
        self.assertIsNotNone(found)
        self.assertTrue(is_fallback)
        self.assertEqual(found['event_id'], 'ev-legacy')
        self.assertEqual(found['total_tokens'], 320)
        self.assertIsNone(found.get('conversation_id'))

        # Negative check 1: Event without conversation_id MUST NOT bind to session with conversation_id
        found_mismatch, _ = match_usage_event(self.events_path, tag, team_id, session_cid='conv-explicit')
        self.assertIsNone(found_mismatch)

        # Negative check 2: Event with conversation_id MUST NOT bind to session without conversation_id
        self._write_events([
            {
                'event_id': 'ev-has-cid',
                'conversation_id': 'conv-scoped',
                'tag': tag,
                'team_id': team_id,
                'provider': 'opencode',
                'model': 'glm-5.3-flash',
                'total_tokens': 777,
                'at': '2026-10-04T08:00:00Z',
            },
        ])
        found_unbound, _ = match_usage_event(self.events_path, tag, team_id, session_cid=None)
        self.assertIsNone(found_unbound)

    def test_03_legacy_fallback_scope_labeling_in_collect(self):
        """Test 3 (labeling): Verify truthful scope labeling in collect.collect() for fallback vs exact."""
        (self.root / 'coordination').mkdir(parents=True, exist_ok=True)
        (self.root / 'coordination/TEAM-REGISTRY.json').write_text(json.dumps({
            'teams': [{
                'id': 'a16',
                'agents': [
                    {'tag': 'legacy-worker', 'role': 'executor', 'session_id': 's-leg'},
                    {'tag': 'exact-worker', 'role': 'executor', 'session_id': 's-ex', 'harness_conversation_id': 'c-ex'},
                ],
            }],
        }))
        (self.root / 'coordination/TASKS.json').write_text(json.dumps({'tasks': []}))

        self._write_events([
            {
                'event_id': 'ev-leg',
                'tag': 'legacy-worker',
                'team_id': 'a16',
                'provider': 'opencode',
                'model': 'glm-5.3-flash',
                'total_tokens': 100,
                'at': '2026-10-04T08:00:00Z',
            },
            {
                'event_id': 'ev-ex',
                'conversation_id': 'c-ex',
                'tag': 'exact-worker',
                'team_id': 'a16',
                'provider': 'gemini',
                'model': 'gemini-2.5-pro',
                'total_tokens': 200,
                'at': '2026-10-04T08:00:00Z',
            },
        ])

        catalog = [
            {'id': 's-leg', 'tag': 'legacy-worker', 'workspace': str(self.root), 'workload_pid': 201},
            {'id': 's-ex', 'tag': 'exact-worker', 'workspace': str(self.root), 'workload_pid': 202},
        ]

        with patch.object(collect, 'quotas', return_value={}), \
             patch.object(collect, 'ROOT', self.root), \
             patch.object(collect, 'STORE', self.store), \
             patch.object(collect, 'APLEXER_STATE', self.aplexer_state), \
             patch.object(collect.subprocess, 'run', return_value=types.SimpleNamespace(returncode=0, stdout=json.dumps(catalog))), \
             patch.object(collect, 'proc', return_value={'alive': True}), \
             patch.object(collect, 'native_usage', return_value=None):
            snap = collect.collect()

        sess_map = {s['id']: s for s in snap['sessions']}
        leg_usage = sess_map['s-leg']['usage']
        ex_usage = sess_map['s-ex']['usage']

        self.assertIn('Fallback tag-matched owner counters without conversation binding', leg_usage['scope'])
        self.assertIn('Exact owner-registered cumulative counters', ex_usage['scope'])

    # --------------------------------------------------------------------------
    # Test 4: Deterministic Reconciliation
    # --------------------------------------------------------------------------
    def test_04_deterministic_reconciliation(self):
        """Test 4: Multiple snapshots for same conversation pick latest timestamp

        regardless of order in file.
        """
        tag = 'worker-recon'
        team_id = 'a16'
        cid = 'conv-reconcile-target'

        # Write snapshots out-of-order in the JSONL file
        snapshots = [
            {
                'event_id': 'ev-t1',
                'conversation_id': cid,
                'tag': tag,
                'team_id': team_id,
                'provider': 'gemini',
                'model': 'gemini-2.5-pro',
                'total_tokens': 100,
                'at': '2026-10-04T07:00:00Z',
            },
            {
                'event_id': 'ev-t3-latest',
                'conversation_id': cid,
                'tag': tag,
                'team_id': team_id,
                'provider': 'gemini',
                'model': 'gemini-2.5-pro',
                'total_tokens': 500,
                'at': '2026-10-04T08:30:00Z',
            },
            {
                'event_id': 'ev-t2',
                'conversation_id': cid,
                'tag': tag,
                'team_id': team_id,
                'provider': 'gemini',
                'model': 'gemini-2.5-pro',
                'total_tokens': 300,
                'at': '2026-10-04T07:45:00Z',
            },
        ]
        self._write_events(snapshots)

        found, is_fallback = match_usage_event(self.events_path, tag, team_id, session_cid=cid)
        self.assertIsNotNone(found)
        self.assertFalse(is_fallback)
        self.assertEqual(found['event_id'], 'ev-t3-latest')
        self.assertEqual(found['total_tokens'], 500)
        self.assertEqual(found['at'], '2026-10-04T08:30:00Z')

    def test_04_deterministic_reconciliation_observed_at_and_numeric_ts(self):
        """Test 4 (variants): Deterministic reconciliation with observed_at, timestamp,

        and epoch numeric timestamps.
        """
        tag = 'worker-ts-variants'
        team_id = 'a16'
        cid = 'conv-ts-var'

        self._write_events([
            {
                'event_id': 'ev-epoch-late',
                'conversation_id': cid,
                'tag': tag,
                'team_id': team_id,
                'provider': 'gemini',
                'model': 'gemini-2.5-pro',
                'total_tokens': 950,
                'observed_at': 1728036000.0,  # Later
            },
            {
                'event_id': 'ev-epoch-early',
                'conversation_id': cid,
                'tag': tag,
                'team_id': team_id,
                'provider': 'gemini',
                'model': 'gemini-2.5-pro',
                'total_tokens': 400,
                'timestamp': 1728030000.0,   # Earlier
            },
        ])

        found, _ = match_usage_event(self.events_path, tag, team_id, session_cid=cid)
        self.assertIsNotNone(found)
        self.assertEqual(found['event_id'], 'ev-epoch-late')
        self.assertEqual(found['total_tokens'], 950)

    # --------------------------------------------------------------------------
    # Authentic Conversation ID Resolution Tests
    # --------------------------------------------------------------------------
    def test_authentic_conversation_id_sources(self):
        """Verify authentic_conversation_id resolves across all 5 standard sources."""
        # 1. item['harness_conversation_id']
        cid1 = authentic_conversation_id({}, {'harness_conversation_id': 'harness-123'})
        self.assertEqual(cid1, 'harness-123')

        # 2. s['engine_session_id']
        cid2 = authentic_conversation_id({'engine_session_id': 'engine-456'}, {})
        self.assertEqual(cid2, 'engine-456')

        # 3. s['conversation_id']
        cid3 = authentic_conversation_id({'conversation_id': 'session-789'}, {})
        self.assertEqual(cid3, 'session-789')

        # 4. Disk session binding via transcript.json
        sess_dir = self.aplexer_state / 'disk-sess-1'
        sess_dir.mkdir(parents=True, exist_ok=True)
        (sess_dir / 'transcript.json').write_text(json.dumps({
            'engine': 'codex',
            'engine_session_id': 'disk-binding-abc',
        }))
        with patch.object(collect, 'APLEXER_STATE', self.aplexer_state):
            cid4 = authentic_conversation_id({'id': 'disk-sess-1'}, {})
            self.assertEqual(cid4, 'disk-binding-abc')

            # Also via item['session_id'] when s has no id
            cid4_item = authentic_conversation_id({}, {'session_id': 'disk-sess-1'})
            self.assertEqual(cid4_item, 'disk-binding-abc')

        # 5. Disk session binding via session.json
        sess_dir2 = self.aplexer_state / 'disk-sess-2'
        sess_dir2.mkdir(parents=True, exist_ok=True)
        (sess_dir2 / 'session.json').write_text(json.dumps({
            'id': 'disk-sess-2',
            'conversation_id': 'session-json-conv',
            'cwd': str(self.root),
        }))
        with patch.object(collect, 'APLEXER_STATE', self.aplexer_state), \
             patch.object(collect, 'ROOT', self.root):
            cid5 = authentic_conversation_id({}, {'session_id': 'disk-sess-2', 'workspace': str(self.root)})
            self.assertEqual(cid5, 'session-json-conv')

        # 6. item['conversation_id'] or item['telemetry']['conversation_id']
        cid6 = authentic_conversation_id({}, {'conversation_id': 'item-conv-def'})
        self.assertEqual(cid6, 'item-conv-def')

        cid7 = authentic_conversation_id({}, {'telemetry': {'conversation_id': 'tele-conv-ghi'}})
        self.assertEqual(cid7, 'tele-conv-ghi')

        # None when no conversation ID is present
        self.assertIsNone(authentic_conversation_id({}, {'tag': 'plain-worker'}))

    # --------------------------------------------------------------------------
    # Neg 1: Conflicting Conversation IDs
    # --------------------------------------------------------------------------
    def test_neg1_conflicting_conversation_ids(self):
        """Neg 1: Session CID vs Event CID conflict.

        When session CID is C1 and event CID is C2 (matching tag and team_id),
        match_usage_event MUST return (None, False), NEVER binding C2 to C1.
        """
        tag = 'worker-conflict'
        team_id = 'a16'
        c1 = '01a0fe3c-c1-session-record'
        c2 = '01a0fe3c-c2-telemetry-event'

        self._write_events([
            {
                'event_id': 'ev-conflict',
                'conversation_id': c2,
                'tag': tag,
                'team_id': team_id,
                'provider': 'gemini',
                'model': 'gemini-2.5-pro',
                'total_tokens': 5000,
                'at': '2026-10-04T08:00:00Z',
            },
        ])

        found, is_fallback = match_usage_event(self.events_path, tag, team_id, session_cid=c1)
        self.assertIsNone(found, "Conflicting conversation IDs must never bind")
        self.assertFalse(is_fallback)

    def test_neg1_conflicting_conversation_ids_end_to_end_collect(self):
        """Neg 1 (end-to-end): When a registered session has CID C1 and usage-events
        only contains C2 for the same tag/team, collect() must NOT attribute C2 to the session,
        leaving session usage None and known_conversation_tokens None.
        """
        tag = 'worker-conflict-e2e'
        team_id = 'a16'
        c1 = 'conv-session-authentic'
        c2 = 'conv-event-different'

        (self.root / 'coordination').mkdir(parents=True, exist_ok=True)
        (self.root / 'coordination/TEAM-REGISTRY.json').write_text(json.dumps({
            'teams': [{
                'id': team_id,
                'agents': [
                    {'tag': tag, 'role': 'executor', 'session_id': 's-conflict', 'harness_conversation_id': c1},
                ],
            }],
        }))
        (self.root / 'coordination/TASKS.json').write_text(json.dumps({'tasks': []}))

        self._write_events([
            {
                'event_id': 'ev-mismatched',
                'conversation_id': c2,
                'tag': tag,
                'team_id': team_id,
                'provider': 'gemini',
                'model': 'gemini-2.5-pro',
                'total_tokens': 3333,
                'at': '2026-10-04T08:00:00Z',
            },
        ])

        catalog = [
            {'id': 's-conflict', 'tag': tag, 'workspace': str(self.root), 'workload_pid': 301, 'reported_state': 'idle'},
        ]

        with patch.object(collect, 'quotas', return_value={}), \
             patch.object(collect, 'ROOT', self.root), \
             patch.object(collect, 'STORE', self.store), \
             patch.object(collect, 'APLEXER_STATE', self.aplexer_state), \
             patch.object(collect.subprocess, 'run', return_value=types.SimpleNamespace(returncode=0, stdout=json.dumps(catalog))), \
             patch.object(collect, 'proc', return_value={'alive': True}), \
             patch.object(collect, 'native_usage', return_value=None):
            snap = collect.collect()

        sess = snap['sessions'][0]
        self.assertIsNone(sess['usage'], "Mismatched telemetry conversation ID must not populate session usage")
        self.assertIsNone(snap['aggregate']['known_conversation_tokens'])

    # --------------------------------------------------------------------------
    # Neg 2: Legacy Fallback Without CID
    # --------------------------------------------------------------------------
    def test_neg2_legacy_fallback_marker_and_never_falsely_verified(self):
        """Neg 2: Legacy fallback without CID.

        Ensure explicit fallback marker (is_fallback=True) is applied when matching
        by (tag, team_id) only, and never falsely labeled as authentic verified conversation binding.
        Also verify that fallback counters are excluded from unique_usage/known_conversation_tokens
        because conversation_id is None.
        """
        tag = 'worker-leg-verify'
        team_id = 'a16'

        self._write_events([
            {
                'event_id': 'ev-leg-tag-only',
                'tag': tag,
                'team_id': team_id,
                'provider': 'opencode',
                'model': 'glm-5.3-flash',
                'total_tokens': 450,
                'at': '2026-10-04T08:00:00Z',
            },
        ])

        # 1. match_usage_event with session_cid=None must return is_fallback=True
        found, is_fallback = match_usage_event(self.events_path, tag, team_id, session_cid=None)
        self.assertIsNotNone(found)
        self.assertTrue(is_fallback, "Must set explicit fallback marker is_fallback=True")
        self.assertIsNone(found.get('conversation_id'))

        # 2. In collect(), scope must explicitly indicate fallback and never claim exact verified binding
        (self.root / 'coordination').mkdir(parents=True, exist_ok=True)
        (self.root / 'coordination/TEAM-REGISTRY.json').write_text(json.dumps({
            'teams': [{
                'id': team_id,
                'agents': [
                    {'tag': tag, 'role': 'executor', 'session_id': 's-leg'},
                ],
            }],
        }))
        (self.root / 'coordination/TASKS.json').write_text(json.dumps({'tasks': []}))

        catalog = [
            {'id': 's-leg', 'tag': tag, 'workspace': str(self.root), 'workload_pid': 401},
        ]

        with patch.object(collect, 'quotas', return_value={}), \
             patch.object(collect, 'ROOT', self.root), \
             patch.object(collect, 'STORE', self.store), \
             patch.object(collect, 'APLEXER_STATE', self.aplexer_state), \
             patch.object(collect.subprocess, 'run', return_value=types.SimpleNamespace(returncode=0, stdout=json.dumps(catalog))), \
             patch.object(collect, 'proc', return_value={'alive': True}), \
             patch.object(collect, 'native_usage', return_value=None):
            snap = collect.collect()

        sess = snap['sessions'][0]
        usage = sess['usage']
        self.assertIsNotNone(usage)
        self.assertIn('Fallback tag-matched owner counters without conversation binding', usage['scope'])
        self.assertNotIn('Exact owner-registered cumulative counters', usage['scope'])
        self.assertIsNone(usage.get('conversation_id'))
        # Crucial: unknown conversation tokens stays None because fallback has no authentic conversation binding
        self.assertIsNone(snap['aggregate']['known_conversation_tokens'])

        # 3. Cross check: session with CID must NEVER bind to this un-scoped event
        found_with_cid, _ = match_usage_event(self.events_path, tag, team_id, session_cid='conv-xyz')
        self.assertIsNone(found_with_cid)

        # 4. Cross check: event with CID must NEVER bind to session without CID
        self._write_events([
            {
                'event_id': 'ev-scoped-only',
                'conversation_id': 'conv-scoped-1',
                'tag': tag,
                'team_id': team_id,
                'total_tokens': 999,
                'at': '2026-10-04T08:00:00Z',
            },
        ])
        found_no_cid, _ = match_usage_event(self.events_path, tag, team_id, session_cid=None)
        self.assertIsNone(found_no_cid)

    # --------------------------------------------------------------------------
    # Neg 3: Empty string CID "" vs None
    # --------------------------------------------------------------------------
    def test_neg3_empty_string_cid_vs_none_prevention_of_empty_equality(self):
        """Neg 3: Empty string CID "" vs None.

        Ensure empty string and whitespace are treated safely as None/falsy,
        preventing empty string equality match ("" == "" or "  " == "  ").
        - If session_cid is "" or "   " and event has "" or "   ":
          must NOT match as exact verified conversation binding (is_fallback must be True).
        - If session_cid is "" and event has "conv-valid":
          must NOT match (session_cid is falsy).
        - If session_cid is "conv-valid" and event has "":
          must NOT match (event CID is falsy).
        - Any returned found event must have conversation_id normalized to None.
        """
        tag = 'worker-empty-cid'
        team_id = 'a16'

        # Event with empty string conversation_id
        self._write_events([
            {
                'event_id': 'ev-empty-cid',
                'conversation_id': '',
                'tag': tag,
                'team_id': team_id,
                'provider': 'gemini',
                'model': 'gemini-2.5-pro',
                'total_tokens': 100,
                'at': '2026-10-04T08:00:00Z',
            },
        ])

        # 1. session_cid="" passed: must NOT match as exact verified binding
        found, is_fallback = match_usage_event(self.events_path, tag, team_id, session_cid='')
        self.assertIsNotNone(found)
        self.assertTrue(is_fallback, "Empty string session_cid and event CID must be legacy fallback, NOT exact")
        self.assertIsNone(found.get('conversation_id'), "Empty string conversation_id must be normalized to None")

        # 2. session_cid="   " (whitespace) passed: must NOT match as exact
        found_ws, is_fallback_ws = match_usage_event(self.events_path, tag, team_id, session_cid='   ')
        self.assertIsNotNone(found_ws)
        self.assertTrue(is_fallback_ws, "Whitespace session_cid must be treated as None and fall back")
        self.assertIsNone(found_ws.get('conversation_id'))

        # 3. Event with whitespace CID
        self._write_events([
            {
                'event_id': 'ev-ws-cid',
                'conversation_id': '   ',
                'tag': tag,
                'team_id': team_id,
                'provider': 'gemini',
                'model': 'gemini-2.5-pro',
                'total_tokens': 200,
                'at': '2026-10-04T08:00:00Z',
            },
        ])
        found_ws2, is_fallback_ws2 = match_usage_event(self.events_path, tag, team_id, session_cid='   ')
        self.assertIsNotNone(found_ws2)
        self.assertTrue(is_fallback_ws2, "Whitespace equality match ('   ' == '   ') must be prevented")
        self.assertIsNone(found_ws2.get('conversation_id'))

        # 4. Valid session CID with empty event CID -> must NOT match
        found_mismatch_1, _ = match_usage_event(self.events_path, tag, team_id, session_cid='conv-real')
        self.assertIsNone(found_mismatch_1, "Valid session CID must not bind to empty/whitespace event CID")

        # 5. Empty session CID with valid event CID -> must NOT match
        self._write_events([
            {
                'event_id': 'ev-real-cid',
                'conversation_id': 'conv-real',
                'tag': tag,
                'team_id': team_id,
                'provider': 'gemini',
                'model': 'gemini-2.5-pro',
                'total_tokens': 300,
                'at': '2026-10-04T08:00:00Z',
            },
        ])
        found_mismatch_2, _ = match_usage_event(self.events_path, tag, team_id, session_cid='')
        self.assertIsNone(found_mismatch_2, "Empty session CID must not bind to valid event CID")
        found_mismatch_3, _ = match_usage_event(self.events_path, tag, team_id, session_cid='   ')
        self.assertIsNone(found_mismatch_3, "Whitespace session CID must not bind to valid event CID")

    def test_neg3_authentic_conversation_id_empty_and_whitespace_strings(self):
        """Neg 3 (resolution): authentic_conversation_id must safely return None
        when candidate fields contain empty or whitespace strings.
        """
        self.assertIsNone(authentic_conversation_id({}, {'harness_conversation_id': ''}))
        self.assertIsNone(authentic_conversation_id({}, {'harness_conversation_id': '   '}))
        self.assertIsNone(authentic_conversation_id({'engine_session_id': ''}, {}))
        self.assertIsNone(authentic_conversation_id({'engine_session_id': '   '}, {}))
        self.assertIsNone(authentic_conversation_id({'conversation_id': ''}, {}))
        self.assertIsNone(authentic_conversation_id({'conversation_id': '   '}, {}))
        self.assertIsNone(authentic_conversation_id({}, {'conversation_id': ''}))
        self.assertIsNone(authentic_conversation_id({}, {'conversation_id': '   '}))
        self.assertIsNone(authentic_conversation_id({}, {'telemetry': {'conversation_id': ''}}))
        self.assertIsNone(authentic_conversation_id({}, {'telemetry': {'conversation_id': '   '}}))

    # --------------------------------------------------------------------------
    # Neg 4: Corrupted or Non-JSON Lines
    # --------------------------------------------------------------------------
    def test_neg4_corrupted_and_non_json_lines_safe_skip_with_warning(self):
        """Neg 4: Corrupted or non-JSON lines in usage-events.jsonl.

        Ensure parser logs warning/skips safely rather than crashing or swallowing subsequent lines:
        - Corrupted JSON lines (e.g. malformed syntax)
        - Non-JSON lines (e.g. plain text log artifact)
        - Non-dict JSON lines (e.g. integer or list)
        - Valid subsequent lines must still be matched and reconciled properly.
        - Warnings must be emitted for corrupted lines.
        """
        tag = 'worker-corrupted-file'
        team_id = 'a16'
        cid = 'conv-corrupted-test'

        # Write file with corrupted lines sandwiched between valid lines
        lines = [
            json.dumps({
                'event_id': 'ev-early',
                'conversation_id': cid,
                'tag': tag,
                'team_id': team_id,
                'provider': 'gemini',
                'model': 'gemini-2.5-pro',
                'total_tokens': 100,
                'at': '2026-10-04T07:00:00Z',
            }),
            '{"corrupted": json without closing brace...',
            'JUST RANDOM TEXT IN LOG FILE',
            '[1, 2, 3]',
            '42',
            '',
            '    ',
            json.dumps({
                'event_id': 'ev-late-reconciled',
                'conversation_id': cid,
                'tag': tag,
                'team_id': team_id,
                'provider': 'gemini',
                'model': 'gemini-2.5-pro',
                'total_tokens': 850,
                'at': '2026-10-04T08:00:00Z',
            }),
        ]
        with self.events_path.open('w', encoding='utf-8') as f:
            for l in lines:
                f.write(l + '\n')

        import warnings
        with warnings.catch_warnings(record=True) as caught_warnings:
            warnings.simplefilter('always')
            found, is_fallback = match_usage_event(self.events_path, tag, team_id, session_cid=cid)

        # 1. Did not crash with JSONDecodeError / ValueError
        self.assertIsNotNone(found, "Parser must not crash and must not swallow valid subsequent lines")
        self.assertFalse(is_fallback)
        self.assertEqual(found['event_id'], 'ev-late-reconciled')
        self.assertEqual(found['total_tokens'], 850)

        # 2. Emitted warnings for corrupted / non-dict lines
        self.assertGreater(len(caught_warnings), 0, "Parser must emit warnings for corrupted/non-dict lines")
        warning_texts = [str(w.message) for w in caught_warnings]
        self.assertTrue(any('corrupted line' in t.lower() or 'non-dict' in t.lower() for t in warning_texts),
                        f"Expected warning text about corrupted/non-dict line, got: {warning_texts}")

    # --------------------------------------------------------------------------
    # Codex Principal C1796 Guidance Tests
    # --------------------------------------------------------------------------
    def test_c1796_stale_registry_vs_fresh_engine_session_id(self):
        """C1796 Counterexample 1: Stale Registry CID H1 vs Fresh Native Session CID E2.

        In authentic_conversation_id(), if item has a stale registry conversation_id (H1),
        but the live session record or disk transcript binding has a fresh native conversation ID (E2),
        the system must prioritize live engine_session_id / disk binding over stale registry H1.
        """
        s = {'id': 's1', 'engine_session_id': 'E2-fresh-engine'}
        item = {'session_id': 's1', 'harness_conversation_id': 'H1-stale-registry'}

        cid = authentic_conversation_id(s, item)
        self.assertEqual(cid, 'E2-fresh-engine',
                         "Live engine_session_id must take priority over stale registry harness_conversation_id")

    def test_c1796_top_level_tag_dedup_preserves_distinct_monitors(self):
        """C1796 Counterexample 2: Top-Level Tag Deduplication Suppression.

        In collect(), top-level agents sharing a tag with a team agent (seen_team_tags)
        must NOT be suppressed if they have distinct conversation IDs or session IDs.
        """
        c_team = 'conv-team-monitor'
        c_top = 'conv-top-monitor'
        (self.root / 'coordination').mkdir(parents=True, exist_ok=True)
        (self.root / 'coordination/TEAM-REGISTRY.json').write_text(json.dumps({
            'teams': [{
                'id': 'team-core',
                'agents': [
                    {'tag': 'monitor-agent', 'role': 'executor', 'session_id': 's-team-mon', 'harness_conversation_id': c_team},
                ],
            }],
            'agents': [
                {'tag': 'monitor-agent', 'role': 'service', 'team_id': 'oversight', 'session_id': 's-top-mon', 'harness_conversation_id': c_top},
            ],
        }))
        (self.root / 'coordination/TASKS.json').write_text(json.dumps({'tasks': []}))

        self._write_events([
            {
                'event_id': 'ev-tm',
                'conversation_id': c_team,
                'tag': 'monitor-agent',
                'team_id': 'team-core',
                'provider': 'gemini',
                'model': 'gemini-2.5-pro',
                'total_tokens': 100,
                'at': '2026-10-04T08:00:00Z',
            },
            {
                'event_id': 'ev-topm',
                'conversation_id': c_top,
                'tag': 'monitor-agent',
                'team_id': 'oversight',
                'provider': 'gemini',
                'model': 'gemini-2.5-pro',
                'total_tokens': 200,
                'at': '2026-10-04T08:00:00Z',
            },
        ])

        catalog = [
            {'id': 's-team-mon', 'tag': 'monitor-agent', 'workspace': str(self.root), 'workload_pid': 501},
            {'id': 's-top-mon', 'tag': 'monitor-agent', 'workspace': str(self.root), 'workload_pid': 502},
        ]

        with patch.object(collect, 'quotas', return_value={}), \
             patch.object(collect, 'ROOT', self.root), \
             patch.object(collect, 'STORE', self.store), \
             patch.object(collect, 'APLEXER_STATE', self.aplexer_state), \
             patch.object(collect.subprocess, 'run', return_value=types.SimpleNamespace(returncode=0, stdout=json.dumps(catalog))), \
             patch.object(collect, 'proc', return_value={'alive': True}), \
             patch.object(collect, 'native_usage', return_value=None):
            snap = collect.collect()

        sessions = snap['sessions']
        # Both team agent and top-level agent must be preserved in observations
        mon_sessions = [s for s in sessions if s['tag'] == 'monitor-agent']
        self.assertEqual(len(mon_sessions), 2, "Top-level monitor must not be dropped due to sharing tag with team agent")
        sess_by_tid = {s['team_id']: s for s in mon_sessions}
        self.assertIn('team-core', sess_by_tid)
        self.assertIn('oversight', sess_by_tid)

        self.assertEqual(sess_by_tid['team-core']['usage']['conversation_id'], c_team)
        self.assertEqual(sess_by_tid['oversight']['usage']['conversation_id'], c_top)

    def test_c1796_mixed_anonymous_legacy_vs_new_bound_events(self):
        """C1796 Counterexample 3: Mixed anonymous legacy vs new bound events.

        When usage-events.jsonl contains both an anonymous legacy event (no CID)
        and a new bound event (with CID C1) under the same tag:
        - The legacy session (no CID) binds only to the legacy event (fallback scope).
        - The new session (with CID C1) binds only to the new bound event (exact scope).
        - Neither leaks or borrows from the other.
        """
        tag = 'worker-mixed'
        team_id = 'a16'
        cid_bound = 'conv-bound-42'

        self._write_events([
            {
                'event_id': 'ev-legacy-unbound',
                'tag': tag,
                'team_id': team_id,
                'provider': 'opencode',
                'model': 'glm-5.3-flash',
                'total_tokens': 100,
                'at': '2026-10-04T07:30:00Z',
            },
            {
                'event_id': 'ev-new-bound',
                'conversation_id': cid_bound,
                'tag': tag,
                'team_id': team_id,
                'provider': 'opencode',
                'model': 'glm-5.3-flash',
                'total_tokens': 500,
                'at': '2026-10-04T08:00:00Z',
            },
        ])

        (self.root / 'coordination').mkdir(parents=True, exist_ok=True)
        (self.root / 'coordination/TEAM-REGISTRY.json').write_text(json.dumps({
            'teams': [{
                'id': team_id,
                'agents': [
                    {'tag': tag, 'role': 'executor', 'session_id': 's-legacy'},
                    {'tag': tag, 'role': 'executor', 'session_id': 's-bound', 'harness_conversation_id': cid_bound},
                ],
            }],
        }))
        (self.root / 'coordination/TASKS.json').write_text(json.dumps({'tasks': []}))

        catalog = [
            {'id': 's-legacy', 'tag': tag, 'workspace': str(self.root), 'workload_pid': 601},
            {'id': 's-bound', 'tag': tag, 'workspace': str(self.root), 'workload_pid': 602},
        ]

        with patch.object(collect, 'quotas', return_value={}), \
             patch.object(collect, 'ROOT', self.root), \
             patch.object(collect, 'STORE', self.store), \
             patch.object(collect, 'APLEXER_STATE', self.aplexer_state), \
             patch.object(collect.subprocess, 'run', return_value=types.SimpleNamespace(returncode=0, stdout=json.dumps(catalog))), \
             patch.object(collect, 'proc', return_value={'alive': True}), \
             patch.object(collect, 'native_usage', return_value=None):
            snap = collect.collect()

        sess_map = {s['id']: s for s in snap['sessions']}
        leg_usage = sess_map['s-legacy']['usage']
        bound_usage = sess_map['s-bound']['usage']

        self.assertIsNotNone(leg_usage)
        self.assertIsNotNone(bound_usage)

        # Legacy session received legacy event (100 tokens), fallback scope
        self.assertEqual(leg_usage['event_id'], 'ev-legacy-unbound')
        self.assertEqual(leg_usage['total_tokens'], 100)
        self.assertIn('Fallback tag-matched owner counters', leg_usage['scope'])
        self.assertIsNone(leg_usage.get('conversation_id'))

        # Bound session received bound event (500 tokens), exact scope
        self.assertEqual(bound_usage['event_id'], 'ev-new-bound')
        self.assertEqual(bound_usage['total_tokens'], 500)
        self.assertIn('Exact owner-registered cumulative counters', bound_usage['scope'])
        self.assertEqual(bound_usage.get('conversation_id'), cid_bound)

        # Only the verified bound conversation contributes to known_conversation_tokens
        self.assertEqual(snap['aggregate']['known_conversation_tokens'], 500)
        self.assertEqual(snap['aggregate']['usage_observed_conversations'], 1)


if __name__ == '__main__':
    unittest.main()

