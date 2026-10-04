#!/usr/bin/env python3
"""Comprehensive unit test suite for multi-workspace metrics collection.

Verifies:
1. Multi-Workspace Session Discovery (Test 1):
   Discovers sessions across multiple distinct workspaces
   (cloudflare-agent-git, agent-dashboard, agent-quota-launcher, agent-coordination).
2. Unregistered Product Workspace Discovery & Attribution (Test 2):
   Unregistered session in a product workspace (e.g. agent-dashboard) is discovered
   and attributed to that workspace, while non-product sessions are excluded.
3. Unknown Tokens Integrity (Test 3):
   Missing or unknown telemetry remains strictly None/null and is never fabricated.
   Zero retroactive fake 24h data.
4. Workspace Path Scoping (Test 4):
   Evidence files inside each respective workspace are counted in that workspace's
   coverage rather than marked out_of_scope. External paths are flagged out_of_scope.
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

# Ensure repository root and tooling directory are on sys.path
REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
METRICS_DIR = REPO_ROOT / 'scripts/metrics'
TOOLING_DIR = REPO_ROOT / 'research/antigravity/tooling'

for p in (str(TOOLING_DIR), str(METRICS_DIR), str(REPO_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

import collect_multiworkspace as cmw


class TestCollectMultiworkspace(unittest.TestCase):
    """Unit tests for collect_multiworkspace.py verifying multi-workspace scoping."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = pathlib.Path(self.temp_dir.name)

        # Create distinct workspaces
        self.ws_main = self.base / 'cloudflare-agent-git'
        self.ws_dash = self.base / 'agent-dashboard'
        self.ws_quota = self.base / 'agent-quota-launcher'
        self.ws_coord = self.base / 'agent-coordination'

        for ws in (self.ws_main, self.ws_dash, self.ws_quota, self.ws_coord):
            ws.mkdir(parents=True, exist_ok=True)
            (ws / 'coordination').mkdir(parents=True, exist_ok=True)
            (ws / '.local/metrics').mkdir(parents=True, exist_ok=True)

        self.store = self.ws_main / '.local/metrics'
        self.aplexer_state = self.ws_main / 'state/aplexer/sessions'
        self.aplexer_state.mkdir(parents=True, exist_ok=True)

        self.product_workspaces = [
            str(self.ws_main),
            str(self.ws_dash),
            str(self.ws_quota),
            str(self.ws_coord),
        ]

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_discover_sessions_across_multiple_distinct_workspaces(self):
        """Test 1: Discover sessions across multiple distinct workspaces.
        Verifies that agents in cloudflare-agent-git, agent-dashboard,
        agent-quota-launcher, and agent-coordination are all discovered,
        matched to their respective workspaces, and counted in live aggregate.
        """
        registry = {
            'teams': [
                {
                    'id': 'a16-runtime-protocol',
                    'workspace': str(self.ws_main),
                    'agents': [
                        {'tag': 'antigravity-head', 'role': 'head', 'workspace': str(self.ws_main), 'session_id': 's-main-head'}
                    ]
                },
                {
                    'id': 'agent-dashboard',
                    'workspace': str(self.ws_dash),
                    'agents': [
                        {'tag': 'agent-dashboard-head', 'role': 'head', 'workspace': str(self.ws_dash), 'session_id': 's-dash-head'}
                    ]
                }
            ],
            'projects': [
                {
                    'id': 'quota-launcher',
                    'name': 'Agent Quota Launcher',
                    'head_tag': 'quota-launcher-head',
                    'head_session_id': 's-quota-head',
                    'workspace': str(self.ws_quota)
                },
                {
                    'id': 'agent-coordination',
                    'name': 'Agent Coordination',
                    'head_tag': 'agent-coordination-head',
                    'head_session_id': 's-coord-head',
                    'workspace': str(self.ws_coord)
                }
            ]
        }
        (self.ws_main / 'coordination/TEAM-REGISTRY.json').write_text(json.dumps(registry))
        (self.ws_main / 'coordination/TASKS.json').write_text(json.dumps({'tasks': []}))

        catalog = [
            {'id': 's-main-head', 'tag': 'antigravity-head', 'workspace': str(self.ws_main), 'workload_pid': 101, 'reported_state': 'working'},
            {'id': 's-dash-head', 'tag': 'agent-dashboard-head', 'workspace': str(self.ws_dash), 'workload_pid': 102, 'reported_state': 'idle'},
            {'id': 's-quota-head', 'tag': 'quota-launcher-head', 'workspace': str(self.ws_quota), 'workload_pid': 103, 'reported_state': 'waiting'},
            {'id': 's-coord-head', 'tag': 'agent-coordination-head', 'workspace': str(self.ws_coord), 'workload_pid': 104, 'reported_state': 'working'},
        ]

        with patch.object(cmw, 'ROOT', self.ws_main), \
             patch.object(cmw, 'STORE', self.store), \
             patch.object(cmw, 'PRODUCT_WORKSPACES', self.product_workspaces), \
             patch.object(cmw, 'APLEXER_STATE', self.aplexer_state), \
             patch.object(cmw, 'quotas', return_value={}), \
             patch.object(cmw, 'proc', return_value={'alive': True, 'cpu_seconds': 1.0, 'rss_bytes': 1024, 'start_ticks': 10}), \
             patch.object(cmw.subprocess, 'run', return_value=types.SimpleNamespace(returncode=0, stdout=json.dumps(catalog))):

            snap = cmw.collect()

        self.assertEqual(snap['aggregate']['registered_agents'], 4)
        self.assertEqual(snap['aggregate']['agents_pid_live'], 4)
        self.assertEqual(snap['aggregate']['agents_hook_working'], 2)

        sessions_by_tag = {s['tag']: s for s in snap['sessions']}
        self.assertIn('antigravity-head', sessions_by_tag)
        self.assertIn('agent-dashboard-head', sessions_by_tag)
        self.assertIn('quota-launcher-head', sessions_by_tag)
        self.assertIn('agent-coordination-head', sessions_by_tag)

        self.assertEqual(sessions_by_tag['antigravity-head']['workspace'], str(self.ws_main))
        self.assertEqual(sessions_by_tag['agent-dashboard-head']['workspace'], str(self.ws_dash))
        self.assertEqual(sessions_by_tag['quota-launcher-head']['workspace'], str(self.ws_quota))
        self.assertEqual(sessions_by_tag['agent-coordination-head']['workspace'], str(self.ws_coord))

        self.assertTrue(sessions_by_tag['antigravity-head']['pid_live'])
        self.assertTrue(sessions_by_tag['agent-dashboard-head']['pid_live'])
        self.assertTrue(sessions_by_tag['quota-launcher-head']['pid_live'])
        self.assertTrue(sessions_by_tag['agent-coordination-head']['pid_live'])

        self.assertEqual(sessions_by_tag['quota-launcher-head']['team_id'], 'quota-launcher')
        self.assertEqual(sessions_by_tag['agent-coordination-head']['team_id'], 'agent-coordination')

    def test_unregistered_session_in_product_workspace_discovered_and_attributed(self):
        """Test 2: Unregistered session in a product workspace (e.g. agent-dashboard)
        is discovered and attributed to that workspace, while non-product sessions
        in unrelated directories are ignored.
        """
        registry = {
            'teams': [
                {
                    'id': 'main-team',
                    'workspace': str(self.ws_main),
                    'agents': [
                        {'tag': 'main-worker', 'role': 'executor', 'workspace': str(self.ws_main), 'session_id': 's-main'}
                    ]
                }
            ]
        }
        (self.ws_main / 'coordination/TEAM-REGISTRY.json').write_text(json.dumps(registry))
        (self.ws_main / 'coordination/TASKS.json').write_text(json.dumps({'tasks': []}))

        catalog = [
            {'id': 's-main', 'tag': 'main-worker', 'workspace': str(self.ws_main), 'workload_pid': 201, 'reported_state': 'working'},
            # Unregistered session inside agent-dashboard product workspace:
            {'id': 's-dash-unreg', 'tag': 'dash-adhoc-worker', 'workspace': str(self.ws_dash), 'workload_pid': 202, 'reported_state': 'working'},
            # Unregistered session in completely unrelated project workspace (must NOT be collected):
            {'id': 's-unrelated', 'tag': 'other-worker', 'workspace': '/home/alexey/git/unrelated-pocketshell', 'workload_pid': 203, 'reported_state': 'working'}
        ]

        with patch.object(cmw, 'ROOT', self.ws_main), \
             patch.object(cmw, 'STORE', self.store), \
             patch.object(cmw, 'PRODUCT_WORKSPACES', self.product_workspaces), \
             patch.object(cmw, 'APLEXER_STATE', self.aplexer_state), \
             patch.object(cmw, 'quotas', return_value={}), \
             patch.object(cmw, 'proc', return_value={'alive': True, 'cpu_seconds': 0.5, 'rss_bytes': 512, 'start_ticks': 5}), \
             patch.object(cmw.subprocess, 'run', return_value=types.SimpleNamespace(returncode=0, stdout=json.dumps(catalog))):

            snap = cmw.collect()

        # Exactly 1 registered agent + 1 unregistered agent in agent-dashboard
        self.assertEqual(snap['aggregate']['registered_agents'], 1)
        self.assertEqual(snap['aggregate']['unregistered_live'], 1)

        sessions_by_id = {s['id']: s for s in snap['sessions']}
        self.assertIn('s-main', sessions_by_id)
        self.assertIn('s-dash-unreg', sessions_by_id)
        self.assertNotIn('s-unrelated', sessions_by_id)

        unreg = sessions_by_id['s-dash-unreg']
        self.assertTrue(unreg['unregistered'])
        self.assertEqual(unreg['tag'], 'dash-adhoc-worker')
        self.assertEqual(unreg['workspace'], str(self.ws_dash))
        self.assertEqual(unreg['team_id'], 'unregistered')

    def test_unknown_tokens_remain_none_null_not_fabricated(self):
        """Test 3: Unknown tokens remain None/null and are not fabricated.
        When usage telemetry is absent or unknown, total_tokens and cost_usd
        remain null. Zero retroactive fake 24h data.
        """
        registry = {
            'teams': [
                {
                    'id': 'a16',
                    'workspace': str(self.ws_main),
                    'agents': [
                        {'tag': 'no-telemetry-worker', 'role': 'executor', 'workspace': str(self.ws_main), 'session_id': 's-notel'}
                    ]
                }
            ]
        }
        (self.ws_main / 'coordination/TEAM-REGISTRY.json').write_text(json.dumps(registry))
        (self.ws_main / 'coordination/TASKS.json').write_text(json.dumps({'tasks': []}))

        catalog = [
            {'id': 's-notel', 'tag': 'no-telemetry-worker', 'workspace': str(self.ws_main), 'workload_pid': 301, 'reported_state': 'idle'}
        ]

        with patch.object(cmw, 'ROOT', self.ws_main), \
             patch.object(cmw, 'STORE', self.store), \
             patch.object(cmw, 'PRODUCT_WORKSPACES', self.product_workspaces), \
             patch.object(cmw, 'APLEXER_STATE', self.aplexer_state), \
             patch.object(cmw, 'quotas', return_value={}), \
             patch.object(cmw, 'proc', return_value={'alive': True, 'cpu_seconds': 0.1, 'rss_bytes': 256, 'start_ticks': 1}), \
             patch.object(cmw, 'native_usage', return_value=None), \
             patch.object(cmw.subprocess, 'run', return_value=types.SimpleNamespace(returncode=0, stdout=json.dumps(catalog))):

            snap = cmw.collect()

        self.assertEqual(len(snap['sessions']), 1)
        row = snap['sessions'][0]
        self.assertIsNone(row['usage'])
        self.assertIsNone(snap['aggregate']['known_conversation_tokens'])
        self.assertEqual(snap['aggregate']['agents_without_token_observation'], 1)

    def test_workspace_path_scoping_evidence_counted_not_out_of_scope(self):
        """Test 4: Workspace path scoping: evidence files inside each respective
        workspace are counted in that workspace's coverage rather than marked out_of_scope.
        External files outside all product workspaces are properly marked out_of_scope.
        """
        # Create evidence files in agent-dashboard
        dash_reports = self.ws_dash / 'reports'
        dash_reports.mkdir(parents=True, exist_ok=True)
        (dash_reports / 'frontend-brief.md').write_text('# Frontend Implementation')
        (self.ws_dash / 'test-results.json').write_text('{"status": "pass"}')

        # External file in /tmp/leak (outside all product workspaces)
        ext_dir = self.base / 'external-unrelated'
        ext_dir.mkdir(parents=True, exist_ok=True)
        (ext_dir / 'forbidden.txt').write_text('external leak')

        registry = {
            'teams': [
                {
                    'id': 'agent-dashboard',
                    'workspace': str(self.ws_dash),
                    'agents': [
                        {'tag': 'ad-exec', 'role': 'executor', 'workspace': str(self.ws_dash), 'session_id': 's-ad-exec'}
                    ]
                }
            ]
        }
        (self.ws_main / 'coordination/TEAM-REGISTRY.json').write_text(json.dumps(registry))

        tasks = {
            'tasks': [
                {
                    'id': 'task-dash-1',
                    'team_id': 'agent-dashboard',
                    'owner_tag': 'ad-exec',
                    'status': 'done',
                    'evidence_paths': [
                        'reports/frontend-brief.md',
                        str(self.ws_dash / 'test-results.json'),
                        str(ext_dir / 'forbidden.txt')  # out-of-scope path
                    ]
                }
            ]
        }
        (self.ws_main / 'coordination/TASKS.json').write_text(json.dumps(tasks))

        catalog = [
            {'id': 's-ad-exec', 'tag': 'ad-exec', 'workspace': str(self.ws_dash), 'workload_pid': 401, 'reported_state': 'idle'}
        ]

        with patch.object(cmw, 'ROOT', self.ws_main), \
             patch.object(cmw, 'STORE', self.store), \
             patch.object(cmw, 'PRODUCT_WORKSPACES', self.product_workspaces), \
             patch.object(cmw, 'APLEXER_STATE', self.aplexer_state), \
             patch.object(cmw, 'quotas', return_value={}), \
             patch.object(cmw, 'proc', return_value={'alive': True, 'cpu_seconds': 0.2, 'rss_bytes': 512, 'start_ticks': 1}), \
             patch.object(cmw.subprocess, 'run', return_value=types.SimpleNamespace(returncode=0, stdout=json.dumps(catalog))):

            snap = cmw.collect()

        self.assertEqual(len(snap['sessions']), 1)
        row = snap['sessions'][0]
        coverage = row['evidence_coverage']

        # Registered 3 distinct paths
        self.assertEqual(coverage['registered_distinct_paths'], 3)
        # Exactly 2 observed files inside ws_dash
        self.assertEqual(coverage['observed_distinct_files'], 2)
        # Exactly 1 out of scope path (the external-unrelated file)
        self.assertEqual(coverage['out_of_scope_paths'], [str(ext_dir / 'forbidden.txt')])
        self.assertEqual(coverage['missing_paths'], [])
        self.assertEqual(coverage['unsupported_directory_paths'], [])

        evidence_paths = {e['path'] for e in row['evidence']}
        self.assertIn('reports/frontend-brief.md', evidence_paths)
        self.assertIn(str(self.ws_dash / 'test-results.json'), evidence_paths)

    def test_discovered_delegate_linking_to_head_parent(self):
        """Test delegate discovery: a live session whose parent_session matches
        a product team's head is attributed to that team as a subagent delegate.
        """
        registry = {
            'projects': [
                {
                    'id': 'quota-launcher',
                    'head_tag': 'quota-launcher-head',
                    'head_session_id': 'head-ql-1',
                    'workspace': str(self.ws_quota)
                }
            ]
        }
        (self.ws_main / 'coordination/TEAM-REGISTRY.json').write_text(json.dumps(registry))
        (self.ws_main / 'coordination/TASKS.json').write_text(json.dumps({'tasks': []}))

        catalog = [
            {'id': 'head-ql-1', 'tag': 'quota-launcher-head', 'workspace': str(self.ws_quota), 'workload_pid': 501, 'reported_state': 'waiting'},
            {'id': 'worker-ql-child', 'tag': 'quota-core-worker', 'parent_session': 'head-ql-1', 'workspace': str(self.ws_quota), 'workload_pid': 502, 'reported_state': 'working'}
        ]

        with patch.object(cmw, 'ROOT', self.ws_main), \
             patch.object(cmw, 'STORE', self.store), \
             patch.object(cmw, 'PRODUCT_WORKSPACES', self.product_workspaces), \
             patch.object(cmw, 'APLEXER_STATE', self.aplexer_state), \
             patch.object(cmw, 'quotas', return_value={}), \
             patch.object(cmw, 'proc', return_value={'alive': True, 'cpu_seconds': 0.5, 'rss_bytes': 512, 'start_ticks': 1}), \
             patch.object(cmw.subprocess, 'run', return_value=types.SimpleNamespace(returncode=0, stdout=json.dumps(catalog))):

            snap = cmw.collect()

        sessions_by_id = {s['id']: s for s in snap['sessions']}
        self.assertIn('worker-ql-child', sessions_by_id)
        child = sessions_by_id['worker-ql-child']
        self.assertEqual(child['team_id'], 'quota-launcher')
        self.assertEqual(child['role'], 'subagent')
        self.assertTrue(child['counted_as_agent'])
        self.assertIn('discovered delegate of head', child['resolution'])

    def test_c1504_pure_function_get_product_workspaces_negative(self):
        """Codex C1504 negative test:
        Verifies that get_product_workspaces(registry={}, catalog=[...]):
        1. Correctly selects 'agent-bus' (the public core coordination repo).
        2. Correctly rejects lookalike 'unrelated-agent-dashboard-notes' (substring lookalike).
        3. Never uses loose substring matching to expand unrelated directories.
        """
        catalog = [
            {'id': 's1', 'workspace': '/home/alexey/git/agent-bus'},
            {'id': 's2', 'workspace': '/home/alexey/git/unrelated-agent-dashboard-notes'},
            {'id': 's3', 'workspace': '/home/alexey/git/agent-dashboard'},
            {'id': 's4', 'workspace': '/home/alexey/git/pocketshell'},
            {'id': 's5', 'workspace': '/home/alexey/git/agent-branches-l6-stack'}
        ]
        res = cmw.get_product_workspaces(registry={}, catalog=catalog)

        # /home/alexey/git/agent-bus MUST be selected
        self.assertIn('/home/alexey/git/agent-bus', res)
        # /home/alexey/git/agent-dashboard MUST be selected
        self.assertIn('/home/alexey/git/agent-dashboard', res)
        # /home/alexey/git/agent-branches-l6-stack MUST be selected
        self.assertIn('/home/alexey/git/agent-branches-l6-stack', res)

        # /home/alexey/git/unrelated-agent-dashboard-notes MUST NOT be selected
        self.assertNotIn('/home/alexey/git/unrelated-agent-dashboard-notes', res,
                         "Lookalike substring directory must not be selected as product workspace")
        # /home/alexey/git/pocketshell MUST NOT be selected
        self.assertNotIn('/home/alexey/git/pocketshell', res)


if __name__ == '__main__':
    unittest.main()
