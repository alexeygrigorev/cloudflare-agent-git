"""Read-only exact Windows kernel/socket membership for owned OpenCode.

Requires the retained reviewed Job/OwnedProcess objects from the cold launcher;
never opens termination rights, creates a Job, or discovers arbitrary peers.
"""
import ctypes as c,hashlib,json,subprocess
from ctypes import wintypes as w

class WinCustody:
    def __init__(self,job_module,job,backend,native,owner,profile_path,profile_sha256,processes,guardian,session_reader):
        self.module=job_module;self.job=job;self.backend=backend;self.native=native;self.owner=owner
        self.profile_path=profile_path;self.profile_sha256=profile_sha256
        self.processes=processes;self.guardian=guardian;self.session_reader=session_reader
    def one(self,expected,member=None):
        api=self.job.api;handle=api.OpenProcess(0x100000|0x1000,False,expected['pid'])
        self.module.require(handle)
        try:
            times=[c.c_uint64() for _ in range(4)]
            self.module.require(api.GetProcessTimes(handle,*[c.byref(t) for t in times]))
            if times[0].value!=expected['creation_filetime'] or api.WaitForSingleObject(handle,0)!=258:
                raise RuntimeError('owned native incarnation unavailable')
            api.ProcessIdToSessionId.argtypes=[w.DWORD,c.POINTER(w.DWORD)];api.ProcessIdToSessionId.restype=w.BOOL
            session=w.DWORD();self.module.require(api.ProcessIdToSessionId(expected['pid'],c.byref(session)))
            if session.value!=2:raise RuntimeError('owned native GUI Session2 required')
            if member is not None:
                inside=w.BOOL();self.module.require(api.IsProcessInJob(handle,self.job.handle,c.byref(inside)))
                if bool(inside.value)!=member:raise RuntimeError('actual retained Job membership mismatch')
            return {'pid':expected['pid'],'creation_filetime':times[0].value,'session_id':session.value,'state':'alive'}
        finally:api.CloseHandle(handle)
    def __call__(self):
        if hashlib.sha256(self.profile_path.read_bytes()).hexdigest()!=self.profile_sha256:
            raise RuntimeError('current incarnation profile changed')
        if len(self.processes)!=4:raise RuntimeError('fixed native family tuple required')
        observed=[self.one(p,True if p['pid']==self.backend.pid else None) for p in self.processes]
        guardian=self.one(self.guardian,False)
        limits=self.job.query();accounting=self.module.BasicAccounting()
        self.module.require(self.job.api.QueryInformationJobObject(self.job.handle,1,c.byref(accounting),c.sizeof(accounting),None))
        if accounting.ActiveProcesses<1:raise RuntimeError('live backend Job unexpectedly empty')
        stable={'native_actor':self.native,'owner':self.owner,'profile_sha256':self.profile_sha256,
            'session_id':self.session_reader(),'processes':observed,'guardian':guardian,
            'job':{'queried':True,'active_processes':int(accounting.ActiveProcesses),'name':self.job.name,'limits':limits}}
        identity=dict(stable,job={'name':self.job.name,'limits':limits})
        stable['kernel_ref']=hashlib.sha256(json.dumps(identity,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        return stable
    def connection(self,sock,context):
        port=sock.getpeername()[1];client_port=sock.getsockname()[1]
        if port not in (8815,8816) or sock.getpeername()[0]!='127.0.0.1' or self.backend.poll() is not None:
            return False
        self.one({'pid':self.backend.pid,'creation_filetime':self.backend.creation_filetime},True)
        # Fixed connected socket tuple before ANY Basic-auth bytes are sent.
        script="$ErrorActionPreference='Stop';$p=Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort "+str(port)+" -RemoteAddress 127.0.0.1 -RemotePort "+str(client_port)+" -State Established;@($p|Select-Object -ExpandProperty OwningProcess)|ConvertTo-Json -Compress"
        result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',script],capture_output=True,text=True,timeout=8,check=True)
        owners=json.loads(result.stdout);owners=owners if type(owners) is list else [owners]
        return owners==[self.backend.pid] and self.backend.poll() is None and self()['kernel_ref']==context['kernel_ref']
