"""Fixed native channel command handler for the enrolled shell incarnation.

Admission precedes acquire and never claims activation. Full owner is selected
only by the authenticated authority fence command. Unknown commands hold;
there is no manual model ACK, stop, shell execution or ownership override.
"""
import copy,hashlib,json,math,time,threading,datetime

class NativeControl:
    def __init__(self,binding,native,read,save,source_guard,identity_guard,final_proof,
                 admission,backend_factory,observation,clock=time.time,monotonic=time.monotonic,check=None,luna=None,post_start_ready=None):
        self.binding=binding;self.native=native;self.read=read;self.save=save
        self.source=source_guard;self.identity=identity_guard;self.proof=final_proof
        self.admission=admission;self.factory=backend_factory;self.observation=observation
        self.check=check
        self.luna=luna
        self.post_start_ready=post_start_ready
        self.clock=clock;self.monotonic=monotonic;self.lock=threading.Lock();self.deadlines={};self.highwater=None
    def selected(self,command):
        self.source();self.identity()
        if type(command) is not dict or command.get('payload')!={} or not command.get('key'):
            raise RuntimeError('fixed authority command envelope required')
        owner=command.get('owner')
        if (type(owner) is not dict or set(owner)!= {'project','role','actor','generation','epoch'}
            or owner['project']!=self.binding['project'] or owner['role']!='root'
            or owner['actor']!=self.native['id'] or owner['generation']!=self.binding['generation']
            or type(owner['epoch']) is not int or owner['epoch']<1):
            raise RuntimeError('actual enrolled native command binding differs')
        deadline=command.get('deadline');now=self.clock()
        if self.highwater is not None and now<self.highwater:raise RuntimeError('authority clock rollback held')
        self.highwater=now
        if type(deadline) not in (int,float) or not math.isfinite(deadline) or not 0<deadline-now<=60:
            raise RuntimeError('finite current authority command required')
        stamp=(command['key'],deadline)
        if stamp not in self.deadlines:self.deadlines[stamp]=self.monotonic()+deadline-now
        if self.monotonic()>=self.deadlines[stamp]:raise RuntimeError('monotonic authority command expired')
        return owner
    def receipt(self,command,evidence):
        return {'v':1,'key':command['key'],'owner':command['owner'],'operation':command['operation'],
                'payload':{},'state':'completed','native_actor':self.native,'evidence':evidence}
    def execute(self,command):
        owner=self.selected(command);operation=command.get('operation')
        if operation=='root-admission':
            gate=self.admission()
            # No cached completed/busy flag can certify a running model safe.
            # A post-start admission requires a separate actual history path.
            unstarted=self.factory.read() is None
            post_ready=False
            if not unstarted and callable(self.post_start_ready):
                state=self.read()
                if type(state) is dict and state.get('phase')=='native-fence-active' and state.get('owner')==owner:
                    try:post_ready=self.post_start_ready(command) is True
                    except Exception:post_ready=False
            self.selected(command)
            allowed=(gate.get('provider')=='zai-coding-plan' and gate.get('model')=='glm-5.3-flash'
                and gate.get('launch_allowed') is True and gate.get('physical_allowed') is True
                and gate.get('account_binding')==self.binding.get('provider_account_binding')
                and bool(self.binding.get('provider_account_binding'))
                and bool(gate.get('source_ref')) and bool(gate.get('resource_ref'))
                and type(gate.get('observed_at')) in (int,float)
                and type(gate.get('valid_until')) in (int,float)
                and gate['observed_at']<=self.clock()<gate['valid_until']<=gate['observed_at']+30)
            return self.receipt(command,{'admission':{'actor':self.native['id'],
                'host':self.binding['host'],'generation':self.binding['generation'],
                'ready':allowed and (unstarted or post_ready),'draft':not (unstarted or post_ready),'quota_ok':allowed,
                'observed_at':datetime.datetime.fromtimestamp(self.clock(),datetime.timezone.utc).isoformat().replace('+00:00','Z'),
                'source':'fixed-own-CodingPlan-and-physical-admission',
                'source_ref':gate.get('source_ref'),'resource_ref':gate.get('resource_ref'),
                'model_started':False}})
        if operation not in ('root-fence-activate','root-start','opencode-native-observation','root-check','opencode-luna-admission'):
            raise RuntimeError('unregistered native operation held')
        if operation=='root-fence-activate':
            self.proof(command);self.selected(command) # RPC outside writer lock
        with self.lock:
            state=self.read()
            if state is None:state={'v':1,'phase':'native-unactivated','owner':None,'receipts':{}}
            if type(state) is not dict or state.get('phase') not in ('native-unactivated','native-fence-active'):
                raise RuntimeError('unknown native control state held')
            if operation=='root-fence-activate':
                if state.get('owner') is not None and state['owner']!=owner:
                    raise RuntimeError('different owner of living native shell preserved')
                state.update(phase='native-fence-active',owner=copy.deepcopy(owner))
                receipt=self.receipt(command,{'fence_activation':owner,'model_started':False})
                self.save(state);return receipt
            if state.get('owner')!=owner:raise RuntimeError('native activation missing or stale')
        # No writer lock is held during authority/native RPC. Final current-role
        # proof is mandatory before root-start; observation is read-only and
        # selected by authenticated native channel for the same fenced owner.
        if operation=='opencode-native-observation':return self.observation.execute(command)
        if operation=='opencode-luna-admission':
            if self.luna is None:raise RuntimeError('fixed own Luna admission collector missing')
            return self.luna.execute(command)
        if operation=='root-check':
            if not callable(self.check):raise RuntimeError('reviewed fixed check dispatcher missing')
            return self.receipt(command,self.check(command))
        self.proof(command);self.selected(command)
        return self.receipt(command,self.factory.start(command))
