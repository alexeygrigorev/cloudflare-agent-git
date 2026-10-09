"""Cold, provisioner-pinned integration into the single existing mTLS server."""
import importlib.util,sys
from pathlib import Path

MODULES=('root_reply_deadline','operational_receiver','managed_check_binding','root_reply_receiver','principal_snapshot','receiver_server','preserving_receiver','preserving_enrollment','host_preserving_wire','operational_host_control')

def load_operational(config,authority,channels,host_wire,pinned_file,*,config_getter=None):
 plan=config.get('operational_receiver')
 if plan is None:return None
 if not isinstance(plan,dict) or set(plan)!={'modules','preserving_bindings','preserving_factory_sha256','check_method'} or set(plan['modules'])!=set(MODULES):raise PermissionError('exact installed operational module plan required')
 for name in MODULES:
  entry=plan['modules'][name]
  if set(entry)!={'path','sha256'}:raise PermissionError('fixed operational source pin required')
  source=pinned_file(entry['path'],entry['sha256'])
  old=sys.modules.get(name)
  if old is not None:
   if Path(old.__file__).resolve()!=source.resolve():raise PermissionError('foreign operational module cache')
   continue
  spec=importlib.util.spec_from_file_location(name,source);module=importlib.util.module_from_spec(spec);sys.modules[name]=module
  try:spec.loader.exec_module(module)
  except BaseException:sys.modules.pop(name,None);raise
 from receiver_server import OperationalReceiver
 from host_preserving_wire import HostPreservingWire
 if host_wire is None:raise PermissionError('existing pinned caretaker required')
 from operational_host_control import OperationalHostControl
 root=OperationalReceiver(authority,config,channels,config_getter=config_getter)
 host=HostPreservingWire(host_wire,bindings=plan['preserving_bindings'],preserving_factory_sha256=plan['preserving_factory_sha256'])
 return {'root':root,'host':host,'control':OperationalHostControl(host,root)}

def role_control(server,config,request,authenticate):
 # Existing HTTP mTLS certificate/native scope is checked BEFORE this call.
 # Existing handle/inspect authenticates the Bus token and native generation.
 authenticate(config,{**request,'op':'inspect'})
 receiver=getattr(server,'operational',None)
 if receiver is None:raise PermissionError('paired operational receiver not installed')
 result=receiver['root'].handle_authenticated(request)
 return {'v':1,'status':'ok','result':result}

def host_control(server,request,fingerprint):
 receiver=getattr(server,'operational',None)
 if receiver is None:raise PermissionError('paired preserving receiver not installed')
 if request.get('op')=='reply-probe':return receiver['control'].handle(request,fingerprint)
 return receiver['host'].handle(request,fingerprint)
