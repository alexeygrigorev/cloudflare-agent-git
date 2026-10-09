"""Owned authenticated native listener driver: health/new empty session only.

No provider prompt, configuration/debug read, arbitrary URL or model tool API.
Basic credentials are sent only after exact connected kernel/socket membership.
"""
import base64,ctypes,http.client,json,re,subprocess,time
from ctypes import wintypes

class BackendAPI:
    def __init__(self,module,source_guard,clock=time.monotonic,sleep=time.sleep):
        self.module=module;self.guard=source_guard;self.clock=clock;self.sleep=sleep
    def verify(self,backend,job):
        self.guard()
        if backend.poll() is not None:raise RuntimeError('owned native backend exited')
        values=[ctypes.c_uint64() for _ in range(4)]
        self.module.require(job.api.GetProcessTimes(backend.handle,*[ctypes.byref(v) for v in values]))
        if values[0].value!=backend.creation_filetime:raise RuntimeError('owned native backend incarnation changed')
        inside=wintypes.BOOL();self.module.require(job.api.IsProcessInJob(backend.handle,job.handle,ctypes.byref(inside)))
        if not inside.value:raise RuntimeError('actual native backend outside owned Job')
        job.query()
        job.api.ProcessIdToSessionId.argtypes=[wintypes.DWORD,ctypes.POINTER(wintypes.DWORD)]
        job.api.ProcessIdToSessionId.restype=wintypes.BOOL
        session=wintypes.DWORD();self.module.require(job.api.ProcessIdToSessionId(backend.pid,ctypes.byref(session)))
        if session.value!=2:raise RuntimeError('actual native GUI Session2 required')
    def request(self,backend,job,port,password,method,path,body=None):
        if port not in (8815,8816) or method not in ('GET','POST'):
            raise RuntimeError('fixed owned native listener operation required')
        allowed=(method,path) in (('GET','/global/health'),('POST','/session'))
        allowed=allowed or (method=='GET' and re.fullmatch(r'/session/ses_[A-Za-z0-9]+/message',path))
        if not allowed or (method=='POST' and body!={}):raise RuntimeError('native config/prompt/generic request forbidden')
        return self._transport(backend,job,port,password,method,path,body)
    def prompt_async(self,backend,job,port,password,session_id,payload,pre_effect):
        if (port not in (8815,8816) or not re.fullmatch('ses_[A-Za-z0-9]+',session_id)
            or type(payload) is not dict or set(payload)!={'model','agent','parts'}
            or payload['model']!={'providerID':'zai-coding-plan','modelID':'glm-5.3-flash'}
            or payload['agent']!='root_contingency' or type(payload['parts']) is not list
            or len(payload['parts'])!=1 or set(payload['parts'][0])!={'type','text'}
            or payload['parts'][0]['type']!='text' or type(payload['parts'][0]['text']) is not str
            or not payload['parts'][0]['text'] or not callable(pre_effect)):
            raise RuntimeError('fixed source-selected native prompt required')
        return self._transport(backend,job,port,password,'POST','/session/'+session_id+'/prompt_async',payload,204,pre_effect)
    def _transport(self,backend,job,port,password,method,path,body=None,expected_status=200,pre_effect=None):
        self.verify(backend,job)
        connection=http.client.HTTPConnection('127.0.0.1',port,timeout=5)
        try:
            connection.connect()
            client_port=connection.sock.getsockname()[1]
            script="$ErrorActionPreference='Stop';$p=Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort "+str(port)+" -RemoteAddress 127.0.0.1 -RemotePort "+str(client_port)+" -State Established;@($p|Select-Object -ExpandProperty OwningProcess)|ConvertTo-Json -Compress"
            result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',script],capture_output=True,text=True,timeout=8,check=True)
            owners=json.loads(result.stdout);owners=owners if type(owners) is list else [owners]
            if owners!=[backend.pid]:raise RuntimeError('connected native listener foreign PID')
            self.verify(backend,job) # still BEFORE Basic credential bytes
            headers={'Authorization':'Basic '+base64.b64encode(('opencode:'+password).encode()).decode(),
                'Content-Type':'application/json','Accept':'application/json'}
            if expected_status==204:
                if not callable(pre_effect):raise RuntimeError('fixed pre-spend current-role/admission guard missing')
                pre_effect() # immediately before native prompt bytes, after socket/kernel binding
            connection.request(method,path,body=json.dumps(body).encode() if body is not None else None,headers=headers)
            response=connection.getresponse();data=response.read(262145)
            if response.status!=expected_status or len(data)>262144:raise RuntimeError('bounded native response unavailable')
            if expected_status==204:
                if data:raise RuntimeError('unexpected native asynchronous response body')
                self.verify(backend,job)
                return {'status':204}
            value=json.loads(data);self.verify(backend,job)
            return value
        except Exception:
            raise RuntimeError('owned authenticated native operation held') from None
        finally:connection.close()
    def __call__(self,backend,job,port,password,operation,payload):
        if operation!='create-session' or payload!={}:raise RuntimeError('fixed empty-session operation required')
        deadline=self.clock()+15
        while True:
            try:
                health=self.request(backend,job,port,password,'GET','/global/health')
                if health.get('healthy') is not True:raise RuntimeError('native listener not healthy')
                break
            except RuntimeError:
                if backend.poll() is not None or self.clock()>=deadline:raise
                self.sleep(.2)
        # POST is ONCE. Timeout is uncertainty, never another session request.
        session=self.request(backend,job,port,password,'POST','/session',{})
        if type(session) is not dict or not re.fullmatch('ses_[A-Za-z0-9]+',session.get('id','')):
            raise RuntimeError('actual native session identity missing')
        history=self.request(backend,job,port,password,'GET','/session/'+session['id']+'/message')
        if history!=[]:raise RuntimeError('new owned native session already contains history')
        return {'id':session['id'],'initial_message_count':0,'model_turn_submitted':False}
