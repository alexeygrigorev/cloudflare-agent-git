"""Fixed shell composition for the reviewed, owner-provisioned cold plan.

No candidate epoch is elected here. No model input is submitted by this
constructor or root-start. The authenticated fence selects the actual owner;
root-start then creates only the native listener and empty session.
"""
import base64,copy,hashlib,json,os,pathlib,re,subprocess
import time

HERE=pathlib.Path(__file__).resolve().parent

def reply_archive_name(pin):
    if type(pin) is not str or not re.fullmatch('[0-9a-f]{64}',pin):raise RuntimeError('fixed reply archive reference required')
    return 'ra-'+base64.urlsafe_b64encode(bytes.fromhex(pin)).decode().rstrip('=')+'.json'

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def selected_plan(profile,load,verify):
    manifest=HERE/'source-pins.json';plan_path=HERE/'cold-plan.private.json'
    pin=profile.get('execution_plan_sha256');source=profile.get('controller_source_manifest_sha256')
    if any(type(v) is not str or not re.fullmatch('[0-9a-f]{64}',v) for v in (pin,source)):
        raise RuntimeError('reviewed enrolled execution plan/source missing')
    verify(plan_path);plan=load(plan_path)
    if digest(plan_path)!=pin or plan.get('controller_source_manifest_sha256')!=source:
        raise RuntimeError('fixed enrolled cold-plan binding differs')
    def guard():
        if digest(plan_path)!=pin or digest(manifest)!=source:raise RuntimeError('cold plan/source changed')
        data=json.loads(manifest.read_bytes())
        if type(data.get('entries')) is not list or not data['entries']:raise RuntimeError('complete source bundle missing')
        for entry in data['entries']:
            rel=pathlib.PurePosixPath(entry['path'])
            if rel.is_absolute() or '..' in rel.parts:raise RuntimeError('source path outside fixed bundle')
            file=HERE.joinpath(*rel.parts)
            if any(p.is_symlink() or getattr(p.stat(),'st_file_attributes',0)&0x400 for p in (file,*file.parents)):
                raise RuntimeError('source reparse held')
            if digest(file)!=entry['sha256']:raise RuntimeError('complete source bundle changed')
    guard();return plan,guard

def build_runtime(profile,native,host_kernel):
    if os.name!='nt':raise RuntimeError('actual Windows shell constructor required')
    from opencode_win_constructor import BASE,APLEXER,APLEXER_PIN,JOB_PIN,WRITER_PIN,load_module,load_private,verify_private
    from opencode_controller_store import BASE as LEAVES,INCARNATION
    from opencode_native_control import NativeControl
    from opencode_backend_factory import BackendFactory
    from opencode_backend_api import BackendAPI
    from opencode_controller_profile_writer import ProfileWriter
    from opencode_root_start import RootStart
    from opencode_native_kernel import NativeKernel
    from opencode_win_custody import WinCustody
    from opencode_role_proof import RoleProof
    from opencode_own_admission import OwnAdmission,physical_reader
    from opencode_memory_provider import read_fixed_machine_slot
    from opencode_win_constructor import construct
    from opencode_observation_channel import ObservationChannel
    from opencode_check_dispatch import CheckDispatch
    from opencode_authority_transport import AuthorityTransport
    from opencode_full_startup import FullStartup
    from opencode_native_dispatch import digest as archive_digest
    from opencode_luna_admission import LunaAdmission
    directory=pathlib.Path(profile['state_dir'])
    if directory.parent!=LEAVES or not INCARNATION.fullmatch(directory.name):
        raise RuntimeError('fixed factory successor leaf required')
    verify_private(directory)
    if (native['id']!=profile['actor'] or profile['generation']!='win32:'+str(host_kernel['pid'])+':'+str(host_kernel['creation_filetime'])
        or profile.get('root_runtime_kind')!='opencode-native-v1'):
        raise RuntimeError('genuine enrolled current shell differs')
    plan,source=selected_plan(profile,load_private,verify_private)
    holding_path=BASE/'api-runtime.private.json';holding_sha=digest(holding_path)
    source_sha=profile['controller_source_manifest_sha256']
    def guard():
        source()
        if digest(holding_path)!=holding_sha or digest(APLEXER)!=APLEXER_PIN:
            raise RuntimeError('holding profile/native executable changed')
        for key,pin in plan['authority']['certificate_pins'].items():
            path=pathlib.Path(plan['authority']['certificate_paths'][key]);verify_private(path)
            if digest(path)!=pin:raise RuntimeError('fixed device certificate changed')
        verify_private(directory)
    def identity(value=None):
        guard()
        actual=json.loads(subprocess.check_output([str(APLEXER),'whoami','--json'],text=True,timeout=10))
        if any(actual.get(k)!=native.get(k) for k in ('id','tag','workspace','engine')):
            raise RuntimeError('actual own shell identity changed')
    identity()
    job_module=load_module('opencode_shell_job',BASE/'next12/win35_root_job.py',JOB_PIN)
    writer=load_module('opencode_shell_writer',HERE/'opencode_private_writer.py',WRITER_PIN)
    def read(name):
        path=directory/name
        if not path.exists():return None
        return load_private(path)
    def save(name,value):
        guard();writer.save(directory/name,value)
        if load_private(directory/name)!=value:raise RuntimeError('private runtime write/readback differs')
    control_state=lambda:read('opencode-native-control.private.json')
    admission=OwnAdmission(profile['provider_account_binding'],guard,
        lambda v:save('opencode-provider-admission.private.json',v),lambda:physical_reader(directory,guard))
    api=BackendAPI(job_module,guard)
    # Retain the controlling Job handle for the full shell lifetime. MCP helper
    # processes reopen only QUERY rights; closing those never releases this one.
    factory_profile=dict(profile,native=native,python_exe=plan['python_exe'],opencode_exe=plan['opencode_exe'],
        mcp_entrypoint=str(HERE/'opencode_mcp_entrypoint.py'))
    control=[None]
    def command_guard(command):
        if control[0] is None:raise RuntimeError('selected native command guard not attached')
        control[0].selected(command)
    factory=BackendFactory(factory_profile,source_sha,
        lambda:read('opencode-backend-start.private.json'),lambda v:save('opencode-backend-start.private.json',v),
        guard,identity,command_guard,admission,read_fixed_machine_slot,job_module.WindowsJob,api,verify_private)
    def enrolled():
        state=control_state()
        if type(state) is not dict or state.get('phase')!='native-fence-active' or state.get('owner') is None:
            raise RuntimeError('actual selected authority fence missing')
        return dict(owner=copy.deepcopy(state['owner']),native=native,
            controller_source_manifest_sha256=source_sha,execution_plan_sha256=profile['execution_plan_sha256'],
            holding_profile_sha256=holding_sha,api_port=profile['api_port'],native_port=profile['native_port'])
    def kernel():
        return NativeKernel(job_module,str(APLEXER),native,host_kernel,profile['guardian_kernel'],
            enrolled()['owner'],factory.backend,factory.job,guard)()
    profile_writer=ProfileWriter(directory,load_private,writer.save,verify_private,identity,kernel,lambda:plan)
    def custody(private,pin):
        return WinCustody(job_module,factory.job,factory.backend,native,private['owner'],
            directory/'opencode-controller.private.json',pin,private['kernel']['processes'],
            private['kernel']['guardian'],lambda:private['session_id'])
    def history(old):
        return api.request(factory.backend,factory.job,profile['native_port'],old['native_password'],
            'GET','/session/'+old['session_id']+'/message')
    start=RootStart(factory,enrolled,lambda:profile['controller_credential'],profile_writer,
        lambda:load_private(directory/'opencode-controller.private.json'),custody,history,
        lambda:read('opencode-root-start-receipt.private.json'),lambda v:save('opencode-root-start-receipt.private.json',v),
        command_guard,source_sha)
    class Observe:
        def execute(self,command):
            guard();elected=enrolled();binding=load_private(directory/'opencode-controller-binding.private.json')
            runtime,backend_query,job_query=construct(directory,binding['profile_sha256'],source_sha)
            try:
                channel=ObservationChannel(native,elected['owner'],source_sha,runtime.journal.selected_context,
                    runtime.input.history,runtime.kernel,command_guard,batch_reader=runtime.journal.selected_observation)
                return channel.execute(command)
            finally:backend_query.close();job_query.close()
    checks=[None];active_check=[None]
    def check(command):
        if read('opencode-root-start-receipt.private.json') is None:
            raise RuntimeError('genuine root-start session binding must precede model input')
        private=load_private(directory/'opencode-controller.private.json')
        binding=load_private(directory/'opencode-controller-binding.private.json')
        if (private.get('owner')!=command['owner'] or digest(directory/'opencode-controller.private.json')!=binding['profile_sha256']):
            raise RuntimeError('actual elected controller profile differs')
        current_custody=custody(private,binding['profile_sha256'])
        current_custody()
        if checks[0] is None:
            authority=AuthorityTransport(plan['authority']['origin'],private['controller_credential'],
                {k:pathlib.Path(v) for k,v in plan['authority']['certificate_paths'].items()},
                plan['authority']['certificate_pins'],guard)
            startup=FullStartup(HERE/'startup-full');startup.documents()
            old=read('opencode-backend-start.private.json')
            def owned_history():
                before=current_custody();value=history(old)
                if current_custody()!=before:raise RuntimeError('native kernel changed during paid dispatcher history read')
                return value
            def native_post(path,body):
                if path!='/session/'+private['session_id']+'/prompt_async':
                    raise RuntimeError('fixed own session prompt path differs')
                current_custody()
                def pre_effect():
                    guard();gate=read('opencode-provider-admission.private.json');now=time.time()
                    if (type(gate) is not dict or gate.get('launch_allowed') is not True or gate.get('physical_allowed') is not True
                        or gate.get('account_binding')!=profile['provider_account_binding']
                        or type(gate.get('valid_until')) not in (int,float) or not now<gate['valid_until']):
                        raise RuntimeError('actual cached provider/resource admission expired before prompt')
                    proof=checks[0].gate({'owner':private['owner']},'root-check')
                    if active_check[0] is None:raise RuntimeError('current native check dispatch missing')
                    command_guard(active_check[0])
                    if time.time()>proof['valid_until'] or time.time()>=gate['valid_until']:
                        raise RuntimeError('pre-spend authority/provider proof expired')
                return api.prompt_async(factory.backend,factory.job,private['native_port'],
                    private['native_password'],private['session_id'],body,pre_effect)
            def archive(value):
                pin=archive_digest(value);name=reply_archive_name(pin)
                previous=read(name)
                if previous is not None and previous!=value:raise RuntimeError('immutable reply archive differs')
                if previous is None:save(name,value)
                if read(name)!=value:raise RuntimeError('reply archive readback differs')
                return pin
            def archive_reader(pin):
                if type(pin) is not str or not re.fullmatch('[0-9a-f]{64}',pin):raise RuntimeError('fixed reply archive reference required')
                return read(reply_archive_name(pin))
            checks[0]=CheckDispatch(command['owner'],private['session_id'],profile['provider_account_binding'],
                private['controller_credential'],startup.instructions_sha256,authority,
                lambda:read('opencode-dispatch.private.json'),lambda v:save('opencode-dispatch.private.json',v),
                owned_history,native_post,admission,command_guard,current_custody,archive,archive_reader)
        if active_check[0] is not None:raise RuntimeError('concurrent native check dispatch held')
        active_check[0]=command
        try:return checks[0](command)
        finally:active_check[0]=None
    proof=RoleProof(profile,guard)
    def post_start_ready(command):
        from opencode_check_dispatch import quiescent
        command_guard(command);guard()
        binding=load_private(directory/'opencode-controller-binding.private.json')
        private=load_private(directory/'opencode-controller.private.json')
        if (private['owner']!=command['owner'] or private['source_manifest_sha256']!=source_sha
            or digest(directory/'opencode-controller.private.json')!=binding['profile_sha256']):
            raise RuntimeError('post-start actual controller/owner changed')
        current=custody(private,binding['profile_sha256']);before=current()
        old=read('opencode-backend-start.private.json');actual=history(old)
        if current()!=before:raise RuntimeError('post-start native kernel changed during history')
        command_guard(command)
        return quiescent(actual,private['session_id'])
    class Luna:
        def execute(self,command):
            # Called only by the fixed authenticated server cache refresh seam,
            # never a model tool or a periodic quota-probe loop.
            quota=load_module('opencode_luna_native_quota',BASE/'operational-runtime1/managed-host-binding3/win35_quota_gate.py',
                '4caabb544c50c9d00046300762de43b81355caa2b6429dda191cbed9a6a9f52f')
            module=LunaAdmission(native,enrolled()['owner'],plan['codex_exe'],plan['codex_sha256'],
                plan['luna_account_binding'],quota,lambda:digest(pathlib.Path(plan['codex_exe'])),command_guard,
                lambda v:save('opencode-luna-admission.private.json',v))
            return module.execute(command)
    result=NativeControl(profile,native,control_state,lambda v:save('opencode-native-control.private.json',v),
        guard,identity,proof,admission,start,Observe(),check=check,luna=Luna(),post_start_ready=post_start_ready)
    control[0]=result
    result.retained_factory=factory
    return result,guard
