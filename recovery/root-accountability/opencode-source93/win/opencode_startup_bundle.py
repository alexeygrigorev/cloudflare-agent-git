"""Read complete pinned canonical startup plus reviewed latest direct steering.

Preserves dirty global work; all paths are constructor-selected private copies.
No missing addendum/default three-document bundle is accepted for operating use.
"""
import hashlib,json

COMMIT='47b5933c0f12eb403aeaad9e5b7c9c9277c79aa0'
DOCS={'AGENTS.md':'f03bd9660aa7e2d1cc6735067736ee86f5431c99a8c65a736845b7f202ac79ff',
 '_docs/04-communication.md':'29d9213ff8deac4f777bf93d188d23aa435fa477955abc1f9fbba8c05cd42b17',
 '_docs/03-way-of-working.md':'60dbb789733467422ce480aca1417f3d3f977716a5f68589f0dd4136c40eb0c4',
 '_docs/team/02-root.md':'da4aa091bf6cc3d2dccd759a34090567a91bbbaef545326ca2ee49f6a070a539',
 '_docs/05-recovery.md':'259a4e380efd385b5aaab84094959c67b8ddb69931e7ed1df07eb2ba65c51f7c',
 'recovery/README.md':'e5c4854562ad78e6033ed92d87b97ec5a7fa27cc111a53ac587862d36bb1324f'}
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()

class StartupBundle:
 def __init__(self,root,steering_path,steering_sha256):
  if (steering_path is None or type(steering_sha256) is not str or len(steering_sha256)!=64
      or any(c not in '0123456789abcdef' for c in steering_sha256)):
   raise RuntimeError('reviewed latest direct steering pin required')
  self.root=root;self.steering_path=steering_path;self.steering_sha256=steering_sha256
  self.instructions_sha256=digest({'commit':COMMIT,'documents':DOCS,'latest_direct_steering_sha256':steering_sha256})
 def read(self,path,expected):
  if (not path.is_file() or path.stat().st_size>524288
      or any(p.is_symlink() or getattr(p.stat(),'st_file_attributes',0)&0x400 for p in (path,*path.parents))):
   raise RuntimeError('fixed approved startup bytes unavailable')
  raw=path.read_bytes()
  if hashlib.sha256(raw).hexdigest()!=expected:raise RuntimeError('approved startup pin differs')
  return raw.decode('utf-8')
 def __call__(self,context):
  documents=[{'path':name,'sha256':expected,'source_kind':'accepted-git-object',
              'commit':COMMIT,'body':self.read(self.root/name,expected)} for name,expected in DOCS.items()]
  documents.append({'path':'latest-direct-steering','sha256':self.steering_sha256,
                    'source_kind':'reviewed-direct-steering-addendum','body':self.read(self.steering_path,self.steering_sha256)})
  return {'instructions_sha256':self.instructions_sha256,'complete_startup_ready':True,
          'documents':documents,'authority_effect':False}
