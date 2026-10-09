import pytest
from test_operational_receiver import setup
from test_root_reply_receiver import make
from operational_receiver import CheckFenced

def test_known_subsecond_future_clock_is_accepted_without_extending_deadline(setup):
 a,c,o,r,ch,data=make(setup);data['input']={'source_event_at':1000.4}
 r.deliver(ch);c[0]+=1;data['reply']={'source_event_at':1001.4}
 assert r.collect_reply(ch.nonce)['state']=='replied'
 assert r.policy._read(ch.nonce)['deadline']==1120.

def test_far_future_native_clock_denied(setup):
 a,c,o,r,ch,data=make(setup);data['input']={'source_event_at':1002.}
 with pytest.raises(CheckFenced):r.deliver(ch)

def test_reply_before_actual_input_denied(setup):
 a,c,o,r,ch,data=make(setup);data['input']={'source_event_at':1000.4};r.deliver(ch)
 data['reply']={'source_event_at':1000.}
 with pytest.raises(CheckFenced):r.collect_reply(ch.nonce)

def test_boolean_helper_exit_never_counts_as_native_success(setup):
 a,c,o,r,ch,data=make(setup);r.deliver(ch);data['reply']={'helper_exit_code':False}
 with pytest.raises(CheckFenced):r.collect_reply(ch.nonce)

def test_restart_after_saved_input_reuses_original_authority_receipt(setup,monkeypatch):
 a,c,o,r,ch,data=make(setup);data['input']={'source_event_at':1000.}
 delivered=r.policy.delivered
 monkeypatch.setattr(r.policy,'delivered',lambda *args:(_ for _ in ()).throw(RuntimeError('crash after save')))
 with pytest.raises(RuntimeError):r.deliver(ch)
 c[0]+=1;monkeypatch.setattr(r.policy,'delivered',delivered)
 assert r.deliver(ch)['state']=='delivered'
 assert r.saved('reply-input:'+ch.nonce,'input',ch)['authority_received_at']==1000.
