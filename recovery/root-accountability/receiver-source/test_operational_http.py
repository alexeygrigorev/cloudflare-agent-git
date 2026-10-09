import types
import pytest
from operational_http import role_control, host_control, load_operational

def test_authentication_precedes_receiver():
    seen=[]
    root=types.SimpleNamespace(handle_authenticated=lambda request:seen.append(request) or 'accepted')
    server=types.SimpleNamespace(operational={'root':root})
    request={'op':'complete_check','credential':'private','receipt_ref':'opaque'}
    def authenticate(config, probe):
        assert probe['op']=='inspect'
        assert probe['credential']=='private'
        seen.append('authenticated')
    result=role_control(server,{},request,authenticate)
    assert seen==['authenticated',request]
    assert result['result']=='accepted'

def test_failed_auth_never_collects_or_completes():
    root=types.SimpleNamespace(handle_authenticated=lambda request:pytest.fail('unauthenticated effect'))
    server=types.SimpleNamespace(operational={'root':root})
    def denied(*args):raise PermissionError('invalid native binding')
    with pytest.raises(PermissionError):role_control(server,{}, {'op':'complete_check'},denied)

def test_missing_receiver_holds_after_auth():
    calls=[]
    with pytest.raises(PermissionError):role_control(types.SimpleNamespace(),{}, {},lambda *a:calls.append(True))
    assert calls==[True]

def test_host_certificate_forwarded_to_installed_verifier():
    seen=[]
    host=types.SimpleNamespace(handle=lambda request,fingerprint:seen.append((request,fingerprint)) or 'verified')
    request={'op':'preserving-observe'}
    assert host_control(types.SimpleNamespace(operational={'host':host}),request,'bound-cert')=='verified'
    assert seen==[(request,'bound-cert')]

def test_missing_host_receiver_denies():
    with pytest.raises(PermissionError):host_control(types.SimpleNamespace(),{},'cert')

def test_no_plan_does_not_import_or_pin():
    assert load_operational({},None,None,None,lambda *a:pytest.fail('unexpected source access')) is None

@pytest.mark.parametrize('plan',[{}, {'modules':{}}, {'modules':{},'preserving_bindings':{},'proof':True}, {'modules':{},'preserving_bindings':{}}])
def test_incomplete_or_extra_plan_denied_before_source_access(plan):
    with pytest.raises(PermissionError):load_operational({'operational_receiver':plan},None,None,None,lambda *a:pytest.fail('unexpected source access'))
