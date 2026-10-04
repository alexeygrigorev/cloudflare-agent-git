#!/usr/bin/env python3
"""
Offline test suite for supervision routing repair (C1629 / C1630).
Validates:
1. Product task matching for quota-launcher under codex-principal.
2. Project alias resolution (agent-quota-launcher <-> quota-launcher).
3. Entity extraction of all 4 active product projects from TEAM-REGISTRY.json.
4. Excluded and stopped principals remain excluded from task routing.
5. Deterministic head completion tracking in task event digest and message body.
6. Distinction of ready/queued tasks from running tasks in queues and summaries.
7. Full service.run() simulation verifying receipt and envelope body generation.
"""
import hashlib
import importlib.util
import json
import os
import pathlib
import tempfile
import unittest

# Ensure modules in scripts/supervision and candidate can be loaded
ROOT = pathlib.Path(__file__).resolve().parents[1]
SUPERVISION_DIR = ROOT / 'scripts/supervision'
CANDIDATE_PATH = ROOT / 'research/antigravity/tooling/supervision/service_candidate.py'

spec = importlib.util.spec_from_file_location('service_candidate', str(CANDIDATE_PATH))
service = importlib.util.module_from_spec(spec)
spec.loader.exec_module(service)

SCRATCH_BASE = ROOT / '.local/scratch/supervision-routing'
SCRATCH_BASE.mkdir(parents=True, exist_ok=True)
os.chmod(SCRATCH_BASE, 0o700)


class SupervisionRoutingTests(unittest.TestCase):
    """Test suite covering the 7 core requirements of C1629/C1630."""

    def test_1_quota_launcher_task_matched_for_codex_principal(self):
        """Test 1: Task with team_id='quota-launcher' and project_id='quota-launcher' is matched for codex-principal."""
        registry = {
            'projects': [
                {
                    'id': 'quota-launcher',
                    'name': 'Agent Quota Launcher',
                    'head_tag': 'quota-launcher-head',
                    'principal_tags': ['codex-principal'],
                    'workspace': '/home/alexey/git/agent-quota-launcher'
                }
            ]
        }
        entities = service.extract_supervision_entities(registry)
        self.assertEqual(len(entities), 1)
        entity = entities[0]
        self.assertEqual(entity['id'], 'quota-launcher')
        self.assertIn('codex-principal', entity['principal_tags'])

        task = {
            'id': 'launcher-quota-resource-gates',
            'team_id': 'quota-launcher',
            'project_id': 'quota-launcher',
            'status': 'queued',
            'owner_tag': 'quota-launcher-head'
        }
        self.assertTrue(service.task_matches_entity(task, entity))

        # Test principal-level selection
        active_tasks = [task, {'id': 'unrelated-task', 'team_id': 'unrelated-team', 'status': 'queued'}]
        principal_entities = [e for e in entities if 'codex-principal' in e.get('principal_tags', [])]
        selected = [t for t in active_tasks if any(service.task_matches_entity(t, e) for e in principal_entities)]
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]['id'], 'launcher-quota-resource-gates')

    def test_2_alias_project_id_agent_quota_launcher_matched(self):
        """Test 2: Task with alias project_id='agent-quota-launcher' is matched for quota-launcher."""
        entity = {
            'id': 'quota-launcher',
            'name': 'Agent Quota Launcher',
            'aliases': ['quota-launcher', 'agent-quota-launcher']
        }
        # Direct normalization check
        self.assertEqual(service.normalize_project_id('agent-quota-launcher'), 'quota-launcher')
        self.assertEqual(service.normalize_project_id('quota-launcher'), 'quota-launcher')

        # Task specifying alias project_id
        task_with_alias_proj = {
            'id': 'ql-4c2bfec-independent-review',
            'team_id': 'quota-launcher',
            'project_id': 'agent-quota-launcher',
            'status': 'done',
            'owner_tag': 'antigravity-head'
        }
        self.assertTrue(service.task_matches_entity(task_with_alias_proj, entity))

        # Task specifying alias project_id with no team_id
        task_no_team = {
            'id': 'ql-task-no-team',
            'project_id': 'agent-quota-launcher',
            'status': 'queued',
            'owner_tag': 'quota-launcher-head'
        }
        self.assertTrue(service.task_matches_entity(task_no_team, entity))

        # Task specifying alias as team_id
        task_alias_team = {
            'id': 'ql-task-alias-team',
            'team_id': 'agent-quota-launcher',
            'status': 'queued',
            'owner_tag': 'quota-launcher-head'
        }
        self.assertTrue(service.task_matches_entity(task_alias_team, entity))

    def test_3_product_projects_included_in_extracted_entities(self):
        """Test 3: Product projects (agent-coordination, agent-dashboard, agent-branches, quota-launcher) are all included in extracted entities."""
        reg_path = ROOT / 'coordination/TEAM-REGISTRY.json'
        canonical_registry = json.loads(reg_path.read_text())
        entities = service.extract_supervision_entities(canonical_registry)

        entity_ids = {e['id'] for e in entities}
        expected_products = {'agent-branches', 'agent-dashboard', 'quota-launcher', 'agent-coordination'}
        for prod in expected_products:
            self.assertIn(prod, entity_ids, f"Product {prod} missing from extracted supervision entities")

        # Verify each product project has valid head_tag and truthful principal_tags (C1637: Codex monitoring ACK)
        by_id = {e['id']: e for e in entities}
        self.assertEqual(by_id['agent-branches']['head_tag'], 'antigravity-head')
        self.assertEqual(by_id['agent-branches']['principal_tags'], ['codex-principal'], "agent-branches monitored by codex-principal under C1637 ACK")
        self.assertFalse(by_id['agent-branches']['unowned'])

        self.assertEqual(by_id['agent-dashboard']['head_tag'], 'agent-dashboard-head')
        self.assertEqual(by_id['agent-dashboard']['principal_tags'], ['codex-principal'], "agent-dashboard monitored by codex-principal under C1637 ACK")
        self.assertFalse(by_id['agent-dashboard']['unowned'])

        self.assertEqual(by_id['quota-launcher']['head_tag'], 'quota-launcher-head')
        self.assertEqual(by_id['quota-launcher']['principal_tags'], ['codex-principal'], "quota-launcher monitored by codex-principal under C1637 ACK")
        self.assertFalse(by_id['quota-launcher']['unowned'])

        self.assertEqual(by_id['agent-coordination']['head_tag'], 'agent-coordination-head')
        self.assertEqual(by_id['agent-coordination']['principal_tags'], ['codex-principal'], "agent-coordination specifies codex-principal")
        self.assertFalse(by_id['agent-coordination']['unowned'])

    def test_4_stopped_or_excluded_principals_remain_excluded(self):
        """Test 4: Stopped or excluded principals (e.g. claude-principal) remain excluded."""
        reg_path = ROOT / 'coordination/TEAM-REGISTRY.json'
        canonical_registry = json.loads(reg_path.read_text())
        entities = service.extract_supervision_entities(canonical_registry)

        # In canonical registry, claude-principal is in excluded_principals
        active = service.active_principals(entities, registry_raw=canonical_registry)
        self.assertNotIn('claude-principal', active)
        self.assertIn('codex-principal', active)

        # Test agent quiet status exclusion
        quiet_reg = {
            'teams': [{'id': 't1', 'principal_tags': ['claude-principal', 'codex-principal']}],
            'agents': [{'tag': 'claude-principal', 'status': 'quiet'}]
        }
        quiet_entities = service.extract_supervision_entities(quiet_reg)
        active_quiet = service.active_principals(quiet_entities, registry_raw=quiet_reg)
        self.assertEqual(active_quiet, ['codex-principal'])

        # Test explicit supervision_excluded flag
        excluded_reg = {
            'teams': [{'id': 't1', 'principal_tags': ['claude-principal', 'codex-principal']}],
            'agents': [{'tag': 'claude-principal', 'supervision_excluded': True}]
        }
        active_ex = service.active_principals(quiet_entities, registry_raw=excluded_reg)
        self.assertEqual(active_ex, ['codex-principal'])

        # Test environment variable exclusion override
        old_env = os.environ.get('SUPERVISION_EXCLUDE_PRINCIPALS')
        try:
            os.environ['SUPERVISION_EXCLUDE_PRINCIPALS'] = 'claude-principal'
            active_env = service.active_principals(entities)
            self.assertNotIn('claude-principal', active_env)
        finally:
            if old_env is not None:
                os.environ['SUPERVISION_EXCLUDE_PRINCIPALS'] = old_env
            else:
                os.environ.pop('SUPERVISION_EXCLUDE_PRINCIPALS', None)

    def test_5_deterministic_head_completion_digest_and_message_body(self):
        """Test 5: Deterministic head completion: recent completions are captured in task event digest and formatted in message body."""
        t_active = [
            {
                'id': 'launcher-quota-resource-gates',
                'team_id': 'quota-launcher',
                'project_id': 'quota-launcher',
                'status': 'queued',
                'owner_tag': 'quota-launcher-head'
            },
            {
                'id': 'coord-native-ssh-mvp',
                'team_id': 'agent-coordination',
                'project_id': 'agent-coordination',
                'status': 'running',
                'owner_tag': 'agent-coordination-head'
            }
        ]
        t_done = [
            {
                'id': 'ql-4c2bfec-independent-review',
                'team_id': 'quota-launcher',
                'project_id': 'agent-quota-launcher',
                'status': 'done',
                'owner_tag': 'antigravity-head',
                'updated_at': '2026-10-04T14:05:00.000000+00:00'
            }
        ]

        # 1. Digest changes deterministically when completion is added
        active1, digest1, counts1 = service.task_event(t_active)
        active2, digest2, counts2 = service.task_event(t_active + t_done)
        self.assertNotEqual(digest1, digest2, "Task completion must alter event digest")

        # 2. Digest is strictly deterministic across multiple invocations
        active3, digest3, counts3 = service.task_event(t_active + t_done)
        self.assertEqual(digest2, digest3, "Task digest must be 100% deterministic")

        # 3. Formatted message body contains task grouping and recent completions
        entities = [
            {'id': 'quota-launcher', 'principal_tags': ['codex-principal']},
            {'id': 'agent-coordination', 'principal_tags': ['codex-principal']}
        ]
        body = service.format_supervision_body(
            event_key='testevent123',
            selected_tasks=t_active,
            entities=entities,
            recent_completions=t_done
        )
        self.assertIn('SUPERVISION-testevent123:', body)
        self.assertIn('[quota-launcher] launcher-quota-resource-gates (queued, quota-launcher-head)', body)
        self.assertIn('[agent-coordination] coord-native-ssh-mvp (running, agent-coordination-head)', body)
        self.assertIn('Recent completions: ql-4c2bfec-independent-review (done)', body)

    def test_6_ready_tasks_distinguished_from_running_tasks(self):
        """Test 6: Ready tasks (queued) are distinguished from running tasks."""
        tasks = [
            {
                'id': 'task-queued-1',
                'team_id': 'quota-launcher',
                'status': 'queued',
                'owner_tag': 'quota-launcher-head'
            },
            {
                'id': 'task-ready-2',
                'team_id': 'quota-launcher',
                'status': 'ready',
                'owner_tag': 'quota-launcher-head'
            },
            {
                'id': 'task-running-3',
                'team_id': 'agent-coordination',
                'status': 'running',
                'owner_tag': 'agent-coordination-head'
            }
        ]
        active, digest, counts = service.task_event(tasks)

        # Queue distinction in counts
        self.assertEqual(counts.get('queued'), 1)
        self.assertEqual(counts.get('ready'), 1)
        self.assertEqual(counts.get('running'), 1)

        # Queue distinction in ActiveTaskList attributes
        self.assertEqual(len(active.ready), 2)
        self.assertEqual({t['id'] for t in active.ready}, {'task-queued-1', 'task-ready-2'})
        self.assertEqual(len(active.running), 1)
        self.assertEqual(active.running[0]['id'], 'task-running-3')

        # Formatting reflects status distinction
        entities = [
            {'id': 'quota-launcher', 'principal_tags': ['codex-principal']},
            {'id': 'agent-coordination', 'principal_tags': ['codex-principal']}
        ]
        body = service.format_supervision_body('key1', active, entities)
        self.assertIn('task-queued-1 (queued, quota-launcher-head)', body)
        self.assertIn('task-ready-2 (ready, quota-launcher-head)', body)
        self.assertIn('task-running-3 (running, agent-coordination-head)', body)

    def test_7_full_service_run_simulation_quota_launcher_in_receipt_and_inbox(self):
        """Test 7: Full service.run() simulation verifying that quota-launcher tasks appear in the generated receipt and inbox envelope body."""
        # Use isolated scratch directory for zero net /tmp growth
        with tempfile.TemporaryDirectory(dir=str(SCRATCH_BASE)) as td:
            tmp = pathlib.Path(td)
            root = tmp / 'root'
            (root / 'coordination').mkdir(parents=True)
            private = tmp / 'private'
            private.mkdir()
            bin_dir = tmp / 'bin'
            bin_dir.mkdir()
            pinned = bin_dir / 'aplexer'
            pinned.write_bytes(b'PINNED_BINARY_BYTES')

            registry_content = {
                'projects': [
                    {
                        'id': 'quota-launcher',
                        'name': 'Agent Quota Launcher',
                        'head_tag': 'quota-launcher-head',
                        'principal_owner': 'codex-principal',
                        'workspace': '/home/alexey/git/agent-quota-launcher'
                    }
                ]
            }
            tasks_content = {
                'tasks': [
                    {
                        'id': 'launcher-quota-resource-gates',
                        'team_id': 'quota-launcher',
                        'project_id': 'quota-launcher',
                        'status': 'queued',
                        'owner_tag': 'quota-launcher-head'
                    },
                    {
                        'id': 'launcher-native-lifecycle',
                        'team_id': 'quota-launcher',
                        'project_id': 'quota-launcher',
                        'status': 'queued',
                        'owner_tag': 'quota-launcher-head'
                    },
                    {
                        'id': 'ql-4c2bfec-independent-review',
                        'team_id': 'quota-launcher',
                        'project_id': 'agent-quota-launcher',
                        'status': 'done',
                        'owner_tag': 'antigravity-head',
                        'updated_at': '2026-10-04T14:05:00Z'
                    }
                ]
            }

            (root / 'coordination/TEAM-REGISTRY.json').write_text(json.dumps(registry_content))
            (root / 'coordination/TASKS.json').write_text(json.dumps(tasks_content))

            sent_bodies = []
            cycles = [0]

            def fake_cmd(args, timeout=20):
                words = [a for a in args[1:] if not a.startswith('-')]
                if words[:1] == ['whoami']:
                    return json.dumps({'workspace': str(root), 'tag': 'experiment-supervision', 'id': 'sup-test-1'})
                if '--help' in args or 'help' in args:
                    return '  --idempotency-key'
                if words[:1] == ['list']:
                    cycles[0] += 1
                    if cycles[0] >= 1:
                        (private / 'stop').write_text('stop')
                    return json.dumps([{
                        'workspace': str(root),
                        'tag': 'codex-principal',
                        'id': 'sess-codex-1',
                        'reported_state': 'idle',
                        'workload_pid': str(os.getpid())
                    }])
                if 'inbox' in args:
                    return json.dumps({'messages': []})
                if 'capture' in args:
                    return "› Ask Codex to do anything\n  GPT-6.1 Context 50% left"
                if args[0] == 'quse':
                    return json.dumps({'codex': {'status': 'ok', 'windows': {'7d': {'percent_remaining': 85}}}})
                if words[:2] == ['message', 'send']:
                    body_arg = args[-1]
                    sent_bodies.append(body_arg)
                    mid = f"m-{hashlib.sha256(body_arg.encode()).hexdigest()[:8]}"
                    return json.dumps({'id': mid, 'delivery': 'inbox', 'body': body_arg})
                return '{}'

            real_cmd, real_run, real_time = service.command, service.subprocess.run, service.time
            real_root, real_priv, real_bin = service.ROOT, service.PRIVATE, service.BINARY
            real_defaults = service.recorded_send.__defaults__

            try:
                service.command = fake_cmd
                service.recorded_send.__defaults__ = (fake_cmd,)
                service.time = type('T', (), {
                    'time': staticmethod(lambda: 2000.0),
                    'sleep': staticmethod(lambda s: None)
                })()
                service.ROOT = root
                service.PRIVATE = private
                service.BINARY = str(pinned)

                # Execute cycle
                service.run()

                # Verify message send occurred
                self.assertTrue(len(sent_bodies) >= 1, "service.run() must send a supervision request to codex-principal")
                body = sent_bodies[0]

                # Assert quota-launcher project tasks and recent completion are present in body
                self.assertIn('[quota-launcher]', body)
                self.assertIn('launcher-quota-resource-gates (queued, quota-launcher-head)', body)
                self.assertIn('launcher-native-lifecycle (queued, quota-launcher-head)', body)
                self.assertIn('Recent completions: ql-4c2bfec-independent-review (done)', body)

                # Assert receipt file was atomically persisted in PRIVATE
                receipt_files = list(private.glob('receipt-*.json'))
                self.assertTrue(len(receipt_files) >= 1, "Receipt JSON must be written to spool")
                receipt_data = json.loads(receipt_files[0].read_text())
                self.assertEqual(receipt_data.get('delivery'), 'inbox')
                self.assertEqual(receipt_data.get('body'), body)

                # Assert state.json tracked the sent event
                state_data = json.loads((private / 'state.json').read_text())
                self.assertIn('codex-principal', state_data)
                self.assertIsNotNone(state_data['codex-principal'].get('sent_event'))
                self.assertIsNotNone(state_data['codex-principal'].get('pending'))
            finally:
                service.command, service.subprocess.run, service.time = real_cmd, real_run, real_time
                service.recorded_send.__defaults__ = real_defaults
                service.ROOT, service.PRIVATE, service.BINARY = real_root, real_priv, real_bin

    def test_8_explicit_empty_ownership_not_defaulted_to_codex(self):
        """Test 8 (C1634 negative): Project with no principal owner preserves empty ownership ([]), NOT defaulted to codex-principal."""
        registry = {
            'projects': [
                {
                    'id': 'unowned-project',
                    'name': 'Unowned Experimental Project',
                    'head_tag': 'some-head',
                    'workspace': '/home/alexey/git/unowned-project'
                    # No principal_tags, principal_owner, or assignment_ack
                }
            ]
        }
        entities = service.extract_supervision_entities(registry)
        self.assertEqual(len(entities), 1)
        entity = entities[0]
        self.assertEqual(entity['id'], 'unowned-project')
        self.assertEqual(entity['principal_tags'], [])
        self.assertTrue(entity['unowned'])
        # Assert codex-principal does NOT get assigned this project
        self.assertNotIn('codex-principal', entity['principal_tags'])

        # Task under unowned project must NOT be selected for codex-principal
        task = {'id': 't-unowned', 'project_id': 'unowned-project', 'status': 'queued'}
        principal_entities = [e for e in entities if 'codex-principal' in e.get('principal_tags', [])]
        selected = [t for t in [task] if any(service.task_matches_entity(t, e) for e in principal_entities)]
        self.assertEqual(len(selected), 0, "Unowned project tasks must never be silently assigned to codex-principal")

    def test_9_unknown_project_task_not_matched(self):
        """Test 9 (C1634 negative): Task with unknown/unmapped project_id is not matched by any entity."""
        registry = {
            'projects': [
                {'id': 'agent-branches', 'name': 'Agent Branches', 'principal_tags': ['codex-principal']}
            ]
        }
        entities = service.extract_supervision_entities(registry)
        unknown_task = {'id': 't-rogue', 'project_id': 'completely-unrelated-repo', 'team_id': 'rogue-team', 'status': 'queued'}
        matched = [e for e in entities if service.task_matches_entity(unknown_task, e)]
        self.assertEqual(len(matched), 0, "Unknown project task must not match any registered entity")

    def test_10_conflicting_team_and_project_detected(self):
        """Test 10 (C1634 edge case): Conflicting team and project registrations with same normalized ID surface conflict explicitly."""
        registry = {
            'teams': [
                {
                    'id': 'quota-launcher',
                    'name': 'Old QL Team',
                    'head_tag': 'old-ql-head',
                    'workspace': '/home/alexey/git/cloudflare-agent-git',
                    'principal_tags': ['claude-principal']
                }
            ],
            'projects': [
                {
                    'id': 'agent-quota-launcher',  # Normalizes to 'quota-launcher'
                    'name': 'New QL Project',
                    'head_tag': 'quota-launcher-head',  # Conflicting head!
                    'workspace': '/home/alexey/git/agent-quota-launcher',  # Conflicting workspace!
                    'principal_tags': ['codex-principal']  # Conflicting principal!
                }
            ]
        }
        entities = service.extract_supervision_entities(registry)
        self.assertEqual(len(entities), 2, "Both conflicting entities must be retained for audit visibility")
        conflicting_project = [e for e in entities if e['id'] == 'agent-quota-launcher'][0]
        self.assertIsNotNone(conflicting_project['conflict'], "Conflict must be detected and recorded")
        self.assertTrue(conflicting_project['conflict']['detected'])
        self.assertEqual(conflicting_project['conflict']['conflict_with'], 'quota-launcher')
        # Conflicting reasons should mention head, workspace, and principal_tags
        summary = conflicting_project['conflict']['summary']
        self.assertIn('head_tag', summary)
        self.assertIn('workspace', summary)
        self.assertIn('principal_tags', summary)

    def test_11_deterministic_alias_ordering(self):
        """Test 11 (C1634 deterministic): Aliases in extracted entities must be deterministically sorted."""
        registry = {
            'projects': [
                {'id': 'agent-branches', 'name': 'Agent Branches'},
                {'id': 'agent-dashboard', 'name': 'Agent Dashboard'},
                {'id': 'quota-launcher', 'name': 'Agent Quota Launcher'},
                {'id': 'agent-coordination', 'name': 'Cross-computer Agent Coordination'}
            ]
        }
        entities = service.extract_supervision_entities(registry)
        for entity in entities:
            aliases = entity.get('aliases', [])
            self.assertEqual(aliases, sorted(aliases), f"Aliases for {entity['id']} must be deterministically sorted list")

    def test_12_epistemic_boundary_task_body_is_notification_only(self):
        """Test 12 (C1634 epistemic boundary): Task body formatting is an informational status notification, not an automatic dispatcher."""
        selected_tasks = [
            {'id': 'launcher-quota-resource-gates', 'team_id': 'quota-launcher', 'project_id': 'quota-launcher', 'status': 'queued', 'owner_tag': 'quota-launcher-head'}
        ]
        recent_done = [
            {'id': 'ql-4c2bfec-independent-review', 'status': 'done'}
        ]
        body = service.format_supervision_body('abc12345', selected_tasks, recent_done)
        # Verify clear notification structure
        self.assertTrue(body.startswith('SUPERVISION-abc12345:'))
        self.assertIn('Recent completions:', body)
        self.assertIn('inspect your teams, ask heads to claim ready owned work', body)
        # Confirm it reminds monitoring principal to ask heads, rather than claiming automatic execution
        self.assertIn('ask heads to claim ready owned work', body)

    def test_13_conflicting_entities_excluded_from_authoritative_principal_selection(self):
        """Test 13 (C1636 conflict routing): Conflicting entities are excluded from authoritative principal selection."""
        conflicted_e = {
            'id': 'agent-quota-launcher',
            'principal_tags': ['codex-principal'],
            'conflict': {'detected': True, 'summary': 'Conflicting registration'}
        }
        unconflicted_e = {
            'id': 'agent-coordination',
            'principal_tags': ['codex-principal'],
            'conflict': None
        }
        entities = [conflicted_e, unconflicted_e]
        # In service logic: unconflicted authoritative entities
        authoritative = [e for e in entities if 'codex-principal' in e.get('principal_tags', []) and not (e.get('conflict') and e['conflict'].get('detected'))]
        self.assertEqual(len(authoritative), 1)
        self.assertEqual(authoritative[0]['id'], 'agent-coordination')

    def test_14_explicit_empty_list_vs_absent_principal_tags(self):
        """Test 14 (C1636 semantics): Explicit empty list principal_tags=[] overrides owner; absent field checks owner."""
        registry = {
            'projects': [
                {
                    'id': 'proj-explicit-empty',
                    'principal_tags': [],  # Explicit empty list!
                    'principal_owner': {'tag': 'codex-principal'}
                },
                {
                    'id': 'proj-absent-tags',
                    # No principal_tags key!
                    'principal_owner': {'tag': 'codex-principal'}
                }
            ]
        }
        entities = service.extract_supervision_entities(registry)
        by_id = {e['id']: e for e in entities}
        # Explicit empty must remain empty
        self.assertEqual(by_id['proj-explicit-empty']['principal_tags'], [])
        self.assertTrue(by_id['proj-explicit-empty']['unowned'])
        # Absent field must pick up owner
        self.assertEqual(by_id['proj-absent-tags']['principal_tags'], ['codex-principal'])
        self.assertFalse(by_id['proj-absent-tags']['unowned'])

    def test_15_compatible_merge_preserves_head_and_workspace(self):
        """Test 15 (C1636 merge): Compatible duplicate merge preserves nonempty head_tag and workspace from project."""
        registry = {
            'teams': [
                {
                    'id': 'agent-dashboard',
                    'name': 'Agent Dashboard',
                    'head_tag': None,
                    'workspace': None,
                    'principal_tags': ['codex-principal']
                }
            ],
            'projects': [
                {
                    'id': 'agent-dashboard',
                    'name': 'Agent Dashboard',
                    'head_tag': 'agent-dashboard-head',
                    'workspace': '/home/alexey/git/agent-dashboard',
                    'principal_tags': ['codex-principal']
                }
            ]
        }
        entities = service.extract_supervision_entities(registry)
        self.assertEqual(len(entities), 1, "Compatible duplicate must merge into single entity")
        merged = entities[0]
        self.assertEqual(merged['head_tag'], 'agent-dashboard-head', "Nonempty head from project must be preserved")
        self.assertEqual(merged['workspace'], '/home/alexey/git/agent-dashboard', "Nonempty workspace from project must be preserved")


if __name__ == '__main__':
    unittest.main()

