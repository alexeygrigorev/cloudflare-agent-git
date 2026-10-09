"""Actual same-session Job query and exact process incarnation observations.

Only query rights are opened. A missing Job object is an error. The caller must
retain this object while the owned model is live, including across root death.
"""
import sys
if not sys.flags.isolated or not sys.flags.no_site:raise SystemExit('requires -I -S')
import ctypes as c
from ctypes import wintypes as w

class JobObservation:
    def __init__(self,api,accounting_type,expected_name,backend,guardian,process_state):
        self.api=api;self.accounting_type=accounting_type;self.process_state=process_state
        if not isinstance(expected_name,str) or not expected_name.startswith('Local\\Win35Root-') or len(expected_name)!=len('Local\\Win35Root-')+32:
            raise RuntimeError('fixed owned model Job name required')
        if backend['pid']==guardian['pid']:raise RuntimeError('guardian overlaps model')
        self.handle=api.OpenJobObjectW(0x4,False,expected_name)
        if not self.handle:raise c.WinError(c.get_last_error())
        try:
            if self.process_state(backend['pid'],backend['creation_filetime'])!='alive':raise RuntimeError('capture Job baseline while backend alive')
            if not self.membership(backend):raise RuntimeError('backend not in recorded Job')
            if self.membership(guardian):raise RuntimeError('guardian inside root ModelJob')
            self.guardian=guardian
        except BaseException:self.close();raise
    def membership(self,binding):
        h=self.api.OpenProcess(0x1000|0x100000,False,binding['pid'])
        if not h:raise c.WinError(c.get_last_error())
        try:
            times=[c.c_uint64() for _ in range(4)]
            if not self.api.GetProcessTimes(h,*[c.byref(t) for t in times]):raise c.WinError(c.get_last_error())
            if times[0].value!=binding['creation_filetime']:raise RuntimeError('PID reused during Job membership query')
            inside=w.BOOL()
            if not self.api.IsProcessInJob(h,self.handle,c.byref(inside)):raise c.WinError(c.get_last_error())
            return bool(inside.value)
        finally:self.api.CloseHandle(h)
    def outside(self):return not self.membership(self.guardian)
    def query(self):
        if not self.handle:raise RuntimeError('lost retained Job handle')
        info=self.accounting_type()
        if not self.api.QueryInformationJobObject(self.handle,1,c.byref(info),c.sizeof(info),None):raise c.WinError(c.get_last_error())
        return dict(active_processes=int(info.ActiveProcesses),source='QueryInformationJobObject')
    def close(self):
        if self.handle:self.api.CloseHandle(self.handle);self.handle=None
