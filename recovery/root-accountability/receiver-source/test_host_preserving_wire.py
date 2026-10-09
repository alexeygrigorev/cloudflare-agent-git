import copy,sys,sqlite3
import pytest
from test_operational_receiver import setup
from test_receiver_server import config_for
from host_preserving_wire import HostPreservingWire
from operational_receiver import CheckFenced

@pytest.fixture
def wire(setup,tmp_path):
 a,c,o,p,r=setup;o['generation']='win32:300:30000'
 with a._tx() as db:
  db.execute('UPDATE roles SET generation=?',(o['generation'],));db.execute('UPDATE agents SET generation=?',(o['generation'],))
 cfg=config_for(a,o,tmp_path);cfg['bindings']['actor']['host']='host'
 sys.path.insert(0,'/home/alexey/git/cloudflare-agent-git/scripts/recovery')
 from host_recovery_adapter import HostRecoveryWire
 h=HostRecoveryWire.__new__(HostRecoveryWire);h.authority=a;h.plan={'project':'p','guardian':{'source_sha256':'fixed-code','task_action_sha256':'fixed-task','session_id':2,'user_sid':'fixture-user'}};h._config=lambda:cfg
 def auth(credential,fingerprint):
  if credential!={'identity_id':'outside-caretaker','token':'fixture'} or fingerprint!='fixed-cert':raise CheckFenced('wrong caretaker device')
 h.authenticate=auth
 kernels=[{'pid':i,'creation_filetime':i*100} for i in (100,200,300,400)]
 history='a'*64
 receipt={'baseline':{'owner':o,'host':'host','profile_sha256':'b'*64,'native':{'id':'actor','worker':kernels[0],'workload':kernels[1],'host_process':kernels[2]},'model':{'owner':o,'backend':kernels[3],'job':{'name':'fixture-live-job','session_id':2}},'guardian':dict(h.plan['guardian'],pid=999,creation_filetime=99900),'checkpoint':{'thread_id':'parent','provider_turn_state':'completed','pending_tool_count':0,'protected_state':'clear','history_receipt_sha256':history}},'observed_at':1000.,'native_alive':[dict(k,state='alive') for k in kernels],'job':{'queried':True,'retained_handle_ref':'retained-actual-query','active_processes':2},'api_port':8813,'opposite_slot':{'port':8814,'free':True},'source_receipt_ref':'c'*64,'owned_sdk':{'thread_id':'parent','turn_id':'current-completed-turn','status':'completed','pending_tool_count':0,'history_receipt_sha256':history}}
 bindings={'actor':{'owner':o,'profile_sha256':'b'*64,'api_port':8813,'thread_id':'parent','activation_ref':'activation'}}
 w=HostPreservingWire(h,bindings=bindings)
 return a,c,o,w,receipt

def request(w,op,**args):return w.handle(dict(v=1,op=op,credential={'identity_id':'outside-caretaker','token':'fixture'},**args),'fixed-cert')

def test_actual_primary_host_schema_then_expired_disposition(wire):
 a,c,o,w,r=wire
 assert request(w,'preserving-challenge')=={'status':'no-preserving-permit'}
 c[0]=5000;r['observed_at']=5000
 assert request(w,'preserving-observe',receipt=r)['status']=='preserving-observation-recorded'
 permit=request(w,'preserving-challenge')['permit'];assert permit['new_api_port']==8814
 assert request(w,'preserving-challenge')['permit']==permit

@pytest.mark.parametrize('field,value',[('observed_at',1.),('observed_at',5002.),('api_port',8803),('opposite_slot',{'port':8814,'free':False}),('job',{'queried':True,'retained_handle_ref':'query','active_processes':0}),('native_alive',[])])
def test_negative_observation_does_not_retire_current_owner(wire,field,value):
 a,c,o,w,r=wire;c[0]=5000;r['observed_at']=5000;r[field]=value
 with pytest.raises((CheckFenced,RuntimeError)):request(w,'preserving-observe',receipt=r)
 with sqlite3.connect(a.path) as db:assert db.execute('SELECT holder FROM roles').fetchone()[0]=='actor'

def test_privileged_caretaker_not_model_or_caller_identity(wire):
 a,c,o,w,r=wire
 with pytest.raises(CheckFenced):w.handle(dict(v=1,op='preserving-observe',receipt=r,credential={'identity_id':'root-model','token':'fixture'}),'fixed-cert')

@pytest.mark.parametrize('part,field,value',[('guardian','source_sha256','other-code'),('owned_sdk','status','busy'),('owned_sdk','thread_id','foreign'),('owned_sdk','pending_tool_count',1)])
def test_pinned_producer_and_fresh_sdk_negatives(wire,part,field,value):
 a,c,o,w,r=wire;c[0]=5000;r['observed_at']=5000
 if part=='guardian':r['baseline']['guardian'][field]=value
 else:r[part][field]=value
 with pytest.raises((CheckFenced,RuntimeError)):request(w,'preserving-observe',receipt=r)
