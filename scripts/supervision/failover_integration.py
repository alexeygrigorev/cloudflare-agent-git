import json
import time
import hashlib
from pathlib import Path

import sys
sys.path.insert(0, '/home/alexey/git/agent-coordination-role-failover')

try:
    from coordination.role_failover import RoleAuthority
    from coordination.failover_bridge import FailoverBridge
except ImportError:
    pass

class SupervisorBusAdapter:
    def __init__(self, binary, spool, supports_key, sender_id, command_fn, recorded_send_fn):
        self.binary = binary
        self.spool = spool
        self.supports_key = supports_key
        self.sender_id = sender_id
        self.command = command_fn
        self.recorded_send = recorded_send_fn

    def send(self, *, sender_id, token, recipient_id, body, data=None, idempotency_key=None, kind="note", reply_to=None):
        key = idempotency_key.replace("/", "_").replace(":", "_") if idempotency_key else f"anon-{time.time()}"
        
        # We can just use recorded_send to send the message
        # We may need to pass data and kind, but recorded_send doesn't support them natively unless we modify it or call command directly
        intentpath = self.spool / f'intent-{key}.json'
        receiptpath = self.spool / f'receipt-{key}.json'
        
        if receiptpath.exists():
            res = json.loads(receiptpath.read_text())
            msg = res.get('message', res)
            class Msg: pass
            m = Msg()
            m.message_id = msg.get('id')
            return m
            
        def atomic(path, value):
            tmp = path.with_suffix(path.suffix + '.tmp')
            tmp.write_text(json.dumps(value, indent=2))
            tmp.replace(path)
            
        def now():
            from datetime import datetime, timezone
            return datetime.now(timezone.utc).isoformat()
            
        atomic(intentpath, {'sender_id':self.sender_id, 'to':recipient_id, 'event_key':key, 'created_at':now(), 'state':'send-may-have-started'})
        
        args = [self.binary, 'message', 'send', '--to', recipient_id, '--json']
        if self.supports_key:
            args += ['--idempotency-key', key]
        if kind:
            args += ['--kind', kind]
        if data:
            args += ['--data', json.dumps(data)]
            
        try:
            receipt = json.loads(self.command(args + [body]))
        except Exception as e:
            # Re-raise so FailoverBridge handles it
            raise e
            
        atomic(receiptpath, receipt)
        msg = receipt.get('message', receipt)
        class Msg: pass
        m = Msg()
        m.message_id = msg.get('id')
        return m

def get_failover_launcher_queue(spool):
    def failover_launcher_queue(key, task):
        from datetime import datetime, timezone
        import subprocess
        payload = task['payload']
        tid = task['id']
        
        # Submit to agent-quota-launcher
        launcher_cwd = '/home/alexey/git/agent-quota-launcher'
        args = [
            'python3', '-m', 'launcher.cli', 'submit',
            '--id', tid,
            '--key', key,
            '--payload', json.dumps(payload)
        ]
        res = subprocess.run(args, cwd=launcher_cwd, capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"Launcher submit failed: {res.stderr}")
            
        record = {
            "task_id": tid,
            "head_owner": payload.get('owner', 'unknown-owner'),
            "project_id": payload.get('project_id', payload.get('role_context',{}).get('project', 'unknown')),
            "idempotency_key": key,
            "status": "enqueued",
            "enqueued_at": datetime.now(timezone.utc).isoformat(),
            "payload": payload,
            "launcher_submitted": True,
            "receipt": res.stdout.strip()
        }
        enqueued_dir = spool / 'enqueued'
        enqueued_dir.mkdir(parents=True, exist_ok=True)
        path = enqueued_dir / f"{tid}.json"
        
        tmp = path.with_suffix('.tmp')
        tmp.write_text(json.dumps(record, indent=2))
        tmp.replace(path)
        
        return {'state': 'queued', 'task_id': tid, 'receipt': res.stdout.strip()}
    return failover_launcher_queue

def run_failover_tick(spool, binary, supports_key, identity_id, command_fn, recorded_send_fn, registry, sessions):
    authority = RoleAuthority(spool / "role_authority.db")
    adapter = SupervisorBusAdapter(binary, spool, supports_key, identity_id, command_fn, recorded_send_fn)
    
    # Extract projects and roles
    projects = set()
    roles_by_project = {}
    recipients = {}
    
    for agent in registry.get('agents', []):
        proj = agent.get('project_id')
        role = agent.get('role')
        tag = agent.get('tag')
        if proj and role and tag:
            projects.add(proj)
            if proj not in roles_by_project:
                roles_by_project[proj] = {}
            if role not in roles_by_project[proj]:
                roles_by_project[proj][role] = []
            roles_by_project[proj][role].append(tag)
            recipients[tag] = tag  # tag is the recipient ID
            
    recipients[identity_id] = identity_id
    
    for proj, roles in roles_by_project.items():
        for role, candidates in roles.items():
            if role in ('principal', 'head', 'project_head', 'coordinator'):
                authority.configure(proj, role, candidates)
                
    # Observe sessions
    for session in sessions:
        tag = session.get('tag')
        if not tag: continue
        sid = session.get('id')
        state = session.get('reported_state')
        ready = state in ('idle', 'waiting', None)
        # We don't have draft or quota info here easily, assume defaults
        authority.observe(actor=tag, host='local', generation=sid, ready=ready, draft=False, quota_ok=True)

    bridge = FailoverBridge(
        authority=authority,
        bus=adapter,
        sender_id=identity_id,
        token="supervisor-token",
        recipients=recipients,
        launcher_queue=get_failover_launcher_queue(spool)
    )
    
    for proj, roles in roles_by_project.items():
        for role in roles:
            if role in ('principal', 'head', 'project_head', 'coordinator'):
                bridge.tick(proj, role)

