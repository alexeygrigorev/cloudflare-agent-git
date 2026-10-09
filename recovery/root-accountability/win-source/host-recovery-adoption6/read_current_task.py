import sys
if not sys.flags.isolated or not sys.flags.no_site:raise SystemExit('requires isolated startup')
import pathlib,hashlib,json,importlib.util,subprocess,base64
BASE=pathlib.Path('C:/Users/User/git/cloudflare-agent-git/.local/win35-root-bootstrap')
def module(name,path,pin):
    if hashlib.sha256(path.read_bytes()).hexdigest()!=pin:raise RuntimeError('source mismatch')
    spec=importlib.util.spec_from_file_location(name,path);value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value
manifest=BASE/'host-recovery-consumer3/source-pins.json'
if hashlib.sha256(manifest.read_bytes()).hexdigest()!='5bfe1941d643dd5cbde2308a6f5f45be1c90fee2e1b0177e064e2306dd488679':raise RuntimeError('manifest mismatch')
pins={e['path']:e['sha256'] for e in json.loads(manifest.read_text(encoding='utf-8-sig'))['entries']}
guardian=module('guardian_observation',BASE/'host-recovery-consumer3/guardian_runtime.py',pins['guardian_runtime.py'])
writer=module('fixed_writer',BASE/'api-adoption5/private_writer.py','53c8f31299ccb87a1ab5faad5b821e3c8870bc9364ab59dacee669681aa53c31')
root=BASE/'host-recovery-adoption6';writer.ensure_private_directory(root)
task=guardian.actual_task_custody()
profile=BASE/'api-runtime.private.json';legacy=BASE/'runtime.private.json'
if hashlib.sha256(profile.read_bytes()).hexdigest()!='46690862edf284ddc8baa6eec3528c57c0dc6f6657f8cd42a63f8e93d62f1aa0':raise RuntimeError('current dead root profile changed')
if hashlib.sha256(legacy.read_bytes()).hexdigest()!='a301bb1227c734c93622d9a5428a55248e3e665c9032120e5268f1adcb0b01ac':raise RuntimeError('protected legacy changed')
status=json.loads((BASE/'host-recovery-consumer3/guardian-status.private.json').read_text()); actual=guardian.native_context(status['kernel']['pid']);assert actual['creation_filetime']==status['kernel']['creation_filetime'];assert guardian.owned_script_command(actual['command'],BASE/'host-recovery-consumer3/guardian_runtime.py')
receipt={'guardian_kernel':actual,'v':1,'task_custody':task,'api_profile_sha256':hashlib.sha256(profile.read_bytes()).hexdigest(),'legacy_profile_sha256':hashlib.sha256(legacy.read_bytes()).hexdigest(),'consumer_manifest_sha256':hashlib.sha256(manifest.read_bytes()).hexdigest(),'task_changes':False,'model_started':False}
target=root/'before.private.json'
if target.exists():raise RuntimeError('preserve existing snapshot')
writer.save(target,receipt)
print(json.dumps({'task_snapshot_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'task_changes':False,'model_started':False,'legacy_unchanged':True}))
