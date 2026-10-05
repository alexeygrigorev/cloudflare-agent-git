#!/usr/bin/env python3
"""One bounded native Codex task; invoked by existing daily automation, not a scheduler."""
import argparse, datetime, fcntl, json, os, pathlib, shutil, signal, subprocess, time

ROOT = pathlib.Path(__file__).resolve().parents[4]
p = argparse.ArgumentParser()
p.add_argument('date', type=datetime.date.fromisoformat)
p.add_argument('mode', choices=['prepare', 'validate'])
p.add_argument('--check', action='store_true', help='admission only; never launch')
p.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
a = p.parse_args()
day = a.date.isoformat()
tag = f'daily-journal-codex-{day}-{a.mode}'
private = ROOT / '.local/journal/remote-preparation' / day / a.mode

def size():
    return sum(x.stat().st_size for x in private.rglob('*') if x.is_file() and not x.is_symlink())

def admission():
    mem = int(next(x.split()[1] for x in pathlib.Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:'))) * 1024
    free = shutil.disk_usage(ROOT).free
    if mem < 10 * 1024**3 or free < 50_000_000_000:
        raise SystemExit('resource hold: need 10GiB MemAvailable and 50GB task-mount free')
    if private.exists() and size() >= 512 * 1024**2:
        raise SystemExit('storage hold: task directory reached 512MiB')
    subprocess.run(['python3', str(ROOT/'scripts/quota-gate.py')], check=True, timeout=60, cwd=ROOT)
    print(json.dumps({'task': f'daily-journal:{day}:{a.mode}', 'MemAvailable': mem, 'mount_free': free}), flush=True)

admission()
if a.check:
    raise SystemExit(0)
private.mkdir(parents=True, exist_ok=True, mode=0o700)
(private/'tmp').mkdir(exist_ok=True, mode=0o700)
if not a.worker:
    # Exact native tag is the second dedup fence. Never --fresh or restart a session.
    with (private/'dispatch.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if (private/'launch.json').exists() or (private/'receipt.json').exists():
            print('already dispatched: inspect retained launch/receipt; no duplicate launch')
            raise SystemExit(0)
        cmd = ['a','start','--workspace',str(ROOT),'--cwd',str(ROOT),'--tag',tag,
               '--engine','shell','--memory','1500M','--pids','256','--json','--',
               'python3',str(pathlib.Path(__file__).resolve()),day,a.mode,'--worker']
        result = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=60)
        if result.returncode:
            print(result.stderr, end=''); raise SystemExit(result.returncode)
        record = json.loads(result.stdout)
        (private/'launch.json').write_text(json.dumps(record, indent=2)+'\n')
        print(json.dumps(record)); raise SystemExit(0)

# Hold the execution fence for the complete model lifetime, including internal retries.
worker_lock = (private/'worker.lock').open('a')
fcntl.flock(worker_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
if (private/'receipt.json').exists():
    raise SystemExit('terminal receipt exists; preserve it and ask the head for recovery')
identity = json.loads(subprocess.check_output(['a','whoami','--json'], cwd=ROOT, text=True, timeout=15))
assert identity['tag'] == tag and identity['workspace'] == str(ROOT), 'wrong native binding'
assert 0 < identity.get('limits', {}).get('memory_bytes', 0) <= 1500 * 1024**2, 'missing/oversized cgroup cap'
(private/'identity.json').write_text(json.dumps(identity, indent=2)+'\n')
readonly = 'Read-only validation: no article/assets edits, writer/image generation or --publish.' if a.mode == 'validate' else 'Prepare only genuinely needed new dated content; reuse a good published article and retained assets.'
prompt = f'''Use .agents/skills/prepare-daily-journal/SKILL.md in {ROOT}. Task daily-journal:{day}:{a.mode}. {readonly} Date {day} Europe/Berlin. Write progress incrementally to {private}/progress.md and final actionable receipt to {private}/receipt.md. Obtain genuine publication-head ACK and register real native identity/task. Preserve protected Claude draft. Coordinate dedicated genuine Opus prose and independent reviews; desktop commands/watches only. No new scheduler. On capacity failure preserve partial work and report failure. Send genuine completion with next owner/action to desktop-orchestrator/public-journal-site/codex-principal.'''
(private/'prompt.txt').write_text(prompt+'\n')
env = dict(os.environ, TMPDIR=str(private/'tmp'))
start = time.monotonic()
reason = 'completed'
with (private/'events.jsonl').open('w') as out, (private/'stderr.log').open('w') as err:
    proc = subprocess.Popen([str(ROOT/'scripts/launch-codex.sh'),'exec',
        '--dangerously-bypass-approvals-and-sandbox','--json','-o',str(private/'final.md'),prompt],
        cwd=ROOT, env=env, stdout=out, stderr=err, start_new_session=True)
    while proc.poll() is None:
        if time.monotonic()-start >= 3600 or size() >= 500*1024**2:
            reason = 'timeout' if time.monotonic()-start >= 3600 else 'storage_limit'
            os.killpg(proc.pid, signal.SIGTERM)
            try: proc.wait(timeout=10)
            except subprocess.TimeoutExpired: os.killpg(proc.pid, signal.SIGKILL); proc.wait()
            break
        time.sleep(2)
(private/'receipt.json').write_text(json.dumps({'task':f'daily-journal:{day}:{a.mode}',
    'session_id':identity['id'],'returncode':proc.returncode,'reason':reason,
    'seconds':round(time.monotonic()-start,2),'private_bytes':size(),
    'completed_at':datetime.datetime.now(datetime.timezone.utc).isoformat()},indent=2)+'\n')
raise SystemExit(proc.returncode if reason == 'completed' else 124)
