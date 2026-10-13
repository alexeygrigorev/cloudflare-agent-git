import pathlib
import tempfile
import unittest

import state


def make_snap():
    return {
        'tasks': [
            {'id': 't1', 'status': 'running', 'owner_tag': 'w1', 'team_id': 'T1',
             'updated_at': '2026-10-13T19:00:00Z', 'acceptance_status': 'pending',
             'reviewer_tag': None, 'evidence_paths': ['result.txt'], 'next_action': 'replay'},
        ],
        'sessions': [
            {'id': 's1', 'tag': 'w1',
             'tasks': [{'id': 't1', 'status': 'running'}],
             'evidence': [{'path': 'result.txt', 'bytes': 15, 'mtime': 100.0}]},
        ],
        'observation': {'task_transitions_this_sample': [
            {'at': '2026-10-13T19:00:00+00:00', 'task_id': 't1',
             'from_status': 'ready', 'to_status': 'running'},
        ]},
    }


class StateTests(unittest.TestCase):
    def test_first_sample_writes_second_identical_sample_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = pathlib.Path(tmp)
            first = state.record_sample(store, make_snap(), '2026-10-13T19:00:00+00:00')
            self.assertEqual(first, {'tasks_changed': 1, 'evidence_changed': 1, 'transitions_added': 1})
            before_tasks = state.read_tasks(store)
            before_evidence = state.read_evidence(store)
            second = state.record_sample(store, make_snap(), '2026-10-13T19:01:00+00:00')
            self.assertEqual(second, {'tasks_changed': 0, 'evidence_changed': 0, 'transitions_added': 0})
            self.assertEqual(state.read_tasks(store), before_tasks)
            self.assertEqual(state.read_evidence(store), before_evidence)

    def test_task_update_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = pathlib.Path(tmp)
            state.record_sample(store, make_snap(), '2026-10-13T19:00:00+00:00')
            snap = make_snap()
            snap['tasks'][0]['status'] = 'review'
            result = state.record_sample(store, snap, '2026-10-13T19:01:00+00:00')
            self.assertEqual(result['tasks_changed'], 1)
            rows = state.read_tasks(store)
            self.assertEqual(rows[0]['status'], 'review')
            self.assertEqual(rows[0]['last_change'], '2026-10-13T19:01:00+00:00')
            self.assertEqual(rows[0]['first_seen'], '2026-10-13T19:00:00+00:00')

    def test_evidence_change_and_removal(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = pathlib.Path(tmp)
            state.record_sample(store, make_snap(), '2026-10-13T19:00:00+00:00')
            snap = make_snap()
            snap['sessions'][0]['evidence'][0]['bytes'] = 20
            result = state.record_sample(store, snap, '2026-10-13T19:01:00+00:00')
            self.assertEqual(result['evidence_changed'], 1)
            self.assertEqual(state.read_evidence(store)[0]['bytes'], 20)
            # Removal from both the task contract and the session is a change.
            snap['tasks'][0]['evidence_paths'] = []
            snap['sessions'][0]['evidence'] = []
            result = state.record_sample(store, snap, '2026-10-13T19:02:00+00:00')
            self.assertEqual(result['evidence_changed'], 1)  # evidence row deleted
            self.assertEqual(result['tasks_changed'], 1)  # task contract changed too
            self.assertEqual(state.read_evidence(store), [])

    def test_transitions_append_and_filter(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = pathlib.Path(tmp)
            state.record_sample(store, make_snap(), '2026-10-13T19:00:00+00:00')
            rows = state.read_transitions(store)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]['to_status'], 'running')
            self.assertEqual(state.read_transitions(store, since='2026-10-13T20:00:00+00:00'), [])

    def test_empty_store_reads_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = pathlib.Path(tmp)
            self.assertEqual(state.read_tasks(store), [])
            self.assertEqual(state.read_evidence(store), [])
            self.assertEqual(state.read_transitions(store), [])

    def test_file_permissions(self):
        import stat as statmod
        with tempfile.TemporaryDirectory() as tmp:
            store = pathlib.Path(tmp)
            state.record_sample(store, make_snap(), '2026-10-13T19:00:00+00:00')
            mode = (store / 'state.sqlite').stat().st_mode & 0o777
            self.assertEqual(mode, 0o600)


if __name__ == '__main__':
    unittest.main()
