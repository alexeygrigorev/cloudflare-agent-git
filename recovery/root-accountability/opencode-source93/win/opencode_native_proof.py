"""OpenCode-native-v1 proof from trusted owned native history, not uploads.

Transport/kernel verification belongs to the pinned installed controller. This
module never translates OpenCode parts into Codex events or grants authority.
"""
import hashlib,json,math,time

PREFIX='root_gateway_'
TOOLS={'root_read_instructions','root_ack_instructions','root_oversight_snapshot','root_role_reply','root_luna_hold'}

def text_sha(text):return hashlib.sha256(text.encode('utf-8')).hexdigest()
def finite_ms(value):return type(value) in (int,float) and math.isfinite(value) and value>0

def completed_tool(history,context,handled,clock=time.time):
    if type(history) is not list or not history:raise RuntimeError('owned native history absent')
    for key in ('session_id','user_message_id','user_input_sha256','provider_id','model_id','agent','owner','kernel'):
        if not context.get(key):raise RuntimeError('fixed controller context missing')
    if (handled.get('owner')!=context['owner'] or handled.get('kernel')!=context['kernel']
        or handled.get('session_id')!=context['session_id'] or handled.get('user_message_id')!=context['user_message_id']
        or handled.get('tool') not in TOOLS or type(handled.get('helper_exit_code')) is not int
        or handled['helper_exit_code']!=0 or not handled.get('receipt_ref')
        or type(handled.get('arguments')) is not dict or not isinstance(handled.get('output'),str)
        or not finite_ms(handled.get('handled_at_ms')) or not finite_ms(context.get('input_accepted_at_ms'))):
        raise RuntimeError('owned helper receipt unbound')
    users=[m for m in history if m.get('info',{}).get('id')==context['user_message_id']]
    if len(users)!=1:raise RuntimeError('actual user input ambiguous')
    info=users[0]['info']
    if info.get('role')!='user' or info.get('sessionID')!=context['session_id']:raise RuntimeError('foreign native input')
    texts=[p.get('text','') for p in users[0].get('parts',[]) if p.get('type')=='text']
    if len(texts)!=1 or text_sha(texts[0])!=context['user_input_sha256']:raise RuntimeError('actual native input changed')
    now=clock()*1000;created=info.get('time',{}).get('created')
    if (not finite_ms(created) or not finite_ms(now) or created<context['input_accepted_at_ms']-1000
        or created>now+1000 or now-handled['handled_at_ms']>30000 or handled['handled_at_ms']>now+1000):
        raise RuntimeError('native input/helper observation stale or future')
    candidates=[]
    for message in history:
        i=message.get('info',{})
        if i.get('sessionID')!=context['session_id'] or i.get('parentID')!=context['user_message_id']:continue
        for part in message.get('parts',[]):
            state=part.get('state',{})
            if part.get('type')=='tool' and part.get('tool')==PREFIX+handled['tool'] and state.get('output')==handled['output']:
                candidates.append((i,part,state))
    if len(candidates)!=1:raise RuntimeError('native helper event absent or reused')
    i,p,s=candidates[0];times=s.get('time',{});message_times=i.get('time',{})
    completed=message_times.get('completed')
    if (i.get('role')!='assistant' or i.get('providerID')!=context['provider_id'] or i.get('modelID')!=context['model_id']
        or i.get('agent')!=context['agent'] or not i.get('id') or not p.get('id') or not p.get('callID')
        or p.get('sessionID')!=context['session_id'] or p.get('messageID')!=i['id']
        or s.get('status')!='completed' or s.get('input')!=handled['arguments']
        or not all(finite_ms(v) for v in (times.get('start'),times.get('end'),message_times.get('created')))
        or times['end']<times['start'] or (completed is not None and (not finite_ms(completed) or completed<times['end']))
        or times['start']<created or times['start']>handled['handled_at_ms']+1000
        or times['end']<handled['handled_at_ms']-1000 or (completed is not None and completed>now+1000)):
        raise RuntimeError('native completed event mismatch')
    if handled['tool']=='root_role_reply':
        args=handled['arguments']
        if (set(args)!={'body','next_action','checkpoint'}
            or any(type(v) is not str or not v.strip() for v in args.values())
            or not context.get('nonce') or not context.get('envelope') or not context.get('challenge_ref')
            or not finite_ms(context.get('issued_at_ms'))
            or created<context['issued_at_ms']-1000 or times['end']>context['issued_at_ms']+120000):
            raise RuntimeError('no exact timely post-challenge model reply')
    return {'proof_kind':'opencode-native-v1','owner':context['owner'],'kernel':context['kernel'],
        'session_id':context['session_id'],'user_message_id':context['user_message_id'],
        'user_input_sha256':context['user_input_sha256'],'assistant_message_id':i['id'],
        'tool_part_id':p['id'],'call_id':p['callID'],'provider_id':i['providerID'],'model_id':i['modelID'],
        'native_tool':p['tool'],'logical_tool':handled['tool'],'arguments':handled['arguments'],
        'helper_receipt_ref':handled['receipt_ref'],'helper_exit_code':0,
        'nonce':context.get('nonce'),'envelope':context.get('envelope'),'challenge_ref':context.get('challenge_ref'),
        'source_event_at':times['end']/1000,'message_completed_at':completed/1000 if completed is not None else None,
        'task_or_check_completed':False,
        'owned_history_sha256':hashlib.sha256(json.dumps(history,sort_keys=True,separators=(',',':')).encode()).hexdigest()}

def fixed_reader_context(context,handled):
    """Private controller record selected by privileged server reader only.

    This is not a model/API upload operation. The installed reader must verify
    the opaque kernel reference against the actual tuple/profile membership.
    """
    owner=context.get('owner',{})
    if set(owner)!={'project','role','actor','generation','epoch'} or type(owner['epoch']) is not int:
        raise RuntimeError('fixed native owner tuple absent')
    for key in ('profile_sha256','kernel_ref','revision'):
        if key not in context:raise RuntimeError('reader binding absent')
    if type(context['revision']) is not int or context['revision']<0:raise RuntimeError('invalid controller revision')
    ref=hashlib.sha256(json.dumps([owner[k] for k in ('project','role','actor','generation','epoch')],separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
    return dict(owner_ref=ref,profile_sha256=context['profile_sha256'],kernel_ref=context['kernel_ref'],
        session_id=context['session_id'],user_message_id=context['user_message_id'],input_sha256=context['user_input_sha256'],
        challenge=context.get('nonce'),envelope=context.get('envelope'),issued_at=context.get('issued_at_ms',0)/1000,
        deadline=context.get('deadline_ms',0)/1000,provider_id=context['provider_id'],model_id=context['model_id'],
        helper=dict(tool=handled['tool'],args=handled['arguments'],output=handled['output'],
            receipt_ref=handled['receipt_ref'],recorded_at=handled['handled_at_ms']/1000),revision=context['revision'])
