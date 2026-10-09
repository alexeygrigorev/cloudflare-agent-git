"""Fixed authenticated owned-native history reader; no config/debug surface.

Constructor bindings are private installed-controller dependencies, not model
arguments. Kernel membership is rechecked across every HTTP observation.
"""
import base64,http.client,json,re,urllib.request

SESSION=re.compile(r'ses_[A-Za-z0-9]+\Z')

class OwnedHistoryReader:
    def __init__(self,port,password,context_reader,kernel_gate,opener=None,connection_gate=None):
        if type(port) is not int or port not in (8815,8816):
            raise ValueError('fixed native listener slot required')
        if type(password) is not str or len(password)<32:
            raise ValueError('private native listener authentication required')
        self.port=port;self._password=password;self.context_reader=context_reader
        self.kernel_gate=kernel_gate
        if opener is None and not callable(connection_gate):
            raise ValueError('connected native listener kernel verifier required')
        self.opener=opener or PinnedLoopback(port,connection_gate,context_reader)
    def __repr__(self):return 'OwnedHistoryReader(fixed-loopback, authentication=private)'
    def __call__(self,selected):
        current=self.context_reader()
        if current!=selected or not self.kernel_gate(current):
            raise RuntimeError('current native listener/kernel context unverified')
        session=current.get('session_id')
        if type(session) is not str or not SESSION.fullmatch(session):
            raise RuntimeError('fixed native session absent')
        # This class has no arbitrary URL/path/request entry point. Never expose
        # authenticated /config, debug, mutation, or another native session.
        request=urllib.request.Request('http://127.0.0.1:'+str(self.port)+'/session/'+session+'/message',
            headers={'Authorization':'Basic '+base64.b64encode(('opencode:'+self._password).encode()).decode(),
                     'Accept':'application/json'},method='GET')
        try:
            with self.opener.open(request,timeout=5) as response:
                if response.status!=200:raise RuntimeError('owned native history unavailable')
                data=response.read(2097153)
                if len(data)>2097152:raise RuntimeError('owned native history exceeds bound')
            history=json.loads(data)
        except Exception:
            # Transport exceptions can contain request data; retain only this
            # fixed failure, never response bodies/headers or authentication.
            raise RuntimeError('authenticated owned native history held') from None
        if type(history) is not list or len(history)>512:
            raise RuntimeError('bounded owned native history required')
        if any(type(item) is not dict or item.get('info',{}).get('sessionID')!=session for item in history):
            raise RuntimeError('foreign native history denied')
        if self.context_reader()!=current or not self.kernel_gate(current):
            raise RuntimeError('native listener/kernel changed across observation')
        return history

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        raise RuntimeError('native listener redirect denied')

class PinnedResponse:
    def __init__(self,response,connection):self.response=response;self.connection=connection;self.status=response.status
    def read(self,limit):return self.response.read(limit)
    def __enter__(self):return self
    def __exit__(self,*args):self.response.close();self.connection.close()

class PinnedLoopback:
    def __init__(self,port,connection_gate,context_reader):
        self.port=port;self.connection_gate=connection_gate;self.context_reader=context_reader
    def open(self,request,timeout):
        # Literal localhost transport never consults proxy environment or follows
        # redirects. Authenticate only after exact connected-PID/FILETIME check.
        connection=http.client.HTTPConnection('127.0.0.1',self.port,timeout=timeout)
        try:
            connection.connect()
            if not self.connection_gate(connection.sock,self.context_reader()):
                raise RuntimeError('connected native listener incarnation denied')
            connection.request('GET',request.selector,headers=dict(request.header_items()))
            return PinnedResponse(connection.getresponse(),connection)
        except Exception:
            connection.close();raise RuntimeError('owned native connection held') from None
