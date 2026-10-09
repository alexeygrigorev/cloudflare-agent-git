import io,json,unittest
from unittest.mock import patch
from opencode_owned_reader import OwnedHistoryReader,PinnedLoopback

class Response(io.BytesIO):
    status=200
class Opener:
    def __init__(self,data):self.data=data;self.requests=[]
    def open(self,request,timeout):
        self.requests.append(request);return Response(json.dumps(self.data).encode())
class ReaderTests(unittest.TestCase):
    def setUp(self):
        self.context={'session_id':'ses_owned1','kernel_ref':'fixed-private','revision':1}
        self.opener=Opener([{'info':{'sessionID':'ses_owned1'}}])
        self.reader=OwnedHistoryReader(8815,'sentinel-only-private-password-1234',lambda:dict(self.context),lambda c:True,self.opener)
    def test_only_fixed_authenticated_owned_history(self):
        self.assertEqual(len(self.reader(dict(self.context))),1)
        request=self.opener.requests[0]
        self.assertEqual(request.full_url,'http://127.0.0.1:8815/session/ses_owned1/message')
        self.assertEqual(request.get_method(),'GET')
        self.assertTrue(request.get_header('Authorization').startswith('Basic '))
        self.assertNotIn('sentinel',repr(self.reader))
    def test_foreign_path_session_denied_before_http(self):
        self.context['session_id']='ses_owned1/../../config'
        with self.assertRaises(RuntimeError):self.reader(dict(self.context))
        self.assertEqual(self.opener.requests,[])
    def test_wrong_context_and_kernel_denied_before_http(self):
        with self.assertRaises(RuntimeError):self.reader(dict(self.context,revision=2))
        self.reader.kernel_gate=lambda c:False
        with self.assertRaises(RuntimeError):self.reader(dict(self.context))
        self.assertEqual(self.opener.requests,[])
    def test_foreign_native_session_rejected(self):
        self.opener.data=[{'info':{'sessionID':'ses_foreign'}}]
        with self.assertRaises(RuntimeError):self.reader(dict(self.context))
    def test_changed_kernel_after_http_rejected(self):
        checks=iter((True,False));self.reader.kernel_gate=lambda c:next(checks)
        with self.assertRaises(RuntimeError):self.reader(dict(self.context))
    def test_nonfixed_listener_rejected(self):
        with self.assertRaises(ValueError):OwnedHistoryReader(8787,'x'*40,lambda:{},lambda c:True)
    def test_connected_kernel_denial_before_authentication(self):
        class Connection:
            sock=object()
            def __init__(self,*a,**kw):self.sent=False
            def connect(self):pass
            def request(self,*a,**kw):self.sent=True;raise AssertionError('authentication must not be sent')
            def close(self):pass
        connection=Connection()
        with patch('opencode_owned_reader.http.client.HTTPConnection',return_value=connection):
            reader=OwnedHistoryReader(8815,'x'*40,lambda:dict(self.context),lambda c:True,connection_gate=lambda s,c:False)
            with self.assertRaises(RuntimeError):reader(dict(self.context))
        self.assertFalse(connection.sent)
if __name__=='__main__':unittest.main()
