"""Genuine no-model shell leaf bootstrap for the single Guardian factory.

No own identity is minted. Model/backend startup is controlled through the
existing native channel only after held enrollment and real native fencing.
"""
import hashlib,json,pathlib,platform,subprocess,time,sys,re
if __name__=='__main__':
    if not sys.flags.isolated or not sys.flags.no_site or len(sys.argv)!=2:
        raise SystemExit('fixed isolated native shell required')
    bootstrap_root=pathlib.Path(__file__).resolve().parent
    bootstrap_pin=sys.argv[1]
    if not re.fullmatch('[0-9a-f]{64}',bootstrap_pin):raise SystemExit('fixed shell source required')
    bootstrap_manifest=bootstrap_root/'source-pins.json'
    if hashlib.sha256(bootstrap_manifest.read_bytes()).hexdigest()!=bootstrap_pin:
        raise SystemExit('fixed shell source changed')
    for entry in json.loads(bootstrap_manifest.read_bytes())['entries']:
        rel=pathlib.PurePosixPath(entry['path'])
        if rel.is_absolute() or '..' in rel.parts:raise SystemExit('fixed shell source path required')
        file=bootstrap_root.joinpath(*rel.parts)
        if any(p.is_symlink() or getattr(p.stat(),'st_file_attributes',0)&0x400 for p in (file,*file.parents)):
            raise SystemExit('fixed shell source reparse held')
        if hashlib.sha256(file.read_bytes()).hexdigest()!=entry['sha256']:raise SystemExit('fixed shell source changed')
    sys.path.insert(0,str(bootstrap_root))

BASE=pathlib.Path('C:/Users/User/git/cloudflare-agent-git/.local/win35-root-bootstrap')
PROFILE=BASE/'api-runtime.private.json'
HERE=pathlib.Path(__file__).resolve().parent

def main():
    from opencode_win_constructor import load_private,verify_private,load_module,JOB_PIN,WRITER_PIN,APLEXER,APLEXER_PIN
    profile=load_private(PROFILE)
    if profile.get('runtime_mode')!='api-root' or profile.get('root_runtime_kind')!='opencode-native-v1':
        raise RuntimeError('explicit accepted OpenCode holding profile required')
    if (pathlib.Path(profile['host_script'])!=pathlib.Path(__file__).resolve()
        or hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest()!=profile['host_script_sha256']):
        raise RuntimeError('fixed native shell source pin changed')
    directory=pathlib.Path(profile['state_dir'])
    from opencode_runtime_profile import INCARNATION,BASE as LEAVES
    if directory.parent!=LEAVES or not INCARNATION.fullmatch(directory.name):raise RuntimeError('fixed successor leaf required')
    verify_private(directory)
    if hashlib.sha256(APLEXER.read_bytes()).hexdigest()!=APLEXER_PIN:raise RuntimeError('native WHOAMI source changed')
    native=json.loads(subprocess.check_output([str(APLEXER),'whoami','--json'],text=True,timeout=10))
    if (native.get('tag')!=profile['root_tag'] or native.get('engine')!='shell'
        or native.get('workspace','').replace('\\','/').lower()!=profile['workspace'].replace('\\','/').lower()):
        raise RuntimeError('actual new native shell identity differs')
    job_module=load_module('root_shell_kernel_dependency',BASE/'next12/win35_root_job.py',JOB_PIN)
    writer=load_module('root_shell_private_writer',HERE/'opencode_private_writer.py',WRITER_PIN)
    kernel=job_module.current_process_binding()
    generation='win32:'+str(kernel['pid'])+':'+str(kernel['creation_filetime'])
    writer.save(directory/('native-startup-'+native['id']+'.private.json'),
        {'native':native,'model_started':False,'host':platform.node(),'kernel':kernel,'generation':generation,
         'runtime_discriminator':'opencode-native-v1','execution_mode':'server-owned-native-session-GUI-Session2'})
    while True:
        current=load_private(PROFILE)
        if current.get('state_dir')!=str(directory):raise RuntimeError('factory profile moved; preserve old native shell')
        if current.get('actor')==native['id'] and current.get('generation')==generation:break
        time.sleep(1)
    # The final cold-plan constructor must compose the existing Guardian's
    # authenticated cache writer/issuer/role proof/observer. Absence holds; an
    # enrollment leaf is never treated as an operating root/model ACK.
    from opencode_shell_runtime import build_runtime
    from opencode_native_channel import channel
    runtime,source_guard=build_runtime(current,native,kernel)
    while True:
        try:channel(current,native,runtime,source_guard)
        except Exception:
            writer.save(directory/'native-channel-failure.private.json',
                {'v':1,'native_actor':native['id'],'generation':generation,'observed_at':time.time(),
                 'phase':'channel-reconcile-required','model_success_claimed':False})
            time.sleep(5)

if __name__=='__main__':
    try:main()
    except Exception:raise SystemExit('fixed new native shell held')
