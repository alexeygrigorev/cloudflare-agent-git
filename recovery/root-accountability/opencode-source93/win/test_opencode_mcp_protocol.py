import io,json,unittest
from opencode_mcp_protocol import FixedMCPProtocol
class Tool:
    def __init__(self):self.calls=[]
    def call(self,r):self.calls.append(r);return {'content':[{'type':'text','text':'fixed receipt'}]}
class ProtocolTests(unittest.TestCase):
    def setUp(self):self.tool=Tool();self.p=FixedMCPProtocol(self.tool)
    def request(self,method,params=None):return {'jsonrpc':'2.0','id':'own-id','method':method,'params':params or {}}
    def start(self):self.p.handle(self.request('initialize'))
    def test_fixed_five_tool_catalog_no_context_inputs(self):
        self.start();tools=self.p.handle(self.request('tools/list'))['result']['tools']
        self.assertEqual(len(tools),5)
        for tool in tools:
            self.assertFalse(tool['inputSchema']['additionalProperties'])
            self.assertNotIn('owner',tool['inputSchema']['properties'])
            self.assertNotIn('session_id',tool['inputSchema']['properties'])
    def test_protocol_does_not_rewrite_native_request_id(self):
        self.start();r=self.request('tools/call',{'name':'root_oversight_snapshot','arguments':{}})
        result=self.p.handle(r);self.assertEqual(result['id'],'own-id');self.assertEqual(self.tool.calls,[r])
    def test_no_generic_resources_prompts_or_method(self):
        self.start()
        for method in ('resources/read','prompts/get','exec_command','root-kill'):
            with self.assertRaises(RuntimeError):self.p.handle(self.request(method))
        self.assertEqual(self.tool.calls,[])
    def test_errors_are_fixed_without_secret_exception(self):
        self.start()
        self.tool.call=lambda r:(_ for _ in ()).throw(RuntimeError('private-password-sentinel'))
        source=io.StringIO(json.dumps(self.request('tools/call',{'name':'root_role_reply','arguments':{}}))+'\n');output=io.StringIO()
        self.p.run(source,output);self.assertNotIn('private-password',output.getvalue())
        self.assertEqual(json.loads(output.getvalue())['error']['message'],'fixed owned ROOT tool held')
if __name__=='__main__':unittest.main()
