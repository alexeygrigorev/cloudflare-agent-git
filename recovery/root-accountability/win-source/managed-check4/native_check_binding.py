"""Authenticate a direct check child from owned SDK/rollout evidence.

These predicates consume producer-read native evidence. They never establish
its provenance from model text, requested IDs or configured defaults.
"""
import json

CHECK_TOOLS = frozenset(('root_read_instructions', 'root_check_reports'))


def require_direct_child(owner, parent_id, parent_turn, spawn, raw, child, context):
    if not isinstance(owner, dict) or type(owner.get('epoch')) is not int:
        raise RuntimeError('actual owner required')
    item = raw.get('item', {})
    if (raw.get('threadId') != parent_id or raw.get('turnId') != parent_turn
            or item.get('type') != 'function_call' or item.get('call_id') != spawn.get('id')
            or item.get('name') not in ('spawn_agent', 'collaboration.spawn_agent')):
        raise RuntimeError('owned raw provider spawn/turn correlation missing')
    try:
        args = json.loads(item['arguments'])
    except (KeyError, TypeError, ValueError):
        raise RuntimeError('raw spawn arguments missing')
    if not isinstance(args, dict):
        raise RuntimeError('raw spawn arguments invalid')
    fresh = (args.get('fork_context') is False and 'fork_turns' not in args
             or args.get('fork_turns') == 'none' and 'fork_context' not in args)
    if not fresh or args.get('model') != 'gpt-6-luna' or args.get('reasoning_effort') != 'max':
        raise RuntimeError('explicit fresh Luna/max request missing')
    cid = child.get('id')
    if (not isinstance(cid, str) or not cid or cid == parent_id
            or child.get('parentThreadId') != parent_id
            or 'forkedFromId' not in child or child['forkedFromId'] is not None
            or child.get('modelProvider') != 'openai' or child.get('model') != 'gpt-6-luna'
            or child.get('reasoningEffort') != 'max'):
        raise RuntimeError('actual direct fresh child metadata missing')
    if (spawn.get('type') != 'collabAgentToolCall' or spawn.get('tool') != 'spawnAgent'
            or spawn.get('status') != 'completed' or spawn.get('senderThreadId') != parent_id
            or spawn.get('receiverThreadIds') != [cid] or spawn.get('model') != 'gpt-6-luna'
            or spawn.get('reasoningEffort') != 'max'):
        raise RuntimeError('native spawn receipt mismatch')
    # Native rollout turn_context provides execution-context evidence beyond
    # Thread.model's documented configured/persisted metadata.
    if (context.get('model') != 'gpt-6-luna' or context.get('effort') != 'max'
            or not isinstance(context.get('turn_id'), str) or not context['turn_id']
            or context.get('approval_policy') != 'never'
            or context.get('sandbox_policy') != {'type': 'read-only'}):
        raise RuntimeError('actual child read-only execution context unavailable')
    return {'owner': dict(owner), 'parent_thread_id': parent_id, 'parent_turn_id': parent_turn,
            'child_thread_id': cid, 'child_turn_id': context['turn_id'], 'spawn_event_id': spawn['id'],
            'model': 'gpt-6-luna', 'effort': 'max', 'fresh_context': True,
            'raw_fork_mode':'none', 'actual_execution_context':{
                'thread_id':cid,'turn_id':context['turn_id'],'model':context['model'],
                'effort':context['effort'],'sandbox_policy':context['sandbox_policy'],
                'approval_policy':context['approval_policy']}}


def authorize_child_request(binding, current_owner, current_parent_turn, request, latest_child_turn):
    params = request.get('params', {})
    return (binding['owner'] == current_owner and binding['parent_turn_id'] == current_parent_turn
            and request.get('method') == 'item/tool/call' and params.get('namespace') in (None, '')
            and params.get('threadId') == binding['child_thread_id']
            and params.get('turnId') == binding['child_turn_id'] == latest_child_turn.get('id')
            and latest_child_turn.get('status') == 'inProgress'
            and isinstance(params.get('callId'), str) and bool(params['callId'])
            and params.get('tool') in CHECK_TOOLS and params.get('arguments') == {})


def verify_supervised_result(binding, child, wait, instruction_receipt, report_receipt):
    latest = (child.get('turns') or [None])[-1]
    if (child.get('id') != binding['child_thread_id'] or not isinstance(latest, dict)
            or latest.get('id') != binding['child_turn_id'] or latest.get('status') != 'completed'
            or latest.get('error')):
        raise RuntimeError('exact latest child turn not completed')
    item = wait.get('item', {})
    if (wait.get('threadId') != binding['parent_thread_id'] or wait.get('turnId') != binding['parent_turn_id']
            or item.get('type') != 'collabAgentToolCall' or item.get('tool') != 'wait'
            or item.get('status') != 'completed' or not item.get('id')
            or item.get('senderThreadId') != binding['parent_thread_id']
            or binding['child_thread_id'] not in item.get('receiverThreadIds', [])):
        raise RuntimeError('actual parent wait missing')
    raw=wait.get('raw_wait',{});raw_item=raw.get('item',{})
    if (raw.get('threadId')!=binding['parent_thread_id'] or raw.get('turnId')!=binding['parent_turn_id']
            or raw_item.get('call_id')!=item['id'] or raw_item.get('type')!='function_call'
            or raw_item.get('name') not in ('wait_agent','collaboration.wait_agent')):
        raise RuntimeError('actual native v2 parent wait call missing')
    try:args=json.loads(raw_item['arguments'])
    except (TypeError,ValueError,KeyError):raise RuntimeError('actual parent wait arguments unknown')
    if (not isinstance(args,dict) or set(args)-{'timeout_ms'} or type(args.get('timeout_ms')) not in (int,float)
            or not 10000<=args['timeout_ms']<=60000):
        raise RuntimeError('check parent wait must be explicit bounded native mailbox wait')
    if item.get('agentsStates',{}).get(binding['child_thread_id'],{}).get('status')!='completed':
        raise RuntimeError('native wait did not observe this completed child')
    for receipt, name in ((instruction_receipt, 'root_read_instructions'), (report_receipt, 'root_check_reports')):
        if (receipt.get('owner') != binding['owner'] or receipt.get('thread_id') != binding['child_thread_id']
                or receipt.get('turn_id') != binding['child_turn_id'] or receipt.get('tool') != name
                or not receipt.get('native_completed_event') or receipt.get('success') is not True):
            raise RuntimeError('child required read completion not proved')
    finals = [i['text'] for i in latest.get('items', []) if i.get('type') == 'agentMessage'
              and isinstance(i.get('text'), str) and i['text'].strip()]
    if not finals:
        raise RuntimeError('own child result absent')
    final_items=[i for i in latest.get('items',[]) if i.get('type')=='agentMessage' and i.get('text','').strip()]
    if not final_items[-1].get('id'):
        raise RuntimeError('actual completed child final event missing')
    return dict(binding, wait_event_id=item['id'], required_reads_completed=True,
                child_status='completed',parent_wait_status='completed',
                child_completed_event=final_items[-1]['id'],
                instruction_completed_event=instruction_receipt['native_completed_event'],
                report_completed_event=report_receipt['native_completed_event'],
                own_result='\n'.join(finals), useful_outcome_independent_acceptance='pending')
