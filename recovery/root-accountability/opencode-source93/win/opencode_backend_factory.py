"""Fixed root-start backend/session stage, with no model prompt submission.

The native shell has already been born/enrolled. The existing authority's
root-start command and activation fence select this owner. Guardian retains
the new Job; failure never kills a predecessor or replays a pending start.
"""
import copy,json,os,pathlib,re,secrets,time,threading

class BackendFactory:
    def __init__(self,profile,source_sha256,read,save,source_guard,identity_guard,
                 command_guard,admission,provider_reader,job_factory,native_api,
                 private_leaf_verify,clock=time.time):
        self.profile=profile;self.source_sha256=source_sha256;self.read=read;self.save=save
        self.source=source_guard;self.identity=identity_guard;self.command_guard=command_guard
        self.admission=admission;self.provider_reader=provider_reader;self.job_factory=job_factory
        self.api=native_api;self.verify=private_leaf_verify;self.clock=clock;self.lock=threading.Lock()
        self.job=None;self.backend=None
    def command(self,command):
        if (type(command) is not dict or command.get('operation')!='root-start'
            or command.get('payload')!={} or command.get('owner')!=self.profile['owner']
            or not command.get('key')):
            raise RuntimeError('existing fixed current-owner root-start required')
        self.source();self.identity(self.profile);self.command_guard(command)
    def start(self,command):
        self.command(command)
        old=self.read()
        if old is not None:
            # Only the actual retained native handles/history can reconcile a
            # previous attempt. A persisted boolean cannot authorize re-spawn.
            raise RuntimeError('native backend start already reserved; reconcile only')
        gate=self.admission();now=self.clock()
        if (type(gate) is not dict or gate.get('provider')!='zai-coding-plan'
            or gate.get('model')!='glm-5.3-flash' or gate.get('launch_allowed') is not True
            or gate.get('physical_allowed') is not True or not gate.get('source_ref') or not gate.get('resource_ref')
            or gate.get('account_binding')!=self.profile['provider_account_binding']
            or type(gate.get('observed_at')) not in (int,float) or type(gate.get('valid_until')) not in (int,float)
            or not gate['observed_at']<=now<gate['valid_until']<=gate['observed_at']+30):
            raise RuntimeError('fresh own CodingPlan/resource admission denied before key/process')
        directory=pathlib.Path(self.profile['state_dir']);self.verify(directory)
        name=directory.name
        if not re.fullmatch(r'(preserving|recovery)-[0-9a-f]{64}',name):raise RuntimeError('fixed factory leaf required')
        if (self.profile['api_port'],self.profile['native_port']) not in ((8813,8815),(8814,8816)):
            raise RuntimeError('fixed outer/inner slot pair required')
        env_dirs={key:directory/leaf for key,leaf in (
            ('XDG_CONFIG_HOME','opencode-config'),('XDG_DATA_HOME','opencode-data'),
            ('XDG_CACHE_HOME','opencode-cache'),('XDG_STATE_HOME','opencode-state'))}
        for path in env_dirs.values():self.verify(path) # factory-provisioned; no global/config mutation
        password=secrets.token_urlsafe(48)
        intent={'v':1,'phase':'start-pending','owner':command['owner'],'key':command['key'],
            'provider_gate_ref':gate['source_ref'],'resource_gate_ref':gate['resource_ref'],
            'recorded_at':self.clock(),'model_turn_submitted':False}
        with self.lock:
            if self.read() is not None:raise RuntimeError('concurrent backend start already reserved')
            self.save(intent)
        self.command(command)
        if self.clock()>=gate['valid_until']:raise RuntimeError('pre-effect admission expired')
        provider=self.provider_reader() # fixed same-machine slot, in memory only
        if provider.account_binding_sha256!=gate['account_binding']:
            raise RuntimeError('actual memory provider account differs from admission')
        environment=provider.private_environment(os.environ)
        config=provider.config()
        config['permission']={'*':'deny','root_gateway_*':'allow'}
        config['agent']['root_contingency']['permission']=dict(config['permission'])
        config['mcp']={'root_gateway':{'type':'local','enabled':True,'command':[
            self.profile['python_exe'],'-I','-S',self.profile['mcp_entrypoint'],name,self.source_sha256]}}
        environment.update({k:str(v) for k,v in env_dirs.items()})
        environment.update(OPENCODE_CONFIG_CONTENT=json.dumps(config),
            OPENCODE_SERVER_USERNAME='opencode',OPENCODE_SERVER_PASSWORD=password)
        self.command(command)
        if self.clock()>=gate['valid_until']:raise RuntimeError('admission expired before native process start')
        self.job=self.job_factory('Local\\Win35Root-'+secrets.token_hex(16))
        self.backend=self.job.start([self.profile['opencode_exe'],'--pure','serve','--hostname','127.0.0.1',
            '--port',str(self.profile['native_port'])],str(directory),env=environment)
        pending=dict(intent,phase='backend-started-session-pending',backend={'pid':self.backend.pid,
            'creation_filetime':self.backend.creation_filetime},job_name=self.job.name,
            native_password=password,model_turn_submitted=False)
        self.save(pending) # retain actual process identity BEFORE uncertain API
        # Driver authenticates only after actual connected PID/FILETIME check.
        # Session creation has no model/provider call; first input is a separate
        # freshly admitted server-selected NativeDispatch operation.
        session=self.api(self.backend,self.job,self.profile['native_port'],password,'create-session',{})
        if type(session) is not dict or not re.fullmatch(r'ses_[A-Za-z0-9]+',session.get('id','')):
            raise RuntimeError('actual fresh native session creation uncertain')
        final=dict(pending,phase='native-session-ready',
            session_id=session['id'],native_password=password,model_turn_submitted=False)
        self.save(final) # PRIVATE only; password never part of returned receipt
        return {'native_backend_started':True,'session_id':session['id'],'model_turn_submitted':False,
                'backend':final['backend'],'job_name':self.job.name,'owner':command['owner']}
