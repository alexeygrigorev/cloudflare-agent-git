"""Parent outcome receipt from observed native events, never caller evidence.

The model may inspect its actually supervised child result, then accept that
exact result. Only the later matching SDK completed event yields server proof.
All producers and persistence callbacks are installed by the fixed host.
"""
import copy,hashlib,json,threading,time
from root_reply_binding import parent_context,require_check_result

def response(value):
    return {'contentItems':[{'type':'inputText','text':json.dumps(value,sort_keys=True)}],'success':True}

class CheckOutcomeProducer:
    def __init__(self,current,supervised,check,persist,clock=time.time,helper=None):
        self.current=current;self.supervised=supervised;self.check=check
        self.persist=persist;self.clock=clock;self.lock=threading.RLock();self.calls={};self.proofs={}
        self.helper=helper

    def context(self,request):
        state=self.current();params=parent_context(state,request);check=self.check()
        if (not isinstance(check,dict) or check.get('owner')!=state['thread_owner']
                or check.get('thread_id')!=params['threadId'] or check.get('turn_id')!=params['turnId']
                or not check.get('envelope')):
            raise RuntimeError('no genuine current check input')
        return state,params,check

    def authorize(self,request):
        state,p,c=self.context(request);a=p.get('arguments')
        if p.get('tool')=='root_check_inspect':
            if not isinstance(a,dict) or set(a)!={'child_thread_id'} or not isinstance(a['child_thread_id'],str):
                raise RuntimeError('fixed check inspection shape')
            self.supervised(a['child_thread_id'])
        elif p.get('tool')=='root_check_result':
            require_check_result(state,request,c,self.supervised((a or {}).get('child_thread_id')))
        else:raise RuntimeError('unapproved parent check tool')
        return True

    def handle(self,request):
        self.authorize(request);state,p,c=self.context(request)
        result=self.supervised(p['arguments']['child_thread_id'])
        result_sha=hashlib.sha256(result['own_result'].encode()).hexdigest()
        key=(p['threadId'],p['turnId'],p['callId'])
        with self.lock:
            if key in self.calls:raise RuntimeError('parent check call already reserved')
            self.calls[key]={'phase':'pending-reconcile-only'}
        if p['tool']=='root_check_inspect':
            output={'check_envelope':c['envelope'],'child_thread_id':result['child_thread_id'],
                    'child_turn_id':result['child_turn_id'],'result_sha256':result_sha,
                    'own_result':result['own_result'],'required_reads_completed':True,
                    'parent_wait_status':result['parent_wait_status']}
        else:
            require_check_result(state,request,c,result)
            if self.helper is None:raise RuntimeError('actual owned result helper not installed')
            helper=self.helper(state,request,c,result)
            if (not isinstance(helper,dict) or helper.get('exit_code')!=0
                    or helper.get('owner')!=state['thread_owner']
                    or helper.get('thread_id')!=p['threadId'] or helper.get('turn_id')!=p['turnId']
                    or helper.get('call_id')!=p['callId'] or not helper.get('helper_kernel')):
                raise RuntimeError('actual owned result helper failed or foreign')
            output={'check_envelope':c['envelope'],'result_sha256':result_sha,
                    'status':'helper-accepted-awaiting-native-completed-event'}
        # Recheck after any off-reader SDK lookup, before receipt persistence.
        self.context(request)
        record={'phase':'returned','owner':copy.deepcopy(state['thread_owner']),
                'thread_id':p['threadId'],'turn_id':p['turnId'],'call_id':p['callId'],
                'check_envelope':c['envelope'],
                'tool':p['tool'],'arguments':copy.deepcopy(p['arguments']),
                'supervised':copy.deepcopy(result),'response':response(output)}
        if p['tool']=='root_check_result':record.update(helper_exit_code=helper['exit_code'],helper_kernel=helper['helper_kernel'])
        self.persist('call:'+p['callId'],record)
        with self.lock:self.calls[key]=record
        return record['response']

    def observe(self,message):
        if message.get('method')!='item/completed':return
        p=message.get('params',{});i=p.get('item',{});key=(p.get('threadId'),p.get('turnId'),i.get('id'))
        with self.lock:r=copy.deepcopy(self.calls.get(key))
        if not r or r.get('phase')!='returned':return False
        state=self.current();check=self.check()
        if (state.get('thread_owner')!=r['owner'] or state.get('conversation_id')!=r['thread_id']
                or state.get('provider_turn_id')!=r['turn_id'] or check.get('envelope')!=r['check_envelope']):
            raise RuntimeError('parent outcome completion belongs to stale check')
        if (i.get('type')!='dynamicToolCall' or i.get('tool')!=r['tool'] or i.get('namespace') not in (None,'')
                or i.get('arguments')!=r['arguments'] or i.get('status')!='completed'
                or i.get('success') is not True or i.get('contentItems')!=r['response']['contentItems']):
            raise RuntimeError('SDK completion differs from handled parent result')
        if r['tool']=='root_check_inspect':return True
        result=copy.deepcopy(r['supervised']);result.update(
            parent_accept_event=copy.deepcopy(i),parent_accept_thread_id=r['thread_id'],
            parent_accept_turn_id=r['turn_id'],result_sha256=r['arguments']['result_sha256'],
            helper_exit_code=r['helper_exit_code'],helper_kernel=r['helper_kernel'],source_event_at=self.clock())
        proof={'check_result':result}
        self.persist('proof:'+check['envelope'],proof)
        with self.lock:self.proofs[check['envelope']]=proof
        return True

    def proof(self,envelope,thread_id):
        state=self.current();check=self.check()
        if (state.get('conversation_id')!=thread_id or check.get('envelope')!=envelope
                or check.get('owner')!=state.get('thread_owner')):raise RuntimeError('foreign check proof poll')
        with self.lock:proof=copy.deepcopy(self.proofs.get(envelope))
        if proof is None:raise RuntimeError('genuine model result not completed')
        if (proof['check_result'].get('owner')!=state['thread_owner']
                or proof['check_result'].get('parent_accept_turn_id')!=state.get('provider_turn_id')
                or check.get('turn_id')!=state.get('provider_turn_id')):
            raise RuntimeError('check proof belongs to prior parent turn')
        return proof
