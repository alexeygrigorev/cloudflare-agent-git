"""Wire-v2 parent reply/check-result binding; no authority or input effects.

Only constructor-owned delivery/child records can authorize these parent tools.
Actual helper exit, SDK completed events and raw input/tool proof are separate
requirements; this classifier does not manufacture those receipts.
"""
import hashlib,json,copy

def sha(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def parent_context(state,request):
    p=request.get('params',{})
    if (request.get('method')!='item/tool/call' or not p.get('callId')
        or p.get('namespace') not in (None,'')
        or p.get('threadId')!=state.get('conversation_id')
        or p.get('turnId')!=state.get('provider_turn_id')
        or not state.get('thread_owner') or state.get('provider_turn_state')!='busy'):
        raise RuntimeError('no current genuine parent turn')
    return p

def require_reply(state,request,delivery):
    p=parent_context(state,request);args=p.get('arguments')
    if (p.get('tool')!='root_role_reply' or not isinstance(args,dict)
        or set(args)!={'nonce','envelope','body','next_action','checkpoint'}
        or any(not isinstance(args[k],str) or not args[k].strip() or len(args[k])>4096 for k in args)):
        raise RuntimeError('reply tool shape invalid')
    if (not isinstance(delivery,dict) or delivery.get('phase')!='input-proven'
        or delivery.get('owner')!=state['thread_owner']
        or delivery.get('thread_id')!=p['threadId'] or delivery.get('turn_id')!=p['turnId']
        or delivery.get('nonce')!=args['nonce'] or delivery.get('envelope')!=args['envelope']
        or delivery.get('body')!=args['body']
        or not delivery.get('input_receipt_ref') or not delivery.get('owned_raw_input_sha256')):
        raise RuntimeError('reply has no exact authenticated post-challenge input')
    return dict(owner=copy.deepcopy(state['thread_owner']),thread_id=p['threadId'],turn_id=p['turnId'],
                call_id=p['callId'],nonce=args['nonce'],envelope=args['envelope'],
                input_receipt_ref=delivery['input_receipt_ref'],
                body=args['body'],
                next_action=args['next_action'],checkpoint=args['checkpoint'])

def require_check_result(state,request,check,supervised):
    p=parent_context(state,request);args=p.get('arguments')
    if (p.get('tool')!='root_check_result' or not isinstance(args,dict)
        or set(args)!={'check_envelope','child_thread_id','child_turn_id','result_sha256','next_action','checkpoint'}
        or any(not isinstance(args[k],str) or not args[k].strip() or len(args[k])>4096 for k in args)):
        raise RuntimeError('check result tool shape invalid')
    if (not isinstance(check,dict) or check.get('owner')!=state['thread_owner']
        or check.get('thread_id')!=p['threadId'] or check.get('turn_id')!=p['turnId']
        or not check.get('envelope')
        or args['check_envelope']!=check['envelope']
        or supervised.get('child_thread_id')!=args['child_thread_id']
        or supervised.get('child_turn_id')!=args['child_turn_id']
        or supervised.get('required_reads_completed') is not True
        or not supervised.get('wait_event_id')
        or args['result_sha256']!=hashlib.sha256(supervised.get('own_result','').encode()).hexdigest()):
        raise RuntimeError('no exact newly supervised check result')
    return dict(owner=copy.deepcopy(state['thread_owner']),thread_id=p['threadId'],turn_id=p['turnId'],
                call_id=p['callId'],envelope=check['envelope'],child_thread_id=args['child_thread_id'],
                result_sha256=args['result_sha256'],next_action=args['next_action'],checkpoint=args['checkpoint'])

def completed_reply(record,message):
    if message.get('method')!='item/completed':return False
    p=message.get('params',{});i=p.get('item',{})
    return (p.get('threadId')==record.get('thread_id') and p.get('turnId')==record.get('turn_id')
            and i.get('id')==record.get('call_id') and i.get('type')=='dynamicToolCall'
            and i.get('tool')=='root_role_reply' and i.get('namespace') in (None,'')
            and i.get('status')=='completed' and i.get('success') is True
            and record.get('helper_exit_code')==0
            and i.get('arguments')=={k:record[k] for k in ('nonce','envelope','body','next_action','checkpoint')}
            and i.get('contentItems')==record.get('contentItems'))
