import copy, hashlib, sqlite3
import pytest
from coordination.role_failover import RoleAuthority, Fenced
from operational_receiver import CompletedCheckReceiver, CheckFenced

@pytest.fixture
def setup(tmp_path):
 clock=[1000.]
 a=RoleAuthority(tmp_path/'authority.db',clock=lambda:clock[0],boot_id='fixture')
 a.configure('p','root',['actor']);a.observe('actor','host','g',ready=True,draft=False,quota_ok=True)
 e=a.tick('p','root')['epoch'];a.renew('p','root','actor','g',e,ttl=1000)
 o=dict(project='p',role='root',actor='actor',generation='g',epoch=e)
 final='Current owner checked evidence; stale team remains held and corrective owner is assigned.'
 sha=hashlib.sha256(final.encode()).hexdigest()
 result=dict(owner=o,parent_thread_id='parent',parent_turn_id='turn',child_thread_id='child',child_turn_id='childturn',model='gpt-6-luna',effort='max',raw_fork_mode='none',actual_execution_context=dict(thread_id='child',turn_id='childturn',model='gpt-6-luna',effort='max',sandbox_policy={'type':'read-only'},approval_policy='never'),required_reads_completed=True,child_status='completed',parent_wait_status='completed',own_result=final,result_sha256=sha,parent_accept_thread_id='parent',parent_accept_turn_id='turn',helper_exit_code=0,source_event_at=1000.)
 for k in ('spawn_event_id','wait_event_id','child_completed_event','instruction_completed_event','report_completed_event','owned_rollout_receipt_sha256'):result[k]='fixed-'+k
 result['parent_accept_event']=dict(type='dynamicToolCall',tool='root_check_result',namespace=None,status='completed',success=True,id='new-event',arguments=dict(check_envelope='request',child_thread_id='child',child_turn_id='childturn',result_sha256=sha,next_action='Follow assigned repair',checkpoint='Next accepted output'))
 def dispatch(owner,command,timeout):
  # Prove there is no authority transaction held across native callback/RPC.
  with sqlite3.connect(a.path,timeout=.1) as db:db.execute('BEGIN IMMEDIATE');db.rollback()
  return dict(command,state='completed',evidence={'check_result':copy.deepcopy(result)})
 r=CompletedCheckReceiver(a,model_binding=lambda owner:{'owner':o,'thread_id':'parent'},dispatch=dispatch,clock=lambda:clock[0])
 return a,clock,o,result,r

def due(a):
 with sqlite3.connect(a.path) as db:return db.execute('SELECT check_due FROM roles').fetchone()[0]

def test_verified_collection_is_not_completion_and_replay_never_extends(setup):
 a,c,o,p,r=setup;before=due(a);ref=r.collect(o,key='key',check_envelope='request')['receipt_ref'];assert due(a)==before
 assert r.complete_check(o,ref)['replayed'] is False;assert due(a)==2800
 c[0]+=10;assert r.complete_check(o,ref)['replayed'] is True;assert due(a)==2800
 with sqlite3.connect(a.path) as db:assert db.execute("SELECT COUNT(*) FROM events WHERE kind='check_completed'").fetchone()[0]==1

@pytest.mark.parametrize('key,value',[('raw_fork_mode','all'),('effort','low'),('child_status','running'),('parent_wait_status','timeout'),('helper_exit_code',1),('parent_thread_id','foreign'),('parent_accept_turn_id','old'),('required_reads_completed',False),('source_event_at',879.),('source_event_at',1002.)])
def test_proof_negatives(setup,key,value):
 a,c,o,p,r=setup;p[key]=value
 with pytest.raises(CheckFenced):r.collect(o,key='key',check_envelope='request')
 with sqlite3.connect(a.path) as db:assert db.execute('SELECT COUNT(*) FROM native_check_receipts').fetchone()[0]==0

def test_configured_metadata_without_raw_execution_context_is_denied(setup):
 a,c,o,p,r=setup;p['actual_execution_context']={}
 with pytest.raises(CheckFenced):r.collect(o,key='key',check_envelope='request')

def test_changed_replayed_native_response_is_denied(setup):
 a,c,o,p,r=setup;r.collect(o,key='key',check_envelope='request');p['parent_accept_event']['id']='other-event'
 with pytest.raises(CheckFenced):r.collect(o,key='key',check_envelope='request')

def test_expired_owner_cannot_complete_or_revive(setup):
 a,c,o,p,r=setup;r.collect(o,key='key',check_envelope='request');c[0]=2001
 with pytest.raises(Fenced):r.complete_check(o,'key')

def test_parent_tool_must_be_model_event_not_child_or_startup_ack(setup):
 a,c,o,p,r=setup;p['parent_accept_event']['tool']='root_role_ack'
 with pytest.raises(CheckFenced):r.collect(o,key='key',check_envelope='request')

def test_actual_model_event_cannot_complete_another_receipt_key(setup):
 a,c,o,p,r=setup;r.collect(o,key='key',check_envelope='request')
 with pytest.raises(CheckFenced):r.collect(o,key='other-key',check_envelope='request')
 with sqlite3.connect(a.path) as db:assert db.execute('SELECT COUNT(*) FROM native_check_receipts').fetchone()[0]==1
