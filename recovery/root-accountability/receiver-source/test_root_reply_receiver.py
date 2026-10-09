import copy,sqlite3
import pytest
from test_operational_receiver import setup
from root_reply_receiver import NativeReplyReceiver
from operational_receiver import CheckFenced
from coordination.role_failover import Fenced

def make(setup):
    a,c,o,p,r=setup
    data={}
    def dispatch(owner,command,timeout):
        with sqlite3.connect(a.path,timeout=.1) as db:db.execute('BEGIN IMMEDIATE');db.rollback()
        payload=command['payload']
        if command['operation']=='root-reply-evidence':
            proof=dict(owner=o,thread_id='parent',nonce=payload['nonce'],envelope=payload['envelope'],turn_id='new-turn',method='turn-steer',accepted=True,input_receipt_ref='SDK-input',source_event_at=c[0])
            proof.update(data.get('input',{}))
            return dict(command,state='completed',evidence={'reply_input':proof})
        proof=dict(owner=o,thread_id='parent',turn_id='new-turn',input_receipt_ref='SDK-input',helper_exit_code=0,source_event_at=c[0],owned_rollout_receipt_sha256='a'*64,model_event=dict(type='dynamicToolCall',tool='root_role_reply',namespace=None,status='completed',success=True,id='model-reply-event',arguments=dict(nonce=payload['nonce'],envelope=payload['envelope'],body='I have consumed the challenge and assigned the evidence check.',next_action='Wait for bounded child outcome while preserving role response',checkpoint='Current check result')))
        for k,v in data.get('reply',{}).items():proof[k]=v
        for k,v in data.get('event',{}).items():proof['model_event'][k]=v
        for k,v in data.get('args',{}).items():proof['model_event']['arguments'][k]=v
        return dict(command,state='completed',evidence={'reply_result':proof})
    receiver=NativeReplyReceiver(a,model_binding=lambda owner:dict(owner=o,thread_id='parent'),dispatch=dispatch)
    ch=receiver.policy.issue('p','root',key='due',body={'request':'current custody'})
    return a,c,o,receiver,ch,data

def test_current_busy_model_response_qualifies_without_completed_child(setup):
    a,c,o,r,ch,data=make(setup)
    assert r.deliver(ch)['state']=='delivered'
    c[0]+=1
    assert r.collect_reply(ch.nonce)['state']=='replied'

@pytest.mark.parametrize('field,value',[('thread_id','child'),('turn_id','old-turn'),('input_receipt_ref','old-input'),('helper_exit_code',1)])
def test_foreign_child_old_turn_or_failed_helper_denied(setup,field,value):
    a,c,o,r,ch,data=make(setup);r.deliver(ch);data['reply']={field:value}
    with pytest.raises(CheckFenced):r.collect_reply(ch.nonce)

@pytest.mark.parametrize('field,value',[('tool','root_role_ack'),('status','inProgress'),('success',False)])
def test_ack_or_incomplete_event_never_reply(setup,field,value):
    a,c,o,r,ch,data=make(setup);r.deliver(ch);data['event']={field:value}
    with pytest.raises(CheckFenced):r.collect_reply(ch.nonce)

@pytest.mark.parametrize('field,value',[('nonce','old-nonce'),('envelope','old-envelope'),('body','')])
def test_challenge_and_meaningful_body_required(setup,field,value):
    a,c,o,r,ch,data=make(setup);r.deliver(ch);data['args']={field:value}
    with pytest.raises(CheckFenced):r.collect_reply(ch.nonce)

def test_mechanical_alive_or_late_reply_cannot_revive(setup):
    a,c,o,r,ch,data=make(setup);r.deliver(ch);c[0]+=121
    with pytest.raises((CheckFenced,Fenced,ValueError)):r.collect_reply(ch.nonce)
    assert r.policy._read(ch.nonce)['state']=='revoked'

def test_unverified_input_does_not_mark_delivery(setup):
    a,c,o,r,ch,data=make(setup);data['input']={'accepted':False}
    with pytest.raises(CheckFenced):r.deliver(ch)
    assert r.policy._read(ch.nonce)['state']=='pending'
