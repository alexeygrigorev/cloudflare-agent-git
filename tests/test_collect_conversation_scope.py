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


if __name__ == '__main__':
    unittest.main()
