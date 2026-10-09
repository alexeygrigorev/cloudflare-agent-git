"""Fixed Windows MCP constructor. Query handles only; starts no model/process.

Factory launch source guard and the reviewed literal cold-plan binding are
mandatory. No predecessor credential or arbitrary constructor import exists.
"""
import base64,ctypes,hashlib,importlib.util,json,os,pathlib,re,subprocess,sys

HERE=pathlib.Path(__file__).resolve().parent
BASE=pathlib.Path('C:/Users/User/git/cloudflare-agent-git/.local/win35-root-bootstrap')
LEAVES=BASE/'runtime/api-root'
JOB_PIN='e9183cee541f590abd45098f24b48950ad9db2e597c2299a5338c4f86feaf96c'
WRITER_PIN='a6618b92b9c6b81d9824f6bdd7500da2a10e483d12c7827b9c0519952eb05123'
APLEXER_PIN='7a9c64b7ce6644d490f8d773f13f44c55ec2066e114e9363bf4caebbab020941'
APLEXER=pathlib.Path('C:/Users/User/AppData/Local/Programs/aplexer/bin/aplexer.exe')

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def verify_private(path):
    path=pathlib.Path(path)
    if os.name!='nt':raise RuntimeError('native owner ACL verification required')
    if not path.exists() or any(p.is_symlink() or getattr(p.stat(),'st_file_attributes',0)&0x400 for p in (path,*path.parents)):
        raise RuntimeError('private source absent/reparse')
    script=r'''$ErrorActionPreference='Stop'
$f=Get-Item -LiteralPath $env:ROOT_CONTROLLER_PRIVATE_TARGET
if($f.Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'reparse'}
$me=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$acl=Get-Acl -LiteralPath $f.FullName
if($acl.GetOwner([Security.Principal.SecurityIdentifier]).Value -ne $me){throw 'owner'}
foreach($r in $acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier])){
if($r.AccessControlType -eq 'Allow' -and $r.IdentityReference.Value -notin @($me,'S-1-5-18','S-1-5-32-544')){throw 'broad ACL'}}
'''
    env=dict(os.environ,ROOT_CONTROLLER_PRIVATE_TARGET=str(path));env.pop('PSModulePath',None)
    result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-EncodedCommand',
        base64.b64encode(script.encode('utf-16-le')).decode()],env=env,capture_output=True,timeout=10)
    if result.returncode:raise RuntimeError('private owner ACL held')

def load_private(path):
    verify_private(path)
    if not path.is_file() or path.stat().st_size>2097152:raise RuntimeError('bounded private JSON required')
    return json.loads(path.read_bytes())

def load_module(name,path,pin):
    if sha(path)!=pin:raise RuntimeError('fixed dependency source changed')
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if sha(path)!=pin:raise RuntimeError('dependency changed during import')
    return module

class QueryJob:
    def __init__(self,module,name):
        if type(name) is not str or not re.fullmatch(r'Local\\Win35Root-[0-9a-f]{32}',name):
            raise RuntimeError('fixed per-incarnation named Job required')
        self.module=module;self.api=module.kernel();self.name=name
        self.handle=self.api.OpenJobObjectW(4,False,name) # JOB_OBJECT_QUERY only
        module.require(self.handle)
    def query(self):return self.module.WindowsJob.query(self)
    def close(self):
        if self.handle:self.api.CloseHandle(self.handle);self.handle=None

class QueryProcess:
    def __init__(self,module,job,expected):
        self.module=module;self.job=job;self.pid=expected['pid']
        self.handle=job.api.OpenProcess(0x100000|0x1000,False,self.pid)
        module.require(self.handle)
        times=[ctypes.c_uint64() for _ in range(4)]
        module.require(job.api.GetProcessTimes(self.handle,*[ctypes.byref(t) for t in times]))
        self.creation_filetime=times[0].value
        if self.creation_filetime!=expected['creation_filetime']:
            self.close();raise RuntimeError('backend incarnation changed')
    def poll(self):return None if self.job.api.WaitForSingleObject(self.handle,0)==258 else 1
    def close(self):
        if self.handle:self.job.api.CloseHandle(self.handle);self.handle=None

def construct(directory,profile_sha256,manifest_sha256):
    if os.name!='nt':raise RuntimeError('native Windows constructor required')
    if directory.parent!=LEAVES or not re.fullmatch(r'(preserving|recovery)-[0-9a-f]{64}',directory.name):
        raise RuntimeError('fixed factory incarnation leaf required')
    profile_path=directory/'opencode-controller.private.json'
    profile=load_private(profile_path)
    if sha(profile_path)!=profile_sha256:raise RuntimeError('factory profile changed')
    # Acyclic hash graph: source is pinned by plan; plan hash is installed into
    # the enrolled owner-private profile, never selected by model arguments.
    plan_sha=profile.get('execution_plan_sha256')
    if type(plan_sha) is not str or not re.fullmatch('[0-9a-f]{64}',plan_sha):
        raise RuntimeError('reviewed native cold-plan constructor binding absent')
    plan_path=HERE/'cold-plan.private.json'
    plan=load_private(plan_path)
    if sha(plan_path)!=plan_sha or plan.get('controller_source_manifest_sha256')!=manifest_sha256:
        raise RuntimeError('reviewed cold-plan/source binding changed')
    manifest_path=HERE/'source-pins.json'
    def source_guard():
        if sha(manifest_path)!=manifest_sha256:raise RuntimeError('controller source manifest changed')
        for entry in json.loads(manifest_path.read_bytes())['entries']:
            relative=pathlib.PurePosixPath(entry['path'])
            if relative.is_absolute() or '..' in relative.parts:raise RuntimeError('source path outside fixed bundle')
            file=HERE.joinpath(*relative.parts)
            if any(p.is_symlink() or getattr(p.stat(),'st_file_attributes',0)&0x400 for p in (file,*file.parents)) or sha(file)!=entry['sha256']:
                raise RuntimeError('controller source file changed')
    source_guard()
    def identity_guard(value):
        source_guard()
        if sha(APLEXER)!=APLEXER_PIN:raise RuntimeError('native identity executable changed')
        actual=json.loads(subprocess.check_output([str(APLEXER),'whoami','--json'],text=True,timeout=10))
        wanted=value['native']
        if any(actual.get(k)!=wanted.get(k) for k in ('id','tag','workspace','engine')):
            raise RuntimeError('actual own native sender identity mismatch')
        if sha(profile_path)!=profile_sha256:raise RuntimeError('private controller profile changed')
    identity_guard(profile)
    job_module=load_module('root_job_query_dependency',BASE/'next12/win35_root_job.py',JOB_PIN)
    writer=load_module('root_private_writer_dependency',HERE/'opencode_private_writer.py',WRITER_PIN)
    from opencode_win_custody import WinCustody
    from opencode_owned_reader import OwnedHistoryReader
    from opencode_authority_transport import AuthorityTransport
    from opencode_controller_runtime import ControllerRuntime
    job=QueryJob(job_module,profile['kernel']['job_name'])
    backend=QueryProcess(job_module,job,profile['kernel']['backend'])
    custody=WinCustody(job_module,job,backend,profile['native'],profile['owner'],profile_path,
        profile_sha256,profile['kernel']['processes'],profile['kernel']['guardian'],lambda:profile['session_id'])
    selected=[None]
    reader=OwnedHistoryReader(profile['native_port'],profile['native_password'],lambda:selected[0],
        lambda context:custody()['kernel_ref']==context['kernel_ref'],connection_gate=custody.connection)
    def history(context):
        if selected[0] is not None:raise RuntimeError('recursive native history read held')
        selected[0]=context
        try:return reader(context)
        finally:selected[0]=None
    transport=AuthorityTransport(profile['authority']['origin'],profile['controller_credential'],
        {k:pathlib.Path(v) for k,v in profile['authority']['certificate_paths'].items()},
        profile['authority']['certificate_pins'],lambda:identity_guard(profile))
    try:
        runtime=ControllerRuntime(profile,directory,manifest_sha256,private_load=load_private,
            private_save=writer.save,verify_private=verify_private,kernel_reader=custody,
            history_reader=history,dispatch_read=lambda:load_private(directory/'opencode-dispatch.private.json'),
            authority_post=transport,denial_reader=lambda:load_private(directory/'opencode-luna-admission.private.json'),
            startup_root=HERE/'startup-full',snapshot_path=HERE/'principal-observation-20261009T043726Z.private.json',
            snapshot_sha256=profile['snapshot_sha256'],source_guard=source_guard,native_identity_guard=identity_guard)
        custody() # actual fresh family/retained-query proof before serving tools
        return runtime,backend,job
    except BaseException:
        backend.close();job.close();raise

def main():
    if len(sys.argv)!=4:raise RuntimeError('fixed incarnation/profile/source arguments required')
    name,profile_sha256,manifest_sha256=sys.argv[1:]
    if not re.fullmatch(r'(preserving|recovery)-[0-9a-f]{64}',name) or any(not re.fullmatch('[0-9a-f]{64}',v) for v in (profile_sha256,manifest_sha256)):
        raise RuntimeError('fixed factory arguments required')
    runtime,backend,job=construct(LEAVES/name,profile_sha256,manifest_sha256)
    try:runtime.run_stdio(sys.stdin,sys.stdout)
    finally:backend.close();job.close()

if __name__=='__main__':
    try:main()
    except Exception:
        # Native stdio/debug must never receive private configuration/exceptions.
        sys.stderr.write('fixed root controller held\n');sys.exit(1)
