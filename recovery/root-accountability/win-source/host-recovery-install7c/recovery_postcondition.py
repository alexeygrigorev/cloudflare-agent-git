"""Same-lock postrestart reconciliation of one already challenged nonce."""
import hashlib,json,re,sqlite3
TABLES=('roles','agents','candidates','activation_receipts','activations')
def capture_connection(db):
    out={}
    for name in TABLES:
        if db.execute('SELECT 1 FROM sqlite_master WHERE type=? AND name=?',('table',name)).fetchone():
            cur=db.execute('SELECT * FROM '+name)
            out[name]={'columns':[d[0] for d in cur.description],'rows':sorted([list(r) for r in cur.fetchall()],key=repr)}
    return out
def capture(path):
    with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as db:
        db.execute('BEGIN');return capture_connection(db)
def selected_attempt(db,guard):
    if not isinstance(guard,dict) or set(guard)!={'nonce','baseline_json_sha256','owner'}:raise RuntimeError('unknown pending guard')
    owner=guard['owner']
    if not isinstance(owner,dict) or set(owner)!={'project','role','actor','generation','epoch'} or type(owner['epoch']) is not int or owner['epoch']<1 or any(not isinstance(owner[k],str) or not owner[k] for k in ('project','role','actor','generation')):raise RuntimeError('unknown owner guard')
    if not isinstance(guard['nonce'],str) or not guard['nonce'] or not isinstance(guard['baseline_json_sha256'],str) or not re.fullmatch('[0-9a-f]{64}',guard['baseline_json_sha256']):raise RuntimeError('unknown nonce guard')
    db.row_factory=sqlite3.Row
    row=db.execute('SELECT * FROM host_recovery_attempts WHERE nonce=?',(guard['nonce'],)).fetchone()
    if not row or hashlib.sha256(row['baseline_json'].encode()).hexdigest()!=guard['baseline_json_sha256']:
        raise RuntimeError('fixed pending recovery baseline changed')
    baseline=json.loads(row['baseline_json'])
    if any(baseline.get(k)!=v for k,v in guard['owner'].items()):raise RuntimeError('fixed recovery owner changed')
    return dict(row)
def preserved_or_drain(path,before,guard):
    with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as db:
        db.execute('BEGIN');after=capture_connection(db);attempt=selected_attempt(db,guard)
    owner=guard['owner'];columns=before['roles']['columns']
    rows=[dict(zip(columns,r)) for r in before['roles']['rows']]
    own=[r for r in rows if (r['project'],r['role'])==(owner['project'],owner['role'])]
    if len(own)!=1 or (own[0]['holder'],own[0]['generation'],own[0]['epoch'])!=(owner['actor'],owner['generation'],owner['epoch']):raise RuntimeError('before role owner changed')
    if after==before:
        if attempt['phase']!='challenged':raise RuntimeError('attempt advanced without exact role CAS')
        return 'unchanged'
    if set(after)!=set(before) or any(after[n]!=before[n] for n in before if n!='roles'):
        raise RuntimeError('unrelated admission/candidate/activation state changed')
    if after['roles']['columns']!=before['roles']['columns']:raise RuntimeError('role schema changed')
    columns=before['roles']['columns'];expected=[];matched=0;owner=guard['owner']
    for row in before['roles']['rows']:
        value=dict(zip(columns,row))
        if (value['project'],value['role'])==(owner['project'],owner['role']):
            if (value['holder'],value['generation'],value['epoch'])!=(owner['actor'],owner['generation'],owner['epoch']):raise RuntimeError('before role owner changed')
            matched+=1;value.update(holder=None,generation=None,epoch=owner['epoch']+1,expires=0,activation_due=0,suspect_since=None)
        expected.append([value[c] for c in columns])
    if matched!=1 or after['roles']['rows']!=sorted(expected,key=repr):raise RuntimeError('unexpected role transition')
    if attempt['phase'] not in ('drained','factory-pending','factory-receipted','enrollment-pending'):
        raise RuntimeError('fixed recovery phase does not prove authorized drain')
    reference=attempt.get('drain_receipt_ref')
    if not isinstance(reference,str) or re.fullmatch('[0-9a-f]{64}',reference) is None or attempt.get('kernel_proof_ref')!=reference:
        raise RuntimeError('authenticated native drain receipt missing')
    return 'expected-recovery-drain'
