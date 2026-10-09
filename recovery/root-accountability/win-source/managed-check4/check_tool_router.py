"""Route only the actual current root's direct, fresh native check child.

SDK reads and raw-rollout reads happen off the socket reader. Callbacks are
constructor-owned fixed producers, never model-selected files or commands.
"""
import copy
import hashlib
import json
import threading
from native_check_binding import require_direct_child, authorize_child_request, verify_supervised_result


class CheckToolRouter:
    def __init__(self, current_state, read_thread, read_rollout, instructions, reports):
        self.current_state=current_state;self.read_thread=read_thread;self.read_rollout=read_rollout
        self.instructions=instructions;self.reports=reports
        self.lock=threading.RLock();self.spawns={};self.waits={};self.bindings={};self.calls={};self.completed={}

    def observe(self, message):
        if message.get('method')!='item/completed':return
        params=message.get('params',{});item=params.get('item',{})
        state=self.current_state()
        if item.get('type')=='collabAgentToolCall':
            if params.get('threadId')!=state.get('conversation_id') or params.get('turnId')!=state.get('provider_turn_id'):
                return
            if item.get('status')!='completed':return
            record={'threadId':params['threadId'],'turnId':params['turnId'],'item':copy.deepcopy(item),'owner':copy.deepcopy(state['thread_owner'])}
            with self.lock:
                if item.get('tool')=='spawnAgent' and len(item.get('receiverThreadIds',[]))==1:
                    child=item['receiverThreadIds'][0]
                    if child in self.spawns and self.spawns[child]!=record:raise RuntimeError('conflicting native child spawn')
                    self.spawns[child]=record
                elif item.get('tool')=='wait':
                    for child in item.get('receiverThreadIds',[]):self.waits[child]=record
                else:raise RuntimeError('unapproved parent collaboration operation')
        elif item.get('type')=='dynamicToolCall':
            key=(params.get('threadId'),params.get('turnId'),item.get('id'))
            with self.lock:call=self.calls.get(key)
            if call is None or call.get('phase')!='returned':return
            if (item.get('tool')!=call['tool'] or item.get('arguments')!={} or item.get('namespace') not in (None,'')
                    or item.get('status')!='completed' or item.get('success') is not True
                    or item.get('contentItems')!=call['response']['contentItems']):
                raise RuntimeError('actual child tool completion differs from fixed producer')
            receipt={'owner':copy.deepcopy(call['owner']),'thread_id':key[0],'turn_id':key[1],
                     'tool':call['tool'],'native_completed_event':item['id'],'success':True,
                     'content_sha256':hashlib.sha256(json.dumps(item['contentItems'],sort_keys=True).encode()).hexdigest()}
            with self.lock:self.completed[(key[0],key[1],call['tool'])]=receipt

    def _verified_binding(self, request):
        params=request.get('params',{});state=self.current_state()
        with self.lock:spawn=copy.deepcopy(self.spawns.get(params.get('threadId')))
        if not spawn or spawn['owner']!=state.get('thread_owner') or spawn['turnId']!=state.get('provider_turn_id'):
            raise RuntimeError('no current owned native spawn for this child')
        parent=self.read_thread(state['conversation_id'])
        child=self.read_thread(params['threadId'])
        if parent.get('id')!=state['conversation_id'] or not child.get('turns'):
            raise RuntimeError('authentic SDK parent/child history missing')
        latest=child['turns'][-1]
        root_evidence=self.read_rollout(parent,spawn['turnId'],spawn['item']['id'])
        child_evidence=self.read_rollout(child,latest['id'],None)
        binding=require_direct_child(state['thread_owner'],state['conversation_id'],spawn['turnId'],spawn['item'],
                                     root_evidence['raw_spawn'],child,child_evidence['context'])
        for evidence in (root_evidence,child_evidence):
            value=evidence.get('rollout_prefix_sha256')
            if not isinstance(value,str) or len(value)!=64:
                raise RuntimeError('actual owned rollout receipt hash missing')
        binding['owned_rollout_receipt_sha256']=hashlib.sha256(json.dumps(
            [root_evidence['rollout_prefix_sha256'],child_evidence['rollout_prefix_sha256']],
            separators=(',',':')).encode()).hexdigest()
        if not authorize_child_request(binding,state['thread_owner'],state['provider_turn_id'],request,latest):
            raise RuntimeError('child is foreign, stale, completed or requested parent authority')
        # A newer owner/parent turn arriving during RPCs invalidates this work.
        after=self.current_state()
        if (after.get('thread_owner'),after.get('conversation_id'),after.get('provider_turn_id')) != (state['thread_owner'],state['conversation_id'],state['provider_turn_id']):
            raise RuntimeError('root custody changed during native lookup')
        with self.lock:self.bindings[binding['child_thread_id']]=binding
        return binding

    def authorize(self, request):
        self._verified_binding(request)
        return True

    def handle(self, request):
        binding=self._verified_binding(request)  # Recheck before fixed producer access.
        params=request['params'];tool=params['tool']
        key=(params['threadId'],params['turnId'],params['callId'])
        with self.lock:
            if key in self.calls:raise RuntimeError('native child call already handled')
            self.calls[key]={'phase':'producer-pending-reconcile-only','owner':copy.deepcopy(binding['owner']),'tool':tool}
        result=self.instructions() if tool=='root_read_instructions' else self.reports(binding['owner'])
        response={'contentItems':[{'type':'inputText','text':json.dumps(result,sort_keys=True)}],'success':True}
        with self.lock:
            self.calls[key]={'phase':'returned','owner':copy.deepcopy(binding['owner']),'tool':tool,'response':copy.deepcopy(response)}
        return response

    def supervised(self, child_id):
        with self.lock:
            binding=copy.deepcopy(self.bindings.get(child_id));wait=copy.deepcopy(self.waits.get(child_id))
            if not binding or not wait:raise RuntimeError('native child supervision missing')
            reads=copy.deepcopy(self.completed.get((child_id,binding['child_turn_id'],'root_read_instructions'),{}))
            reports=copy.deepcopy(self.completed.get((child_id,binding['child_turn_id'],'root_check_reports'),{}))
        state=self.current_state()
        if binding['owner']!=state.get('thread_owner') or binding['parent_turn_id']!=state.get('provider_turn_id'):
            raise RuntimeError('completed check belongs to prior owner/turn')
        parent=self.read_thread(state['conversation_id'])
        raw_wait=self.read_rollout(parent,wait['turnId'],wait['item']['id'])
        wait['raw_wait']=raw_wait['raw_spawn']
        return verify_supervised_result(binding,self.read_thread(child_id),wait,reads,reports)
