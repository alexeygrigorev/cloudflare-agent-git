"""Same-Guardian fixed shell birth for death or preserving server permit.

No model/session call; native identity comes from Aplexer and actual startup
leaf. The predecessor archive/nonce intent is immutable and uncertainty never
replays spawn. Both logical reservation and inner native API slots must be free.
"""
import base64,copy,hashlib,json,pathlib,socket,subprocess,uuid

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def encoded(value):return json.dumps(value).encode()
def free_pair(port):
    if type(port) is not int or port not in (8813,8814):raise RuntimeError('fixed logical slot required')
    for selected in (port,port+2):
        with socket.socket() as probe:probe.bind(('127.0.0.1',selected))

class NativeFactory:
    def __init__(self,profile_path,source_root,plan,load,save,ensure,verify_process,source_guard,guardian):
        self.profile_path=pathlib.Path(profile_path);self.here=pathlib.Path(source_root);self.plan=plan
        self.load=load;self.save=save;self.ensure=ensure;self.verify=verify_process;self.guard=source_guard;self.guardian=guardian
    def prepare(self,permit):
        self.guard()
        if (permit.get('operation') not in ('fixed-native-factory','fixed-preserving-successor')
            or not permit.get('challenge') or type(permit.get('profile_sha256')) is not str):
            raise RuntimeError('authenticated fixed factory permit required')
        key=hashlib.sha256(permit['challenge'].encode()).hexdigest()
        preserving=permit['operation']=='fixed-preserving-successor'
        directory=self.profile_path.parent/'runtime/api-root'/(('preserving-' if preserving else 'recovery-')+key)
        holding_path=self.here/('opencode-holding-'+key+'.private.json')
        archive_path=self.here/('opencode-predecessor-'+key+'.private.json')
        if holding_path.exists():
            held=self.load(holding_path);pin=hashlib.sha256(encoded(held)).hexdigest()
            if sha(self.profile_path)!=pin:
                if sha(self.profile_path)!=permit['profile_sha256']:raise RuntimeError('foreign profile after factory intent')
                archive=self.load(archive_path)
                if (archive.get('sha256')!=permit['profile_sha256']
                    or base64.b64decode(archive['raw_base64'])!=self.profile_path.read_bytes()):
                    raise RuntimeError('exact predecessor archive differs')
                self.provision(directory)
                free_pair(held['api_port']);self.save(self.profile_path,held)
            if sha(self.profile_path)!=pin:raise RuntimeError('immutable holding write/readback differs')
            return dict(state_dir=str(directory),root_tag=held['root_tag'],holding_profile_sha256=pin)
        if sha(self.profile_path)!=permit['profile_sha256']:raise RuntimeError('current predecessor profile changed')
        old=self.load(self.profile_path)
        if (old.get('runtime_mode')!='api-root' or old.get('actor')!=permit['owner']['actor']
            or old.get('generation')!=permit['owner']['generation']):raise RuntimeError('predecessor owner differs')
        old_port=old.get('api_port',8813)
        port=permit.get('new_api_port') if preserving else old_port
        if preserving and (permit.get('predecessor_api_port')!=old_port or {old_port,port}!={8813,8814}):
            raise RuntimeError('opposite preserving slot differs')
        free_pair(port)
        from opencode_full_startup import FullStartup
        startup=FullStartup(self.here/'startup-full');startup.documents()
        fields=('project','authority_url','ca_certificate','client_certificate','client_key','python_exe',
            'python_sha256','aplexer_exe','aplexer_sha256','workspace','expected_host')
        held={field:old[field] for field in fields}
        held.update(runtime_mode='api-root',root_runtime_kind='opencode-native-v1',actor=None,generation=None,
            owner=None,credential=None,state_dir=str(directory),api_port=port,native_port=port+2,
            root_tag='win35-root-capsule-api-'+('preserving-' if preserving else 'recovery-')+key[:16],
            deployment_stage='unenrolled-no-model-holding',host_script=str(self.here/'opencode_native_shell.py'),
            host_script_sha256=self.plan['native_shell_sha256'],
            controller_source_manifest_sha256=self.plan['controller_source_manifest_sha256'],
            execution_plan_sha256=self.plan['execution_plan_sha256'],
            provider_account_binding=self.plan['provider_account_binding'],guardian_kernel=self.guardian(),
            instruction_read_files=[dict(path=str(self.here/'startup-full'/e['path']),sha256=e['sha256']) for e in startup.entries])
        archive=dict(v=1,sha256=sha(self.profile_path),raw_base64=base64.b64encode(self.profile_path.read_bytes()).decode())
        if archive_path.exists():
            if self.load(archive_path)!=archive:raise RuntimeError('different predecessor archive preserved')
        else:self.save(archive_path,archive)
        self.save(holding_path,held)
        self.provision(directory)
        self.guard();free_pair(port);self.save(self.profile_path,held)
        pin=hashlib.sha256(encoded(held)).hexdigest()
        if sha(self.profile_path)!=pin:raise RuntimeError('factory holding readback differs')
        return dict(state_dir=str(directory),root_tag=held['root_tag'],holding_profile_sha256=pin)
    def provision(self,directory):
        self.ensure(directory)
        names={'opencode-config','opencode-data','opencode-cache','opencode-state','opencode-controller.lock'}
        if any(p.name not in names for p in directory.iterdir()):raise RuntimeError('unknown successor leaf preserved')
        for name in names-{'opencode-controller.lock'}:
            path=directory/name;self.ensure(path)
            if any(path.iterdir()):raise RuntimeError('unknown native environment preserved before birth')
        lock=directory/'opencode-controller.lock'
        if lock.exists():
            if lock.read_bytes()!=b'0':raise RuntimeError('fixed preprovisioned lock differs')
        else:self.save(lock,0)
    def spawn(self,holding):
        self.guard();profile=self.load(self.profile_path)
        if (sha(self.profile_path)!=holding['holding_profile_sha256'] or profile.get('actor') is not None
            or profile['state_dir']!=holding['state_dir'] or profile['root_tag']!=holding['root_tag']):
            raise RuntimeError('genuine holding profile differs')
        free_pair(profile['api_port'])
        for field in ('python','aplexer'):
            if sha(pathlib.Path(profile[field+'_exe']))!=profile[field+'_sha256']:raise RuntimeError('fixed native executable changed')
        if sha(pathlib.Path(profile['host_script']))!=profile['host_script_sha256']:raise RuntimeError('native shell changed')
        from opencode_native_kernel import rows
        catalog=json.loads(subprocess.check_output([profile['aplexer_exe'],'list','--all','--json'],text=True,timeout=15))
        if any(r.get('tag')==holding['root_tag'] for r in rows(catalog)):raise RuntimeError('native already exists; reconcile only')
        response=subprocess.run([profile['aplexer_exe'],'start','--workspace',profile['workspace'],'--tag',holding['root_tag'],
            '--engine','shell','--no-skip-permissions','--memory','1500M','--pids','100','--json','--',
            profile['python_exe'],'-I','-S',profile['host_script'],profile['controller_source_manifest_sha256']],
            capture_output=True,text=True,timeout=30,check=True)
        result=json.loads(response.stdout);uuid.UUID(result['id']);return result
    def reconcile(self,holding,response):
        self.guard();profile=self.load(self.profile_path)
        if sha(self.profile_path)!=holding['holding_profile_sha256']:raise RuntimeError('holding changed during native reconcile')
        from opencode_native_kernel import rows
        catalog=json.loads(subprocess.check_output([profile['aplexer_exe'],'list','--all','--json'],text=True,timeout=15))
        matches=[r for r in rows(catalog) if r.get('tag')==holding['root_tag'] and
            r.get('workspace','').replace('\\','/').lower()==profile['workspace'].replace('\\','/').lower()]
        if len(matches)!=1:raise RuntimeError('exact native capsule uncertain')
        native=matches[0];uuid.UUID(native['id'])
        if response is not None and response.get('id')!=native['id']:raise RuntimeError('native response differs')
        path=pathlib.Path(holding['state_dir'])/('native-startup-'+native['id']+'.private.json')
        leaf=self.load(path);kernel=leaf['kernel'];observed=self.verify(kernel['pid'])
        if (leaf.get('runtime_discriminator')!='opencode-native-v1' or leaf.get('model_started') is not False
            or leaf['native'].get('id')!=native['id'] or leaf['native'].get('tag')!=holding['root_tag']
            or leaf.get('generation')!='win32:'+str(kernel['pid'])+':'+str(kernel['creation_filetime'])
            or observed['creation_filetime']!=kernel['creation_filetime'] or native.get('worker_alive') is not True
            or leaf['host']!=profile['expected_host']):raise RuntimeError('actual native leaf/kernel differs')
        return dict(actual_leaf_verified=True,actor=native['id'],generation=leaf['generation'],host=leaf['host'],
            root_tag=holding['root_tag'],whoami=leaf['native'],kernel=kernel,leaf_sha256=sha(path),
            holding_profile_sha256=holding['holding_profile_sha256'],state_dir=holding['state_dir'],
            api_port=profile['api_port'],native_port=profile['native_port'],runtime_discriminator='opencode-native-v1')
