import hashlib,copy,threading,sqlite3
import pytest
from test_host_preserving_wire import wire,request
from test_operational_receiver import setup
from preserving_enrollment import PreservingEnrollment
from operational_receiver import CheckFenced
from host_recovery_adapter import VerifiedSuccessor

def prepare(wire):
    a,c,o,w,r=wire;c[0]=5000;r['observed_at']=5000
    request(w,'preserving-observe',receipt=r)
    permit=request(w,'preserving-challenge')['permit'];nonce=permit['challenge']
    w.host._lock=threading.RLock();w.host.plan.update(win_state_root='C:/owned/state',win_workspace='C:/owned/repo')
    suffix=hashlib.sha256(nonce.encode()).hexdigest();actor='fa25a965-b56b-43dd-8907-3264175b9b75'
    leaf=dict(actor=actor,generation='win32:1001:100100',kernel={'pid':1001,'creation_filetime':100100},whoami={'id':actor,'tag':'win35-root-capsule-api-recovery-'+suffix[:16],'workspace':'C:/owned/repo'},root_tag='win35-root-capsule-api-recovery-'+suffix[:16],state_dir='C:/owned/state/recovery-'+suffix,host='host',actual_leaf_verified=True,leaf_sha256='d'*64,holding_profile_sha256='e'*64,api_port=8814)
    seen=[]
    def enroll(proof,s):
        assert type(proof) is VerifiedSuccessor
        assert proof.baseline.actor==o['actor'];assert proof.nonce==nonce
        assert proof.factory_source=='f'*64
        with a._tx() as db:
            row=a._get(db,'p','root');assert row['holder'] is None and row['epoch']==o['epoch']+1
        seen.append((proof,s));return {'binding_digest':'actual-held-record'}
    w.host._held_enrollment=enroll;w.host._read_handoff=lambda n,d:dict(status='enrolled_held_api_candidate',challenge=n,binding_digest=d)
    return a,c,o,w,permit,leaf,seen,PreservingEnrollment(w,factory_sha256='f'*64)

def test_typed_successor_reuses_existing_gate_without_death(wire):
    a,c,o,w,p,s,seen,e=prepare(wire)
    assert e.enroll(p['challenge'],s)['status']=='enrolled_held_api_candidate'
    assert len(seen)==1
    assert e.enroll(p['challenge'],s)['status']=='enrolled_held_api_candidate'
    assert len(seen)==1

@pytest.mark.parametrize('field,value',[('actor','not-uuid'),('generation','win32:1001:old'),('api_port',8813),('actual_leaf_verified',False),('leaf_sha256','unknown'),('host','foreign'),('root_tag','foreign'),('state_dir','C:/unrelated')])
def test_invalid_new_leaf_never_reaches_enrollment(wire,field,value):
    a,c,o,w,p,s,seen,e=prepare(wire);s[field]=value
    with pytest.raises((CheckFenced,RuntimeError)):e.enroll(p['challenge'],s)
    assert not seen

def test_other_current_holder_not_overwritten(wire):
    a,c,o,w,p,s,seen,e=prepare(wire)
    with a._tx() as db:db.execute('UPDATE roles SET holder=?,generation=?,epoch=epoch+1',('productive','generation'))
    with pytest.raises(CheckFenced):e.enroll(p['challenge'],s)
    assert not seen

def test_ambiguous_enrollment_never_replayed(wire):
    a,c,o,w,p,s,seen,e=prepare(wire)
    def crash(*args):seen.append('attempt');raise RuntimeError('unknown effect')
    w.host._held_enrollment=crash
    with pytest.raises(RuntimeError):e.enroll(p['challenge'],s)
    with pytest.raises(CheckFenced):e.enroll(p['challenge'],s)
    assert seen==['attempt']

def test_unknown_nonce_never_enrolls(wire):
    a,c,o,w,p,s,seen,e=prepare(wire)
    with pytest.raises(CheckFenced):e.enroll('invented-nonce',s)
    assert not seen
