"""Fixed late-binding MCP entry, for the reviewed factory's own incarnation.

OpenCode session ID/backend FILETIME exist only after listener/session creation.
Factory writes the immutable private binding BEFORE any model prompt. MCP config
contains only leaf/source identifiers, never a credential or mutable profile.
"""
import hashlib,json,pathlib,re,sys
if __name__=='__main__':
    if not sys.flags.isolated or not sys.flags.no_site or len(sys.argv)!=3:
        raise SystemExit('fixed isolated MCP entry required')
    bootstrap_root=pathlib.Path(__file__).resolve().parent
    bootstrap_pin=sys.argv[2]
    if not re.fullmatch('[0-9a-f]{64}',bootstrap_pin):raise SystemExit('fixed MCP source required')
    bootstrap_manifest=bootstrap_root/'source-pins.json'
    if hashlib.sha256(bootstrap_manifest.read_bytes()).hexdigest()!=bootstrap_pin:
        raise SystemExit('fixed MCP source changed')
    for entry in json.loads(bootstrap_manifest.read_bytes())['entries']:
        rel=pathlib.PurePosixPath(entry['path'])
        if rel.is_absolute() or '..' in rel.parts:raise SystemExit('fixed MCP source path required')
        file=bootstrap_root.joinpath(*rel.parts)
        if any(p.is_symlink() or getattr(p.stat(),'st_file_attributes',0)&0x400 for p in (file,*file.parents)):
            raise SystemExit('fixed MCP source reparse held')
        if hashlib.sha256(file.read_bytes()).hexdigest()!=entry['sha256']:raise SystemExit('fixed MCP source changed')
    sys.path.insert(0,str(bootstrap_root))
from opencode_win_constructor import LEAVES,load_private,construct
from opencode_mcp_protocol import FixedMCPProtocol

class LazyTools:
    """Native MCP prewarm can list fixed tools before session/profile exists.

    First actual model call constructs the fully gated controller, after the
    factory has persisted the real session/backend binding before its prompt.
    Initialize/listing proves no role or model action.
    """
    def __init__(self,name,source_sha256):
        self.name=name;self.source_sha256=source_sha256
        self.runtime=None;self.backend=None;self.job=None
    def call(self,request):
        if self.runtime is None:
            directory,profile_sha256=selected_binding(self.name,self.source_sha256)
            self.runtime,self.backend,self.job=construct(directory,profile_sha256,self.source_sha256)
        self.runtime.guard();self.runtime.identity(self.runtime.profile)
        return self.runtime.binder.tools.call(request)
    def close(self):
        if self.backend is not None:self.backend.close()
        if self.job is not None:self.job.close()

def selected_binding(name,source_sha256):
    if not re.fullmatch(r'(preserving|recovery)-[0-9a-f]{64}',name) or not re.fullmatch('[0-9a-f]{64}',source_sha256):
        raise RuntimeError('fixed factory incarnation/source required')
    directory=LEAVES/name
    binding=load_private(directory/'opencode-controller-binding.private.json')
    if (type(binding) is not dict or set(binding)!= {'v','state_dir','source_manifest_sha256','profile_sha256'}
        or type(binding['v']) is not int or binding['v']!=1 or binding['state_dir']!=str(directory)
        or binding['source_manifest_sha256']!=source_sha256
        or not re.fullmatch('[0-9a-f]{64}',binding.get('profile_sha256',''))):
        raise RuntimeError('immutable factory controller binding absent')
    return directory,binding['profile_sha256']

def main():
    if len(sys.argv)!=3:raise RuntimeError('fixed factory arguments required')
    name,source_sha256=sys.argv[1:]
    if not re.fullmatch(r'(preserving|recovery)-[0-9a-f]{64}',name) or not re.fullmatch('[0-9a-f]{64}',source_sha256):
        raise RuntimeError('fixed factory arguments required')
    tools=LazyTools(name,source_sha256)
    try:FixedMCPProtocol(tools).run(sys.stdin,sys.stdout)
    finally:tools.close()

if __name__=='__main__':
    try:main()
    except Exception:
        sys.stderr.write('fixed root controller held\n');sys.exit(1)
