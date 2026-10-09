"""Exact fixed77 own-root gate/input requests; never model launch allowance."""
import hashlib,json,math,time

def ref(owner):return hashlib.sha256(json.dumps([owner[k] for k in ('project','role','actor','generation','epoch')],separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
def finite(v):return type(v) in (int,float) and math.isfinite(v)

class ControllerGate:
    def __init__(self,owner,credential,instructions_sha256,post,clock=time.time):
        self.owner=dict(owner);self._credential=credential;self.instructions_sha256=instructions_sha256
        self.post=post;self.clock=clock
    def __repr__(self):return 'ControllerGate(fixed-root-controller; credential=private; launch=false)'
    def request(self,operation):
        if operation not in ('opencode-controller-gate','opencode-input'):raise RuntimeError('fixed controller operation required')
        return self.post('/v1/host-recovery',{'v':1,'credential':self._credential,'op':operation})
    def __call__(self,context,tool):
        if context.get('owner')!=self.owner:raise RuntimeError('current source-selected owner differs')
        result=self.request('opencode-controller-gate');now=self.clock()
        if (type(result) is not dict or type(result.get('v')) is not int or result['v']!=1
            or result.get('owner')!=self.owner or result.get('owner_ref')!=ref(self.owner)
            or result.get('helper_allowed') is not True or result.get('model_launch_allowed') is not False
            or result.get('authority_effect') is not False or type(result.get('activation_pending')) is not bool
            or not result.get('role_gate_ref') or result.get('instructions_sha256')!=self.instructions_sha256
            or not all(finite(result.get(k)) for k in ('issued_at','valid_until'))
            or not result['issued_at']-1<=now<=result['valid_until']
            or not 0<result['valid_until']-result['issued_at']<=5):
            raise RuntimeError('fresh authenticated own-root helper gate denied')
        return {k:result[k] for k in ('owner_ref','role_gate_ref','issued_at','valid_until','activation_pending')}
    def initial_input(self):
        result=self.request('opencode-input');now=self.clock()
        if (type(result) is not dict or result.get('v')!=1 or type(result.get('v')) is not int
            or result.get('owner_ref')!=ref(self.owner) or not result.get('challenge') or not result.get('envelope')
            or type(result.get('body')) is not str or not result['body']
            or hashlib.sha256(result['body'].encode()).hexdigest()!=result.get('input_sha256')
            or result.get('model_launch_allowed') is not False or result.get('check_completed') is not False
            or result.get('response_completed') is not False
            or not all(finite(result.get(k)) for k in ('issued_at','deadline'))
            or not 0<result['deadline']-result['issued_at']<=120 or not result['issued_at']-1<=now<result['deadline']):
            raise RuntimeError('current pending server-selected native input absent')
        return result
