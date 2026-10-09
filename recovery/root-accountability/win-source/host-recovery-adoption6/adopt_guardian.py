"""Fixed same-task adoption adapter. Absent concrete plan means no effects."""
import sys
if not sys.flags.isolated or not sys.flags.no_site:raise SystemExit('requires -I -S')
import pathlib,json,hashlib,importlib.util,subprocess,base64,time,os,xml.etree.ElementTree as ET
BASE=pathlib.Path('C:/Users/User/git/cloudflare-agent-git/.local/win35-root-bootstrap')
HERE=BASE/'host-recovery-adoption6';CONSUMER=BASE/'host-recovery-consumer4'
CONSUMER_PIN='94b0953c7f28dfe4f730680613807210536f5e472fc1bce2d4aa506bb6b2a8d4'
def owned_script_command(command,script):
    return str(script).replace('\\','/').casefold() in command.replace('\\','/').casefold()

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def ps(script):
    result=subprocess.run(['powershell.exe','-NoProfile','-EncodedCommand',base64.b64encode(("$ErrorActionPreference='Stop';$ProgressPreference='SilentlyContinue';"+script).encode('utf-16-le')).decode()],capture_output=True,text=True,timeout=35)
    if result.returncode:raise RuntimeError('fixed Task operation failed; preserve intent')
    return result.stdout
def module(name,path,pin):
    if sha(path)!=pin or path.is_symlink() or getattr(path.stat(),'st_file_attributes',0)&0x400:raise RuntimeError('fixed source mismatch')
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def normalized_task(task):
    value=dict(task);xml=ET.fromstring(value.pop('xml'));ns={'t':'http://schemas.microsoft.com/windows/2004/02/mit/task'}
    xml.find('t:Actions/t:Exec/t:Arguments',ns).text='FIXED-ACTION'
    enabled=xml.find('t:Settings/t:Enabled',ns)
    if enabled is not None:xml.find('t:Settings',ns).remove(enabled)  # Enabled is checked separately against the actual boolean.
    for node in xml.iter():
        if node.text is not None and not node.text.strip():node.text=None
        node.tail=None
    value.pop('arguments');value.pop('enabled');value['xml']=ET.tostring(xml,encoding='unicode')
    return value
def verify_repair_boundary(historical,before):
    expected=before
    actual=historical['observations']['guardian']
    if historical.get('source_sha256')!='99380eb28690f0d52e7f30aded2c14274947115e7e3d770117bb3e35971038cb' or historical.get('owner',{}).get('epoch')!=7 or historical.get('guardian_alive') is not True or historical.get('job_drained',{}).get('active_processes')!=0 or historical.get('job_drained',{}).get('source')!='QueryInformationJobObject' or any(historical.get('dead',{}).get(n) is not True for n in ('native','worker','workload','backend')):raise RuntimeError('fixed actual repair death proof mismatch')
    if any(actual.get(f)!=expected.get(f) for f in ('pid','creation_filetime','session_id','user_sid','image','command')):raise RuntimeError('repair Guardian differs from exact before kernel')

class Hooks:
    def __init__(self,plan,load,writer,guardian,protocol):
        self.plan,self.load,self.writer,self.guardian,self.protocol=plan,load,writer,guardian,protocol
        self.plan_sha256=sha(HERE/'adoption-plan.private.json')
        self.before=load(HERE/'before.private.json');self.old=self.before['task_custody'];self.new=plan['new_arguments']
        self.old_pids=None
    def verify_all_source_and_private_inputs(self):
        if self.plan.get('authorization')!='same-owned-guardian-host-recovery-adoption6' or self.plan.get('consumer_manifest_sha256')!=CONSUMER_PIN:raise RuntimeError('fixed adoption authorization mismatch')
        if sha(HERE/'before.private.json')!=self.plan['before_sha256']:raise RuntimeError('exact old task snapshot changed')
        for name,pin in self.plan['adoption_source_pins'].items():
            if pathlib.Path(name).name!=name or sha(HERE/name)!=pin:raise RuntimeError('adoption source pin mismatch')
        for e in json.loads((CONSUMER/'source-pins.json').read_text(encoding='utf-8-sig'))['entries']:self.guardian.check_file(CONSUMER/e['path'],e['sha256'])
        self.guardian.check_file(pathlib.Path(self.plan['deployment']['python_exe']),self.plan['deployment']['python_sha256'])
        credential=BASE/'runtime/api-root/caretaker-recovery.credentials.private.json'
        self.load(credential)
        if sha(credential)!=self.plan['caretaker_credential_sha256']:raise RuntimeError('approved host credential mismatch')
        existing=CONSUMER/'deployment.private.json'
        if existing.exists() and sha(existing)!=self.plan['deployment_sha256']:raise RuntimeError('unknown existing deployment')
        self.writer.ensure_private_directory(CONSUMER)
    def assert_legacy_and_dead_predecessor(self):
        p=self.load(BASE/'api-runtime.private.json');legacy=self.load(BASE/'runtime.private.json')
        if sha(BASE/'runtime.private.json')!='a301bb1227c734c93622d9a5428a55248e3e665c9032120e5268f1adcb0b01ac':raise RuntimeError('protected legacy profile changed')
        if sha(BASE/'api-runtime.private.json')!='46690862edf284ddc8baa6eec3528c57c0dc6f6657f8cd42a63f8e93d62f1aa0':
            intent=self.read_journal()
            recovery=self.load(CONSUMER/'recovery.private.json')
            if not isinstance(intent,dict) or intent.get('phase') not in ('start-intent','completed') or recovery.get('permit',{}).get('profile_sha256')!='46690862edf284ddc8baa6eec3528c57c0dc6f6657f8cd42a63f8e93d62f1aa0':raise RuntimeError('unknown advanced API profile')
            allowed={recovery.get('successor',{}).get('holding_profile_sha256'),recovery.get('merge',{}).get('after')}
            if sha(BASE/'api-runtime.private.json') not in allowed:raise RuntimeError('unbound profile after factory')
        from win35_root_job import recorded_process_state
        historical=self.load(BASE/'whole-root-kill-repair4/kill-result.private.json')
        if sha(BASE/'whole-root-kill-repair4/kill-result.private.json')!='b317550d12038ab6b1acad20d52836e8bf20104eda8568b98d3ed99ee2eee3e0':raise RuntimeError('fixed prior test receipt changed')
        verify_repair_boundary(historical,self.before['guardian_kernel'])
        for name,k in historical['observations'].items():
            if name!='guardian' and recorded_process_state(k['pid'],k['creation_filetime']) not in ('exited','original-exited-pid-reused'):raise RuntimeError('tested native/model family no longer dead')
        state=self.load(pathlib.Path(legacy['state_dir'])/'root-runtime.json')
        if recorded_process_state(state['pid'],state['process_creation_filetime'])!='alive':raise RuntimeError('protected legacy backend changed')
        frontend=recorded_process_state(state['frontend_pid'],state['frontend_creation_filetime'])
        if frontend not in ('alive','exited'):raise RuntimeError('protected legacy frontend unknown or foreign incarnation')
        # An exact exited historical frontend is preserved; no vacancy/draft
        # conclusion, input, termination, or old backend effect follows.
    def read_journal(self):
        p=HERE/'adoption-journal.private.json'
        return self.load(p) if p.exists() else None
    def save(self,value):self.writer.save(HERE/'adoption-journal.private.json',value)
    def task(self):return self.guardian.actual_task_custody()
    def exact(self,arguments,enabled=None):
        t=self.task()
        if normalized_task(t)!=normalized_task(self.old) or t['arguments']!=arguments or (enabled is not None and t['enabled'] is not enabled):raise RuntimeError('same-task normalized custody mismatch')
        return t
    def assert_exact_old_task_and_quiescence(self):
        self.exact(self.old['arguments'],True)
        self.mechanical_processes()
    def mechanical_processes(self):
        code="ConvertTo-Json -InputObject @(Get-CimInstance Win32_Process | Where-Object {$_.CommandLine -and $_.CommandLine.Replace('\\','/').Contains('/host-recovery-consumer3/guardian_runtime.py')} | Select-Object ProcessId) -Compress"
        raw=ps(code).strip();values=json.loads(raw) if raw else []
        if isinstance(values,dict):values=[values]
        result=[]
        for item in values:
            k=self.guardian.native_context(item['ProcessId'])
            if k['image'].replace('\\','/').lower()!=self.plan['deployment']['python_exe'].replace('\\','/').lower() or ' -I -S ' not in k['command'] or ' Guard' not in k['command']:raise RuntimeError('unknown mechanical process custody')
            result.append(k)
        from win35_root_job import recorded_process_state
        expected=self.before['guardian_kernel']
        status=recorded_process_state(expected['pid'],expected['creation_filetime'])
        if status not in ('alive','exited','original-exited-pid-reused'):raise RuntimeError('original mechanical state unknown')
        if len(result)>1 or (status=='alive' and len(result)!=1):raise RuntimeError('original mechanical scan incomplete or duplicate')
        if result and any(result[0][field]!=expected[field] for field in ('pid','creation_filetime','session_id','user_sid','image','command')):raise RuntimeError('foreign mechanical kernel')
        return result
    def disable_only_exact_old_task(self):
        t=self.exact(self.old['arguments']);self.old_pids=self.mechanical_processes()
        if t['enabled']:ps("Disable-ScheduledTask -TaskName 'Win35Root-Guardian' -TaskPath '\\' | Out-Null")
        self.exact(self.old['arguments'],False)
    def stop_exact_mechanical_task_and_wait_dead(self):
        self.exact(self.old['arguments'],False)
        self.assert_legacy_and_dead_predecessor()
        from win35_root_job import kernel,require
        import ctypes as c
        api=kernel();held=[]
        try:
            for k in self.mechanical_processes():
                expected=self.before['guardian_kernel']
                if any(k[field]!=expected[field] for field in ('pid','creation_filetime','session_id','user_sid','image','command')):raise RuntimeError('original mechanical kernel changed')
                h=api.OpenProcess(0x1000|0x100000|0x1,False,k['pid']);require(h)
                values=[c.c_uint64() for _ in range(4)];require(api.GetProcessTimes(h,*[c.byref(v) for v in values]))
                if values[0].value!=k['creation_filetime']:api.CloseHandle(h);raise RuntimeError('held original Guardian incarnation changed')
                held.append(h)
            if held:ps("Stop-ScheduledTask -TaskName 'Win35Root-Guardian' -TaskPath '\\'")
            self.exact(self.old['arguments'],False);self.assert_legacy_and_dead_predecessor()
            for h in held:
                if api.WaitForSingleObject(h,1000)==258:require(api.TerminateProcess(h,137))
                if api.WaitForSingleObject(h,10000)!=0:raise RuntimeError('mechanical death uncertain; no rebind')
            if self.mechanical_processes():raise RuntimeError('foreign mechanical process; preserve')
        finally:
            for h in held:api.CloseHandle(h)
    def rebind_only_action_and_readback(self):
        t=self.task()
        if normalized_task(t)!=normalized_task(self.old) or t['enabled'] is not False or t['arguments'] not in (self.old['arguments'],self.new):raise RuntimeError('disabled same-task action conflict')
        if t['arguments']!=self.new:
            args=base64.b64encode(self.new.encode('utf-8')).decode()
            ps("$t=Get-ScheduledTask -TaskName 'Win35Root-Guardian' -TaskPath '\\';$a=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('"+args+"'));$action=New-ScheduledTaskAction -Execute $t.Actions[0].Execute -Argument $a -WorkingDirectory $t.Actions[0].WorkingDirectory;Set-ScheduledTask -TaskName 'Win35Root-Guardian' -TaskPath '\\' -Action $action | Out-Null")
        self.exact(self.new,False)
    def write_exact_private_deployment_after_task_readback(self):
        task=self.exact(self.new,False);task['enabled']=True
        # The recorded XML includes Enabled; compare the actual read-back with
        # the planned complete Task representation before any start.
        if normalized_task(task)!=normalized_task(self.plan['deployment']['task_custody']):raise RuntimeError('new planned task custody mismatch')
        deployment=self.plan['deployment']
        p=CONSUMER/'deployment.private.json'
        if p.exists():
            if sha(p)!=self.plan['deployment_sha256']:raise RuntimeError('foreign deployment')
        else:self.writer.save(p,deployment)
        if sha(p)!=self.plan['deployment_sha256']:raise RuntimeError('private deployment serialization mismatch')
    def enable_exact_task(self):
        self.exact(self.new,False);ps("Enable-ScheduledTask -TaskName 'Win35Root-Guardian' -TaskPath '\\' | Out-Null");self.exact(self.new,True)
    def actual_one_instance(self):
        raw=ps("$s=New-Object -ComObject Schedule.Service;$s.Connect();$t=$s.GetFolder('\\').GetTask('Win35Root-Guardian');ConvertTo-Json -InputObject @($t.GetInstances(0) | Select-Object InstanceGuid) -Compress").strip()
        values=json.loads(raw) if raw else []
        if isinstance(values,dict):values=[values]
        if len(values)>1:raise RuntimeError('duplicate Task instances')
        return len(values)==1
    def start_exact_task_once(self):
        self.exact(self.new,True);ps("Start-ScheduledTask -TaskName 'Win35Root-Guardian' -TaskPath '\\'")
    def reconcile_actual_guardian(self):
        end=time.monotonic()+30;path=CONSUMER/'guardian-status.private.json'
        while time.monotonic()<end:
            if path.exists():
                value=self.load(path);k=value['kernel'];actual=self.guardian.native_context(k['pid'])
                if actual['creation_filetime']==k['creation_filetime'] and value['source_sha256']==self.plan['deployment']['guardian_script_sha256'] and owned_script_command(actual['command'],CONSUMER/'guardian_runtime.py'):
                    self.exact(self.new,True)
                    return {'kernel':k,'source_sha256':value['source_sha256'],'status_sha256':sha(path)}
            time.sleep(.25)
        raise RuntimeError('start intent uncertain; no second Start')
def main():
    if sys.argv[1:] not in (['Validate'],['Install']):raise RuntimeError('fixed Validate/Install only')
    if sha(CONSUMER/'source-pins.json')!=CONSUMER_PIN:raise RuntimeError('consumer manifest changed')
    entries={e['path']:e['sha256'] for e in json.loads((CONSUMER/'source-pins.json').read_text(encoding='utf-8-sig'))['entries']}
    guardian=module('guardian_pinned',CONSUMER/'guardian_runtime.py',entries['guardian_runtime.py']);load=guardian.load_dependencies()
    writer=module('fixed_writer',BASE/'api-adoption5/private_writer.py','53c8f31299ccb87a1ab5faad5b821e3c8870bc9364ab59dacee669681aa53c31')
    path=HERE/'adoption-plan.private.json'
    if not path.exists():raise RuntimeError('concrete reviewed plan absent; no effects')
    plan=load(path)
    protocol=module('adoption_protocol',HERE/'adoption_protocol.py',plan['adoption_source_pins']['adoption_protocol.py'])
    hooks=Hooks(plan,load,writer,guardian,protocol)
    import msvcrt
    profile=load(BASE/'api-runtime.private.json');state_dir=pathlib.Path(profile['state_dir'])
    if not state_dir.resolve().is_relative_to((BASE/'runtime/api-root').resolve()):raise RuntimeError('fixed API control lock boundary')
    lock=state_dir/'control.lock'
    # Existing shared byte-zero owner lock spans the entire transition; a late
    # Recover child cannot race task retirement or profile adoption.
    with lock.open('r+b') as stream:
        stream.seek(0);msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
        try:
            if sys.argv[1]=='Validate':
                hooks.verify_all_source_and_private_inputs();hooks.assert_legacy_and_dead_predecessor();hooks.assert_exact_old_task_and_quiescence();print(json.dumps({'preflight_ready':True,'effects':False}));return
            result=protocol.transition(hooks);print(json.dumps({'phase':result['phase'],'model_or_root_kill':False}))
        finally:
            stream.seek(0);msvcrt.locking(stream.fileno(),msvcrt.LK_UNLCK,1)
if __name__=='__main__':main()
