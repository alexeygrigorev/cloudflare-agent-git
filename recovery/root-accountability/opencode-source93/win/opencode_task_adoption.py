"""Fixed one-Task Windows adapter; living expired histories remain protected.

An independently reviewed concrete private plan and fresh custody are mandatory.
Only the exact childless outside Guardian is retired with a retained process
handle. Neither Stop-ScheduledTask nor a root/model family termination is used.
Unknown state and uncertain start are reconcile-only, never blind replay.
"""
import pathlib,hashlib,json,sys,subprocess,base64,time,os,re,xml.etree.ElementTree as ET
HERE=pathlib.Path(__file__).resolve().parent
BASE=pathlib.Path('C:/Users/User/git/cloudflare-agent-git/.local/win35-root-bootstrap')

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def guardian_arguments(directory,source_pin,guardian_pin,python_exe,python_pin):
    script=str(pathlib.Path(directory)/'opencode_guardian_runtime.py')
    if any("'" in value for value in (script,python_exe)) or not all(re.fullmatch('[0-9a-f]{64}',v) for v in (source_pin,guardian_pin,python_pin)):
        raise RuntimeError('fixed wrapper path/source required')
    body=("$ErrorActionPreference='Stop';$ProgressPreference='SilentlyContinue';"
        "if((Get-FileHash -Algorithm SHA256 '"+script+"').Hash.ToLower() -ne '"+guardian_pin+"'){throw 'Guardian source mismatch'};"
        "if((Get-FileHash -Algorithm SHA256 '"+python_exe+"').Hash.ToLower() -ne '"+python_pin+"'){throw 'Interpreter mismatch'};"
        "& '"+python_exe+"' -I -S '"+script+"' Guard "+source_pin+";exit $LASTEXITCODE")
    return '-NoProfile -NonInteractive -WindowStyle Hidden -EncodedCommand '+base64.b64encode(body.encode('utf-16-le')).decode()
def normalized(task):
    value=dict(task);xml=ET.fromstring(value.pop('xml'));ns={'t':'http://schemas.microsoft.com/windows/2004/02/mit/task'}
    xml.find('t:Actions/t:Exec/t:Arguments',ns).text='FIXED-ACTION'
    settings=xml.find('t:Settings',ns);enabled=settings.find('t:Enabled',ns)
    if enabled is not None:settings.remove(enabled)
    for node in xml.iter():
        if node.text is not None and not node.text.strip():node.text=None
        node.tail=None
    value.pop('arguments');value.pop('enabled');value['xml']=ET.tostring(xml,encoding='unicode')
    return value

def ps(code):
    command="$ErrorActionPreference='Stop';$ProgressPreference='SilentlyContinue';"+code
    p=subprocess.run(['powershell.exe','-NoProfile','-EncodedCommand',base64.b64encode(command.encode('utf-16-le')).decode()],capture_output=True,text=True,timeout=35)
    if p.returncode:raise RuntimeError('fixed Task operation refused or uncertain')
    return p.stdout

class WindowsHooks:
    def __init__(self,plan,plan_pin,source,load,writer,helpers,job):
        self.plan=plan;self.plan_sha256=plan_pin;self.source=source;self.load=load
        self.writer=writer;self.helpers=helpers;self.job=job
        self.directory=HERE/'task-adoption-private';writer.ensure_private_directory(self.directory)
        self.old=plan['old_task'];self.arguments=plan['new_arguments'];self.before=plan['old_guardian']
    def verify_plan_and_source(self):
        self.source()
        execution=self.helpers.native_context(os.getpid())
        if (execution['session_id']!=2 or execution['user_sid']!=self.old['sid']
            or execution['image'].replace('\\','/').lower()!=self.plan['python_exe'].replace('\\','/').lower()):
            raise RuntimeError('actual fixed same-user Session2 Task cutover required')
        if sha(HERE/'task-adoption.private.json')!=self.plan_sha256 or self.plan['authorization']!='same-owned-guardian-opencode-preserving-cutover':
            raise RuntimeError('exact reviewed preserving Task plan missing')
        if (self.plan.get('source_accepted') is not True or self.plan.get('runtime_plan_accepted') is not True
            or self.old['execute']!=self.plan['task_execute']
            or sha(pathlib.Path(self.old['execute']))!=self.plan['task_execute_sha256']
            or self.old['sid']!=self.before['user_sid'] or self.before['session_id']!=2
            or self.old['logon_type']!='Interactive' or self.old['run_level']!='Limited'
            or self.old['multiple_instances']!='IgnoreNew'):
            raise RuntimeError('actual single GUI Task/source acceptance missing')
        expected=guardian_arguments(HERE,self.plan['source_manifest_sha256'],sha(HERE/'opencode_guardian_runtime.py'),self.plan['python_exe'],self.plan['python_sha256'])
        if self.arguments!=expected:raise RuntimeError('fixed reviewed Guardian arguments differ')
        from opencode_guardian_runtime import require_execution_plan
        require_execution_plan(self.plan['runtime_plan'],self.plan['source_manifest_sha256'])
        if self.plan['runtime_plan']['controller_source_manifest_sha256']!=self.plan['source_manifest_sha256']:
            raise RuntimeError('runtime source graph differs')
    def read(self):
        p=self.directory/'transition.private.json';return self.load(p) if p.exists() else None
    def save(self,v):self.writer.save(self.directory/'transition.private.json',v)
    def task(self):return self.helpers.actual_task_custody()
    def exact(self,arguments,enabled):
        value=self.task()
        if normalized(value)!=normalized(self.old) or value['arguments']!=arguments or value['enabled'] is not enabled:
            raise RuntimeError('Task semantic/argument/enabled custody changed')
        return value
    def verify_protected_family(self):
        self.source()
        for entry in self.plan['protected_files']:
            p=pathlib.Path(entry['path'])
            if not p.is_relative_to(BASE) or any(q.is_symlink() or getattr(q.stat(),'st_file_attributes',0)&0x400 for q in (p,*p.parents)):
                raise RuntimeError('protected fixed owned path differs')
            if sha(p)!=entry['sha256']:raise RuntimeError('protected history/profile changed')
        processes=self.plan['protected_processes']
        if not processes:raise RuntimeError('protected living root custody missing')
        for process in processes:
            state=self.job.recorded_process_state(process['pid'],process['creation_filetime'])
            if state!=process['expected_state']:raise RuntimeError('protected exact incarnation changed')
    def children(self):
        code='ConvertTo-Json -InputObject @(Get-CimInstance Win32_Process -Filter "ParentProcessId='+str(self.before['pid'])+'" | Select-Object ProcessId) -Compress'
        values=json.loads(ps(code).strip() or '[]')
        return [values] if type(values) is dict else values
    def old_alive(self):
        state=self.job.recorded_process_state(self.before['pid'],self.before['creation_filetime'])
        if state not in ('alive','exited','original-exited-pid-reused'):raise RuntimeError('old Guardian incarnation unknown')
        if state=='alive':
            actual=self.helpers.native_context(self.before['pid'])
            if any(actual.get(k)!=self.before[k] for k in ('pid','creation_filetime','session_id','user_sid','image','command')):
                raise RuntimeError('old Guardian exact custody changed')
        return state=='alive'
    def verify_old_task_and_quiescence(self):
        self.exact(self.old['arguments'],True)
        if not self.old_alive():raise RuntimeError('actual old Guardian absent')
        end=time.monotonic()+20
        while self.children():
            if time.monotonic()>=end:raise RuntimeError('old Guardian child work protected; bounded quiescence elapsed')
            self.verify_protected_family();time.sleep(.25)
    def disable_exact_task_reconcile(self):
        value=self.task()
        if normalized(value)!=normalized(self.old) or value['arguments']!=self.old['arguments']:
            raise RuntimeError('different Task before Disable')
        if value['enabled']:
            self.verify_protected_family()
            if self.old_alive() and self.children():raise RuntimeError('old Guardian child work protected')
            ps("Disable-ScheduledTask -TaskName 'Win35Root-Guardian' -TaskPath '\\' | Out-Null")
        self.exact(self.old['arguments'],False)
    def retire_exact_outside_guardian(self):
        self.exact(self.old['arguments'],False);self.verify_protected_family()
        if not self.old_alive():return
        if self.children():raise RuntimeError('old Guardian child work cannot be retired')
        import ctypes as c
        api=self.job.kernel();h=api.OpenProcess(0x1000|0x100000|1,False,self.before['pid']);self.job.require(h)
        handles=[]
        try:
            times=[c.c_uint64() for _ in range(4)];self.job.require(api.GetProcessTimes(h,*[c.byref(v) for v in times]))
            if times[0].value!=self.before['creation_filetime']:raise RuntimeError('retained Guardian process reused')
            for name in self.plan['protected_job_names']:
                j=api.OpenJobObjectW(4,False,name);self.job.require(j);handles.append(j)
                member=c.c_int();self.job.require(api.IsProcessInJob(h,j,c.byref(member)))
                if member.value:raise RuntimeError('Guardian belongs to protected family Job')
            if not handles:raise RuntimeError('actual protected Job separation unknown')
            self.verify_protected_family()
            if self.children():raise RuntimeError('new child appeared before retirement')
            self.job.require(api.TerminateProcess(h,137))
            if api.WaitForSingleObject(h,10000)!=0:raise RuntimeError('mechanical retirement uncertain')
        finally:
            for j in handles:api.CloseHandle(j)
            api.CloseHandle(h)
        self.verify_protected_family()
    def rebind_only_arguments_reconcile(self):
        value=self.task()
        if normalized(value)!=normalized(self.old) or value['enabled'] is not False or value['arguments'] not in (self.old['arguments'],self.arguments):
            raise RuntimeError('disabled Task semantic conflict')
        if value['arguments']!=self.arguments:
            data=base64.b64encode(self.arguments.encode()).decode()
            ps("$t=Get-ScheduledTask -TaskName 'Win35Root-Guardian' -TaskPath '\\';$args=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('"+data+"'));$a=New-ScheduledTaskAction -Execute $t.Actions[0].Execute -Argument $args -WorkingDirectory $t.Actions[0].WorkingDirectory;Set-ScheduledTask -TaskName 'Win35Root-Guardian' -TaskPath '\\' -Action $a | Out-Null")
        self.exact(self.arguments,False)
    def persist_exact_runtime_plan(self):
        value=self.exact(self.arguments,False);plan=self.plan['runtime_plan']
        planned=plan['task_custody']
        if normalized(planned)!=normalized(value) or planned['arguments']!=self.arguments or planned['enabled'] is not True:
            raise RuntimeError('new exact runtime Task plan differs')
        path=HERE/'cold-plan.private.json'
        if path.exists():
            if self.load(path)!=plan:raise RuntimeError('existing execution plan held')
        else:self.writer.save(path,plan)
        if self.load(path)!=plan:raise RuntimeError('runtime plan readback differs')
    def enable_exact_task(self):
        self.exact(self.arguments,False);ps("Enable-ScheduledTask -TaskName 'Win35Root-Guardian' -TaskPath '\\' | Out-Null");self.exact(self.arguments,True)
    def actual_one_instance(self):
        values=json.loads(ps("$s=New-Object -ComObject Schedule.Service;$s.Connect();$t=$s.GetFolder('\\').GetTask('Win35Root-Guardian');ConvertTo-Json -InputObject @($t.GetInstances(0) | Select-Object InstanceGuid) -Compress").strip() or '[]')
        if type(values) is dict:values=[values]
        if len(values)>1:raise RuntimeError('duplicate Task instances')
        return len(values)==1
    def start_once(self):
        self.exact(self.arguments,True);ps("Start-ScheduledTask -TaskName 'Win35Root-Guardian' -TaskPath '\\'")
    def reconcile_guardian(self):
        end=time.monotonic()+30;path=HERE/'guardian-private/status.private.json'
        while time.monotonic()<end:
            if path.exists():
                value=self.load(path)
                k=value.get('kernel')
                if k is not None:
                    actual=self.helpers.native_context(k['pid'])
                    if (actual['creation_filetime']==k['creation_filetime'] and value.get('source_sha256')==sha(HERE/'opencode_guardian_runtime.py')
                        and self.helpers.owned_script_command(actual['command'],HERE/'opencode_guardian_runtime.py')):
                        self.exact(self.arguments,True);return {'kernel':k,'status_sha256':sha(path),'authority_claimed':False}
            time.sleep(.25)
        raise RuntimeError('actual new Guardian absent; no second Start')
    def verify_new_task(self):self.exact(self.arguments,True)

def main():
    if len(sys.argv)!=3 or sys.argv[1] not in ('Validate','Install'):raise RuntimeError('fixed Task Validate/Install source arguments required')
    if not sys.flags.isolated or not sys.flags.no_site or not re.fullmatch('[0-9a-f]{64}',sys.argv[2]):
        raise RuntimeError('fixed isolated Task source required')
    manifest=HERE/'source-pins.json'
    if sha(manifest)!=sys.argv[2]:raise RuntimeError('Task source manifest changed')
    for entry in json.loads(manifest.read_bytes())['entries']:
        relative=pathlib.PurePosixPath(entry['path'])
        if relative.is_absolute() or '..' in relative.parts:raise RuntimeError('Task source path escape')
        file=HERE.joinpath(*relative.parts)
        if any(p.is_symlink() or getattr(p.stat(),'st_file_attributes',0)&0x400 for p in (file,*file.parents)) or sha(file)!=entry['sha256']:
            raise RuntimeError('Task source changed')
    sys.path.insert(0,str(HERE))
    from opencode_guardian_runtime import bootstrap
    source=bootstrap(sys.argv[2])
    from opencode_win_constructor import load_private,load_module,JOB_PIN,WRITER_PIN
    plan=load_private(HERE/'task-adoption.private.json');pin=sha(HERE/'task-adoption.private.json')
    if plan['source_manifest_sha256']!=sys.argv[2]:raise RuntimeError('Task source differs')
    helpers=load_module('opencode_task_helpers',BASE/'host-recovery-consumer4/guardian_runtime.py',plan['helpers_sha256'])
    writer=load_module('opencode_task_writer',HERE/'opencode_private_writer.py',WRITER_PIN)
    job=load_module('opencode_task_job',BASE/'next12/win35_root_job.py',JOB_PIN)
    h=WindowsHooks(plan,pin,source,load_private,writer,helpers,job)
    if sys.argv[1]=='Validate':h.verify_plan_and_source();h.verify_protected_family();h.verify_old_task_and_quiescence()
    else:
        from opencode_task_transition import transition
        transition(h)

if __name__=='__main__':
    try:main()
    except Exception:raise SystemExit('fixed preserving Task cutover held')
