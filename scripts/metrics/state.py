#!/usr/bin/env python3
"""Change-only SQLite store for task/evidence details.

Numeric time series go to VictoriaMetrics every minute; this database keeps
only the slow-moving detail rows (task contracts, evidence file metadata,
task status transitions) and writes a row only when its content actually
changes. An unchanged sample performs zero writes.

Readers must open read-only (see open_readonly). The collector is the sole
writer and already serializes samples with its sample.lock.
"""
import hashlib
import json
import os
import pathlib
import sqlite3

FILENAME = 'state.sqlite'

SCHEMA = '''
CREATE TABLE IF NOT EXISTS tasks (
  task_id TEXT PRIMARY KEY,
  status TEXT,
  owner_tag TEXT,
  team_id TEXT,
  updated_at TEXT,
  acceptance_status TEXT,
  reviewer_tag TEXT,
  evidence_paths_json TEXT,
  next_action TEXT,
  detail_hash TEXT NOT NULL,
  first_seen TEXT NOT NULL,
  last_change TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS evidence (
  path TEXT PRIMARY KEY,
  bytes INTEGER,
  mtime REAL,
  task_id TEXT,
  first_seen TEXT NOT NULL,
  last_change TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS transitions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  at TEXT NOT NULL,
  task_id TEXT NOT NULL,
  from_status TEXT,
  to_status TEXT,
  UNIQUE (at, task_id, from_status, to_status)
);
CREATE TABLE IF NOT EXISTS meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
'''

TASK_DETAIL_KEYS = (
    'status', 'owner_tag', 'team_id', 'updated_at', 'acceptance_status',
    'reviewer_tag', 'evidence_paths', 'next_action',
)


def _connect(path, read_only=False):
    path = str(path)
    if read_only:
        uri = 'file:%s?mode=ro' % pathlib.Path(path).as_posix().replace('?', '%3F')
        connection = sqlite3.connect(uri, uri=True, timeout=2)
        connection.execute("PRAGMA query_only = ON")
        return connection
    parent = pathlib.Path(path).parent
    parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=30)
    connection.execute('PRAGMA journal_mode = WAL')
    connection.execute('PRAGMA synchronous = NORMAL')
    connection.executescript(SCHEMA)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return connection


def open_readonly(path):
    return _connect(path, read_only=True)


def _detail_hash(detail):
    canonical = json.dumps(detail, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def record_sample(store_path, snap, at):
    """Upsert changed task/evidence rows, append new transitions.

    Returns {'tasks_changed': int, 'evidence_changed': int,
             'transitions_added': int}.
    """
    db_path = pathlib.Path(store_path) / FILENAME if pathlib.Path(store_path).is_dir() or not str(store_path).endswith('.sqlite') else pathlib.Path(store_path)
    connection = _connect(db_path)
    try:
        return _record_sample(connection, snap if isinstance(snap, dict) else {}, at)
    finally:
        connection.commit()
        connection.close()


def _record_sample(connection, snap, at):
    tasks_changed = 0
    evidence_changed = 0

    tasks = snap.get('tasks', [])
    if not isinstance(tasks, list):
        tasks = []
    current_paths_by_task = {}
    for task in tasks:
        if not isinstance(task, dict) or not task.get('id'):
            continue
        task_id = str(task['id'])
        detail = {key: task.get(key) for key in TASK_DETAIL_KEYS}
        digest = _detail_hash(detail)
        row = connection.execute(
            'SELECT detail_hash FROM tasks WHERE task_id = ?', (task_id,)).fetchone()
        if row is None:
            connection.execute(
                'INSERT INTO tasks (task_id, status, owner_tag, team_id, updated_at,'
                ' acceptance_status, reviewer_tag, evidence_paths_json, next_action,'
                ' detail_hash, first_seen, last_change)'
                ' VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (task_id, detail['status'], detail['owner_tag'], detail['team_id'],
                 detail['updated_at'], detail['acceptance_status'], detail['reviewer_tag'],
                 json.dumps(detail['evidence_paths'], default=str), detail['next_action'],
                 digest, at, at))
            tasks_changed += 1
        elif row[0] != digest:
            connection.execute(
                'UPDATE tasks SET status = ?, owner_tag = ?, team_id = ?, updated_at = ?,'
                ' acceptance_status = ?, reviewer_tag = ?, evidence_paths_json = ?,'
                ' next_action = ?, detail_hash = ?, last_change = ? WHERE task_id = ?',
                (detail['status'], detail['owner_tag'], detail['team_id'],
                 detail['updated_at'], detail['acceptance_status'], detail['reviewer_tag'],
                 json.dumps(detail['evidence_paths'], default=str), detail['next_action'],
                 digest, at, task_id))
            tasks_changed += 1
        current_paths_by_task[task_id] = {
            str(p) for p in (detail['evidence_paths'] or []) if isinstance(p, str) and p}

    sessions = snap.get('sessions', [])
    if not isinstance(sessions, list):
        sessions = []
    current_evidence = {}
    for session in sessions:
        if not isinstance(session, dict):
            continue
        owned = {str(t.get('id')) for t in (session.get('tasks') or []) if isinstance(t, dict) and t.get('id')}
        owner = next(iter(owned), None)
        for item in session.get('evidence') or []:
            if not isinstance(item, dict) or not item.get('path'):
                continue
            current_evidence[str(item['path'])] = (item.get('bytes'), item.get('mtime'), owner)
    for path, (size, mtime, owner) in current_evidence.items():
        row = connection.execute(
            'SELECT bytes, mtime FROM evidence WHERE path = ?', (path,)).fetchone()
        if row is None:
            connection.execute(
                'INSERT INTO evidence (path, bytes, mtime, task_id, first_seen, last_change)'
                ' VALUES (?, ?, ?, ?, ?, ?)', (path, size, mtime, owner, at, at))
            evidence_changed += 1
        elif (row[0], row[1]) != (size, mtime):
            connection.execute(
                'UPDATE evidence SET bytes = ?, mtime = ?, task_id = ?, last_change = ?'
                ' WHERE path = ?', (size, mtime, owner, at, path))
            evidence_changed += 1

    # Deletion is a change too: drop stored evidence rows whose owning task is
    # in this sample but no longer lists the path.
    for task_id, current_paths in current_paths_by_task.items():
        stored = connection.execute(
            'SELECT path FROM evidence WHERE task_id = ?', (task_id,)).fetchall()
        for (stored_path,) in stored:
            if stored_path not in current_paths and stored_path not in current_evidence:
                connection.execute('DELETE FROM evidence WHERE path = ?', (stored_path,))
                evidence_changed += 1

    observation = snap.get('observation', {})
    events = observation.get('task_transitions_this_sample', []) if isinstance(observation, dict) else []
    transitions_added = 0
    for event in events or []:
        if not isinstance(event, dict) or not event.get('task_id'):
            continue
        cursor = connection.execute(
            'INSERT OR IGNORE INTO transitions (at, task_id, from_status, to_status)'
            ' VALUES (?, ?, ?, ?)',
            (event.get('at') or at, str(event['task_id']),
             event.get('from_status'), event.get('to_status')))
        transitions_added += cursor.rowcount

    connection.execute(
        'INSERT INTO meta (key, value) VALUES (?, ?)'
        ' ON CONFLICT (key) DO UPDATE SET value = excluded.value',
        ('last_sample_at', at))
    return {'tasks_changed': tasks_changed, 'evidence_changed': evidence_changed,
            'transitions_added': transitions_added}


def read_tasks(path, task_id=None):
    db_path = pathlib.Path(path) / FILENAME if pathlib.Path(path).is_dir() or not str(path).endswith('.sqlite') else pathlib.Path(path)
    if not db_path.is_file():
        return []
    connection = open_readonly(db_path)
    try:
        if task_id is not None:
            rows = connection.execute(
                'SELECT task_id, status, owner_tag, team_id, updated_at, acceptance_status,'
                ' reviewer_tag, evidence_paths_json, next_action, first_seen, last_change'
                ' FROM tasks WHERE task_id = ?', (str(task_id),)).fetchall()
        else:
            rows = connection.execute(
                'SELECT task_id, status, owner_tag, team_id, updated_at, acceptance_status,'
                ' reviewer_tag, evidence_paths_json, next_action, first_seen, last_change'
                ' FROM tasks').fetchall()
        result = []
        for row in rows:
            result.append({
                'id': row[0], 'status': row[1], 'owner_tag': row[2], 'team_id': row[3],
                'updated_at': row[4], 'acceptance_status': row[5], 'reviewer_tag': row[6],
                'evidence_paths': json.loads(row[7]) if row[7] else [],
                'next_action': row[8], 'first_seen': row[9], 'last_change': row[10],
            })
        return result
    finally:
        connection.close()


def read_evidence(path):
    db_path = pathlib.Path(path) / FILENAME if pathlib.Path(path).is_dir() or not str(path).endswith('.sqlite') else pathlib.Path(path)
    if not db_path.is_file():
        return []
    connection = open_readonly(db_path)
    try:
        rows = connection.execute(
            'SELECT path, bytes, mtime, task_id, first_seen, last_change FROM evidence').fetchall()
        return [{'path': r[0], 'bytes': r[1], 'mtime': r[2], 'task_id': r[3],
                 'first_seen': r[4], 'last_change': r[5]} for r in rows]
    finally:
        connection.close()


def read_transitions(path, since=None):
    db_path = pathlib.Path(path) / FILENAME if pathlib.Path(path).is_dir() or not str(path).endswith('.sqlite') else pathlib.Path(path)
    if not db_path.is_file():
        return []
    connection = open_readonly(db_path)
    try:
        if since is not None:
            rows = connection.execute(
                'SELECT at, task_id, from_status, to_status FROM transitions'
                ' WHERE at >= ? ORDER BY at', (since,)).fetchall()
        else:
            rows = connection.execute(
                'SELECT at, task_id, from_status, to_status FROM transitions'
                ' ORDER BY at').fetchall()
        return [{'at': r[0], 'task_id': r[1], 'from_status': r[2], 'to_status': r[3]} for r in rows]
    finally:
        connection.close()
