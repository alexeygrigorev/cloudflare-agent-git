"""Multi-store OpenCode usage: owned isolated DB plus user home DB, deduped read-only."""
import json
import pathlib
import sqlite3
import tempfile
import unittest
from opencode_usage import read_usage, DB_REL

SCHEMA = 'CREATE TABLE IF NOT EXISTS session(id TEXT PRIMARY KEY,parent_id TEXT,directory TEXT);CREATE TABLE IF NOT EXISTS message(id TEXT PRIMARY KEY,session_id TEXT,time_created INTEGER,data TEXT);'

def make_db(path, root, sid='ses_a', parent=None, messages=()):
    path.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(path)
    c.executescript(SCHEMA)
    c.execute('INSERT OR REPLACE INTO session VALUES(?,?,?)', (sid, parent, str(root)))
    for m in messages:
        c.execute('INSERT OR REPLACE INTO message VALUES(?,?,?,?)', m)
    c.commit()
    c.close()

def msg_row(id='m1', sid='ses_a', created=20, total=115, completed=21, **kw):
    data = {'role': 'assistant', 'providerID': 'go', 'modelID': 'bunny',
            'time': {'completed': completed},
            'tokens': {'total': total, 'input': 10, 'output': 5, 'reasoning': 5,
                       'cache': {'read': 100, 'write': 0}}, 'cost': 0}
    data.update(kw)
    return (id, sid, created, json.dumps(data))

class MultiStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp.name) / 'proj'
        self.home = pathlib.Path(self.temp.name) / 'home'
        self.owned = self.root / DB_REL
        self.homedb = self.home / '.local/share/opencode/opencode.db'
        self.assign = [{'conversation_id': 'ses_a', 'tag': 'bunny', 'team_id': 'a05'}]

    def tearDown(self):
        self.temp.cleanup()

    def read(self, **kw):
        kw.setdefault('home_db', str(self.homedb))
        return read_usage(str(self.root), self.assign, 15, **kw)

    def test_single_store_parity(self):
        make_db(self.owned, self.root, messages=[msg_row()])
        r = self.read()
        self.assertEqual(r['status'], 'observed')
        self.assertEqual(r['unique_assistant_records'], 1)
        self.assertEqual(r['by_team']['a05']['total_tokens'], 115)
        roles = {s['role']: s['status'] for s in r['stores']}
        self.assertEqual(roles, {'owned': 'queried', 'home': 'missing-skipped'})

    def test_home_only_observed(self):
        make_db(self.homedb, self.root, messages=[msg_row(total=200)])
        r = self.read()
        self.assertEqual(r['status'], 'observed')
        self.assertEqual(r['by_team']['a05']['total_tokens'], 200)

    def test_cross_store_dedup_counts_once(self):
        make_db(self.owned, self.root, messages=[msg_row()])
        make_db(self.homedb, self.root, messages=[msg_row()])
        r = self.read()
        self.assertEqual(r['queried_assistant_records'], 2)
        self.assertEqual(r['unique_assistant_records'], 1)
        self.assertEqual(r['by_team']['a05']['total_tokens'], 115)
        self.assertEqual(len(r['sessions']), 1)

    def test_distinct_messages_sum(self):
        make_db(self.owned, self.root, messages=[msg_row('m1')])
        make_db(self.homedb, self.root, messages=[msg_row('m2')])
        r = self.read()
        self.assertEqual(r['unique_assistant_records'], 2)
        self.assertEqual(r['by_team']['a05']['total_tokens'], 230)

    def test_missing_owned_uses_home(self):
        make_db(self.homedb, self.root, messages=[msg_row()])
        r = self.read()
        self.assertEqual(r['status'], 'observed')
        self.assertFalse(self.owned.exists())
        roles = {s['role']: s['status'] for s in r['stores']}
        self.assertEqual(roles['owned'], 'missing-skipped')

    def test_both_missing_unknown(self):
        r = self.read()
        self.assertEqual(r['status'], 'unknown')
        self.assertFalse(self.owned.exists())
        self.assertFalse(self.homedb.exists())

    def test_read_only_wal_isolation(self):
        make_db(self.owned, self.root, messages=[msg_row()])
        make_db(self.homedb, self.root, messages=[msg_row('m2')])
        for p in (self.owned, self.homedb):
            c = sqlite3.connect(p)
            c.execute('PRAGMA journal_mode=WAL')
            c.execute("INSERT INTO message VALUES('probe', 'ses_a', 1, '{}')")
            c.commit()
            c.close()
            c = sqlite3.connect(p)
            c.execute("DELETE FROM message WHERE id='probe'")
            c.commit()
            c.close()
        # -shm/-wal bytes are transient shared memory; the durable content must not move.
        before_content = {}
        before_names = {}
        for p in (self.owned, self.homedb):
            c = sqlite3.connect(p.as_uri() + '?mode=ro', uri=True)
            before_content[p] = (c.execute('SELECT * FROM session ORDER BY id').fetchall(),
                                 c.execute('SELECT * FROM message ORDER BY id').fetchall())
            c.close()
            before_names[p] = sorted(q.name for q in p.parent.iterdir())
            before_db = p.read_bytes()
            r = self.read()
            self.assertEqual(r['status'], 'observed')
            c = sqlite3.connect(p.as_uri() + '?mode=ro', uri=True)
            self.assertEqual(before_content[p], (c.execute('SELECT * FROM session ORDER BY id').fetchall(),
                                                 c.execute('SELECT * FROM message ORDER BY id').fetchall()))
            c.close()
            self.assertEqual(before_db, p.read_bytes())
            self.assertEqual(before_names[p], sorted(q.name for q in p.parent.iterdir()))

    def test_no_prompt_text_leaks(self):
        make_db(self.owned, self.root, messages=[msg_row(prompt='SECRET-A')])
        make_db(self.homedb, self.root, messages=[msg_row('m2', prompt='SECRET-B')])
        self.assertNotIn('SECRET', json.dumps(self.read()))

    def test_home_outside_root_still_attributed_by_directory(self):
        make_db(self.homedb, self.root, messages=[msg_row()])
        c = sqlite3.connect(self.homedb)
        c.execute('INSERT INTO session VALUES(?,?,?)', ('ses_x', None, '/elsewhere'))
        c.execute('INSERT INTO message VALUES(?,?,?,?)', msg_row('mx', 'ses_x'))
        c.commit()
        c.close()
        r = self.read()
        self.assertEqual(r['unique_assistant_records'], 1)

    def test_foreign_sid_in_second_store_not_attributed(self):
        make_db(self.owned, self.root, messages=[msg_row()])
        make_db(self.homedb, '/elsewhere', messages=[msg_row('mX')])
        r = self.read()
        self.assertEqual(r['unique_assistant_records'], 1)
        self.assertEqual(r['by_team']['a05']['total_tokens'], 115)

    def test_parent_child_collision_across_stores(self):
        make_db(self.owned, self.root, messages=[msg_row()])
        make_db(self.homedb, self.root, sid='ses_c', parent='ses_a',
                messages=[msg_row('mc', 'ses_c')])
        r = self.read()
        self.assertEqual(r['unique_assistant_records'], 1)
        self.assertEqual(len(r['sessions']), 1)

    def test_pending_owned_vs_completed_home(self):
        make_db(self.owned, self.root, messages=[msg_row(total=None, completed=None)])
        make_db(self.homedb, self.root, messages=[msg_row()])
        r = self.read()['sessions'][0]['interval']
        self.assertEqual(r['total_tokens'], 115)
        self.assertEqual(r['pending_or_missing_records'], 0)

    def test_completed_owned_vs_pending_home(self):
        make_db(self.owned, self.root, messages=[msg_row()])
        make_db(self.homedb, self.root, messages=[msg_row(total=None, completed=None)])
        r = self.read()['sessions'][0]['interval']
        self.assertEqual(r['total_tokens'], 115)
        self.assertEqual(r['pending_or_missing_records'], 0)

    def test_conflicting_totals_reconcile_deterministically(self):
        make_db(self.owned, self.root, messages=[msg_row(created=20, total=100, completed=21)])
        make_db(self.homedb, self.root, messages=[msg_row(created=30, total=200, completed=31)])
        self.assertEqual(self.read()['by_team']['a05']['total_tokens'], 200)
        make_db(self.homedb, self.root, messages=[msg_row(created=20, total=200, completed=21)])
        self.assertEqual(self.read()['by_team']['a05']['total_tokens'], 200)
        make_db(self.homedb, self.root, messages=[msg_row(created=20, total=100, completed=21)])
        r = self.read()
        self.assertEqual(r['by_team']['a05']['total_tokens'], 100)
        self.assertEqual(r['unique_assistant_records'], 1)

    def test_global_bounds_preserved(self):
        make_db(self.owned, self.root, messages=[msg_row()])
        make_db(self.homedb, self.root, messages=[msg_row('m2')])
        self.assertEqual(self.read(max_messages=0)['status'], 'unavailable-or-bound-exceeded')
        self.assertEqual(self.read(max_sessions=0)['status'], 'unavailable-or-bound-exceeded')

if __name__ == '__main__':
    unittest.main()
