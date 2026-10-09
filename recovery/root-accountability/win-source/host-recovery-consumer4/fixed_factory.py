"""Fixed successor paths and pinned native lifecycle; never launches a model.

All methods run only after an authenticated server permit and exact death proof.
The old API profile bytes/history are retained; the protected legacy profile is
never written. Unknown native start stays pending, never another start.
"""
import sys
if not sys.flags.isolated or not sys.flags.no_site:raise SystemExit('requires -I -S')
import pathlib,hashlib,json,base64,socket,subprocess,time,uuid
BASE=pathlib.Path('C:/Users/User/git/cloudflare-agent-git/.local/win35-root-bootstrap')
PROFILE=BASE/'api-runtime.private.json';HERE=BASE/'host-recovery-consumer4';CORE=BASE/'next12'
AUDIT_PIN='e90689b1c4348b4c7daf207fc014cac5e611ddc0a69acd3450f97c93ed65edb0'
PROMPT_PIN='33fe2dc0b1b492a2c6cd16d97de48c297ac55fbe6cf53e7c29de53e237de714f'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def serialized_hash(value):return hashlib.sha256(json.dumps(value).encode()).hexdigest()

class FixedFactory:
    def __init__(self,load,save,ensure,verify_process,pin,profile_path=PROFILE):
        if profile_path!=PROFILE:raise RuntimeError('fixed profile only')
        self.load,self.save,self.ensure,self.verify_process,self.pin=load,save,ensure,verify_process,pin
    def prepare(self,permit):
        self.pin(HERE/'principal-accountability-input.md',AUDIT_PIN)
        self.pin(HERE/'successor-first-turn.md',PROMPT_PIN)
        key=hashlib.sha256(permit['challenge'].encode()).hexdigest()
        directory=BASE/'runtime/api-root'/('recovery-'+key)
        self.ensure(directory)
        holding_file=HERE/('holding-'+key+'.private.json')
        old_file=HERE/('predecessor-'+key+'.private.json')
        if holding_file.exists():
            held=self.load(holding_file)
            expected=serialized_hash(held)
            if sha(PROFILE)==expected:return dict(state_dir=str(directory),root_tag=held['root_tag'],holding_profile_sha256=expected)
            # Only the exact old bytes can complete an interrupted profile write.
            if sha(PROFILE)!=permit['profile_sha256']:raise RuntimeError('foreign profile after preparation; preserve')
            prior=self.load(old_file)
            if prior.get('sha256')!=permit['profile_sha256'] or base64.b64decode(prior['raw_base64'])!=PROFILE.read_bytes():raise RuntimeError('predecessor archive mismatch')
            self.save(PROFILE,held)
            if sha(PROFILE)!=expected:raise RuntimeError('holding profile write mismatch')
            return dict(state_dir=str(directory),root_tag=held['root_tag'],holding_profile_sha256=expected)
        if sha(PROFILE)!=permit['profile_sha256']:raise RuntimeError('predecessor profile changed')
        old=self.load(PROFILE)
        if old.get('actor')!=permit['owner']['actor'] or old.get('generation')!=permit['owner']['generation'] or old.get('runtime_mode')!='api-root':raise RuntimeError('wrong predecessor binding')
        if any(directory.iterdir()):raise RuntimeError('unknown successor directory; preserve')
        held=dict(old,actor=None,generation=None,owner=None,credential=None,state_dir=str(directory),
            root_tag='win35-root-capsule-api-recovery-'+key[:16],deployment_stage='unenrolled-no-model-holding',
            root_prompt=str(HERE/'successor-first-turn.md'),root_prompt_sha256=PROMPT_PIN)
        held.update(host_script=str(CORE/'win35_root_host.py'),host_script_sha256='5a39a34e40d563dd86d939d54cca6be586e22214184f29f19e1d0a43959ef048',
            control_script=str(CORE/'win35_root_control.py'),control_sha256='42a74ae13e93b1e9e8f80b6b6738450533e87b548e68af8afcef0af70e29020c')
        entries=list(old['instruction_read_files'])
        audit=dict(path=str(HERE/'principal-accountability-input.md'),sha256=AUDIT_PIN)
        existing=[e for e in entries if e['path']==audit['path']]
        if existing and existing!=[audit]:raise RuntimeError('unexpected predecessor audit alias')
        if not existing:entries.append(audit)
        held['instruction_read_files']=entries
        archived=dict(v=1,sha256=sha(PROFILE),raw_base64=base64.b64encode(PROFILE.read_bytes()).decode())
        if old_file.exists():
            if self.load(old_file)!=archived:raise RuntimeError('foreign predecessor archive')
        else:self.save(old_file,archived)
        self.save(holding_file,held) # Durable expected after-state BEFORE replacing profile.
        self.save(PROFILE,held)
        return dict(state_dir=str(directory),root_tag=held['root_tag'],holding_profile_sha256=sha(PROFILE))
    def spawn(self,holding):
        profile=self.load(PROFILE)
        if sha(PROFILE)!=holding['holding_profile_sha256'] or profile.get('actor') is not None or profile['state_dir']!=holding['state_dir'] or profile['root_tag']!=holding['root_tag']:raise RuntimeError('holding profile drift')
        for field in ('python','aplexer'):
            self.pin(profile[field+'_exe'],profile[field+'_sha256'])
        self.pin(profile['host_script'],profile['host_script_sha256'])
        if pathlib.Path(profile['host_script'])!=CORE/'win35_root_host.py':raise RuntimeError('fixed accepted host source required')
        with socket.socket() as port:port.bind(('127.0.0.1',8813))
        catalog=json.loads(subprocess.check_output([profile['aplexer_exe'],'list','--all','--json'],text=True,timeout=15))
        if any(row.get('tag')==holding['root_tag'] for row in rows(catalog)):raise RuntimeError('successor native already exists; reconcile')
        result=subprocess.run([profile['aplexer_exe'],'start','--workspace',profile['workspace'],'--tag',profile['root_tag'],
            '--engine','shell','--no-skip-permissions','--memory','1500M','--pids','100','--json','--',profile['python_exe'],profile['host_script']],capture_output=True,text=True,timeout=30,check=True)
        response=json.loads(result.stdout);uuid.UUID(response['id']);return response
    def reconcile(self,holding,response):
        profile=self.load(PROFILE);directory=pathlib.Path(holding['state_dir'])
        if sha(PROFILE)!=holding['holding_profile_sha256']:raise RuntimeError('holding profile changed during reconcile')
        self.pin(profile['aplexer_exe'],profile['aplexer_sha256'])
        catalog=json.loads(subprocess.check_output([profile['aplexer_exe'],'list','--all','--json'],text=True,timeout=15))
        candidates=[r for r in rows(catalog) if r.get('tag')==holding['root_tag'] and r.get('workspace','').replace('\\','/').lower()==profile['workspace'].replace('\\','/').lower()]
        if len(candidates)!=1:raise RuntimeError('uncertain native factory; preserve')
        native=candidates[0];uuid.UUID(native['id'])
        if response is not None and native['id']!=response.get('id'):raise RuntimeError('native response/capture mismatch')
        leaf_path=directory/('native-startup-'+native['id']+'.private.json')
        if not leaf_path.exists():raise RuntimeError('actual startup leaf pending; reconcile later')
        leaf=self.load(leaf_path);kernel=leaf['kernel']
        actual=self.verify_process(kernel['pid'])
        if (leaf['native']['id']!=native['id'] or leaf.get('model_started') is not False
            or leaf['native']['tag']!=holding['root_tag'] or leaf['generation']!='win32:'+str(kernel['pid'])+':'+str(kernel['creation_filetime'])
            or actual['creation_filetime']!=kernel['creation_filetime'] or native.get('worker_alive') is not True):raise RuntimeError('genuine native leaf/custody mismatch')
        if leaf['host']!=profile['expected_host'] or leaf['native'].get('workspace','').replace('\\','/').lower()!=profile['workspace'].replace('\\','/').lower():raise RuntimeError('native host/workspace mismatch')
        return dict(actual_leaf_verified=True,actor=native['id'],generation=leaf['generation'],host=leaf['host'],root_tag=holding['root_tag'],
            whoami=leaf['native'],kernel=kernel,leaf_sha256=sha(leaf_path),holding_profile_sha256=holding['holding_profile_sha256'],state_dir=holding['state_dir'])

def rows(value):
    if isinstance(value,list):
        for x in value:yield from rows(x)
    elif isinstance(value,dict):
        yield value
        for x in value.values():
            if isinstance(x,(dict,list)):yield from rows(x)
