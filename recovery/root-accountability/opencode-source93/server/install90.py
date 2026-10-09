"""Exact source/profile adoption; one existing service, no restart replay."""
import pathlib,json,hashlib,os,stat,tempfile,sqlite3,subprocess,fcntl,time,sys,grp,pwd,math
ROOT=pathlib.Path('/home/alexey/git/cloudflare-agent-git')
HERE=ROOT/'.local/win35-root-bootstrap/operational-runtime1/server-cutover93'
PACKET=HERE
AUTH=ROOT/'.local/win35-root-authority'
BASE=pathlib.Path('/home/alexey/.local/recovery/situational-head-root-outage-20261008/operating-issuer85')
RUNTIME=BASE/'server-runtime88';COLD=BASE/'cold-composition93'
PROFILE_BEFORE='e3ea58893f2d78dd2c6c258976d05ee878ea682977d99cd356b419a3114c7f20'
PROFILE_AFTER='3aa75a87a9d7c1d52644de06239dcfbf85c9ab33c87efb9d6b41643f2976e296'
MANIFEST='257d909993d8e790b0fea471afe3c59fefc66c0c68f699d08db5b7cab6759f10'
COMPOSITION='0f3cbdc6e0a3aacd0b4fbf28f0faa2c7329f3552c9e60f699bf16f0f81c4486f'
HOSTPLAN='6606e0887053dc18fa909cc0f89ed1cb42fbd1a6ff0f41e6f39f9f21d4729dbf'
OLD_HOSTPLAN=ROOT/'.local/root-outage-analysis/host-operator-plan/host-plan.candidate.private.json'
OLD_HOSTPIN='620c0b3e434e900f262efd4bade6529a7b316228ac3bff17967089439ee4384f'
TARGETS=(('role_fence_cli.py','cb6a1568dd45ff2a6840cab72cbf332f769979f93c339f10e2d25ec9bbff15c8','cb6a1568dd45ff2a6840cab72cbf332f769979f93c339f10e2d25ec9bbff15c8'),
 ('role_fence_http.py','63a4b0f07ca2e9783b1b597bba65d35190675b554a316bd58c140fbd3c5f4c4c','63a4b0f07ca2e9783b1b597bba65d35190675b554a316bd58c140fbd3c5f4c4c'))
UNIT='win35-role-authority.service'
PREDECESSOR_PLAN='ec857b66ca17a010217e4484d1db2290067a52f444a3f0cd7ef207dac2a4b8f8'
PREDECESSOR_PROGRESS='da22b6447301148970cebb566fdd09e277f4124a1f010d1f88bda1e4b4413b6b'
PREDECESSOR_WRITE='efa2b14e22b8d011365675f9834c4efe8c2b90f090ed571ea43523a7295b0ea0'
PRESERVED_DEPENDENCIES={
 'bus_source':('/home/alexey/git/agent-coordination/coordination/bus.py','22da5250efa0ef9366d7bb58137607987052e008f6cfa060d28e344dfbd75dc8'),
 'authority_source':(str(RUNTIME/'role_core75.py'),'c4b96b23440ba18aebf6be74de7fa482929f72d5272551cca34255be5f7e7e94')}

def preserved_dependency(config,key):
    expected_path,expected_hash=PRESERVED_DEPENDENCIES[key]
    p=pathlib.Path(expected_path)
    if config[key]!=expected_path or config[key.replace('_source','_sha256')]!=expected_hash or any(q.is_symlink() for q in (p,*p.parents)):
        raise RuntimeError('preserved dependency binding changed')
    if key=='authority_source':
        if sha(p)!=expected_hash:raise RuntimeError('owned current core bytes changed')
        return
    s=p.stat()
    if not stat.S_ISREG(s.st_mode) or s.st_uid!=1000 or s.st_gid!=1000 or stat.S_IMODE(s.st_mode)!=0o664 or os.getuid()!=1000:
        raise RuntimeError('preserved dependency custody changed')
    group=grp.getgrgid(1000)
    writer_uids={u.pw_uid for u in pwd.getpwall() if u.pw_gid==1000}
    writer_uids.update(pwd.getpwnam(name).pw_uid for name in group.gr_mem)
    if writer_uids!={1000}:raise RuntimeError('foreign preserved dependency group writer')
    if hash_bytes(p.read_bytes())!=expected_hash:raise RuntimeError('preserved dependency bytes changed')
def hash_bytes(v):return hashlib.sha256(v).hexdigest()

def parent_custody(p):
    if any(q.is_symlink() for q in (p,*p.parents)):raise RuntimeError('directory reparse hold')
    s=p.stat()
    if not stat.S_ISDIR(s.st_mode) or s.st_uid!=os.getuid():raise RuntimeError('owned fixed directory required')
    if s.st_mode&0o022:
        if p!=ROOT/'scripts/recovery' or s.st_uid!=1000 or s.st_gid!=1000 or stat.S_IMODE(s.st_mode)!=0o775 or os.getuid()!=1000:
            raise RuntimeError('owned fixed directory required')
        writers={u.pw_uid for u in pwd.getpwall() if u.pw_gid==1000}
        writers.update(pwd.getpwnam(n).pw_uid for n in grp.getgrgid(1000).gr_mem)
        if writers!={1000}:raise RuntimeError('foreign alias-parent group writer')
def regular(p,private=False):
    p=pathlib.Path(p)
    if any(q.is_symlink() for q in (p,*p.parents)):raise RuntimeError('symlink custody hold')
    s=p.stat()
    if not stat.S_ISREG(s.st_mode) or s.st_uid!=os.getuid() or s.st_mode&0o022 or private and s.st_mode&0o077:
        raise RuntimeError('source owner/mode hold')
    return p
def sha(p):return hash_bytes(regular(p).read_bytes())
def load(p):return json.loads(regular(p,True).read_bytes())
def atomic(p,data):
    parent_custody(p.parent)
    fd,name=tempfile.mkstemp(prefix='.owned-adoption-',dir=p.parent)
    try:
        os.fchmod(fd,0o600)
        with os.fdopen(fd,'wb') as out:out.write(data);out.flush();os.fsync(out.fileno())
        os.replace(name,p)
        parent=os.open(p.parent,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(parent)
        finally:os.close(parent)
        parent_custody(p.parent)
    finally:
        if os.path.exists(name):os.unlink(name)
def save(p,v):atomic(p,json.dumps(v,sort_keys=True).encode())
def call(argv):return subprocess.check_output(argv,text=True,timeout=20).strip()
def service():
    value=dict(x.split('=',1) for x in call(['systemctl','--user','show',UNIT,'--property=ActiveState,MainPID,InvocationID']).splitlines())
    if value['ActiveState']!='active' or not value['MainPID'].isdigit() or int(value['MainPID'])<=0 or not value['InvocationID']:
        raise RuntimeError('one existing active service required')
    return value
def listener(port):
    import re
    value=call(['ss','-ltnpH','sport = :'+str(port)])
    pids=set(re.findall(r'pid=(\d+)',value))
    if len(pids)!=1:raise RuntimeError('one exact listener required')
    pid=int(next(iter(pids)))
    ticks=pathlib.Path('/proc/'+str(pid)+'/stat').read_text().rsplit(') ',1)[1].split()[19]
    return {'pid':pid,'startticks':ticks}
def snapshot(db_path):
    with sqlite3.connect(pathlib.Path(db_path).as_uri()+'?mode=ro',uri=True) as db:
        db.execute('BEGIN')
        result={}
        for name,sql in db.execute("SELECT name,sql FROM sqlite_master WHERE type='table' ORDER BY name"):
            quoted='"'+name.replace('"','""')+'"'
            rows=sorted(db.execute('SELECT * FROM '+quoted).fetchall(),key=repr)
            result[name]={'rows_sha256':hash_bytes(repr(rows).encode()),'count':len(rows),'schema_sha256':hash_bytes((sql or '').encode())}
            if name=='authority_meta':
                values=dict(rows)
                if set(values)!={'boot','last_clock'} or values['boot']!=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip():raise RuntimeError('authority boot/metadata custody changed')
                clock=float(values['last_clock'])
                if not math.isfinite(clock) or clock<0 or clock>time.time()+1:raise RuntimeError('authority metadata clock unknown/future')
                result[name]['source_clock']={'stable_rows_sha256':hash_bytes(repr(sorted((k,v) for k,v in rows if k!='last_clock')).encode()),'last_clock':clock}
        return result
def preserve_rows(before,after):
    for k,v in before.items():
        current=after.get(k)
        if k=='authority_meta' and 'source_clock' in v and current and 'source_clock' in current:
            if current['count']!=v['count'] or current['schema_sha256']!=v['schema_sha256'] or current['source_clock']['stable_rows_sha256']!=v['source_clock']['stable_rows_sha256'] or current['source_clock']['last_clock']<v['source_clock']['last_clock']:
                raise RuntimeError('existing schema/row custody changed')
        elif current!=v:raise RuntimeError('existing schema/row custody changed')
    if any(v['count']!=0 for k,v in after.items() if k not in before):raise RuntimeError('unexpected new table rows')
def reconcile_stage(record,plan_pin):
    if type(record) is not dict or record.get('plan_sha256')!=plan_pin or record.get('phase') not in ('install-pending','restart-pending','completed'):
        raise RuntimeError('unknown adoption journal')
    if record['phase']=='restart-pending':raise RuntimeError('restart uncertain: readonly reconciliation only; never replay')
    return record['phase']
def checked_sources():
    if sha(COLD/'composition-pins.private.json')!=COMPOSITION or sha(RUNTIME/'runtime-pins.private.json')!=MANIFEST:
        raise RuntimeError('composition manifest changed')
    manifest=load(RUNTIME/'runtime-pins.private.json')
    if len(manifest['entries'])!=28:raise RuntimeError('complete fixed runtime required')
    for entry in manifest['entries']:
        relative=pathlib.PurePosixPath(entry['path'])
        if relative.is_absolute() or '..' in relative.parts or sha(RUNTIME/entry['path'])!=entry['sha256']:
            raise RuntimeError('runtime source changed')
    if sha(COLD/'authority.candidate.private.json')!=PROFILE_AFTER or sha(COLD/'host-plan.candidate.private.json')!=HOSTPLAN or sha(OLD_HOSTPLAN)!=OLD_HOSTPIN:
        raise RuntimeError('fixed profile/hostplan changed')
    for name,before,after in TARGETS:
        if sha(RUNTIME/name)!=after:raise RuntimeError('alias source changed')
    for key,(path,pin) in PRESERVED_DEPENDENCIES.items():preserved_dependency({key:path,key.replace('_source','_sha256'):pin},key)
    parent_custody(ROOT/'scripts/recovery');parent_custody(AUTH)
def profile_compare(old,new):
    fields={'host_recovery'}
    if {k:v for k,v in old.items() if k not in fields}!={k:v for k,v in new.items() if k not in fields}:
        raise RuntimeError('unapproved authority configuration changed')

def accepted_execution(plan,source_pin):
    if plan.get('execution_authorized') is not True:raise RuntimeError('actual distinct acceptance required before effects')
    receipt_path=PACKET/'installer-acceptance.private.json'
    if plan.get('acceptance_receipt_sha256')!=sha(receipt_path):raise RuntimeError('actual acceptance receipt differs')
    receipt=load(receipt_path)
    reviewed=dict(plan,execution_authorized=False)
    reviewed.pop('acceptance_receipt_sha256',None)
    reviewed_pin=hash_bytes(json.dumps(reviewed,sort_keys=True).encode())
    if receipt.get('verdict')!='ACCEPT_SOURCE_PLAN' or receipt.get('installer_source_sha256')!=source_pin or receipt.get('reviewed_plan_sha256')!=reviewed_pin or not receipt.get('review_report_sha256') or not receipt.get('genuine_acceptance_message_id'):
        raise RuntimeError('distinct source/plan acceptance binding absent')
def verify_baseline():
    checked_sources()
    if sha(AUTH/'authority.json')!=PROFILE_BEFORE:raise RuntimeError('current authority profile changed')
    old=load(AUTH/'authority.json');new=load(COLD/'authority.candidate.private.json');profile_compare(old,new)
    for name,before,after in TARGETS:
        if sha(ROOT/'scripts/recovery'/name)!=before:raise RuntimeError('current alias changed')
    for key in ('bus_source','authority_source'):
        preserved_dependency(old,key)
    current=service();root=listener(8801)
    if root['pid']!=int(current['MainPID']):raise RuntimeError('service/listener differs')
    return old,{'service':current,'root_listener':root,'old_listener':listener(8788),'db':snapshot(old['authority_db'])}

def backup_and_write(target,data,before,after,name):
    journal=HERE/(name+'.write.private.json');backup=HERE/(name+'.before.private')
    if not backup.exists():
        if sha(target)!=before:raise RuntimeError('backup missing after possible write')
        atomic(backup,regular(target).read_bytes())
    if sha(backup)!=before or hash_bytes(data)!=after:raise RuntimeError('backup/candidate differs')
    if journal.exists():
        value=load(journal)
        if value!={'before':before,'after':after,'phase':'write-pending'} and value!={'before':before,'after':after,'phase':'completed'}:
            raise RuntimeError('foreign write journal')
        if value['phase']=='completed' and sha(target)!=after:raise RuntimeError('completed target changed')
    else:save(journal,{'before':before,'after':after,'phase':'write-pending'})
    current=sha(target)
    if current==before:atomic(target,data)
    elif current!=after:raise RuntimeError('unknown target after intent')
    if sha(target)!=after:raise RuntimeError('write readback differs')
    save(journal,{'before':before,'after':after,'phase':'completed'})
def postconditions(record):
    checked_sources()
    if sha(AUTH/'authority.json')!=PROFILE_AFTER:raise RuntimeError('adopted profile differs')
    for name,before,after in TARGETS:
        if sha(ROOT/'scripts/recovery'/name)!=after:raise RuntimeError('adopted alias differs')
    if listener(8788)!=record['old_listener']:raise RuntimeError('protected8788 changed')
    current=service()
    if current['InvocationID']==record['service']['InvocationID']:raise RuntimeError('actual existing-unit restart not observed')
    until=time.monotonic()+10
    while True:
        if service()!=current:raise RuntimeError('service incarnation changed during readiness')
        try:
            if listener(8801)['pid']==int(current['MainPID']):break
        except RuntimeError:
            if time.monotonic()>=until:raise
            time.sleep(.05)
    preserve_rows(record['db'],snapshot(load(AUTH/'authority.json')['authority_db']))
    return current
def main():
    if not sys.flags.isolated or not sys.flags.no_site or len(sys.argv)!=3 or sys.argv[1] not in ('Validate','Apply','Reconcile'):
        raise RuntimeError('fixed isolated install operation/plan pin required')
    plan_path=PACKET/'install-plan.private.json';plan=load(plan_path);pin=sys.argv[2]
    if sha(plan_path)!=pin or plan.get('installer_source_sha256')!=sha(pathlib.Path(__file__)) or plan.get('authorization')!='same-one8801-profile92-path-budget-correction':
        raise RuntimeError('fixed reviewed plan absent')
    regular(AUTH/'install.lock',True)
    with (AUTH/'install.lock').open('r+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        progress=HERE/'install-progress.private.json'
        if sys.argv[1]=='Validate':
            if progress.exists():raise RuntimeError('existing profile-update intent; reconcile only')
            old,record=verify_baseline();print(json.dumps({'preflight':True,'fresh_profile_update':True,'profile_changed':False,'service_changed':False}));return
        accepted_execution(plan,sha(pathlib.Path(__file__)))
        if progress.exists():
            record=load(progress)
            if sys.argv[1]=='Reconcile':
                if record.get('plan_sha256')!=pin or record.get('phase')!='restart-pending':raise RuntimeError('only known restart intent may reconcile')
                current=postconditions(record);save(progress,dict(record,phase='completed',new_service=current));print('reconciled existing restart; no restart action');return
            if reconcile_stage(record,pin)=='completed':postconditions(record);print('completed exact adoption retained');return
            checked_sources()
        else:
            if sys.argv[1]=='Reconcile':raise RuntimeError('no restart intent; no action')
            old,record=verify_baseline();record.update(phase='install-pending',plan_sha256=pin);save(progress,record)
        preserve_rows(record['db'],snapshot(load(AUTH/'authority.json')['authority_db']))
        if listener(8788)!=record['old_listener']:raise RuntimeError('protected listener changed')
        for name,before,after in TARGETS:
            if before==after:continue # Alias bytes are read-only in this exact profile correction.
            backup_and_write(ROOT/'scripts/recovery'/name,regular(RUNTIME/name).read_bytes(),before,after,name)
        backup_and_write(AUTH/'authority.json',regular(COLD/'authority.candidate.private.json',True).read_bytes(),PROFILE_BEFORE,PROFILE_AFTER,'authority')
        preserve_rows(record['db'],snapshot(load(AUTH/'authority.json')['authority_db']))
        if listener(8788)!=record['old_listener']:raise RuntimeError('protected listener changed before restart')
        save(progress,dict(record,phase='restart-pending'))
        subprocess.run(['systemctl','--user','restart',UNIT],check=True,timeout=20)
        current=postconditions(record)
        save(progress,dict(record,phase='completed',new_service=current))
        print(json.dumps({'installation_complete':True,'existing_service_restarted_once':True,'model_effect':False,'native_root_started':False}))
if __name__=='__main__':main()
