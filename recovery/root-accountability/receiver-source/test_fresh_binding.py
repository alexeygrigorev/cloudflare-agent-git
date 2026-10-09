import copy
import pytest
from test_operational_receiver import setup
from test_receiver_server import config_for
from receiver_server import OperationalReceiver
from operational_receiver import CheckFenced

def test_fresh_enrollment_binding_is_read_without_reloading_code(setup,tmp_path):
    a,c,o,p,r=setup;before=config_for(a,o,tmp_path);fresh=copy.deepcopy(before)
    fresh['bindings']['actor']['retired']=True
    receiver=OperationalReceiver(a,before,None,config_getter=lambda:fresh)
    with pytest.raises(CheckFenced):receiver.handle_authenticated(dict(o,op='complete_check',receipt_ref='receipt'))
    fresh['bindings']['actor']['retired']=False
    receiver.checks.complete_check=lambda owner,ref:dict(current_binding_seen=True)
    assert receiver.handle_authenticated(dict(o,op='complete_check',receipt_ref='receipt'))['current_binding_seen']

@pytest.mark.parametrize('field,value',[('authority_db','foreign.db'),('sink_journal','foreign-sink.db'),('operational_receiver',{'modules':'foreign'}),('operational_http',{'path':'foreign-source'})])
def test_fresh_profile_cannot_hot_reload_source_or_databases(setup,tmp_path,field,value):
    a,c,o,p,r=setup;before=config_for(a,o,tmp_path);fresh=copy.deepcopy(before);fresh[field]=value
    receiver=OperationalReceiver(a,before,None,config_getter=lambda:fresh)
    with pytest.raises(CheckFenced):receiver.current_config()
