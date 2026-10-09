"""Same-Guardian bounded owner bootstrap/renewal, no native/model impersonation.

Only actual authority acquire selects epoch. Native fence and root-start sink
receipts are required before dispatch. OpenCode activation is collected by the
separate privileged native verifier, never manufactured by this keeper.
"""
import copy,hashlib,json,time
from opencode_controller_gate import ref,finite

def sha(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()

class Keeper:
    def __init__(self,candidate,request,read,save,kernel_guard,clock=time.time):
        self.candidate=copy.deepcopy(candidate);self.request=request;self.read=read;self.save=save
        self.guard=kernel_guard;self.clock=clock
    def selected(self,result):
        if (type(result) is not dict or type(result.get('v')) is not int or result['v']!=1
            or result.get('status')!='ok' or type(result.get('result')) is not dict):
            raise RuntimeError('exact existing role-control envelope required')
        return result['result']
    def stage(self,state,name,body):
        if name in state['receipts']:
            if state.get('requests',{}).get(name)!=body:raise RuntimeError('immutable keeper request differs')
            return state['receipts'][name]
        pending=state.get('pending')
        if pending is not None:
            if pending!={'stage':name,'body':body}:raise RuntimeError('different uncertain keeper request held')
        else:
            state['pending']={'stage':name,'body':copy.deepcopy(body)};self.save(state)
        self.guard()
        response=self.request(body)
        self.selected(response);self.guard()
        state['receipts'][name]=response;state.setdefault('requests',{})[name]=copy.deepcopy(body)
        state['pending']=None;self.save(state)
        return response
    def control(self,state,control):
        owner=state['owner']
        fields={'v','owner','ordinal','envelope','input_sha256','issued_at','deadline','operation','payload','key','response_completed','check_completed'}
        if (type(control) is not dict or set(control)!=fields or type(control['v']) is not int or control['v']!=1
            or control['owner']!=owner or type(control['ordinal']) is not int or control['ordinal']<1
            or control['operation']!='root-check' or control['payload']!={} or control['check_completed'] is not False
            or type(control['response_completed']) is not bool or type(control['envelope']) is not str or not control['envelope']
            or type(control['input_sha256']) is not str or len(control['input_sha256'])!=64
            or control['key']!='opencode-control:'+ref(owner)+':'+str(control['ordinal'])
            or not all(finite(control[k]) for k in ('issued_at','deadline'))
            or control['deadline']-control['issued_at']!=120):
            raise RuntimeError('actual server-selected recurring root control differs')
        name='control:'+str(control['ordinal']);immutable={k:v for k,v in control.items() if k!='response_completed'}
        prior=state.setdefault('controls',{}).get(name)
        if prior is not None and prior!=immutable:raise RuntimeError('same ordinal changed protected control')
        state['controls'][name]=copy.deepcopy(immutable);self.save(state)
        if control['response_completed']:return
        if name in state['receipts']:return
        if not control['issued_at']-1<=self.clock()<=control['deadline']:
            raise RuntimeError('expired pending control cannot dispatch')
        # A persisted admission receipt is not fresh launch permission. Before
        # every not-yet-acknowledged ordinal effect, collect actual own provider/
        # resources and post-start authenticated history through NativeControl.
        self.guard();admission=self.request(dict(owner,op='admission_refresh'));self.selected(admission);self.guard()
        state['last_control_admission']={'ordinal':control['ordinal'],'observed_at':self.clock(),'response':admission}
        self.save(state)
        self.stage(state,name,dict(owner,op='execute',key=control['key'],operation='root-check',payload={}))
    def step(self):
        self.guard();state=self.read()
        if state is None:
            state={'v':1,'phase':'candidate','candidate':self.candidate,'owner':None,'receipts':{},'requests':{},'pending':None}
            self.save(state)
        if (type(state) is not dict or state.get('v')!=1 or state.get('candidate')!=self.candidate
            or state.get('phase') not in ('candidate','acquired','fenced','session-ready','input-submitted')):
            raise RuntimeError('unknown or foreign keeper state preserved')
        if state['phase']=='candidate':
            self.stage(state,'admission',dict(self.candidate,op='admission_refresh'))
            result=self.selected(self.stage(state,'acquire',dict(self.candidate,op='acquire')))
            if (result.get('read_only') is not False or result.get('holder')!=self.candidate['actor']
                or result.get('generation')!=self.candidate['generation']
                or type(result.get('epoch')) is not int or result['epoch']<1):
                raise RuntimeError('actual different/unknown authority owner preserved')
            state.update(owner=dict(self.candidate,epoch=result['epoch']),phase='acquired');self.save(state)
        owner=state['owner']
        if (type(owner) is not dict or any(owner.get(k)!=self.candidate[k] for k in ('project','role','actor','generation'))
            or type(owner.get('epoch')) is not int or owner['epoch']<1):
            raise RuntimeError('authority-selected owner missing')
        if state['phase']=='acquired':
            self.stage(state,'fence',dict(owner,op='first_action',operation='root-fence-activate',payload={}))
            state['phase']='fenced';self.save(state)
        if state['phase']=='fenced':
            self.stage(state,'start',dict(owner,op='bootstrap_start',operation='root-start',payload={}))
            state['phase']='session-ready';self.save(state)
        if state['phase']=='session-ready':
            self.control(state,self.selected(state['receipts']['start']).get('root_control'))
            state['phase']='input-submitted';self.save(state)
        # Reconcile the exact prior uncertain dispatch before asking renewal to
        # select a later ordinal. Never replace an unknown native input.
        pending=state.get('pending')
        if pending is not None and str(pending.get('stage','')).startswith('control:'):
            saved=state.get('controls',{}).get(pending['stage'])
            if saved is None:raise RuntimeError('uncertain control has no immutable source receipt')
            self.control(state,dict(saved,response_completed=False))
        # Renewal cannot manufacture activation/useful action or clear check/
        # reply/standup deadlines. Installed common authority owns every guard.
        self.guard()
        try:renew=self.selected(self.request(dict(owner,op='renew',ttl=180)))
        except Exception:
            state['last_renew_failure']={'observed_at':self.clock(),'phase':'refused-or-uncertain','owner':owner}
            self.save(state);raise
        self.guard()
        state['last_renew_observed_at']=self.clock();state['last_renew']=renew;self.save(state)
        self.control(state,renew.get('root_control'))
        return {'phase':state['phase'],'owner':owner,'native_input_submitted':True,
                'activated_claimed':False,'check_completed':False,'model_success_claimed':False}
