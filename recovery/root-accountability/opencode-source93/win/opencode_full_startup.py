"""Exact twelve-entry candidate startup bundle, read without global mutation."""
import hashlib,json,pathlib

MANIFEST_SHA='dc5f9605d5d30444050cd1075910d483bf339f891f683efb54e3ea95f92724d2'

def sha(data):return hashlib.sha256(data).hexdigest()

class FullStartup:
    def __init__(self,root,manifest_sha256=MANIFEST_SHA):
        self.root=pathlib.Path(root);self.manifest_sha256=manifest_sha256
        self.manifest=self.read('bundle-pins.private.json',manifest_sha256)
        value=json.loads(self.manifest)
        if value.get('v')!=1 or len(value.get('entries',[]))!=12:
            raise RuntimeError('complete fixed twelve-entry startup manifest required')
        entries=value['entries'];names=[e['path'] for e in entries]
        if len(set(names))!=12 or 'AGENTS.md' not in names or 'latest-human-steering.private.json' not in names:
            raise RuntimeError('startup paths missing or duplicated')
        self.entries=entries
        self.instructions_sha256=sha(json.dumps(entries,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode())
    def read(self,name,expected):
        relative=pathlib.PurePosixPath(name)
        if relative.is_absolute() or '..' in relative.parts or '\\' in name:
            raise RuntimeError('fixed relative startup path required')
        path=self.root.joinpath(*relative.parts)
        if (not path.is_file() or path.stat().st_size>1048576
            or any(p.is_symlink() or getattr(p.stat(),'st_file_attributes',0)&0x400 for p in (path,*path.parents))):
            raise RuntimeError('bounded non-reparse startup file required')
        data=path.read_bytes()
        if sha(data)!=expected:raise RuntimeError('fixed startup bytes changed')
        return data
    def documents(self):
        # Review acceptance belongs to the cold plan; this reader cannot turn
        # the candidate manifest's reviewed=false into acceptance.
        return [{'name':e['path'],'sha256':e['sha256'],'source_kind':e['source_kind'],
                 'body':self.read(e['path'],e['sha256']).decode('utf-8')} for e in self.entries]
