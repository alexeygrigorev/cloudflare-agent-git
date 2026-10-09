"""Owned Windows JobObject: assign suspended processes before execution.

No name-based cleanup. Closing the guardian-owned job kills only its members.
"""
import ctypes as c
from ctypes import wintypes as w
import os
import subprocess
import time

MEMORY_LIMIT = 1500 * 1024 * 1024
PROCESS_LIMIT = 100

class BasicLimits(c.Structure):
    _fields_ = [("PerProcessUserTimeLimit", c.c_int64), ("PerJobUserTimeLimit", c.c_int64),
                ("LimitFlags", w.DWORD), ("MinimumWorkingSetSize", c.c_size_t),
                ("MaximumWorkingSetSize", c.c_size_t), ("ActiveProcessLimit", w.DWORD),
                ("Affinity", c.c_size_t), ("PriorityClass", w.DWORD), ("SchedulingClass", w.DWORD)]

class IOCounters(c.Structure):
    _fields_ = [(name, c.c_uint64) for name in ("ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                                              "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

class ExtendedLimits(c.Structure):
    _fields_ = [("BasicLimitInformation", BasicLimits), ("IoInfo", IOCounters),
                ("ProcessMemoryLimit", c.c_size_t), ("JobMemoryLimit", c.c_size_t),
                ("PeakProcessMemoryUsed", c.c_size_t), ("PeakJobMemoryUsed", c.c_size_t)]

class BasicAccounting(c.Structure):
    _fields_ = [(name, c.c_int64) for name in ("TotalUserTime", "TotalKernelTime", "ThisPeriodTotalUserTime", "ThisPeriodTotalKernelTime")] + [(name, w.DWORD) for name in ("TotalPageFaultCount", "TotalProcesses", "ActiveProcesses", "TotalTerminatedProcesses")]

class StartupInfo(c.Structure):
    _fields_ = [("cb", w.DWORD), ("lpReserved", w.LPWSTR), ("lpDesktop", w.LPWSTR), ("lpTitle", w.LPWSTR),
                ("dwX", w.DWORD), ("dwY", w.DWORD), ("dwXSize", w.DWORD), ("dwYSize", w.DWORD),
                ("dwXCountChars", w.DWORD), ("dwYCountChars", w.DWORD), ("dwFillAttribute", w.DWORD),
                ("dwFlags", w.DWORD), ("wShowWindow", w.WORD), ("cbReserved2", w.WORD),
                ("lpReserved2", c.POINTER(w.BYTE)), ("hStdInput", w.HANDLE),
                ("hStdOutput", w.HANDLE), ("hStdError", w.HANDLE)]

class ProcessInfo(c.Structure):
    _fields_ = [("hProcess", w.HANDLE), ("hThread", w.HANDLE), ("dwProcessId", w.DWORD), ("dwThreadId", w.DWORD)]

def kernel():
    if os.name != "nt":
        raise RuntimeError("native Windows containment unavailable")
    api = c.WinDLL("kernel32", use_last_error=True)
    signatures = {
        "CreateJobObjectW": ([c.c_void_p, w.LPCWSTR], w.HANDLE),
        "OpenJobObjectW": ([w.DWORD, w.BOOL, w.LPCWSTR], w.HANDLE),
        "IsProcessInJob": ([w.HANDLE, w.HANDLE, c.POINTER(w.BOOL)], w.BOOL),
        "SetInformationJobObject": ([w.HANDLE, c.c_int, c.c_void_p, w.DWORD], w.BOOL),
        "QueryInformationJobObject": ([w.HANDLE, c.c_int, c.c_void_p, w.DWORD, c.c_void_p], w.BOOL),
        "CreateProcessW": ([w.LPCWSTR, w.LPWSTR, c.c_void_p, c.c_void_p, w.BOOL, w.DWORD,
                            c.c_void_p, w.LPCWSTR, c.POINTER(StartupInfo), c.POINTER(ProcessInfo)], w.BOOL),
        "AssignProcessToJobObject": ([w.HANDLE, w.HANDLE], w.BOOL),
        "ResumeThread": ([w.HANDLE], w.DWORD), "CloseHandle": ([w.HANDLE], w.BOOL),
        "GetExitCodeProcess": ([w.HANDLE, c.POINTER(w.DWORD)], w.BOOL),
        "WaitForSingleObject": ([w.HANDLE, w.DWORD], w.DWORD),
        "TerminateJobObject": ([w.HANDLE, w.UINT], w.BOOL),
        "TerminateProcess": ([w.HANDLE, w.UINT], w.BOOL),
        "GetProcessTimes": ([w.HANDLE, c.c_void_p, c.c_void_p, c.c_void_p, c.c_void_p], w.BOOL),
        "GetStdHandle": ([w.DWORD], w.HANDLE),
        "OpenProcess": ([w.DWORD, w.BOOL, w.DWORD], w.HANDLE),
        "GetCurrentProcess": ([], w.HANDLE),
    }
    for name, (args, result) in signatures.items():
        getattr(api, name).argtypes, getattr(api, name).restype = args, result
    return api

def require(ok):
    if not ok:
        raise c.WinError(c.get_last_error())

def recorded_process_state(pid, creation_filetime):
    """Read-only exact-incarnation reconciliation, never obtains kill rights."""
    api = kernel()
    handle = api.OpenProcess(0x100000 | 0x1000, False, pid)
    if not handle:
        if c.get_last_error() == 87:  # ERROR_INVALID_PARAMETER: PID no longer exists.
            return "exited"
        raise c.WinError(c.get_last_error())
    try:
        values = [c.c_uint64() for _ in range(4)]
        require(api.GetProcessTimes(handle, *[c.byref(v) for v in values]))
        if values[0].value != creation_filetime:
            return "original-exited-pid-reused"
        result = api.WaitForSingleObject(handle, 0)
        if result == 258:
            return "alive"
        if result != 0:
            raise c.WinError(c.get_last_error())
        return "exited"
    finally:
        api.CloseHandle(handle)

def current_process_binding():
    api = kernel()
    values = [c.c_uint64() for _ in range(4)]
    require(api.GetProcessTimes(api.GetCurrentProcess(), *[c.byref(v) for v in values]))
    return {"pid": os.getpid(), "creation_filetime": values[0].value}

def verify_backend_connection(connection, backend, server_port=8803):
    # Check the established accepted server socket, not just the listener. No
    # bearer token is sent until the kernel attributes this exact connection
    # to our retained, live backend handle.
    if backend.poll() is not None:
        raise RuntimeError("owned backend exited")
    port = connection.getsockname()[1]
    if server_port not in (8803,8813):raise RuntimeError('unapproved owned backend port')
    script = "$ErrorActionPreference='Stop';$p=Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort " + str(server_port) + " -RemoteAddress 127.0.0.1 -RemotePort " + str(port) + " -State Established;@($p | Select-Object -ExpandProperty OwningProcess)|ConvertTo-Json -Compress"
    result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script], capture_output=True, text=True, timeout=8, check=True)
    import json
    owners = json.loads(result.stdout)
    if not isinstance(owners, list):
        owners = [owners]
    if owners != [backend.pid] or backend.poll() is not None:
        raise RuntimeError("socket is not owned by the retained backend")

class OwnedProcess:
    def __init__(self, job, handle, pid):
        self.job, self.handle, self.pid = job, handle, pid
        values = [c.c_uint64() for _ in range(4)]
        require(job.api.GetProcessTimes(handle, *[c.byref(v) for v in values]))
        self.creation_filetime = values[0].value

    def poll(self):
        code = w.DWORD()
        require(self.job.api.GetExitCodeProcess(self.handle, c.byref(code)))
        # STILL_ACTIVE is also a legal exit code; the wait result disambiguates.
        return None if self.job.api.WaitForSingleObject(self.handle, 0) == 258 else code.value

    def wait(self, timeout=10):
        result = self.job.api.WaitForSingleObject(self.handle, int(timeout * 1000))
        if result == 258:
            raise subprocess.TimeoutExpired("owned Windows handle", timeout)
        if result != 0:
            raise c.WinError(c.get_last_error())
        return self.poll()

    def kill(self):
        self.job.kill()

class WindowsJob:
    def __init__(self, name=None):
        self.api = kernel()
        self.handle = self.api.CreateJobObjectW(None, name)
        require(self.handle)
        if name is not None and c.get_last_error() == 183:
            self.close()
            raise RuntimeError("managed job name already occupied")
        self.name = name
        limits = ExtendedLimits()
        limits.BasicLimitInformation.LimitFlags = 0x8 | 0x200 | 0x2000
        limits.BasicLimitInformation.ActiveProcessLimit = PROCESS_LIMIT
        limits.JobMemoryLimit = MEMORY_LIMIT
        try:
            require(self.api.SetInformationJobObject(self.handle, 9, c.byref(limits), c.sizeof(limits)))
            self.evidence = self.query()
        except BaseException:
            self.close()
            raise

    def query(self):
        limits = ExtendedLimits()
        require(self.api.QueryInformationJobObject(self.handle, 9, c.byref(limits), c.sizeof(limits), None))
        if limits.BasicLimitInformation.LimitFlags & 0x2208 != 0x2208 or limits.JobMemoryLimit != MEMORY_LIMIT or limits.BasicLimitInformation.ActiveProcessLimit != PROCESS_LIMIT:
            raise RuntimeError("native containment limits mismatch")
        return {"job_memory_limit_bytes": limits.JobMemoryLimit,
                "active_process_limit": limits.BasicLimitInformation.ActiveProcessLimit,
                "kill_on_guardian_close": True, "source": "QueryInformationJobObject"}

    def start(self, argv, cwd, env=None, new_console=False):
        if not os.path.isabs(argv[0]):
            raise ValueError("absolute pinned application required")
        si, pi = StartupInfo(), ProcessInfo()
        si.cb = c.sizeof(si)
        # Genuine inherited console/ConPTY handles, not fabricated pipes.
        if not new_console:
            si.dwFlags = 0x100
            si.hStdInput, si.hStdOutput, si.hStdError = [self.api.GetStdHandle(n & 0xffffffff) for n in (-10, -11, -12)]
        command = c.create_unicode_buffer(subprocess.list2cmdline(argv))
        environment = c.create_unicode_buffer("\0".join(k + "=" + v for k, v in sorted((env or os.environ).items(), key=lambda i: i[0].upper())) + "\0\0")
        require(self.api.CreateProcessW(argv[0], command, None, None, not new_console, 0x4 | 0x400 | (0x10 if new_console else 0),
                                       environment, cwd, c.byref(si), c.byref(pi)))
        try:
            require(self.api.AssignProcessToJobObject(self.handle, pi.hProcess))
            child = OwnedProcess(self, pi.hProcess, pi.dwProcessId)
            if self.api.ResumeThread(pi.hThread) == 0xffffffff:
                raise c.WinError(c.get_last_error())
            return child
        except BaseException:
            self.api.TerminateProcess(pi.hProcess, 75)
            self.api.WaitForSingleObject(pi.hProcess, 5000)
            self.api.CloseHandle(pi.hProcess)
            raise
        finally:
            self.api.CloseHandle(pi.hThread)

    def kill(self):
        require(self.api.TerminateJobObject(self.handle, 75))

    def wait_empty(self, timeout=10):
        until = time.monotonic() + timeout
        while time.monotonic() < until:
            accounting = BasicAccounting()
            require(self.api.QueryInformationJobObject(self.handle, 1, c.byref(accounting), c.sizeof(accounting), None))
            if accounting.ActiveProcesses == 0:
                return {"active_processes": 0, "source": "QueryInformationJobObject"}
            time.sleep(.05)
        raise TimeoutError("owned job still has active descendants")

    def close(self):
        if self.handle:
            self.api.CloseHandle(self.handle)
            self.handle = None

def drain_recorded_job(state):
    """Only a provisioner-recorded managed Job; never unrelated principal."""
    name = state.get("job_name", "")
    if not name.startswith("Local\\Win35Root-") or len(name) != len("Local\\Win35Root-") + 32:
        raise RuntimeError("unverified managed job; preserve")
    job = WindowsJob.__new__(WindowsJob)
    job.api = kernel()
    job.handle = job.api.OpenJobObjectW(0x4 | 0x8, False, name)
    require(job.handle)
    try:
        job.query()
        for prefix in ("process", "frontend"):
            pid = state.get("pid") if prefix == "process" else state.get("frontend_pid")
            stamp = state.get(prefix + "_creation_filetime")
            if pid is None:
                continue
            if not stamp:
                raise RuntimeError("missing exact managed process identity")
            if recorded_process_state(pid, stamp) != "alive":
                continue
            handle = job.api.OpenProcess(0x1000 | 0x100000, False, pid)
            require(handle)
            try:
                inside = w.BOOL()
                require(job.api.IsProcessInJob(handle, job.handle, c.byref(inside)))
                if not inside.value or recorded_process_state(pid, stamp) != "alive":
                    raise RuntimeError("managed job/process incarnation mismatch")
            finally:
                job.api.CloseHandle(handle)
        job.kill()
        return job.wait_empty()
    finally:
        job.close()
