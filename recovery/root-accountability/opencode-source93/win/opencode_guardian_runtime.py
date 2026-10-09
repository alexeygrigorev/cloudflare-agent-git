"""One existing Guardian Task: fenced keeper, native observation and recovery.

The cold plan and actual Task/SID/Session2 are mandatory before effects. Root
process status never implies authority. Query handles survive owned family death
and remain retained for living shadows; unknown/protected state is a hold.
"""
import copy,hashlib,json,os,pathlib,re,sys,time

HERE=pathlib.Path(__file__).resolve().parent
BASE=pathlib.Path('C:/Users/User/git/cloudflare-agent-git/.local/win35-root-bootstrap')

class NativePending(RuntimeError):pass

def opencode_checkpoint(session_id,history_receipt_sha256):
    return dict(discriminator='opencode-native-v1',session_id=session_id,
        provider_turn_state='completed',pending_tool_count=0,
        history_receipt_sha256=history_receipt_sha256,protected_state='clear')

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def task_matches(actual,planned):
    from opencode_task_adoption import normalized
    return (normalized(actual)==normalized(planned)
        and actual['arguments']==planned['arguments'] and actual['enabled'] is True
        and planned['enabled'] is True)

def require_execution_plan(plan,source_pin):
    if (plan.get('controller_source_manifest_sha256')!=source_pin
        or plan.get('authorization')!='owned-opencode-root-cold-trial'
        or plan.get('plan_execution_authorized') is not True or not plan.get('execution_pin')):
        raise RuntimeError('reviewed fixed cold plan absent')

def bootstrap(source_pin):
    if not sys.flags.isolated or not sys.flags.no_site or not re.fullmatch('[0-9a-f]{64}',source_pin):
        raise RuntimeError('fixed isolated Guardian/source required')
    manifest=HERE/'source-pins.json'
    def source():
        if sha(manifest)!=source_pin:raise RuntimeError('Guardian source manifest changed')
        for entry in json.loads(manifest.read_bytes())['entries']:
            relative=pathlib.PurePosixPath(entry['path'])
            if relative.is_absolute() or '..' in relative.parts:raise RuntimeError('source path escape')
            file=HERE.joinpath(*relative.parts)
            if any(p.is_symlink() or getattr(p.stat(),'st_file_attributes',0)&0x400 for p in (file,*file.parents)):
                raise RuntimeError('Guardian source reparse held')
            if sha(file)!=entry['sha256']:raise RuntimeError('Guardian source file changed')
    source();sys.path.insert(0,str(HERE))
    return source

class Hooks:
    def __init__(self,plan,plan_pin,source_pin,source,load,writer,job_module,helpers,modules):
        self.plan=plan;self.plan_pin=plan_pin;self.source_pin=source_pin;self.source=source
        self.load=load;self.writer=writer;self.job_module=job_module;self.helpers=helpers;self.modules=modules
        self.profile_path=BASE/'api-runtime.private.json';self.directory=HERE/'guardian-private'
        writer.ensure_private_directory(self.directory)
        self.guardian=helpers.native_context(os.getpid())
        task=helpers.actual_task_custody()
        action=hashlib.sha256(json.dumps({k:task[k] for k in ('execute','arguments','working_directory')},sort_keys=True,separators=(',',':')).encode()).hexdigest()
        if (not task_matches(task,plan['task_custody']) or action!=plan['task_action_sha256'] or task['enabled'] is not True
            or task['sid']!=self.guardian['user_sid'] or task['logon_type']!='Interactive'
            or task['run_level']!='Limited' or task['multiple_instances']!='IgnoreNew'
            or self.guardian['session_id']!=2 or self.guardian['image'].replace('\\','/').lower()!=plan['python_exe'].replace('\\','/').lower()
            or not helpers.owned_script_command(self.guardian['command'],HERE/'opencode_guardian_runtime.py')):
            raise RuntimeError('actual single Guardian Task/kernel custody differs')
        self.guardian.update(source_sha256=sha(HERE/'opencode_guardian_runtime.py'),task_action_sha256=action)
        self.credential=load(BASE/'runtime/api-root/caretaker-recovery.credentials.private.json')
        if self.credential.get('scope')!='fixed-host-caretaker':raise RuntimeError('fixed separate caretaker scope required')
        self.retained={};self.current=None;self.keeper=None;self.keeper_key=None;self.next_keeper=0
    def guard(self):
        self.source()
        if sha(HERE/'cold-plan.private.json')!=self.plan_pin:raise RuntimeError('Guardian cold plan changed')
        if sha(BASE/'runtime.private.json')!='a301bb1227c734c93622d9a5428a55248e3e665c9032120e5268f1adcb0b01ac':
            raise RuntimeError('protected legacy changed')
        actual=self.helpers.native_context(self.guardian['pid'])
        if any(actual.get(k)!=self.guardian[k] for k in ('pid','creation_filetime','session_id','user_sid')):
            raise RuntimeError('actual outside Guardian changed')
    def current_profile(self):
        self.guard();p=self.load(self.profile_path)
        if p.get('runtime_mode')!='api-root':raise RuntimeError('fixed root profile required')
        if p.get('root_runtime_kind')!='opencode-native-v1':
            if sha(self.profile_path)!=self.plan['predecessor_profile_sha256']:
                raise RuntimeError('unaccepted predecessor profile preserved')
        elif (p.get('controller_source_manifest_sha256')!=self.source_pin
            or p.get('execution_plan_sha256')!=self.plan_pin):raise RuntimeError('new controller plan differs')
        return p
    def host(self,operation,**fields):
        self.guard();result=self.helpers.host_request(self.current_profile(),self.credential['credential'],dict(op=operation,**fields))
        self.guard();return result
    def path_read(self,path):return self.load(path) if path.exists() else None
    def read_recovery(self):
        value=self.path_read(self.directory/'recovery.private.json')
        return None if type(value) is dict and value.get('phase')=='archived-completed' else value
    def write_recovery(self,value):self.writer.save(self.directory/'recovery.private.json',value)
    def read_factory(self):
        value=self.read_recovery()
        return None if type(value) is dict and value.get('phase')=='completed' else value
    def native_alive(self,p):
        if p.get('actor') is None:return False
        leaf=self.load(pathlib.Path(p['state_dir'])/('native-startup-'+p['actor']+'.private.json'))
        if leaf['native']['id']!=p['actor'] or leaf['generation']!=p['generation']:raise RuntimeError('native leaf owner differs')
        state=self.job_module.recorded_process_state(leaf['kernel']['pid'],leaf['kernel']['creation_filetime'])
        if state not in ('alive','exited','original-exited-pid-reused'):raise RuntimeError('native liveness unknown')
        return state=='alive'
    def observation(self):
        p=self.current_profile();leaf=pathlib.Path(p['state_dir'])
        if p.get('root_runtime_kind')!='opencode-native-v1':return self.predecessor_observation(p)
        profile_path=leaf/'opencode-controller.private.json'
        if not profile_path.exists():return None
        private=self.load(profile_path);owner=private['owner'];kernel=private['kernel']
        key=(owner['actor'],owner['generation'],owner['epoch'],kernel['job_name'])
        if key not in self.retained:
            observer=self.modules['windows_observation'].JobObservation(self.job_module.kernel(),self.job_module.BasicAccounting,
                kernel['job_name'],kernel['backend'],self.job_module.current_process_binding(),self.job_module.recorded_process_state)
            self.retained[key]=dict(observer=observer,baseline=None,checkpoint=None,private=private,
                                   controller_profile_sha256=sha(profile_path),leaf=leaf)
        selected=self.retained[key];self.current=selected
        from opencode_win_constructor import QueryJob,QueryProcess
        from opencode_win_custody import WinCustody
        from opencode_backend_api import BackendAPI
        from opencode_check_dispatch import quiescent
        qjob=QueryJob(self.job_module,kernel['job_name']);qprocess=QueryProcess(self.job_module,qjob,kernel['backend'])
        try:
            custody=WinCustody(self.job_module,qjob,qprocess,private['native'],owner,profile_path,selected['controller_profile_sha256'],
                kernel['processes'],self.job_module.current_process_binding(),lambda:private['session_id'])
            before=custody()
            history=BackendAPI(self.job_module,self.guard).request(qprocess,qjob,private['native_port'],private['native_password'],
                'GET','/session/'+private['session_id']+'/message')
            after=custody()
            if before!=after:raise RuntimeError('actual native kernel changed across observation')
            if not quiescent(history,private['session_id']):raise NativePending('actual native turn incomplete; preserve')
            history_pin=hashlib.sha256(json.dumps(history,sort_keys=True,separators=(',',':')).encode()).hexdigest()
            checkpoint=opencode_checkpoint(private['session_id'],history_pin)
            baseline=dict(owner=owner,host=p['expected_host'],profile_sha256=sha(self.profile_path),
                guardian={k:self.guardian[k] for k in ('pid','creation_filetime','session_id','user_sid','task_action_sha256','source_sha256')},
                native=kernel['native'],model=dict(owner=owner,backend=kernel['backend'],job=dict(name=kernel['job_name'],session_id=2)),checkpoint=checkpoint)
            selected.update(baseline=baseline,checkpoint=checkpoint)
            self.writer.save(leaf/'opencode-guardian-checkpoint.private.json',dict(v=1,baseline=baseline,
                controller_profile_sha256=selected['controller_profile_sha256'],observed_at=time.time()))
            return selected
        finally:qprocess.close();qjob.close()
    def predecessor_observation(self,p):
        # Exact fixed predecessor read only. No resume, input, quota query or
        # state normalization; all SDK facts must come from the current backend.
        from opencode_win_constructor import QueryJob,QueryProcess
        from opencode_native_kernel import rows
        import subprocess
        leaf=pathlib.Path(p['state_dir']);state=self.load(leaf/'root-runtime.json');owner=state['thread_owner']
        if (state.get('provider_pending_tools')!={} or state.get('provider_event_conflict')
            or any(state.get(k) for k in ('frontend_pid','viewer_pid','launch_pending'))):raise RuntimeError('predecessor protected')
        native_leaf=self.load(leaf/('native-startup-'+p['actor']+'.private.json'))
        catalog=json.loads(subprocess.check_output([p['aplexer_exe'],'list','--all','--json'],text=True,timeout=15))
        matches=[r for r in rows(catalog) if r.get('id')==p['actor'] and r.get('tag')==p['root_tag']]
        if len(matches)!=1 or matches[0].get('worker_alive') is not True:raise RuntimeError('predecessor native unknown')
        row=matches[0];native=dict(id=p['actor'])
        for name,pid in [('worker',row['worker_pid']),('workload',row['workload_pid']),('host_process',native_leaf['kernel']['pid'])]:
            actual=self.helpers.native_context(pid);native[name]={k:actual[k] for k in ('pid','creation_filetime')}
        backend=dict(pid=state['pid'],creation_filetime=state['process_creation_filetime'])
        key=(owner['actor'],owner['generation'],owner['epoch'],state['job_name'])
        if key not in self.retained:
            observer=self.modules['windows_observation'].JobObservation(self.job_module.kernel(),self.job_module.BasicAccounting,
                state['job_name'],backend,self.job_module.current_process_binding(),self.job_module.recorded_process_state)
            self.retained[key]=dict(observer=observer,baseline=None,checkpoint=None,leaf=leaf)
        selected=self.retained[key];self.current=selected
        def read_sdk(cid):
            qjob=QueryJob(self.job_module,state['job_name']);qprocess=QueryProcess(self.job_module,qjob,backend)
            token=self.load(leaf/'backend-capability.private')['token']
            rpc=None
            try:
                rpc=self.modules['legacy_rpc'].AppServerRPC('ws://127.0.0.1:'+str(p.get('api_port',8813)),token,
                    lambda sock:self.job_module.verify_backend_connection(sock,qprocess,p.get('api_port',8813)),timeout=8)
                return rpc.call('thread/read',{'threadId':cid,'includeTurns':True})['thread']
            finally:
                if rpc is not None:rpc.close()
                qprocess.close();qjob.close()
        thread=read_sdk(state['conversation_id']);latest=thread['turns'][-1]
        if (thread.get('id')!=state['conversation_id'] or latest.get('id')!=state.get('provider_turn_id')
            or latest.get('status')!='completed'):raise RuntimeError('actual predecessor SDK incomplete')
        checkpoint=dict(thread_id=state['conversation_id'],provider_turn_state='completed',pending_tool_count=0,
            history_receipt_sha256=state['api_history_receipt_sha256'],protected_state='clear')
        baseline=dict(owner=owner,host=p['expected_host'],profile_sha256=sha(self.profile_path),native=native,
            guardian={k:self.guardian[k] for k in ('pid','creation_filetime','session_id','user_sid','task_action_sha256','source_sha256')},
            model=dict(owner=owner,backend=backend,job=dict(name=state['job_name'],session_id=2)),checkpoint=checkpoint)
        selected.update(baseline=baseline,checkpoint=checkpoint,read_sdk=read_sdk,state=lambda:self.load(leaf/'root-runtime.json'))
        return selected
    def observe_live(self):
        p=self.current_profile()
        if p.get('root_runtime_kind')=='opencode-native-v1':
            for op in ('opencode-observe','opencode-activate','opencode-reply','root-luna-hold'):
                try:self.host(op)
                except Exception as error:
                    self.writer.save(self.directory/(op+'-failure.private.json'),dict(observed_at=time.time(),phase='refused-or-pending',error_type=type(error).__name__))
        try:selected=self.observation()
        except NativePending:return # outside native collection above remains independent of final
        if selected is not None:self.host('observe-baseline',baseline=selected['baseline'])
    def server_preserving_authorization(self):
        p=self.current_profile()
        if p.get('root_runtime_kind')=='opencode-native-v1':self.observe_live()
        try:selected=self.observation()
        except NativePending:return None
        if selected is None:return None
        if p.get('root_runtime_kind')!='opencode-native-v1':
            from opencode_native_factory import free_pair
            observer=selected['observer']
            def slot_free(port):
                free_pair(port);return True
            collector=self.modules['preserving_observation'].PreservingObservation(selected['baseline'],
                self.job_module.recorded_process_state,observer.query,observer.outside,selected['read_sdk'],
                selected['state'],slot_free,lambda ref,v:self.writer.save(self.directory/('preserving-'+ref+'.private.json'),v))
            receipt=collector.collect(p.get('api_port',8813),hashlib.sha256(str(selected['baseline']).encode()).hexdigest())
            self.host('preserving-observe',receipt=receipt)
        else:
            # New OpenCode living retirement must be resolved through the
            # server's typed current-session observer; no Codex SDK disguise.
            self.host('opencode-observe')
        result=self.host('preserving-challenge')
        if result=={'status':'no-preserving-permit'}:return None
        if type(result.get('permit')) is not dict or type(result.get('expected')) is not dict:
            raise RuntimeError('fixed preserving permit missing')
        self.modules['preserving_protocol'].validate(result['permit'],result['expected']);return result
    def supervise_recover(self):
        p=self.current_profile()
        if p.get('root_runtime_kind')!='opencode-native-v1' or p.get('actor') is None:return 'keeper-not-enrolled'
        from opencode_keeper import Keeper
        from opencode_role_transport import RoleTransport
        key=(p['actor'],p['generation'],p['state_dir'])
        if key!=self.keeper_key:
            directory=pathlib.Path(p['state_dir']);path=directory/'opencode-keeper.private.json'
            self.keeper=Keeper(p['owner'],RoleTransport(p,self.guard,self.plan['server_certificate_sha256']),
                lambda:self.path_read(path),lambda v:self.writer.save(path,v),self.guard)
            self.keeper_key=key;self.next_keeper=0
        if time.monotonic()<self.next_keeper:return 'keeper-completed'
        self.next_keeper=time.monotonic()+20
        try:
            result=self.keeper.step();self.writer.save(self.directory/'last-keeper.private.json',dict(observed_at=time.time(),result=result))
            return 'keeper-completed'
        except Exception as error:
            self.writer.save(self.directory/'last-keeper.private.json',dict(observed_at=time.time(),phase='refused-or-uncertain',error_type=type(error).__name__))
            return 'keeper-failed'
    def server_challenge(self):return self.host('challenge')
    def observe_death(self,challenge):
        if self.current is None or self.current.get('checkpoint') is None:raise RuntimeError('retained current death baseline missing')
        selected=self.current;observer=selected['observer']
        monitor=self.modules['death_monitor'].DeathMonitor(selected['baseline'],observer.query,self.job_module.recorded_process_state,
            lambda:{k:self.guardian[k] for k in ('pid','creation_filetime','session_id','user_sid','source_sha256','task_action_sha256')},
            observer.outside,lambda:selected['checkpoint'],self.read_factory)
        return monitor.observe({'nonce':challenge['challenge'],'owner':challenge['baseline']['owner']})
    def server_reconcile(self,challenge,evidence):return self.host('reconcile',challenge=challenge['challenge'],receipt=evidence)
    def perform_factory(self,permit,expected):
        from opencode_native_factory import NativeFactory
        key=hashlib.sha256(permit['challenge'].encode()).hexdigest();path=self.directory/('factory-'+key+'.private.json')
        class Store:
            def read(inner):return self.path_read(path)
            def write(inner,value):self.writer.save(path,value)
        bound=dict(self.plan,execution_plan_sha256=self.plan_pin)
        factory=NativeFactory(self.profile_path,HERE,bound,self.load,self.writer.save,self.writer.ensure_private_directory,
            self.helpers.native_context,self.guard,lambda:{k:self.guardian[k] for k in ('pid','creation_filetime')})
        protocol=self.modules['preserving_protocol'] if permit['operation']=='fixed-preserving-successor' else self.modules['factory_protocol']
        return protocol.perform(permit,expected,Store(),factory.prepare,factory.spawn,factory.reconcile)
    def server_enroll(self,challenge,successor):
        op='preserving-reconcile' if pathlib.Path(successor['state_dir']).name.startswith('preserving-') else 'reconcile'
        return self.host(op,challenge=challenge,successor=successor)
    def prepare_credential_merge(self,handoff,successor):
        p=self.current_profile();credential=handoff.get('credential')
        if (handoff.get('status')!='enrolled_held_api_candidate' or handoff.get('actor')!=successor['actor']
            or handoff.get('generation')!=successor['generation'] or handoff.get('owner_is_candidate_context_only') is not True
            or handoff.get('controller_scope')!='fixed-root-controller' or type(credential) is not dict
            or set(credential)!={'identity_id','token'} or not all(type(v) is str and v for v in credential.values())):
            raise RuntimeError('actual new native/controller scope issuance missing')
        if sha(self.profile_path)!=successor['holding_profile_sha256']:raise RuntimeError('holding merge before pin differs')
        candidate=dict(project=p['project'],role='root',actor=successor['actor'],generation=successor['generation'],epoch=1)
        if handoff.get('owner')!=candidate:raise RuntimeError('new candidate context differs')
        profile=dict(p,actor=candidate['actor'],generation=candidate['generation'],owner=candidate,credential=credential,
            native_actor=copy.deepcopy(successor['whoami']),
            controller_credential=dict(credential,scope='fixed-root-controller'),deployment_stage='enrolled-held-api-candidate')
        return dict(before=successor['holding_profile_sha256'],after=hashlib.sha256(json.dumps(profile).encode()).hexdigest(),profile=profile)
    def complete_credential_merge(self,merge,successor):
        if not self.successor_live(successor):raise RuntimeError('new native leaf exited before merge')
        if sha(self.profile_path)==merge['after']:return
        if sha(self.profile_path)!=merge['before']:raise RuntimeError('foreign profile merge preserved')
        self.writer.save(self.profile_path,merge['profile'])
        if sha(self.profile_path)!=merge['after']:raise RuntimeError('credential merge readback differs')
    def successor_live(self,successor):
        path=pathlib.Path(successor['state_dir'])/('native-startup-'+successor['actor']+'.private.json')
        if not path.exists():return False
        leaf=self.load(path)
        if sha(path)!=successor['leaf_sha256'] or leaf['generation']!=successor['generation']:raise RuntimeError('new native leaf differs')
        return self.job_module.recorded_process_state(leaf['kernel']['pid'],leaf['kernel']['creation_filetime'])=='alive'
    def archive_completed(self,record):
        key=hashlib.sha256(record['permit']['challenge'].encode()).hexdigest()
        self.writer.save(self.directory/('completed-'+key+'.private.json'),record)
        self.write_recovery(dict(record,phase='archived-completed'))

def main():
    if sys.argv[1:2]!=['Guard'] or len(sys.argv)!=3:raise RuntimeError('fixed Guardian Guard/source arguments required')
    source_pin=sys.argv[2];source=bootstrap(source_pin)
    from opencode_win_constructor import load_private,load_module,JOB_PIN,WRITER_PIN
    plan_path=HERE/'cold-plan.private.json';plan=load_private(plan_path);plan_pin=sha(plan_path)
    require_execution_plan(plan,source_pin)
    job=load_module('opencode_guardian_job',BASE/'next12/win35_root_job.py',JOB_PIN)
    writer=load_module('opencode_guardian_writer',HERE/'opencode_private_writer.py',WRITER_PIN)
    dependency_paths={
        'helpers':BASE/'host-recovery-consumer4/guardian_runtime.py',
        'windows_observation':BASE/'host-recovery-consumer5/windows_observation.py',
        'death_monitor':BASE/'host-recovery-consumer5/death_monitor.py',
        'factory_protocol':BASE/'host-recovery-consumer5/factory_protocol.py',
        'preserving_protocol':BASE/'host-recovery-consumer5/preserving_protocol.py',
        'preserving_observation':BASE/'host-recovery-consumer5/preserving_observation.py',
        'recovery_driver':BASE/'host-recovery-consumer5/recovery_driver.py',
        'legacy_rpc':BASE/'next12/win35_root_rpc.py'}
    if set(plan.get('guardian_dependency_pins',{}))!=set(dependency_paths):raise RuntimeError('complete fixed Guardian dependencies required')
    modules={name:load_module('opencode_guardian_'+name,path,plan['guardian_dependency_pins'][name]) for name,path in dependency_paths.items()}
    hooks=Hooks(plan,plan_pin,source_pin,source,load_private,writer,job,modules['helpers'],modules)
    driver=modules['recovery_driver'].Driver(hooks)
    status_binding=dict(kernel=hooks.guardian,source_sha256=sha(HERE/'opencode_guardian_runtime.py'),authority_claimed=False)
    writer.save(hooks.directory/'status.private.json',dict(status_binding,phase='ready-before-recovery',observed_at=time.time()))
    while True:
        try:
            hooks.guard();phase=driver.step();hooks.guard()
            writer.save(hooks.directory/'status.private.json',dict(status_binding,phase=phase,observed_at=time.time()))
        except Exception as error:
            writer.save(hooks.directory/'status.private.json',dict(status_binding,phase='held-reconcile-only',observed_at=time.time(),error_type=type(error).__name__))
        time.sleep(2)

if __name__=='__main__':
    try:main()
    except Exception:raise SystemExit('fixed reviewed Guardian held')
