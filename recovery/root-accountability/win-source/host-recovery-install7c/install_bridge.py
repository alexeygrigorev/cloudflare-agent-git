"""Fixed one-service bridge adoption. Concrete reviewed authorization is absent."""
import sys
if not sys.flags.isolated or not sys.flags.no_site:raise SystemExit('requires -I -S')
import pathlib,hashlib,json,os,stat,sqlite3,subprocess,fcntl,tempfile,re
ROOT=pathlib.Path('/home/alexey/git/cloudflare-agent-git')
HERE=ROOT/'.local/win35-root-bootstrap/host-recovery-install7c'
SOURCE=ROOT/'.local/root-outage-analysis/host-operator-drain'
CANDIDATES=ROOT/'.local/root-outage-analysis/host-operator-drain-plan'
AUTH=ROOT/'.local/win35-root-authority'
PLAN_PIN='3102807b8cc175d6e91bbc9dffb953dd18133bec13a80d05762cbf0b6bebff15'
PROFILE_BEFORE='4425e63ad6e42159b74cc2f60a3188be4ca68d5426c0d3f4e28d93e5d14c79de'
PROFILE_AFTER='3d42fa5b88f6b72a49eaaaab24cfddeaed7f99f1b5bd968bd69d668c48c013b9'
HOST_PLAN_PIN='620c0b3e434e900f262efd4bade6529a7b316228ac3bff17967089439ee4384f'
CORE=pathlib.Path('/home/alexey/git/agent-coordination/coordination/role_failover.py')
CORE_PIN='577a9516357b791e48c3f4ce1a8ba0e6870a29df4bcbbe90463113b30a44904f'
TARGETS=(('host_recovery_adapter.py','624c3cdbfed8e58f69b7461143a9513086e40c1739eca5b15e5109a9a4f76ec6','b4f097aa353462d4cab598b7ad338f70e38960972b5969447bd3078163a3d67b'),)
UNIT='win35-role-authority.service'

def sha_bytes(data):return hashlib.sha256(data).hexdigest()
def regular(p,private=False):
    for node in (p,*p.parents):
        if node.is_symlink():raise RuntimeError('symlink path held')
    s=p.stat()
    if not stat.S_ISREG(s.st_mode) or s.st_uid!=os.getuid() or s.st_mode&0o002:raise RuntimeError('source custody held')
    if private and s.st_mode&0o077:raise RuntimeError('private file permissions held')
    return p
def digest(p):
    if any(node.is_symlink() for node in (p,*p.parents)):raise RuntimeError('symlink target held')
    return sha_bytes(regular(p).read_bytes()) if p.exists() else None
def load(p):return json.loads(regular(p,True).read_text())
def atomic(p,data):
    if not p.parent.is_dir() or p.parent.is_symlink():raise RuntimeError('fixed directory required')
    fd,name=tempfile.mkstemp(prefix='.bridge-pending-',dir=p.parent)
    try:
        os.fchmod(fd,0o600)
        with os.fdopen(fd,'wb') as out:out.write(data);out.flush();os.fsync(out.fileno())
        os.replace(name,p)
        fd=os.open(p.parent,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(fd)
        finally:os.close(fd)
    finally:
        if os.path.exists(name):os.unlink(name)
def save(p,v):atomic(p,json.dumps(v,sort_keys=True).encode())
def phase(previous,current,before,after):
    if previous is None:
        if current!=before:raise RuntimeError('unowned after-state held')
        return 'write'
    if not isinstance(previous,dict) or set(previous)!={'phase','before','after'} or previous['phase'] not in ('write-pending','completed') or previous['before']!=before or previous['after']!=after:
        raise RuntimeError('unknown write journal held')
    if previous['phase']=='completed':
        if current!=after:raise RuntimeError('completed conflict held')
        return 'done'
    if current==after:return 'done'
    if current==before:return 'write'
    raise RuntimeError('foreign target held')
def commit_target(target,data,before,after,journal):
    if sha_bytes(data)!=after:raise RuntimeError('candidate hash mismatch')
    present=journal.exists();previous=load(journal) if present else None
    if present and previous is None:raise RuntimeError('present null journal held')
    action=phase(previous,digest(target),before,after)
    if action=='write':
        save(journal,dict(phase='write-pending',before=before,after=after))
        if digest(target)!=before:raise RuntimeError('target changed after intent')
        atomic(target,data)
    if digest(target)!=after:raise RuntimeError('target readback mismatch')
    save(journal,dict(phase='completed',before=before,after=after))
def db_snapshot(path):
    with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as db:
        result={}
        for table in ('roles','agents','candidates','activation_receipts','activations'):
            exists=db.execute('SELECT 1 FROM sqlite_master WHERE type=? AND name=?',('table',table)).fetchone()
            if exists:result[table]=sorted(db.execute('SELECT * FROM '+table).fetchall(),key=repr)
        return sha_bytes(json.dumps(result,sort_keys=True).encode())
def call(args):return subprocess.check_output(args,text=True,timeout=20).strip()
def service():
    data=call(['systemctl','--user','show',UNIT,'--property=ActiveState,MainPID,InvocationID'])
    result=dict(line.split('=',1) for line in data.splitlines())
    if result.get('ActiveState')!='active' or not result.get('MainPID','').isdigit() or int(result['MainPID'])<=0:raise RuntimeError('one active service required')
    return result
def listener(port):
    out=call(['ss','-ltnpH','sport = :'+str(port)])
    pids=set(re.findall(r'pid=(\d+)',out))
    if len(pids)!=1:raise RuntimeError('one known listener required')
    pid=int(next(iter(pids)));raw=pathlib.Path('/proc/'+str(pid)+'/stat').read_text();ticks=raw.rsplit(') ',1)[1].split()[19]
    return dict(pid=pid,startticks=ticks)
def validate_candidates():
    if digest(SOURCE/'source-pins.json')!='c1f2eb93c3bcca8ecd0e2cee828d071ec3409362cfbc49daccc4228bb5a82e9e':raise RuntimeError('bridge manifest changed')
    if digest(CORE)!=CORE_PIN or digest(ROOT/'.local/root-outage-analysis/host-operator-plan/host-plan.candidate.private.json')!=HOST_PLAN_PIN:raise RuntimeError('core or host plan changed')
    old=load(AUTH/'authority.json');new=load(CANDIDATES/'authority.candidate.private.json')
    if digest(CANDIDATES/'authority.candidate.private.json')!=PROFILE_AFTER:raise RuntimeError('candidate profile changed')
    if {k:v for k,v in new.items() if k!='host_recovery'}!={k:v for k,v in old.items() if k!='host_recovery'}:raise RuntimeError('existing authority settings changed')
    for name,before,after in TARGETS:
        if digest(SOURCE/name)!=after:raise RuntimeError('candidate source changed')
    for key in ('bus_source','authority_source'):
        if digest(pathlib.Path(old[key]))!=old[key.replace('_source','_sha256')]:raise RuntimeError('preserved dependency changed')
    return old
PENDING_PIN='0dbe020b367c3e39687f08f0aff8538276e6c0b2bac3db0d2fce3ad8bb42406d'
POSTCONDITION_PIN='06bffdd6f0a641291f84141e6913ea663316b680f991e3382bbf93946b681a1a'
def postcondition_module():
    import importlib.util
    path=HERE/'recovery_postcondition.py'
    if digest(path)!=POSTCONDITION_PIN:raise RuntimeError('postcondition source changed')
    spec=importlib.util.spec_from_file_location('fixed_postcondition',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def wait_existing_new_listener(current):
    import time
    until=time.monotonic()+10
    while time.monotonic()<until:
        actual=service()
        if actual!=current:raise RuntimeError('service incarnation changed during readiness; hold')
        try:
            if listener(8801)['pid']==int(current['MainPID']):return
        except RuntimeError:pass
        time.sleep(.05)
    raise RuntimeError('new existing listener not ready; preserve restart intent')

def main():
    if PLAN_PIN is None:raise RuntimeError('concrete reviewed install authorization absent; no effects')
    if digest(HERE/'install-plan.private.json')!=PLAN_PIN:raise RuntimeError('install authorization changed')
    plan=load(HERE/'install-plan.private.json')
    if plan!={'version':1,'authorization':'fixed-single-service-host-recovery','source_manifest_sha256':'c1f2eb93c3bcca8ecd0e2cee828d071ec3409362cfbc49daccc4228bb5a82e9e','host_plan_sha256':HOST_PLAN_PIN,'profile_after_sha256':PROFILE_AFTER,'pending_recovery_sha256':PENDING_PIN}:raise RuntimeError('exact authorization required')
    regular(AUTH/'install.lock',True)
    with (AUTH/'install.lock').open('r+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        old=validate_candidates();db=pathlib.Path(old['authority_db']);progress=HERE/'install-progress.private.json'
        checker=postcondition_module()
        if digest(HERE/'pending-recovery.private.json')!=PENDING_PIN:raise RuntimeError('fixed pending nonce changed')
        guard=load(HERE/'pending-recovery.private.json')
        present=progress.exists();prior=load(progress) if present else None
        if present and (not isinstance(prior,dict) or prior.get('plan')!=PLAN_PIN or prior.get('phase') not in ('install-pending','restart-pending','completed')):raise RuntimeError('unknown install progress held')
        if prior and prior['phase']=='restart-pending':raise RuntimeError('restart uncertain; reconcile existing invocation, never replay')
        if prior and prior['phase']=='completed':
            if digest(AUTH/'authority.json')!=PROFILE_AFTER or db_snapshot(db)!=prior['db']:raise RuntimeError('completed state conflict')
            print(json.dumps({'installation_complete':True,'reconciled':True,'model_started':False}));return
        if prior is None:
            if digest(AUTH/'authority.json')!=PROFILE_BEFORE:raise RuntimeError('existing profile conflict')
            for name,before,after in TARGETS:
                if digest(ROOT/'scripts/recovery'/name)!=before:raise RuntimeError('existing source conflict')
            current=service();old_listener=listener(8788);root_listener=listener(8801)
            if root_listener['pid']!=int(current['MainPID']):raise RuntimeError('service listener mismatch')
            capture=checker.capture(db)
            if checker.preserved_or_drain(db,capture,guard)!='unchanged':raise RuntimeError('recovery already advanced before cold adoption')
            prior=dict(plan=PLAN_PIN,phase='install-pending',db=db_snapshot(db),capture=capture,service=current,old_listener=old_listener)
            save(progress,prior)
        backup=HERE/'authority-before.private.json'
        if not backup.exists():
            if digest(AUTH/'authority.json')!=PROFILE_BEFORE:raise RuntimeError('predecessor backup missing after write')
            atomic(backup,regular(AUTH/'authority.json',True).read_bytes())
        if digest(backup)!=PROFILE_BEFORE:raise RuntimeError('predecessor backup conflict')
        if db_snapshot(db)!=prior['db'] or listener(8788)!=prior['old_listener']:raise RuntimeError('preserved state changed')
        for name,before,after in TARGETS:
            if before is not None:
                backup=HERE/(name+'.before.private')
                if not backup.exists():
                    if digest(ROOT/'scripts/recovery'/name)!=before:raise RuntimeError('source backup missing after write')
                    atomic(backup,regular(ROOT/'scripts/recovery'/name).read_bytes())
                if digest(backup)!=before:raise RuntimeError('source backup conflict')
            commit_target(ROOT/'scripts/recovery'/name,regular(SOURCE/name).read_bytes(),before,after,HERE/(name+'.write.private.json'))
        commit_target(AUTH/'authority.json',regular(CANDIDATES/'authority.candidate.private.json',True).read_bytes(),PROFILE_BEFORE,PROFILE_AFTER,HERE/'profile.write.private.json')
        if db_snapshot(db)!=prior['db'] or listener(8788)!=prior['old_listener']:raise RuntimeError('state changed before restart')
        prior['phase']='restart-pending';save(progress,prior)
        subprocess.run(['systemctl','--user','restart',UNIT],check=True,timeout=40)
        current=service()
        if current['InvocationID']==prior['service']['InvocationID']:raise RuntimeError('fresh service incarnation missing')
        wait_existing_new_listener(current)
        outcome=checker.preserved_or_drain(db,prior['capture'],guard)
        if listener(8788)!=prior['old_listener'] or digest(CORE)!=CORE_PIN:raise RuntimeError('preserved state mismatch')
        prior.update(phase='completed',service_after=current,post_db_outcome=outcome);save(progress,prior)
        print(json.dumps(dict(installation_complete=True,profile_sha256=PROFILE_AFTER,unrelated_state_preserved=True,authorized_recovery_transition=outcome,old_listener_preserved=True,model_started=False)))
if __name__=='__main__':main()
