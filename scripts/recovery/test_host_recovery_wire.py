import copy
import hashlib
import json
import uuid
import pytest
from coordination.role_failover import RoleAuthority, Fenced
from host_recovery_adapter import HostRecoveryWire, HostRecoveryFenced


@pytest.fixture
def wire(tmp_path, monkeypatch):
    import role_fence_cli
    auth = RoleAuthority(tmp_path/'db', clock=lambda: 1000., boot_id='fixture')
    actor=str(uuid.uuid4()); gen='win32:3:30'
    auth.configure('project','root',[actor])
    auth.observe(actor,'win35',gen,ready=True,draft=False,quota_ok=True)
    owner=auth.tick('project','root')
    owner=dict(project='project',role='root',actor=actor,generation=gen,epoch=owner['epoch'])
    config={'bindings':{actor:dict(host='win35',generation=gen,project='project',role='root')},'authority_db':str(auth.path)}
    path=tmp_path/'profile';path.write_text(json.dumps(config));path.chmod(0o600)
    producer=tmp_path/'producer';producer.write_text('source fixture')
    guardian=dict(source_sha256=hashlib.sha256(producer.read_bytes()).hexdigest(),task_action_sha256='a'*64,session_id=2,user_sid='fixed-sid',pid=10,creation_filetime=100)
    plan=dict(producer_source_path=str(producer),scope='fixed-host-caretaker',project='project',tls_fingerprint='cert',credential_id='host',token_sha256=hashlib.sha256(b'secret').hexdigest(),guardian={k:v for k,v in guardian.items() if k not in ('pid','creation_filetime')},factory_sha256='b'*64,win_state_root='C:/state',win_workspace='C:/project')
    w=HostRecoveryWire(auth,path,plan)
    monkeypatch.setattr(role_fence_cli,'active_model',lambda *args:'cid')
    native=dict(id=actor,worker=dict(pid=1,creation_filetime=10),workload=dict(pid=2,creation_filetime=20),host_process=dict(pid=3,creation_filetime=30))
    model=dict(owner=owner,backend=dict(pid=4,creation_filetime=40),job=dict(name='job',session_id=2))
    baseline=dict(owner=owner,host='win35',guardian=guardian,native=native,model=model,checkpoint=dict(thread_id='cid',provider_turn_state='completed',pending_tool_count=0,history_receipt_sha256='c'*64,protected_state='clear'),profile_sha256='d'*64)
    credential=dict(identity_id='host',token='secret')
    def send(op,**data):return w.handle(dict(v=1,credential=credential,op=op,**data),'cert')
    send('observe-baseline',baseline=baseline)
    nonce=send('challenge')['challenge']
    receipt=copy.deepcopy(baseline);receipt.update(v=1,challenge=nonce,observed_at=1000.,factory_attempt=None)
    receipt.pop('profile_sha256');receipt['guardian'].update(state='alive',outside_owned_jobs=True)
    for key in ('worker','workload','host_process'):receipt['native'][key]['state']='dead'
    receipt['model']['backend']['state']='dead';receipt['model']['job'].update(queried=True,active_processes=0)
    return w,send,receipt,owner


@pytest.mark.parametrize('credential,cert',[(dict(identity_id='forged',token='secret'),'cert'),(dict(identity_id='host',token='forged'),'cert'),(dict(identity_id='host',token='secret'),'forged'),(dict(identity_id='host',token='secret',proof=True),'cert')])
def test_fake_auth_denied(wire,credential,cert):
    w,*_=wire
    with pytest.raises(HostRecoveryFenced):w.handle(dict(v=1,credential=credential,op='challenge'),cert)


@pytest.mark.parametrize('mutation',[lambda r:r.update(observed_at=1002.),lambda r:r.update(observed_at=969.),lambda r:r['model']['job'].update(queried=False),lambda r:r['model']['job'].update(active_processes=False),lambda r:r['native']['worker'].update(creation_filetime=11),lambda r:r['guardian'].update(pid=11),lambda r:r['checkpoint'].update(pending_tool_count=1),lambda r:r.update(factory_attempt='unknown'),lambda r:r.update(challenge='wrong')])
def test_unknown_or_stale_death_denied(wire,mutation):
    w,send,receipt,owner=wire;mutation(receipt)
    with pytest.raises((HostRecoveryFenced,KeyError)):send('reconcile',challenge=receipt['challenge'],receipt=receipt)
    with w.authority._tx() as db:assert w.authority._get(db,'project','root')['holder']==owner['actor']


def test_bounded_future_skew_and_cas_fence(wire):
    w,send,receipt,owner=wire;receipt['observed_at']=1000.403
    result=send('reconcile',challenge=receipt['challenge'],receipt=receipt)
    assert result['permit']['profile_sha256']=='d'*64
    with w.authority._tx() as db:
        row=w.authority._get(db,'project','root')
        assert row['holder'] is None and row['epoch']==owner['epoch']+1
        with pytest.raises(Fenced):w.authority._valid(db,*[owner[k] for k in ('project','role','actor','generation','epoch')])


def test_current_profile_changes_per_incarnation(wire):
    w,send,receipt,owner=wire
    with w.authority._tx() as db:
        payload=json.loads(db.execute('SELECT payload FROM host_kernel_baselines').fetchone()[0])
        payload['profile_sha256']='e'*64
        # The current challenge is frozen. Later observations cannot rewrite it.
        db.execute('UPDATE host_kernel_baselines SET payload=?',(json.dumps(payload),))
    result=send('reconcile',challenge=receipt['challenge'],receipt=receipt)
    assert result['permit']['profile_sha256']=='d'*64

