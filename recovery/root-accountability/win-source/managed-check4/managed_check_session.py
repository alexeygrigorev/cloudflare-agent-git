"""Managed SDK child, explicitly distinct from native collaboration ancestry.

All admission/proof producers are fixed constructor dependencies. Model arguments
cannot choose model, effort, history, paths, provider or identities. RPC runs only
on an off-reader tool worker, never while holding an authority transaction.
"""
import copy
import hashlib
import json
import threading
import time

READ_TOOLS = frozenset(('root_read_instructions', 'root_check_reports'))


class ManagedCheckSession:
    def __init__(self, current, fresh_admission, rpc, persist, instructions, reports,
                 envelope, workspace, verify_context):
        self.current = current
        self.fresh_admission = fresh_admission
        self.rpc = rpc
        self.persist = persist
        self.instructions = instructions
        self.reports = reports
        self.envelope = envelope
        self.workspace = workspace
        self.verify_context = verify_context
        self.lock = threading.RLock()
        self.record = None
        self.calls = set()
        self.reads = {}
        self.waits = {}
        self.parent_calls = {}

    def _parent(self, request):
        state = self.current()  # Must resolve authenticated current activation/lease.
        p = request.get('params', {})
        if (request.get('method') != 'item/tool/call' or p.get('namespace') not in (None, '')
                or p.get('threadId') != state.get('thread_id')
                or p.get('turnId') != state.get('turn_id')
                or p.get('arguments') != {} or not isinstance(p.get('callId'), str)
                or not p['callId'] or state.get('activated') is not True
                or state.get('lease_fresh') is not True or not isinstance(state.get('owner'), dict)):
            raise RuntimeError('managed check requires the actual current activated parent')
        return copy.deepcopy(state)

    def _unchanged(self, before):
        after = self.current()
        if after != before:
            raise RuntimeError('parent custody changed before managed effect')

    def _admit(self, state, phase):
        self._unchanged(state)
        admission = self.fresh_admission(state, phase, self.envelope)
        # The installed host obtains quota/resources first, then an authenticated
        # fresh role gate last. Model arguments never supply any of these records.
        if (not isinstance(admission, dict) or admission.get('launch_allowed') is not True
                or admission.get('fresh') is not True
                or admission.get('provider') != 'openai'
                or admission.get('physical_allowed') is not True
                or type(admission.get('remaining_percent')) not in (float, int)
                or not 15 < admission['remaining_percent'] <= 100
                or any(not isinstance(admission.get(k), str) or not admission[k]
                       for k in ('role_gate_ref', 'quota_gate_ref', 'resource_gate_ref'))):
            raise RuntimeError('fresh real provider reserve/physical admission unavailable')
        gate = admission.get('role_gate')
        now = time.time()
        if (not isinstance(gate, dict) or gate.get('v') != 1
                or gate.get('owner') != state['owner'] or gate.get('thread_id') != state['thread_id']
                or gate.get('parent_turn_id') != state['turn_id'] or gate.get('phase') != phase
                or gate.get('check_envelope') != self.envelope or gate.get('current_activated') is not True
                or gate.get('proof_kind') != 'server-authority-gate'
                or gate.get('role_gate_ref') != admission['role_gate_ref']
                or type(gate.get('observed_at')) not in (int, float)
                or type(gate.get('valid_until')) not in (int, float)
                or not 0 <= gate['valid_until'] - gate['observed_at'] <= 5
                or not -1 <= now - gate['observed_at'] <= 5 or not now < gate['valid_until']):
            raise RuntimeError('fresh authenticated exact phase/owner authority gate missing')
        self._unchanged(state)
        if time.time() >= gate['valid_until']:
            raise RuntimeError('role gate expired before effect')
        return admission

    def spawn(self, request):
        state = self._parent(request)
        if request['params'].get('tool') != 'root_spawn_check':
            raise RuntimeError('fixed managed spawn tool only')
        with self.lock:
            if self.record is not None:
                raise RuntimeError('existing managed attempt must reconcile, never replay')
            admission = self._admit(state, 'thread-start')
            self.record = {'v': 1, 'kind': 'managed-sdk-check', 'phase': 'context-pending',
                           'owner': state['owner'], 'parent_thread_id': state['thread_id'],
                           'parent_turn_id': state['turn_id'], 'parent_call_id': request['params']['callId'],
                           'check_envelope': self.envelope, 'model': 'gpt-6-luna',
                           'reasoning_effort': 'max', 'context_mode': 'new-thread-no-history',
                           'history_mode': 'fresh-empty', 'initial_turn_count': 0,
                           **{k: admission[k] for k in ('role_gate_ref', 'quota_gate_ref', 'resource_gate_ref')}}
            self.persist(copy.deepcopy(self.record))  # Durable intent BEFORE any native effect.
        self._unchanged(state)
        context_start_at = time.time()
        if context_start_at >= admission['role_gate']['valid_until']:
            raise RuntimeError('context gate expired before native dispatch')
        with self.lock:
            self.record.update(native_start_at=context_start_at,
                               role_gate=copy.deepcopy(admission['role_gate']))
            self.persist(copy.deepcopy(self.record))
        start_response = self.rpc.call('thread/start', {
            'model': 'gpt-6-luna', 'modelProvider': 'openai', 'cwd': self.workspace,
            'sandbox': 'read-only', 'approvalPolicy': 'never', 'historyMode': 'legacy',
            'config': {'model_reasoning_effort': 'max', 'features': {
                'multi_agent': False, 'unified_exec': False, 'shell_tool': False,
                'goals': False, 'view_image': False}, 'web_search': 'disabled'},
            'dynamicTools': [{'type': 'function', 'name': name,
                'description': 'Read fixed check evidence, without caller-selected paths.',
                'inputSchema': {'type': 'object', 'properties': {}, 'additionalProperties': False}}
                for name in sorted(READ_TOOLS)]})
        if (start_response.get('sandbox') != {'type': 'readOnly', 'networkAccess': False}
                or start_response.get('approvalPolicy') != 'never'):
            raise RuntimeError('actual SDK child read-only/network-disabled/never policy differs')
        child = start_response['thread']
        if (not isinstance(child.get('id'), str) or not child['id']
                or child['id'] == state['thread_id'] or child.get('forkedFromId', 'missing') is not None
                or child.get('parentThreadId', 'missing') is not None
                or child.get('modelProvider') != 'openai' or child.get('model') != 'gpt-6-luna'
                or child.get('reasoningEffort') != 'max' or child.get('turns') != []):
            raise RuntimeError('actual fresh managed SDK context metadata differs')
        with self.lock:
            self.record.update(phase='context-created', child_thread_id=child['id'],
                native_start_ref=hashlib.sha256(json.dumps(start_response, sort_keys=True).encode()).hexdigest(),
                native_start_receipt=copy.deepcopy(start_response))
            self.persist(copy.deepcopy(self.record))
        admission = self._admit(state, 'turn-start')
        with self.lock:
            if admission['role_gate_ref'] == self.record['role_gate_ref']:
                raise RuntimeError('separate context/turn role gate receipts required')
            self.record.update({k: admission[k] for k in ('quota_gate_ref', 'resource_gate_ref')})
            self.record['turn_role_gate_ref'] = admission['role_gate_ref']
            self.record['turn_role_gate'] = copy.deepcopy(admission['role_gate'])
            self.record['phase'] = 'turn-start-pending'
            self.record['native_turn_at'] = time.time()
            if self.record['native_turn_at'] >= admission['role_gate']['valid_until']:
                raise RuntimeError('turn gate expired before native dispatch')
            self.persist(copy.deepcopy(self.record))
        turn = self.rpc.call('turn/start', {'threadId': child['id'], 'model': 'gpt-6-luna',
            'effort': 'max', 'input': [{'type': 'text', 'text':
                'Perform a fresh read-only accountability check. Read both fixed tools. '
                'Label provenance, unknowns and proposed actions. Return a useful result. '
                'You have no root authority or inherited parent conversation.'}]})['turn']
        if not isinstance(turn.get('id'), str) or not turn['id']:
            raise RuntimeError('actual managed child turn identity missing')
        with self.lock:
            self.record.update(phase='running', child_turn_id=turn['id'],
                native_turn_ref=hashlib.sha256(json.dumps(turn, sort_keys=True).encode()).hexdigest(),
                native_turn_receipt=copy.deepcopy(turn))
            self.persist(copy.deepcopy(self.record))
        return copy.deepcopy(self.record)

    def child_read(self, request):
        p = request.get('params', {})
        state = self.current()
        with self.lock:
            r = copy.deepcopy(self.record)
            key = (p.get('threadId'), p.get('turnId'), p.get('callId'))
            if (not r or r['phase'] != 'running' or state.get('owner') != r['owner']
                    or state.get('thread_id') != r['parent_thread_id']
                    or state.get('turn_id') != r['parent_turn_id']
                    or state.get('activated') is not True or state.get('lease_fresh') is not True
                    or request.get('method') != 'item/tool/call'
                    or p.get('namespace') not in (None, '') or p.get('arguments') != {}
                    or key[:2] != (r['child_thread_id'], r['child_turn_id'])
                    or not isinstance(key[2], str) or not key[2]
                    or p.get('tool') not in READ_TOOLS or key in self.calls):
                raise RuntimeError('foreign/stale/replayed child or parent-only tool denied')
            self.verify_context(r)  # Actual same child/CID/turn/model/effort/read-only evidence.
            self.calls.add(key)
        value = (self.instructions if p['tool'] == 'root_read_instructions' else self.reports)()
        with self.lock:
            self.reads[key] = {'tool': p['tool'], 'phase': 'returned',
                               'response': copy.deepcopy(value),
                               'content_sha256': hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()}
        return value

    def authorize(self, request):
        """Off-reader authorization has no launch/read or reservation effect."""
        p = request.get('params', {})
        if p.get('tool') in ('root_spawn_check', 'root_wait_check'):
            self._parent(request)
            return True
        state = self.current()
        with self.lock: r = copy.deepcopy(self.record)
        if (not r or r.get('phase') != 'running' or state.get('owner') != r['owner']
                or state.get('thread_id') != r['parent_thread_id'] or state.get('turn_id') != r['parent_turn_id']
                or state.get('activated') is not True or state.get('lease_fresh') is not True
                or request.get('method') != 'item/tool/call' or p.get('namespace') not in (None, '')
                or p.get('threadId') != r['child_thread_id'] or p.get('turnId') != r['child_turn_id']
                or p.get('tool') not in READ_TOOLS or p.get('arguments') != {}
                or not isinstance(p.get('callId'), str) or not p['callId']):
            raise RuntimeError('fixed managed child-only read policy denied')
        return True

    def observe(self, message):
        """Only actual completed SDK tool events supply model event identities."""
        if message.get('method') != 'item/completed': return
        p = message.get('params', {}); item = p.get('item', {})
        if (item.get('type') != 'dynamicToolCall' or item.get('status') != 'completed'
                or item.get('success') is not True or item.get('namespace') not in (None, '')
                or item.get('arguments') != {} or not isinstance(item.get('id'), str)): return
        key = (p.get('threadId'), p.get('turnId'), item['id'])
        with self.lock:
            r = self.record
            if not r: return
            call = self.parent_calls.get(key)
            if (call and call['owner'] == r['owner'] and item.get('tool') == call['tool']
                    and item.get('contentItems') == call['response']['contentItems']):
                if call['tool'] == 'root_spawn_check':
                    r.update(parent_spawn_event_id=item['id'], parent_spawn_event=copy.deepcopy(item))
                elif call['tool'] == 'root_wait_check' and call['result'].get('status') == 'completed':
                    r.update(parent_wait_event_id=item['id'], parent_wait_event=copy.deepcopy(item),
                             completed_wait=copy.deepcopy(call['result']))
                self.persist(copy.deepcopy(r))
            read = self.reads.get(key)
            if (read and read['phase'] == 'returned' and item.get('tool') == read['tool']
                    and isinstance(read['response'].get('contentItems'), list)
                    and item.get('contentItems') == read['response']['contentItems']):
                read.update(phase='completed', native_completed_event=item['id'])

    def wait(self, request):
        state = self._parent(request)
        if request['params'].get('tool') != 'root_wait_check':
            raise RuntimeError('fixed managed wait tool only')
        with self.lock:
            r = copy.deepcopy(self.record)
            if (not r or r.get('phase') != 'running' or r['owner'] != state['owner']
                    or r['parent_thread_id'] != state['thread_id']
                    or r['parent_turn_id'] != state['turn_id']
                    or not r.get('parent_spawn_event_id')):
                raise RuntimeError('actual current parent spawn completion missing')
        until = time.monotonic() + 30
        while time.monotonic() < until:
            self._unchanged(state)
            child = self.rpc.call('thread/read', {'threadId': r['child_thread_id'], 'includeTurns': True})['thread']
            latest = (child.get('turns') or [{}])[-1]
            if child.get('id') != r['child_thread_id'] or latest.get('id') != r['child_turn_id']:
                raise RuntimeError('current managed child history identity changed')
            if latest.get('status') == 'completed' and not latest.get('error'):
                self.verify_context(r)
                with self.lock:
                    completed = [v['tool'] for k,v in self.reads.items()
                        if k[:2] == (r['child_thread_id'], r['child_turn_id']) and v['phase'] == 'completed']
                if set(completed) != READ_TOOLS:
                    raise RuntimeError('actual completed child instruction/report reads missing')
                finals = [i.get('text') for i in latest.get('items', []) if i.get('type') == 'agentMessage'
                          and isinstance(i.get('text'), str) and i['text'].strip()]
                if not finals: raise RuntimeError('actual completed child useful final absent')
                self._unchanged(state)
                result = {'kind': 'managed-sdk-check', 'child_thread_id': r['child_thread_id'],
                          'child_turn_id': r['child_turn_id'], 'status': 'completed',
                          'result_sha256': hashlib.sha256(finals[-1].encode()).hexdigest(), 'result': finals[-1]}
                with self.lock:
                    self.waits[request['params']['callId']] = copy.deepcopy(result)
                    self.persist(dict(r, last_wait_returned=copy.deepcopy(result)))
                return result
            if latest.get('status') != 'inProgress':
                raise RuntimeError('managed child failed or state unknown; preserve it')
            time.sleep(.1)
        return {'kind': 'managed-sdk-check', 'status': 'pending', 'child_thread_id': r['child_thread_id']}

    def handle_parent(self, request):
        state = self._parent(request)
        tool = request['params'].get('tool')
        if tool not in ('root_spawn_check', 'root_wait_check'):
            raise RuntimeError('fixed managed parent operations only')
        key = (state['thread_id'], state['turn_id'], request['params']['callId'])
        with self.lock:
            if key in self.parent_calls: raise RuntimeError('parent managed call already reserved')
            self.parent_calls[key] = {'phase': 'pending-reconcile-only'}
        result = self.spawn(request) if tool == 'root_spawn_check' else self.wait(request)
        response = {'contentItems': [{'type': 'inputText', 'text': json.dumps(result, sort_keys=True)}], 'success': True}
        record = {'phase': 'returned', 'owner': state['owner'], 'tool': tool,
                  'response': response, 'result': result}
        with self.lock:
            self.parent_calls[key] = record
            self.persist(dict(self.record, parent_calls=copy.deepcopy(self.parent_calls_to_list())))
        return response

    def parent_calls_to_list(self):
        return [{'thread_id':k[0], 'turn_id':k[1], 'call_id':k[2], **v} for k,v in self.parent_calls.items()]

    def supervised(self, child_id):
        state = self.current()
        with self.lock: r = copy.deepcopy(self.record)
        if (not r or r.get('phase') != 'running' or child_id != r.get('child_thread_id')
                or state.get('owner') != r['owner'] or state.get('thread_id') != r['parent_thread_id']
                or state.get('turn_id') != r['parent_turn_id'] or state.get('lease_fresh') is not True
                or state.get('activated') is not True or not r.get('parent_spawn_event_id')
                or not r.get('parent_wait_event_id')):
            raise RuntimeError('actual current parent managed spawn/wait incomplete')
        child = self.rpc.call('thread/read', {'threadId': child_id, 'includeTurns': True})['thread']
        latest = (child.get('turns') or [{}])[-1]
        context = self.verify_context(r)
        if (child.get('id') != child_id or latest.get('id') != r['child_turn_id']
                or latest.get('status') != 'completed' or latest.get('error')
                or not isinstance(context, dict) or context.get('model') != 'gpt-6-luna'
                or context.get('effort') != 'max' or context.get('turn_id') != r['child_turn_id']
                or context.get('approval_policy') != 'never'
                or context.get('sandbox_policy') != {'type': 'read-only'}
                or not isinstance(context.get('owned_rollout_receipt_sha256'), str)
                or len(context['owned_rollout_receipt_sha256']) != 64):
            raise RuntimeError('actual latest fresh Luna context/final proof missing')
        finals = [i.get('text') for i in latest.get('items', []) if i.get('type') == 'agentMessage'
                  and isinstance(i.get('text'), str) and i['text'].strip()]
        if not finals or hashlib.sha256(finals[-1].encode()).hexdigest() != r['completed_wait']['result_sha256']:
            raise RuntimeError('actual child final changed after completed parent wait')
        with self.lock:
            reads = [copy.deepcopy(v) for k,v in self.reads.items()
                if k[:2] == (child_id, r['child_turn_id']) and v['phase'] == 'completed']
        if {v['tool'] for v in reads} != READ_TOOLS:
            raise RuntimeError('genuine child required reads not completed')
        self._unchanged(state)
        launch_fields = ('owner','parent_thread_id','parent_turn_id','check_envelope','parent_spawn_event_id',
            'child_thread_id','child_turn_id','history_mode','initial_turn_count','native_start_ref',
            'native_start_at','native_turn_at',
            'role_gate_ref','turn_role_gate_ref','quota_gate_ref','resource_gate_ref')
        def source_ref(kind, value):
            return 'managed-owned-record:'+kind+':'+hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()
        read_refs={v['tool']:source_ref('required-read',v) for v in reads}
        execution={'thread_id':child_id,'turn_id':r['child_turn_id'],'model':context['model'],
                   'effort':context['effort'],'sandbox_policy':context['sandbox_policy'],
                   'approval_policy':context['approval_policy']}
        return {'check_method': 'managed-sdk-fresh-v1', 'launch_method':'managed-sdk-fresh-v1', 'owner':r['owner'],
            'parent_thread_id':r['parent_thread_id'],'parent_turn_id':r['parent_turn_id'],
            'parent_spawn_thread_id':r['parent_thread_id'],'parent_spawn_turn_id':r['parent_turn_id'],
            'spawn_event_id':r['parent_spawn_event_id'],
            'parent_wait_thread_id':r['parent_thread_id'],'parent_wait_turn_id':r['parent_turn_id'],
            'child_thread_id':child_id, 'child_turn_id':r['child_turn_id'],
            'model':context['model'],'effort':context['effort'],'child_status':latest['status'],
            'child_completed_event':source_ref('authenticated-latest-child-turn',latest),
            'instruction_completed_event':read_refs['root_read_instructions'],
            'report_completed_event':read_refs['root_check_reports'],
            'own_result':finals[-1], 'required_reads_completed':True,
            'parent_wait_status':'completed', 'wait_event_id':r['parent_wait_event_id'],
            'managed_launch':{k:r[k] for k in launch_fields},
            'parent_spawn_event':r['parent_spawn_event'], 'parent_wait_event':r['parent_wait_event'],
            'actual_execution_context':execution,
            'owned_rollout_receipt_sha256':context['owned_rollout_receipt_sha256'],
            'required_read_receipts':reads}
