import json,sqlite3
import pytest
from test_operational_receiver import setup
from receiver_server import OperationalReceiver,activated_model
from operational_receiver import CheckFenced

def config_for(a,o,tmp_path):
 sink=tmp_path/'sink.db'
 with sqlite3.connect(sink) as db:
  db.execute('CREATE TABLE sink_receipts(key TEXT PRIMARY KEY,body TEXT,result TEXT)')
  db.execute('INSERT INTO sink_receipts VALUES(?,?,?)',('activation',json.dumps({'owner':o,'operation':'root-model-evidence'}),json.dumps({'state':'completed','evidence':{'model':{'native_actor':o['actor'],'thread_id':'parent','first_tool':{'exit_code':0}}}})))
 with a._tx() as db:db.execute('INSERT INTO activation_receipts VALUES(?,?,?,?,?)',(o['project'],'root',o['epoch'],'own-ack','activation'))
 return {'authority_db':a.path,'sink_journal':str(sink),'bindings':{o['actor']:{'generation':o['generation'],'role':'root','project':o['project']}}}

def test_readonly_binding_does_not_create_missing_sink(setup,tmp_path):
 a,c,o,p,r=setup;cfg=config_for(a,o,tmp_path);missing=tmp_path/'absent.db';cfg['sink_journal']=str(missing)
 with pytest.raises(sqlite3.OperationalError):activated_model(cfg,o)
 assert not missing.exists()

@pytest.mark.parametrize('field,value',[('native_actor','other'),('thread_id',''),('first_tool',{'exit_code':1})])
def test_foreign_or_failed_model_activation_denied(setup,tmp_path,field,value):
 a,c,o,p,r=setup;cfg=config_for(a,o,tmp_path)
 with sqlite3.connect(cfg['sink_journal']) as db:
  x=json.loads(db.execute('SELECT result FROM sink_receipts').fetchone()[0]);x['evidence']['model'][field]=value;db.execute('UPDATE sink_receipts SET result=?',(json.dumps(x),))
 with pytest.raises(CheckFenced):activated_model(cfg,o)

def test_caller_shaped_receipt_never_reaches_native_dispatch(setup,tmp_path):
 a,c,o,p,r=setup;cfg=config_for(a,o,tmp_path)
 class Channels:
  def dispatch(self,*args):raise AssertionError('must not dispatch forged evidence')
 receiver=OperationalReceiver(a,cfg,Channels())
 with pytest.raises(CheckFenced):receiver.handle_authenticated(dict(o,op='complete_check',receipt_ref='fake',evidence=p))

def test_fixed_channel_bound_to_owner_not_request_actor_metadata(setup,tmp_path):
 a,c,o,p,r=setup;cfg=config_for(a,o,tmp_path);seen=[]
 class Channels:
  def dispatch(self,owner,command,timeout):
   seen.append((owner.actor,owner.generation,command))
   return dict(command,state='completed',evidence={'check_result':p})
 receiver=OperationalReceiver(a,cfg,Channels());result=receiver.handle_authenticated(dict(o,op='check_result_collect',key='proof',check_envelope='request'))
 assert result['receipt_ref']=='proof';assert seen[0][:2]==('actor','g');assert seen[0][2]['payload']['thread_id']=='parent'
 receiver.handle_authenticated(dict(o,op='complete_check',receipt_ref='proof'))
 cfg['bindings']['actor']['retired']=True
 with pytest.raises(CheckFenced):receiver.handle_authenticated(dict(o,op='complete_check',receipt_ref='proof'))
