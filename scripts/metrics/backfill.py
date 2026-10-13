#!/usr/bin/env python3
"""One-time backfill: read existing snapshot archives into VictoriaMetrics.

Reads every snapshots-*.jsonl(.gz) row in STORE and STORE/archive (read-only;
archives are never modified) and pushes the same numeric series the live
collector emits, stamped with each row's own observation time. Run once after
the collector stops writing snapshots; reruns skip files recorded in
backfill-state.json with matching size+mtime.

Usage:
    python3 scripts/metrics/backfill.py [--store PATH] [--vm-url URL]
        [--batch-snapshots N] [--dry-run]
"""
import argparse
import datetime
import gzip
import json
import os
import pathlib
import sys
import time

METRICS_DIR = pathlib.Path(__file__).resolve().parent
if str(METRICS_DIR) not in sys.path:
    sys.path.insert(0, str(METRICS_DIR))

import tsdb

ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_STORE = ROOT / '.local/metrics'
STATE_FILENAME = 'backfill-state.json'


def iter_snapshot_files(store):
    store = pathlib.Path(store)
    candidates = list(store.glob('snapshots-*')) + list((store / 'archive').glob('snapshots-*'))
    files = [p for p in candidates if p.is_file() and 'manifest' not in p.name
             and not p.name.startswith('.') and not p.name.endswith(('.tmp', '.pending', '.lock'))]
    return sorted(files, key=lambda p: (p.name[:20], p.stat().st_mtime))


def open_lines(path):
    if path.suffix == '.gz':
        return gzip.open(path, 'rt', encoding='utf-8', errors='replace')
    return path.open('r', encoding='utf-8', errors='replace')


def parse_ts_ms(row):
    try:
        return int(datetime.datetime.fromisoformat(
            str(row['at']).replace('Z', '+00:00')).timestamp() * 1000)
    except (KeyError, ValueError, TypeError):
        return None


def load_state(store):
    try:
        data = json.loads((pathlib.Path(store) / STATE_FILENAME).read_text())
        return data.get('files', {}) if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_state(store, files):
    path = pathlib.Path(store) / STATE_FILENAME
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps({'files': files, 'updated_at': time.time()}))
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    tmp.replace(path)


def backfill(store=DEFAULT_STORE, vm_url=tsdb.VM_URL, batch_snapshots=20,
             dry_run=False, progress=None):
    store = pathlib.Path(store)
    done = load_state(store)
    files = iter_snapshot_files(store)
    stats = {'files_total': len(files), 'files_skipped': 0, 'files_imported': 0,
             'snapshots': 0, 'series': 0, 'errors': []}

    pending_lines = []
    pending_files = []

    def flush(record_files):
        if dry_run or not pending_lines:
            return True
        ok, err = '', ''
        for attempt in range(3):
            ok, err = tsdb.push_series(pending_lines, vm_url, timeout=60)
            if ok:
                break
            time.sleep(2 * (attempt + 1))
        if not ok:
            stats['errors'].append('push failed after 3 attempts: %s' % err)
            return False
        stats['series'] += len(pending_lines)
        if record_files:
            for entry in pending_files:
                done[entry['name']] = {'bytes': entry['bytes'], 'mtime_ns': entry['mtime_ns']}
                stats['files_imported'] += 1
            save_state(store, done)
            if progress:
                progress(stats)
        return True

    for path in files:
        try:
            st = path.stat()
        except OSError as exc:
            stats['errors'].append('%s: %s' % (path.name, exc))
            continue
        record = done.get(path.name)
        if record and record.get('bytes') == st.st_size and record.get('mtime_ns') == st.st_mtime_ns:
            stats['files_skipped'] += 1
            continue
        try:
            handle = open_lines(path)
        except OSError as exc:
            stats['errors'].append('%s: %s' % (path.name, exc))
            continue
        with handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                ts_ms = parse_ts_ms(row)
                if ts_ms is None or not isinstance(row, dict):
                    continue
                pending_lines.extend(tsdb.build_series(row, ts_ms))
                stats['snapshots'] += 1
                if len(pending_lines) >= batch_snapshots * 400 and not dry_run:
                    # Mid-file flush: lines are pushed but the file is only
                    # recorded complete at its boundary, so a crash reruns it.
                    if not flush(record_files=False):
                        return stats
                    pending_lines = []
        # File boundary: flush so state attribution stays exact per file.
        if pending_lines and not dry_run:
            pending_files.append({'name': path.name, 'bytes': st.st_size, 'mtime_ns': st.st_mtime_ns})
            if not flush(record_files=True):
                return stats
            pending_lines = []
            pending_files = []
        elif dry_run:
            stats['files_imported'] += 1
    if pending_lines and not dry_run:
        flush(record_files=True)
    return stats


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--store', default=str(DEFAULT_STORE))
    parser.add_argument('--vm-url', default=tsdb.VM_URL)
    parser.add_argument('--batch-snapshots', type=int, default=20)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args(argv)

    def show(stats):
        print('  ... %d files imported, %d snapshots, %d series' % (
            stats['files_imported'], stats['snapshots'], stats['series']), flush=True)

    stats = backfill(store=args.store, vm_url=args.vm_url,
                     batch_snapshots=args.batch_snapshots,
                     dry_run=args.dry_run, progress=None if args.dry_run else show)
    print(json.dumps(stats, indent=2))
    return 1 if stats['errors'] else 0


if __name__ == '__main__':
    sys.exit(main())
