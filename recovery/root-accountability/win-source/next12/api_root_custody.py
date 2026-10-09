"""Provider-owned API root state; no UI absence is interpreted as vacancy."""
API_ENDPOINT='ws://127.0.0.1:8813'

def observe(state, message):
    params=message.get('params',{})
    if params.get('threadId')!=state.get('conversation_id'):return
    method=message.get('method')
    if method in ('turn/started','turn/completed'):
        turn=params.get('turn',{})
        if not isinstance(turn,dict) or not turn.get('id'):return
        if method=='turn/started':
            terminal=state.setdefault('provider_terminal_turns',{})
            if turn['id'] in terminal or (turn['id']==state.get('provider_turn_id') and state.get('provider_turn_state')=='completed'):
                return  # Delayed/duplicate start cannot downgrade a terminal turn.
            if turn['id']==state.get('provider_turn_id') and state.get('provider_turn_state')=='busy':return
            if state.get('provider_turn_id') and state.get('provider_turn_state') not in ('starting','unknown'):
                state.update(provider_event_conflict=True,api_history_validated=False)
                return  # Unrequested/out-of-order foreign turn cannot become current.
            state.update(provider_turn_id=turn['id'],provider_turn_state='busy',api_history_validated=False)
        elif turn['id']==state.get('provider_turn_id'):
            state['provider_turn_state']='completed' if turn.get('status')=='completed' else 'unknown'
            if turn.get('status')=='completed':state.setdefault('provider_terminal_turns',{})[turn['id']]=True
    if method=='item/tool/call' and params.get('callId'):
        state['api_history_validated']=False
        state.setdefault('provider_pending_tools',{})[params['callId']]=True
    elif method=='item/completed':
        item=params.get('item',{})
        state.setdefault('provider_pending_tools',{}).pop(item.get('id'),None)

def owned_api_custody(profile,state,owner,backend,live):
    if profile.get('runtime_mode')!='api-root' or state.get('runtime_mode')!='api-root':return False
    if any(state.get(key) for key in ('frontend_pid','viewer_pid','frontend_attempt_pending','launch_pending')):return False
    if state.get('thread_owner')!=owner or state.get('fence_owner')!=owner:return False
    if not state.get('conversation_id') or not state.get('native_session_id'):return False
    if state.get('native_policy')!={'sandbox':{'type':'readOnly','networkAccess':False},'approvalPolicy':'never'}:return False
    if not backend or state.get('pid')!=backend.pid or state.get('process_creation_filetime')!=backend.creation_filetime:return False
    return backend.poll() is None and live(backend.pid,backend.creation_filetime)=='alive'

def dispatch_clear(state):
    return not state.get('provider_event_conflict') and state.get('provider_turn_state')=='completed' and state.get('provider_pending_tools')=={} and state.get('api_history_validated') is True

def validate_latest_history(state,thread):
    turns=thread.get('turns')
    state['api_history_validated']=False
    if state.get('provider_event_conflict'):return False
    if thread.get('id')!=state.get('conversation_id') or thread.get('historyMode')!='legacy' or not isinstance(turns,list) or not turns:return False
    latest=turns[-1]
    if not isinstance(latest,dict) or latest.get('id')!=state.get('provider_turn_id') or latest.get('status')!='completed':return False
    if state.get('provider_turn_state')!='completed' or state.get('provider_pending_tools')!={}:return False
    state['api_history_validated']=True
    return True

def valid_lease_tuple(role,owner):
    return (all(role.get(key)==owner.get(other) for key,other in [('holder','actor'),('generation','generation'),('epoch','epoch')])
            and role.get('lease_fresh') is True and role.get('activation_due') is False)

def recorded_api_custody(profile,state,owner,live):
    if profile.get('runtime_mode')!='api-root' or state.get('runtime_mode')!='api-root':return False
    if state.get('thread_owner')!=owner or state.get('fence_owner')!=owner:return False
    if profile.get('actor')!=owner.get('actor') or profile.get('generation')!=owner.get('generation'):return False
    if not state.get('conversation_id') or not state.get('native_session_id'):return False
    if not state.get('initial_turn_submitted') or not isinstance(state.get('initial_turn_receipt'),dict):return False
    if state.get('native_policy')!={'sandbox':{'type':'readOnly','networkAccess':False},'approvalPolicy':'never'}:return False
    if any(state.get(key) for key in ('frontend_pid','viewer_pid','frontend_attempt_pending','launch_pending')):return False
    binding=state.get('guardian_binding',{})
    expected='win32:'+str(binding.get('pid'))+':'+str(binding.get('creation_filetime'))
    if expected!=owner.get('generation') or live(binding.get('pid'),binding.get('creation_filetime'))!='alive':return False
    return bool(state.get('pid') and state.get('process_creation_filetime') and live(state['pid'],state['process_creation_filetime'])=='alive')
