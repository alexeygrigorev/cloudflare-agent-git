import json,sqlite3
import pytest
from test_operational_receiver import setup
from test_receiver_server import config_for
from receiver_server import OperationalReceiver
from operational_receiver import CheckFenced

def request(o):
 return dict(o,v=1,op='root_check_gate',credential={'identity_id':'bound'},check_envelope='check-1',parent_turn_id='turn-1',phase='thread-start')

def test_gate_is_current_server_activation_and_durable_no_deadline_extension(setup,tmp_path):
 a,c,o,p,r=setup;cfg=config_for(a,o,tmp_path);receiver=OperationalReceiver(a,cfg,None)
 with a._tx() as db:before=dict(a._get(db,o['project'],'root'))
 result=receiver.handle_authenticated(request(o))
 assert result['thread_id']=='parent' and result['owner']==o
 assert result['valid_until']<=c[0]+5 and result['proof_kind']=='server-authority-gate'
 with a._tx() as db:
  assert json.loads(db.execute('SELECT body FROM native_check_gates WHERE ref=?',(result['role_gate_ref'],)).fetchone()[0])==result
  assert dict(a._get(db,o['project'],'root'))==before

@pytest.mark.parametrize('change',[{'phase':'arbitrary'},{'thread_id':'caller-cid'},{'proof':True},{'parent_turn_id':''},{'check_envelope':''},{'model':'expensive'}])
def test_gate_denies_caller_proof_or_arbitrary_effect(setup,tmp_path,change):
 a,c,o,p,r=setup;receiver=OperationalReceiver(a,config_for(a,o,tmp_path),None)
 with pytest.raises(CheckFenced):receiver.handle_authenticated(dict(request(o),**change))

def test_expired_owner_cannot_obtain_pre_spend_gate(setup,tmp_path):
 a,c,o,p,r=setup;receiver=OperationalReceiver(a,config_for(a,o,tmp_path),None)
 c[0]+=10000
 with pytest.raises(Exception):receiver.handle_authenticated(request(o))
 with a._tx() as db:assert not db.execute("SELECT name FROM sqlite_master WHERE name='native_check_gates'").fetchone()

def test_boolean_tool_exit_is_not_activation(setup,tmp_path):
 a,c,o,p,r=setup;cfg=config_for(a,o,tmp_path)
 with sqlite3.connect(cfg['sink_journal']) as db:
  body=json.loads(db.execute('SELECT result FROM sink_receipts').fetchone()[0]);body['evidence']['model']['first_tool']['exit_code']=False
  db.execute('UPDATE sink_receipts SET result=?',(json.dumps(body),))
 with pytest.raises(CheckFenced):OperationalReceiver(a,cfg,None).handle_authenticated(request(o))
