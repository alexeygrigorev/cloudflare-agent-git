"""Fixed provisioner-pinned sanitized report; freshness is facts, not receipt age."""
import os,stat,json,hashlib,datetime,math
from operational_receiver import CheckFenced,owner_values,text

KINDS={'native-principal-report','native-head-report','head-verified-snapshot','operator-audit'}
STATES={'unknown','pending-owner-ack','action-observed','accepted-outcome','blocked','held','finished'}

def stamp(value):
    if not isinstance(value,str):raise CheckFenced('source event time required')
    try:date=datetime.datetime.fromisoformat(value.replace('Z','+00:00'))
    except ValueError:raise CheckFenced('source event time invalid')
    if date.tzinfo is None:raise CheckFenced('source time must be aware')
    return date.timestamp()

def fixed_snapshot(plan, owner, now):
    owner_values(owner)
    if not isinstance(plan,dict) or set(plan)!={'path','sha256'}:raise CheckFenced('installed fixed snapshot pin required')
    fd=os.open(plan['path'],os.O_RDONLY|getattr(os,'O_NOFOLLOW',0))
    try:
        metadata=os.fstat(fd)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid!=os.getuid() or metadata.st_mode&0o077:raise CheckFenced('private snapshot custody required')
        with os.fdopen(fd,'rb',closefd=False) as stream:raw=stream.read(65537)
        if len(raw)>65536 or hashlib.sha256(raw).hexdigest()!=plan['sha256']:raise CheckFenced('fixed bounded source snapshot changed')
    finally:os.close(fd)
    source=json.loads(raw)
    allowed={'source_kind','source_event_at','source_receipt_sha256','native_message_id','native_sender','facts'}
    if not isinstance(source,dict) or set(source)-allowed or not allowed-{'native_message_id','native_sender'}<=set(source):raise CheckFenced('sanitized fixed report schema required')
    kind=source['source_kind'];native=kind in {'native-principal-report','native-head-report'}
    if kind not in KINDS:raise CheckFenced('truthful source attribution required')
    if native:raise CheckFenced('direct native report resolver not installed; pinned snapshot is not native authentication')
    when=stamp(source['source_event_at'])
    if type(now) not in (int,float) or not math.isfinite(now) or when>now+1:raise CheckFenced('future report time denied')
    sha=source['source_receipt_sha256']
    if not isinstance(sha,str) or len(sha)!=64 or any(c not in '0123456789abcdef' for c in sha):raise CheckFenced('source receipt digest required')
    if native:
        text(source.get('native_message_id'));text(source.get('native_sender'))
    elif 'native_message_id' in source or 'native_sender' in source:raise CheckFenced('snapshot cannot impersonate native sender')
    facts=source['facts']
    if not isinstance(facts,list) or len(facts)>32:raise CheckFenced('bounded structured facts required')
    for fact in facts:
        if not isinstance(fact,dict) or set(fact)!={'topic','state','evidence_ref','owner','next_action','checkpoint'} or fact['state'] not in STATES:raise CheckFenced('bounded outcome fact required')
        for field in ('topic','owner','next_action','checkpoint'):text(fact[field])
        if fact['state']=='accepted-outcome':text(fact['evidence_ref'])
        elif fact['evidence_ref'] is not None:text(fact['evidence_ref'])
    # Keep stale source age visible. A fresh read does not refresh old facts.
    return dict(source,recipient_owner=owner,received_at=datetime.datetime.fromtimestamp(now,datetime.timezone.utc).isoformat(),principal_authored=native and kind=='native-principal-report',current_source_fresh=now-when<=120)
