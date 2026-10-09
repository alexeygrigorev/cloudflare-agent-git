"""Fixed incarnation journal store and shared cross-process writer lock.

Factory must provision the owner-private leaf and one-byte lock BEFORE launch.
This store neither provisions directories/ACLs nor accepts model-selected paths.
Reviewed private_writer.save establishes temporary-file ACL before JSON bytes.
"""
import contextlib,json,os,pathlib,re,threading

BASE=pathlib.Path('C:/Users/User/git/cloudflare-agent-git/.local/win35-root-bootstrap/runtime/api-root')
INCARNATION=re.compile(r'(?:preserving|recovery)-[0-9a-f]{64}\Z')

class ControllerStore:
    def __init__(self,directory,private_load,private_save,private_directory_verify,lock_api=None):
        directory=pathlib.Path(directory)
        if directory.parent!=BASE or not INCARNATION.fullmatch(directory.name):
            raise ValueError('fixed nonce-derived incarnation leaf required')
        self.directory=directory;self.load=private_load;self.save_private=private_save
        self.verify=private_directory_verify;self.lock_api=lock_api;self.thread_lock=threading.RLock()
        self.path=directory/'opencode-controller-journal.private.json'
        self.lock_path=directory/'opencode-controller.lock'
    def check(self):
        self.verify(self.directory)
        for path in (self.path,self.lock_path):
            if path.exists() and (path.is_symlink() or getattr(path.stat(),'st_file_attributes',0)&0x400):
                raise RuntimeError('controller file reparse held')
    @contextlib.contextmanager
    def transaction(self):
        with self.thread_lock:
            self.check()
            if not self.lock_path.is_file() or self.lock_path.stat().st_size!=1:
                raise RuntimeError('factory-provisioned fixed controller lock absent')
            # Private loader must independently verify owner/DACL of lock too.
            # Lock bytes are not JSON: the verifier is supplied by the same
            # pinned cold factory and called before opening any writer handle.
            self.verify(self.lock_path)
            api=self.lock_api
            if api is None:
                if os.name!='nt':raise RuntimeError('native Windows writer lock required')
                import msvcrt
                api=msvcrt
            with self.lock_path.open('r+b') as stream:
                stream.seek(0);api.locking(stream.fileno(),api.LK_NBLCK,1)
                try:
                    self.check()
                    yield
                finally:
                    stream.seek(0);api.locking(stream.fileno(),api.LK_UNLCK,1)
    def read(self):
        self.check()
        if not self.path.exists():return None
        if not self.path.is_file() or self.path.stat().st_size>2097152:
            raise RuntimeError('bounded private controller journal required')
        value=self.load(self.path)
        if type(value) is not dict:raise RuntimeError('present malformed controller journal held')
        return value
    def save(self,value):
        self.check()
        if type(value) is not dict or value.get('phase') not in ('selected','handled'):
            raise RuntimeError('explicit controller journal phase required')
        raw=json.dumps(value)
        if len(raw.encode())>2097152:raise RuntimeError('controller journal bound')
        self.save_private(self.path,value)
        if self.load(self.path)!=value:raise RuntimeError('private controller journal readback differs')

class JournalLock:
    """Inject as ControllerJournal.lock so read/modify/save share ONE file lock."""
    def __init__(self,store):self.store=store;self.local=threading.local()
    def __enter__(self):
        if getattr(self.local,'active',None) is not None:raise RuntimeError('nested journal transaction held')
        active=self.store.transaction();result=active.__enter__();self.local.active=active;return result
    def __exit__(self,*args):
        try:return self.local.active.__exit__(*args)
        finally:self.local.active=None
