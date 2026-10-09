"""Explicit managed fresh SDK child method; never impersonates builtin spawn."""
import json,math,sqlite3
from operational_receiver import CheckFenced,text

def completed_tool(event,tool):
    if not isinstance(event,dict) or event.get('type')!='dynamicToolCall' or event.get('tool')!=tool or event.get('namespace') not in (None,'') or event.get('status')!='completed' or event.get('success') is not True:raise CheckFenced('genuine completed parent custom event required')
    text(event.get('id'))
    if not isinstance(event.get('arguments'),dict):raise CheckFenced('actual model arguments required')
    return event['arguments']

def validate_managed(result,owner,cid,parent_turn,child,child_turn,envelope):
    if result.get('launch_method')!='managed-sdk-fresh-v1' or 'raw_fork_mode' in result:raise CheckFenced('managed launch is not builtin raw fork proof')
    launch=result.get('managed_launch',{})
    fields={'owner','parent_thread_id','parent_turn_id','check_envelope','parent_spawn_event_id','child_thread_id','child_turn_id','history_mode','initial_turn_count','native_start_ref','role_gate_ref','turn_role_gate_ref','native_start_at','native_turn_at','quota_gate_ref','resource_gate_ref'}
    if not isinstance(launch,dict) or set(launch)!=fields:raise CheckFenced('immutable host-owned launch correlation required')
    expected={'owner':owner,'parent_thread_id':cid,'parent_turn_id':parent_turn,'check_envelope':envelope,'child_thread_id':child,'child_turn_id':child_turn,'history_mode':'fresh-empty'}
    if any(launch.get(k)!=v for k,v in expected.items()) or type(launch['initial_turn_count']) is not int or launch['initial_turn_count']!=0:raise CheckFenced('actual fresh child start/parent request mismatch')
    for name in ('native_start_ref','role_gate_ref','quota_gate_ref','resource_gate_ref'):text(launch[name])
    args=completed_tool(result.get('parent_spawn_event'),'root_spawn_check')
    if result.get('parent_spawn_thread_id')!=cid or result.get('parent_spawn_turn_id')!=parent_turn or args.get('check_envelope')!=envelope or launch['parent_spawn_event_id']!=result['parent_spawn_event']['id'] or result.get('spawn_event_id')!=launch['parent_spawn_event_id']:raise CheckFenced('genuine current parent launch event missing')
    args=completed_tool(result.get('parent_wait_event'),'root_wait_check')
    if result.get('parent_wait_thread_id')!=cid or result.get('parent_wait_turn_id')!=parent_turn or args.get('child_thread_id')!=child or args.get('child_turn_id')!=child_turn or result.get('wait_event_id')!=result['parent_wait_event']['id']:raise CheckFenced('genuine managed parent wait absent')


def validate_server_gates(authority,result,owner,cid,parent_turn,envelope):
    launch=result['managed_launch']
    if launch['role_gate_ref']==launch['turn_role_gate_ref']:raise CheckFenced('distinct pre-effect phases required')
    with authority._tx() as db:
        for field,phase,event_field in (('role_gate_ref','thread-start','native_start_at'),('turn_role_gate_ref','turn-start','native_turn_at')):
            try:row=db.execute('SELECT owner,body FROM native_check_gates WHERE ref=?',(launch[field],)).fetchone()
            except sqlite3.OperationalError:raise CheckFenced('actual server-issued pre-effect gates absent')
            if row is None:raise CheckFenced('caller-shaped gate reference absent')
            gate=json.loads(row['body']);event_at=launch.get(event_field)
            expected={'owner':owner,'thread_id':cid,'parent_turn_id':parent_turn,'check_envelope':envelope,'phase':phase,'role_gate_ref':launch[field],'current_activated':True,'proof_kind':'server-authority-gate'}
            if json.loads(row['owner'])!=owner or any(gate.get(k)!=v for k,v in expected.items()):raise CheckFenced('other owner/turn/request/phase gate')
            if type(event_at) not in (int,float) or not math.isfinite(event_at) or not gate['observed_at']-1<=event_at<=gate['valid_until']+1 or event_at>authority.clock()+1:raise CheckFenced('native effect outside fresh pre-effect gate')
        if launch['native_turn_at']<launch['native_start_at']:raise CheckFenced('native child turn predates start')
