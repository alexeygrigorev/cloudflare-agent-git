"""Fresh fixed own-capsule catalog/kernel collector, no process mutation."""
import ctypes,json,subprocess
from ctypes import wintypes

def rows(value):
    if type(value) is list:
        for item in value:yield from rows(item)
    elif type(value) is dict:
        yield value
        for item in value.values():
            if type(item) in (dict,list):yield from rows(item)

class NativeKernel:
    def __init__(self,module,aplexer,native,host_kernel,guardian,owner,backend,job,source_guard):
        self.module=module;self.aplexer=aplexer;self.native=native;self.host=host_kernel
        self.guardian=guardian;self.owner=owner;self.backend=backend;self.job=job;self.guard=source_guard
    def process(self,pid,expected=None,member=None):
        api=self.job.api;handle=api.OpenProcess(0x100000|0x1000,False,pid);self.module.require(handle)
        try:
            times=[ctypes.c_uint64() for _ in range(4)]
            self.module.require(api.GetProcessTimes(handle,*[ctypes.byref(t) for t in times]))
            if api.WaitForSingleObject(handle,0)!=258 or (expected is not None and times[0].value!=expected):
                raise RuntimeError('exact native kernel incarnation missing')
            api.ProcessIdToSessionId.argtypes=[wintypes.DWORD,ctypes.POINTER(wintypes.DWORD)]
            api.ProcessIdToSessionId.restype=wintypes.BOOL
            session=wintypes.DWORD();self.module.require(api.ProcessIdToSessionId(pid,ctypes.byref(session)))
            if session.value!=2:raise RuntimeError('native family outside GUI Session2')
            if member is not None:
                inside=wintypes.BOOL();self.module.require(api.IsProcessInJob(handle,self.job.handle,ctypes.byref(inside)))
                if bool(inside.value)!=member:raise RuntimeError('actual native Job membership mismatch')
            return {'pid':pid,'creation_filetime':times[0].value}
        finally:api.CloseHandle(handle)
    def __call__(self):
        self.guard()
        catalog=json.loads(subprocess.check_output([self.aplexer,'list','--all','--json'],text=True,timeout=15))
        matches=[r for r in rows(catalog) if r.get('id')==self.native['id'] and r.get('tag')==self.native['tag']
                 and r.get('workspace','').replace('\\','/').lower()==self.native['workspace'].replace('\\','/').lower()]
        if len(matches)!=1 or matches[0].get('worker_alive') is not True:raise RuntimeError('actual own native catalog unknown')
        row=matches[0]
        worker=self.process(row['worker_pid']);workload=self.process(row['workload_pid'])
        host=self.process(self.host['pid'],self.host['creation_filetime'])
        backend=self.process(self.backend.pid,self.backend.creation_filetime,True)
        guardian=self.process(self.guardian['pid'],self.guardian['creation_filetime'],False)
        self.job.query();self.guard()
        return {'owner':self.owner,'native_actor':self.native,'backend':backend,'job_name':self.job.name,
            'processes':[worker,workload,host,backend],'guardian':guardian,
            'native':{'id':self.native['id'],'worker':worker,'workload':workload,'host_process':host}}
