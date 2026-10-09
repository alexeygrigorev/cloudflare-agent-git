import types,sqlite3
import pytest
from test_operational_receiver import setup
from test_root_reply_receiver import make
from operational_host_control import OperationalHostControl
from operational_receiver import CheckFenced

def control(setup):
 a,c,o,r,ch,data=make(setup)
 def auth(credential,fingerprint):
  if credential!='caretaker' or fingerprint!='device':raise CheckFenced('bad privileged device')
 host=types.SimpleNamespace(authority=a,plan={'project':'p'},authenticate=auth,_owner=lambda row:o)
 return a,c,o,r,OperationalHostControl(host,types.SimpleNamespace(replies=r)),data

def test_privileged_probe_returns_genuine_reply_not_check_completion(setup):
 a,c,o,r,ctl,data=control(setup)
 with a._tx() as db:due=a._get(db,'p','root')['check_due']
 result=ctl.handle({'v':1,'credential':'caretaker','op':'reply-probe'},'device')
 assert result['current_model_reply'] and result['check_outcome_not_implied']
 with a._tx() as db:assert a._get(db,'p','root')['check_due']==due
 assert ctl.handle({'v':1,'credential':'caretaker','op':'reply-probe'},'device')['nonce']==result['nonce']

@pytest.mark.parametrize('change',[{'credential':'model'},{'nonce':'caller'},{'proof':{}},{'op':'unknown'}])
def test_privileged_probe_denies_arbitrary_source_or_model_credential(setup,change):
 a,c,o,r,ctl,data=control(setup)
 with pytest.raises(CheckFenced):ctl.handle(dict({'v':1,'credential':'caretaker','op':'reply-probe'},**change),'device')

def test_no_authentication_cannot_issue_challenge(setup):
 a,c,o,r,ctl,data=control(setup)
 with pytest.raises(CheckFenced):ctl.handle({'v':1,'credential':'caretaker','op':'reply-probe'},'other-device')

def test_missing_model_reply_event_is_not_healthy_custody(setup):
 a,c,o,r,ctl,data=control(setup);data['event']={'tool':'root_role_ack'}
 result=ctl.handle({'v':1,'credential':'caretaker','op':'reply-probe'},'device')
 assert result['status']=='delivered' and not result['current_model_reply']
