import hashlib,json,pathlib,tempfile,unittest
from opencode_authority_transport import AuthorityTransport

class TransportTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.paths={n:pathlib.Path(self.temp.name)/n for n in ('ca','certificate','key')}
        for p in self.paths.values():p.write_bytes(b'sentinel-only-not-a-real-certificate')
        self.pins={n:hashlib.sha256(p.read_bytes()).hexdigest() for n,p in self.paths.items()}
        self.calls=[];self.gates=[];self.response={'v':1,'status':'ok','result':{'v':1,'helper_allowed':True}};outer=self
        class Connection:
            def request(self,*a,**k):outer.calls.append((a,k))
            def getresponse(self):return type('Response',(),{'status':200,'read':lambda self,n:json.dumps(outer.response).encode()})()
            def close(self):outer.calls.append('closed')
        self.t=AuthorityTransport('https://owned-authority.invalid:8801',{'identity_id':'own','token':'sentinel'},
            self.paths,self.pins,lambda:self.gates.append('checked'),Connection)
        self.body={'v':1,'credential':{'identity_id':'own','token':'sentinel'},'op':'opencode-controller-gate'}
    def test_fixed_request_guards_before_and_after(self):
        self.assertTrue(self.t('/v1/host-recovery',self.body)['helper_allowed'])
        self.assertEqual(self.calls[0][0][:2],('POST','/v1/host-recovery'))
        self.assertEqual(len(self.gates),2);self.assertEqual(self.calls[-1],'closed')
    def test_unknown_route_or_op_has_no_transport(self):
        for path,body in (('/config',self.body),('/v1/host-recovery',dict(self.body,op='root-start')),
                          ('/v1/host-recovery',dict(self.body,owner='model-selected'))):
            with self.assertRaises(RuntimeError):self.t(path,body)
        self.assertFalse(self.calls)
    def test_foreign_credential_or_changed_certificate_has_no_send(self):
        with self.assertRaises(RuntimeError):self.t('/v1/host-recovery',dict(self.body,credential={}))
        self.paths['certificate'].write_bytes(b'changed')
        with self.assertRaises(RuntimeError):self.t('/v1/host-recovery',self.body)
        self.assertFalse(self.calls)
    def test_arbitrary_origin_not_supported(self):
        with self.assertRaises(ValueError):AuthorityTransport('http://example.invalid:8801',{},self.paths,self.pins,lambda:None)
    def test_raw_gateway_or_bad_outer_envelope_never_falls_back(self):
        for result in ({'v':1,'helper_allowed':True},{'v':1,'status':'held','result':{}},
                       {'v':True,'status':'ok','result':{}},{'v':1,'status':'ok','result':[]},
                       {'v':1,'status':'ok','result':{},'caller_owner':'foreign'}):
            self.response=result
            with self.assertRaises(RuntimeError):self.t('/v1/host-recovery',self.body)

if __name__=='__main__':unittest.main()
