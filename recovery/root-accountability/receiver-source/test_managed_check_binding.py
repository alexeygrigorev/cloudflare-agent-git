import copy,json
import pytest
from test_operational_receiver import setup,due
from operational_receiver import CheckFenced

def managed(setup):
    a,c,o,p,r=setup;r.method='managed-sdk-fresh-v1';p.pop('raw_fork_mode')
    p.update(launch_method='managed-sdk-fresh-v1',parent_spawn_thread_id='parent',parent_spawn_turn_id='turn',parent_wait_thread_id='parent',parent_wait_turn_id='turn')
    p['parent_spawn_event']=dict(type='dynamicToolCall',tool='root_spawn_check',namespace=None,status='completed',success=True,id=p['spawn_event_id'],arguments={'check_envelope':'request'})
    p['parent_wait_event']=dict(type='dynamicToolCall',tool='root_wait_check',namespace=None,status='completed',success=True,id=p['wait_event_id'],arguments={'child_thread_id':'child','child_turn_id':'childturn'})
    p['managed_launch']=dict(owner=o,parent_thread_id='parent',parent_turn_id='turn',check_envelope='request',parent_spawn_event_id=p['spawn_event_id'],child_thread_id='child',child_turn_id='childturn',history_mode='fresh-empty',initial_turn_count=0,native_start_ref='actual-sdk-start',role_gate_ref='current-role-before-start',turn_role_gate_ref='current-role-before-turn',native_start_at=1000.,native_turn_at=1000.,quota_gate_ref='fresh-reserve-before-start',resource_gate_ref='physical-check-before-start')
    with a._tx() as db:
        db.execute('CREATE TABLE native_check_gates(ref TEXT PRIMARY KEY,owner TEXT,body TEXT)')
        for field,phase in (('role_gate_ref','thread-start'),('turn_role_gate_ref','turn-start')):
            ref=p['managed_launch'][field]
            body=dict(owner=o,thread_id='parent',parent_turn_id='turn',check_envelope='request',phase=phase,observed_at=1000.,valid_until=1005.,role_gate_ref=ref,current_activated=True,proof_kind='server-authority-gate')
            db.execute('INSERT INTO native_check_gates VALUES(?,?,?)',(ref,json.dumps(o),json.dumps(body)))
    return a,c,o,p,r

def test_managed_parent_request_actual_context_wait_and_acceptance(setup):
    a,c,o,p,r=managed(setup)
    ref=r.collect(o,key='managed',check_envelope='request')['receipt_ref']
    assert r.complete_check(o,ref)['completed'];assert due(a)==2800

@pytest.mark.parametrize('field,value',[('owner',{'actor':'foreign'}),('parent_thread_id','foreign'),('child_thread_id','foreign'),('history_mode','forked'),('initial_turn_count',1),('quota_gate_ref',''),('role_gate_ref',''),('resource_gate_ref','')])
def test_forged_or_ungated_launch_never_completes(setup,field,value):
    a,c,o,p,r=managed(setup);p['managed_launch'][field]=value
    with pytest.raises(CheckFenced):r.collect(o,key='managed',check_envelope='request')

def test_managed_route_cannot_claim_builtin_fork_ancestry(setup):
    a,c,o,p,r=managed(setup);p['raw_fork_mode']='none'
    with pytest.raises(CheckFenced):r.collect(o,key='managed',check_envelope='request')

def test_caller_method_does_not_override_installed_native_contract(setup):
    a,c,o,p,r=managed(setup);r.method='native-direct-v1';p['raw_fork_mode']='none'
    with pytest.raises(CheckFenced):r.collect(o,key='managed',check_envelope='request')

def test_incomplete_parent_wait_is_not_accepted_managed_outcome(setup):
    a,c,o,p,r=managed(setup);p['parent_wait_event']['status']='inProgress'
    with pytest.raises(CheckFenced):r.collect(o,key='managed',check_envelope='request')


@pytest.mark.parametrize('field,value',[('role_gate_ref','caller-shaped'),('turn_role_gate_ref','caller-shaped'),('native_start_at',990.),('native_turn_at',1007.),('native_turn_at',float('nan'))])
def test_server_gate_references_and_actual_effect_time_required(setup,field,value):
    a,c,o,p,r=managed(setup);p['managed_launch'][field]=value
    with pytest.raises(CheckFenced):r.collect(o,key='managed',check_envelope='request')

def test_foreign_persisted_gate_cannot_be_used(setup):
    a,c,o,p,r=managed(setup)
    with a._tx() as db:
        ref=p['managed_launch']['role_gate_ref'];body=json.loads(db.execute('SELECT body FROM native_check_gates WHERE ref=?',(ref,)).fetchone()[0]);body['thread_id']='foreign'
        db.execute('UPDATE native_check_gates SET body=? WHERE ref=?',(json.dumps(body),ref))
    with pytest.raises(CheckFenced):r.collect(o,key='managed',check_envelope='request')
