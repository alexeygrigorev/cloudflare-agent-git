import json,hashlib,os
import pytest
from test_operational_receiver import setup
from principal_snapshot import fixed_snapshot
from operational_receiver import CheckFenced

def source(tmp_path,kind='head-verified-snapshot'):
    p=tmp_path/'snapshot.json'
    raw=json.dumps(dict(source_kind=kind,source_event_at='1970-01-01T00:00:01+00:00',source_receipt_sha256='a'*64,facts=[dict(topic='Current operational custody',state='unknown',evidence_ref=None,owner='recovery operator',next_action='Verify genuine current report',checkpoint='Accepted receiver integration')])).encode()
    p.write_bytes(raw);p.chmod(0o600)
    return p,dict(path=str(p),sha256=hashlib.sha256(raw).hexdigest())

def test_fresh_mirror_cannot_make_old_facts_current(setup,tmp_path):
    a,c,o,p,r=setup;path,plan=source(tmp_path)
    report=fixed_snapshot(plan,o,1000)
    assert report['current_source_fresh'] is False
    assert report['source_event_at']=='1970-01-01T00:00:01+00:00'
    assert report['principal_authored'] is False and report['recipient_owner']==o

@pytest.mark.parametrize('kind',['native-principal-report','native-head-report'])
def test_pinned_caller_header_cannot_forge_native_auth(setup,tmp_path,kind):
    a,c,o,p,r=setup;path,plan=source(tmp_path,kind)
    with pytest.raises(CheckFenced):fixed_snapshot(plan,o,1000)

def test_changed_bytes_or_unsafe_acl_held(setup,tmp_path):
    a,c,o,p,r=setup;path,plan=source(tmp_path)
    path.chmod(0o644)
    with pytest.raises(CheckFenced):fixed_snapshot(plan,o,1000)
    path.chmod(0o600);path.write_bytes(b'foreign')
    with pytest.raises(CheckFenced):fixed_snapshot(plan,o,1000)

def test_arbitrary_caller_path_field_denied(setup,tmp_path):
    a,c,o,p,r=setup;path,plan=source(tmp_path);plan['receipt']=True
    with pytest.raises(CheckFenced):fixed_snapshot(plan,o,1000)
