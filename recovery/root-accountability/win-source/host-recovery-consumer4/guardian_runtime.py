"""Fixed outside-root Guardian transport/kernel adapter. No public CLI effects.

Deployment remains absent until complete source/plan review. Secrets stay in
owner-private host scope files; neither status nor exceptions include bodies.
"""
import sys
if not sys.flags.isolated or not sys.flags.no_site:raise SystemExit('requires -I -S before imports')
import pathlib,hashlib,json,ssl,http.client,subprocess,base64,os,time,importlib.util,ctypes as c
from urllib.parse import urlparse
BASE=pathlib.Path('C:/Users/User/git/cloudflare-agent-git/.local/win35-root-bootstrap')
CORE=BASE/'next12';HERE=BASE/'host-recovery-consumer4'
CORE_PIN='2f4d93e4bd31218474a1d270c5627d7fa00647e3eac3d59bb3fd4ebec7ec4f58'
SERVER_PIN='d09d0fcd68994479a469eec50c0edce6251ff14d4dc5418fe3e6ac034562667a'

def owned_script_command(command,script):
    return str(script).replace('\\','/').casefold() in command.replace('\\','/').casefold()

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def check_file(path,digest):
    for x in (path,*path.parents):
        if x.is_symlink() or getattr(x.stat(),'st_file_attributes',0)&0x400:raise RuntimeError('reparse source')
    if not path.is_file() or sha(path)!=digest:raise RuntimeError('fixed source pin mismatch')

def load_dependencies():
    check_file(CORE/'core-pins.json',CORE_PIN)
    for e in json.loads((CORE/'core-pins.json').read_text(encoding='utf-8-sig'))['entries']:
        if pathlib.Path(e['path']).name!=e['path']:raise RuntimeError('core path escape')
        check_file(CORE/e['path'],e['sha256'])
    sys.path.insert(0,str(CORE))
    from win35_quota_gate import load_private_profile
    return load_private_profile

def native_context(pid):
    if type(pid) is not int or pid<=0:raise RuntimeError('unknown process')
    script="$ErrorActionPreference='Stop';$ProgressPreference='SilentlyContinue';$p=Get-Process -Id PID;$c=Get-CimInstance Win32_Process -Filter 'ProcessId=PID';@{pid=PID;creation_filetime=$p.StartTime.ToUniversalTime().ToFileTimeUtc();session_id=$p.SessionId;user_sid=(Invoke-CimMethod -InputObject $c -MethodName GetOwnerSid).Sid;owner=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value;image=$c.ExecutablePath;command=$c.CommandLine}|ConvertTo-Json -Compress".replace('PID',str(pid))
    value=json.loads(subprocess.check_output(['powershell.exe','-NoProfile','-EncodedCommand',base64.b64encode(script.encode('utf-16-le')).decode()],text=True,timeout=10))
    if value['session_id']!=2 or value['user_sid']!=value['owner']:raise RuntimeError('actual Session2/SID custody mismatch')
    return value

def actual_task_custody():
    script="""$ErrorActionPreference='Stop';$t=Get-ScheduledTask -TaskName 'Win35Root-Guardian' -TaskPath '\\';if(@($t.Actions).Count -ne 1){throw 'action count'};$sid=([Security.Principal.NTAccount]$t.Principal.UserId).Translate([Security.Principal.SecurityIdentifier]).Value;@{execute=[string]$t.Actions[0].Execute;arguments=[string]$t.Actions[0].Arguments;working_directory=[string]$t.Actions[0].WorkingDirectory;sid=$sid;logon_type=[string]$t.Principal.LogonType;run_level=[string]$t.Principal.RunLevel;multiple_instances=[string]$t.Settings.MultipleInstances;enabled=[bool]$t.Settings.Enabled;xml=[string](Export-ScheduledTask -TaskName 'Win35Root-Guardian' -TaskPath '\\')}|ConvertTo-Json -Compress"""
    return json.loads(subprocess.check_output(['powershell.exe','-NoProfile','-EncodedCommand',base64.b64encode(script.encode('utf-16-le')).decode()],text=True,timeout=10))

def host_request(profile,credential,body):
    endpoint=urlparse(profile['authority_url'])
    if endpoint.scheme!='https' or endpoint.path not in ('','/') or endpoint.port!=8801:raise RuntimeError('fixed authority transport required')
    context=ssl.create_default_context(cafile=profile['ca_certificate']);context.minimum_version=ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(profile['client_certificate'],profile['client_key'])
    connection=http.client.HTTPSConnection(endpoint.hostname,8801,context=context,timeout=40)
    try:
        connection.connect()
        if hashlib.sha256(connection.sock.getpeercert(binary_form=True)).hexdigest()!=SERVER_PIN:raise RuntimeError('authority server certificate changed')
        wire=dict(body,v=1,credential=credential)
        connection.request('POST','/v1/host-recovery',body=json.dumps(wire),headers={'Content-Type':'application/json'})
        response=connection.getresponse();raw=response.read(131073)
        if response.status!=200 or len(raw)>131072:raise RuntimeError('host recovery transport held')
        result=json.loads(raw)
        if result.get('v')!=1 or result.get('status')!='ok':raise RuntimeError('host recovery protocol held')
        return result['result']
    finally:connection.close()

class PrivateFactoryStore:
    def __init__(self,path,load,write):self.path=path;self.load=load;self.write_private=write
    def read(self):return self.load(self.path) if self.path.exists() else None
    def write(self,value):self.write_private(self.path,value)

def fixed_module(name,path,digest):
    check_file(path,digest)
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module);return module

def live_checkpoint(profile,state,owner):
    if state.get('thread_owner')!=owner or state.get('fence_owner')!=owner or not state.get('conversation_id'):
        raise RuntimeError('current owned conversation missing')
    if any(state.get(k) for k in ('frontend_pid','viewer_pid','frontend_attempt_pending','launch_pending')):
        raise RuntimeError('protected input or uncertain launch preserved')
    history=state.get('api_history_receipt_sha256')
    if not isinstance(history,str) or len(history)!=64:raise RuntimeError('current genuine history receipt missing')
    pending=state.get('provider_pending_tools')
    if not isinstance(pending,dict):raise RuntimeError('pending tools unknown')
    return dict(thread_id=state['conversation_id'],provider_turn_state=state.get('provider_turn_state','unknown'),
        pending_tool_count=len(pending),history_receipt_sha256=history,
        protected_state='clear' if state.get('api_history_validated') is True and state.get('provider_turn_state')=='completed' and not pending else 'unknown')

class WindowsHooks:
    def __init__(self,plan,load,modules,writer):
        from win35_root_job import kernel,BasicAccounting,recorded_process_state,current_process_binding,WindowsJob
        self.plan,self.load,self.modules,self.writer=plan,load,modules,writer
        self.api,self.accounting=kernel(),BasicAccounting
        self.process_state,self.binding,self.WindowsJob=recorded_process_state,current_process_binding,WindowsJob
        self.credential=load(BASE/'runtime/api-root/caretaker-recovery.credentials.private.json')
        if self.credential.get('scope')!='fixed-host-caretaker':raise RuntimeError('separate host scope required')
        self.observer=None;self.observer_key=None;self.monitor=None;self.baseline=None;self.child=None;self.child_job=None;self.next_recover=0
        self.guardian=native_context(os.getpid())
        if self.guardian['image'].replace('\\','/').lower()!=plan['python_exe'].replace('\\','/').lower():raise RuntimeError('guardian executable mismatch')
        if ' -I -S ' not in self.guardian['command'] or not owned_script_command(self.guardian['command'],HERE/'guardian_runtime.py'):
            raise RuntimeError('fixed isolated Guardian action required')
        task=actual_task_custody()
        if task!=plan['task_custody'] or task['sid']!=self.guardian['user_sid'] or task['logon_type']!='Interactive' or task['run_level']!='Limited' or task['multiple_instances']!='IgnoreNew' or task['enabled'] is not True:
            raise RuntimeError('actual normalized same-task custody mismatch')
        action_hash=hashlib.sha256(json.dumps({k:task[k] for k in ('execute','arguments','working_directory')},sort_keys=True,separators=(',',':')).encode()).hexdigest()
        if action_hash!=plan['task_action_sha256']:raise RuntimeError('actual task action pin mismatch')
        check_file(pathlib.Path(plan['python_exe']),plan['python_sha256'])
        self.guardian.update(source_sha256=sha(pathlib.Path(__file__)),task_action_sha256=action_hash)
    def current_profile(self):
        p=self.load(BASE/'api-runtime.private.json')
        if p.get('runtime_mode')!='api-root' or not pathlib.Path(p['state_dir']).resolve().is_relative_to((BASE/'runtime/api-root').resolve()):raise RuntimeError('API profile/state boundary changed')
        for field in ('python','aplexer'):check_file(pathlib.Path(p[field+'_exe']),p[field+'_sha256'])
        operator_old=sha(BASE/'api-runtime.private.json')=='46690862edf284ddc8baa6eec3528c57c0dc6f6657f8cd42a63f8e93d62f1aa0'
        if operator_old:
            state=self.load(pathlib.Path(p['state_dir'])/'root-runtime.json')
            leaf=self.load(pathlib.Path(p['state_dir'])/('native-startup-'+p['actor']+'.private.json'))
            for pid,stamp in [(state['pid'],state['process_creation_filetime']),(leaf['kernel']['pid'],leaf['kernel']['creation_filetime'])]:
                if self.process_state(pid,stamp) not in ('exited','original-exited-pid-reused'):raise RuntimeError('fixed operator predecessor still alive or unknown')
        for field in ('host_script','control_script'):

            expected=(BASE/'next10' if operator_old else CORE)/('win35_root_host.py' if field=='host_script' else 'win35_root_control.py')
            if pathlib.Path(p[field])!=expected:raise RuntimeError('unreviewed root source')
            check_file(expected,p['host_script_sha256'] if field=='host_script' else p['control_sha256'])
        if sha(BASE/'runtime.private.json')!='a301bb1227c734c93622d9a5428a55248e3e665c9032120e5268f1adcb0b01ac':raise RuntimeError('protected legacy changed')
        return p
    def native_alive(self,p):
        if p.get('actor') is None:return False
        leaf=self.load(pathlib.Path(p['state_dir'])/('native-startup-'+p['actor']+'.private.json'))
        if leaf['native']['id']!=p['actor'] or leaf['generation']!=p['generation']:raise RuntimeError('native leaf/profile mismatch')
        observed=self.process_state(leaf['kernel']['pid'],leaf['kernel']['creation_filetime'])
        if observed=='alive':return True
        if observed not in ('exited','original-exited-pid-reused'):raise RuntimeError('native liveness unknown')
        return False
    def supervise_recover(self):
        if self.child is not None:
            if self.child.poll() is None:return
            self.child_job.wait_empty();self.child_job.close();self.child=self.child_job=None
        if time.monotonic()<self.next_recover:return
        p=self.current_profile()
        if p.get('actor') is None:return
        self.child_job=self.WindowsJob()
        self.child=self.child_job.start([p['python_exe'],p['control_script'],'Recover'],p['workspace'])
        self.next_recover=time.monotonic()+20
    def state(self):
        p=self.current_profile();d=pathlib.Path(p['state_dir'])
        return p,self.load(d/'root-runtime.json'),self.load(d/'control-journal.private.json')
    def observe_live(self):
        p=self.current_profile();d=pathlib.Path(p['state_dir'])
        if not (d/'root-runtime.json').exists() or not (d/'control-journal.private.json').exists():return
        p,s,j=self.state();owner=j['owner']
        if s.get('thread_owner')!=owner or not s.get('pid'):return
        backend=dict(pid=s['pid'],creation_filetime=s['process_creation_filetime'])
        if self.process_state(backend['pid'],backend['creation_filetime'])!='alive':return
        observation_key=(p['actor'],p['generation'],backend['pid'],backend['creation_filetime'],s['job_name'])
        if self.observer_key is not None and self.observer_key!=observation_key:
            # A genuine completed factory/enrollment has selected a new live
            # incarnation. Only now release the predecessor's retained handle.
            self.observer.close();self.observer=self.monitor=self.baseline=None
        if self.observer is None:
            self.observer=self.modules['windows_observation'].JobObservation(self.api,self.accounting,s['job_name'],backend,self.binding(),self.process_state)
            self.observer_key=observation_key
        checkpoint=live_checkpoint(p,s,owner)
        if checkpoint['protected_state']!='clear':return
        leaf=self.load(d/('native-startup-'+p['actor']+'.private.json'))
        catalog=json.loads(subprocess.check_output([p['aplexer_exe'],'list','--all','--json'],text=True,timeout=15))
        matches=[r for r in self.modules['fixed_factory'].rows(catalog) if r.get('id')==p['actor'] and r.get('tag')==p['root_tag']]
        if len(matches)!=1 or matches[0].get('worker_alive') is not True:raise RuntimeError('actual native catalog held')
        row=matches[0]
        native={}
        for name,pid in [('worker',row['worker_pid']),('workload',row['workload_pid']),('host_process',leaf['kernel']['pid'])]:
            actual=native_context(pid);native[name]={k:actual[k] for k in ('pid','creation_filetime')}
        native['id']=p['actor']
        if native['host_process']!=leaf['kernel']:raise RuntimeError('native host baseline changed')
        baseline=dict(owner=owner,host=p['expected_host'],profile_sha256=sha(BASE/'api-runtime.private.json'),guardian={k:self.guardian[k] for k in ('pid','creation_filetime','session_id','user_sid','task_action_sha256','source_sha256')},
            native=native,model=dict(owner=owner,backend=backend,job=dict(name=s['job_name'],session_id=2)),checkpoint=checkpoint)
        if baseline!=self.baseline:
            # Only the authenticated pinned producer sends this candidate. Server
            # resolves current activation/native/CID before freezing any nonce.
            host_request(p,self.credential['credential'],dict(op='observe-baseline',baseline=baseline))
            self.baseline=baseline
            self.monitor=self.modules['death_monitor'].DeathMonitor(baseline,self.observer.query,self.process_state,
                lambda:{k:self.guardian[k] for k in ('pid','creation_filetime','session_id','user_sid','task_action_sha256','source_sha256')},
                self.observer.outside,self.current_checkpoint,self.read_factory)
    def current_checkpoint(self):
        p,s,j=self.state()
        return live_checkpoint(p,s,j['owner'])
    def server_challenge(self):return host_request(self.current_profile(),self.credential['credential'],dict(op='challenge'))
    def observe_death(self,challenge):
        if self.monitor is not None:
            return self.monitor.observe(dict(nonce=challenge['challenge'],owner=challenge['baseline']['owner']))
        # Initial explicit operator-bootstrap repair is separately labelled. It
        # cannot be accepted as a fresh automatic Job query.
        if challenge.get('mode')!='operator-bootstrap' or challenge.get('operator_receipt_sha256')!='b317550d12038ab6b1acad20d52836e8bf20104eda8568b98d3ed99ee2eee3e0':raise RuntimeError('no live Job baseline; hold')
        receipt_path=BASE/'whole-root-kill-repair4/kill-result.private.json'
        check_file(receipt_path,challenge['operator_receipt_sha256']);r=self.load(receipt_path)
        if r.get('phase')!='killed-awaiting-automatic-recovery' or r.get('job_drained')!={'active_processes':0,'source':'QueryInformationJobObject'}:raise RuntimeError('historical exact drain missing')
        if any(self.process_state(x['pid'],x['creation_filetime']) not in ('exited','original-exited-pid-reused') for n,x in r['observations'].items() if n!='guardian'):
            raise RuntimeError('current whole-family death unverified')
        p,s,j=self.state();check_file(BASE/'api-authority-integration/epoch7-completed-checkpoint.private.json','cc69f762a11661d0f68a3f7e1f10616a9463844cb686d6689f4102b36f85958b');checkpoint=self.load(BASE/'api-authority-integration/epoch7-completed-checkpoint.private.json')
        if j['owner']!=r['owner'] or checkpoint['protected_state']!='clear':raise RuntimeError('operator provider checkpoint mismatch')
        return dict(v=1,challenge=challenge['challenge'],mode='operator-bootstrap',owner=r['owner'],host=p['expected_host'],
            observed_at=time.time(),operator_receipt_sha256=challenge['operator_receipt_sha256'],operator_receipt=r,
            guardian=self.guardian,current_exact_family_dead=True,job=dict(queried=False,historical_receipt_sha256=challenge['operator_receipt_sha256']),checkpoint=checkpoint)
    def server_reconcile(self,challenge,evidence):
        return host_request(self.current_profile(),self.credential['credential'],dict(op='reconcile',challenge=challenge['challenge'],receipt=evidence))
    def read_recovery(self):
        path=HERE/'recovery.private.json'
        record=self.load(path) if path.exists() else None
        if isinstance(record,dict) and record.get('phase')=='archived-completed':return None
        return record
    def write_recovery(self,record):self.writer.save(HERE/'recovery.private.json',record)
    def read_factory(self):
        record=self.read_recovery()
        if record is None:return None
        return record if record.get('phase') not in ('completed','archived-completed') else None
    def perform_factory(self,permit,expected):
        from win35_root_host import RootRuntime
        from win35_root_sink import pin
        p=self.current_profile()
        # Actual fresh provider+physical admission before native start; no model
        # is launched by this temporary quota Job. Ordinary bootstrap repeats it.
        factory=self.modules['fixed_factory'].FixedFactory(self.load,self.writer.save,self.writer.ensure_private_directory,native_context,pin)
        key=hashlib.sha256(permit['challenge'].encode()).hexdigest()
        store=PrivateFactoryStore(HERE/('factory-'+key+'.private.json'),self.load,self.writer.save)
        def admitted_spawn(holding):
            current=self.current_profile()
            if not RootRuntime(current,dict(id=current['actor'])).fresh_admission()[0]:raise RuntimeError('fresh provider admission held')
            return factory.spawn(holding)
        return self.modules['factory_protocol'].perform(permit,expected,store,factory.prepare,admitted_spawn,factory.reconcile)
    def server_enroll(self,challenge,successor):
        return host_request(self.current_profile(),self.credential['credential'],dict(op='reconcile',challenge=challenge,successor=successor))
    def prepare_credential_merge(self,handoff,successor):
        p=self.current_profile()
        if (handoff.get('status')!='enrolled_held_api_candidate' or handoff.get('actor')!=successor['actor'] or handoff.get('generation')!=successor['generation']
            or handoff.get('root_tag')!=successor['root_tag'] or handoff.get('project')!=p['project'] or handoff.get('role')!='root'
            or handoff.get('owner_is_candidate_context_only') is not True):raise RuntimeError('actual successor private handoff mismatch')
        owner=dict(project=p['project'],role='root',actor=successor['actor'],generation=successor['generation'],epoch=1)
        if handoff.get('owner')!=owner or not isinstance(handoff.get('credential'),dict) or set(handoff['credential'])!={'identity_id','token'}:raise RuntimeError('root-only held credential schema')
        if any(not isinstance(handoff['credential'][k],str) or not 1<=len(handoff['credential'][k])<=4096 for k in ('identity_id','token')):raise RuntimeError('malformed root credential')
        if sha(BASE/'api-runtime.private.json')!=successor['holding_profile_sha256']:raise RuntimeError('holding profile changed before merge')
        bound=dict(p,actor=successor['actor'],generation=successor['generation'],owner=owner,credential=handoff['credential'],deployment_stage='enrolled-held-api-candidate')
        return dict(before=successor['holding_profile_sha256'],after=hashlib.sha256(json.dumps(bound).encode()).hexdigest(),profile=bound)
    def complete_credential_merge(self,merge,successor):
        if not self.successor_live(successor):raise RuntimeError('actual new native leaf exited before private merge')
        path=BASE/'api-runtime.private.json';current=sha(path)
        if current==merge['after']:return
        if current!=merge['before']:raise RuntimeError('foreign profile at credential merge')
        self.writer.save(path,merge['profile'])
        if sha(path)!=merge['after']:raise RuntimeError('private merge write mismatch')
    def successor_live(self,successor):
        leaf_path=pathlib.Path(successor['state_dir'])/('native-startup-'+successor['actor']+'.private.json')
        if not leaf_path.exists():return False
        leaf=self.load(leaf_path)
        if leaf['native']['id']!=successor['actor'] or leaf['generation']!=successor['generation'] or sha(leaf_path)!=successor['leaf_sha256']:raise RuntimeError('genuine successor leaf changed')
        return self.process_state(leaf['kernel']['pid'],leaf['kernel']['creation_filetime'])=='alive'
    def archive_completed(self,pending):
        nonce=pending['permit']['challenge'];key=hashlib.sha256(nonce.encode()).hexdigest()
        self.writer.save(HERE/('completed-'+key+'.private.json'),pending)
        self.write_recovery(dict(pending,phase='archived-completed'))
        # Keep the original live-acquired Job handle and death baseline until
        # the next nonce has consumed its fresh zero-count proof. Archiving a
        # completed enrollment must never convert missing containment into zero.

def main():
    load=load_dependencies()
    # Explicit absence is a source-only candidate, never permission to start.
    plan_path=HERE/'deployment.private.json'
    if not plan_path.exists():raise RuntimeError('reviewed fixed deployment absent; no effects')
    plan=load(plan_path)
    if sys.argv[1:]!=['Guard'] or plan.get('authorization')!='owned-api-root-death-recovery':raise RuntimeError('fixed Guardian entry only')
    check_file(pathlib.Path(__file__),plan['guardian_script_sha256'])
    names=('death_monitor','windows_observation','factory_protocol','fixed_factory','recovery_driver')
    if set(plan.get('module_pins',{}))!=set(names):raise RuntimeError('complete dependency pins required')
    modules={name:fixed_module(name,HERE/(name+'.py'),plan['module_pins'][name]) for name in names}
    writer=fixed_module('fixed_private_writer',BASE/'api-adoption5/private_writer.py','53c8f31299ccb87a1ab5faad5b821e3c8870bc9364ab59dacee669681aa53c31')
    writer.ensure_private_directory(HERE)
    hooks=WindowsHooks(plan,load,modules,writer);driver=modules['recovery_driver'].Driver(hooks)
    while True:
        try:
            result=driver.step()
            writer.save(HERE/'guardian-status.private.json',dict(phase=result,observed_at=time.time(),kernel=hooks.binding(),source_sha256=sha(pathlib.Path(__file__))))
        except Exception as error:
            # Unknown/protected/ambiguous state persists and keeps the external
            # Guardian alive. Never normalizes a failure into vacancy/success.
            writer.save(HERE/'guardian-status.private.json',dict(phase='held-reconcile-only',error_type=type(error).__name__,observed_at=time.time(),kernel=hooks.binding(),source_sha256=sha(pathlib.Path(__file__))))
        time.sleep(2)

if __name__=='__main__':main()
