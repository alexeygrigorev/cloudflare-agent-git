import gzip
import http.server
import json
import pathlib
import tempfile
import threading
import unittest

import backfill


def make_row(at, tag='w'):
    return {
        'at': at,
        'aggregate': {'known_conversation_tokens': 10, 'unregistered_live': 0},
        'errors': [],
        'sessions': [
            {'id': 's1', 'tag': tag, 'role': 'executor', 'team_id': 'T1',
             'counted_as_agent': True, 'pid_live': True, 'hook_working': True,
             'reported_state': 'working',
             'usage': {'source': 'codex-native-cumulative', 'conversation_id': 'c1',
                       'total_tokens': 50, 'tokens_since_observer': 5}},
        ],
        'tasks': [{'id': 't1', 'status': 'running', 'team_id': 'T1'}],
        'observation': {'task_transitions_this_sample': []},
    }


class StubVM:
    def __init__(self):
        self.bodies = []
        stub = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get('Content-Length', 0))
                stub.bodies.append(self.rfile.read(length))
                self.send_response(204)
                self.end_headers()

            def log_message(self, *args):
                pass

        self.server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    @property
    def url(self):
        return 'http://127.0.0.1:%d' % self.server.server_address[1]

    def close(self):
        self.server.shutdown()


class BackfillTests(unittest.TestCase):
    def test_imports_with_original_timestamps_and_skips_on_rerun(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = pathlib.Path(tmp)
            rows = [make_row('2026-10-10T10:00:00+00:00'), make_row('2026-10-10T10:01:00+00:00')]
            (store / 'snapshots-2026-10-10.jsonl').write_text('\n'.join(json.dumps(r) for r in rows) + '\n')
            archive = store / 'archive'
            archive.mkdir()
            with gzip.open(archive / 'snapshots-2026-10-09.jsonl.1.gz', 'wt') as f:
                f.write(json.dumps(make_row('2026-10-09T10:00:00+00:00', tag='old')) + '\n')
            vm = StubVM()
            try:
                stats = backfill.backfill(store=store, vm_url=vm.url)
                self.assertEqual(stats['files_imported'], 2)
                self.assertEqual(stats['snapshots'], 3)
                self.assertEqual(stats['errors'], [])
                body = b'\n'.join(vm.bodies).decode()
                self.assertIn('exp_agents_registered{role="executor",team="T1"} 1 1791626400000', body)
                self.assertIn('exp_tasks{status="running",team="T1"} 1 1791540000000', body)
                # Rerun skips recorded files and pushes nothing.
                vm.bodies.clear()
                again = backfill.backfill(store=store, vm_url=vm.url)
                self.assertEqual(again['files_skipped'], 2)
                self.assertEqual(again['snapshots'], 0)
                self.assertEqual(vm.bodies, [])
            finally:
                vm.close()

    def test_dry_run_pushes_nothing_and_archives_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = pathlib.Path(tmp)
            archive = store / 'archive'
            archive.mkdir()
            gz = archive / 'snapshots-2026-10-09.jsonl.1.gz'
            with gzip.open(gz, 'wt') as f:
                f.write(json.dumps(make_row('2026-10-09T10:00:00+00:00')) + '\n')
            before = gz.read_bytes()
            vm = StubVM()
            try:
                stats = backfill.backfill(store=store, vm_url=vm.url, dry_run=True)
                self.assertEqual(vm.bodies, [])
                self.assertFalse((store / 'backfill-state.json').exists())
                self.assertEqual(gz.read_bytes(), before)
                self.assertEqual(stats['snapshots'], 1)
            finally:
                vm.close()

    def test_corrupt_lines_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = pathlib.Path(tmp)
            (store / 'snapshots-2026-10-10.jsonl').write_text(
                'not json\n' + json.dumps(make_row('2026-10-10T10:00:00+00:00')) + '\n\n')
            vm = StubVM()
            try:
                stats = backfill.backfill(store=store, vm_url=vm.url)
                self.assertEqual(stats['snapshots'], 1)
                self.assertEqual(stats['errors'], [])
            finally:
                vm.close()


if __name__ == '__main__':
    unittest.main()
