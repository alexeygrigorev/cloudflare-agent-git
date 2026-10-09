"""Finite stdio MCP protocol for the fixed trusted Win controller binder.

No model-selected profile, session, listener, command, recipient or provider.
Tool callbacks must be installed from the pinned runtime/cold plan, not CLI.
"""
import json
from opencode_root_tools import TOOLS

def schemas():
    output=[]
    for name,fields in TOOLS.items():
        properties={key:{'type':'string','minLength':1,'maxLength':8192} for key in fields}
        output.append({'name':name,'description':'Fixed owned ROOT '+name,
            'inputSchema':{'type':'object','properties':properties,'required':list(fields),'additionalProperties':False}})
    return output

class FixedMCPProtocol:
    def __init__(self,tools):self.tools=tools;self.initialized=False
    def handle(self,request):
        if type(request) is not dict or request.get('jsonrpc')!='2.0':raise RuntimeError('invalid MCP envelope')
        method=request.get('method')
        if 'id' not in request:
            if method!='notifications/initialized':raise RuntimeError('unsupported MCP notification')
            return None
        if type(request['id']) not in (int,str):raise RuntimeError('invalid MCP request identity')
        if method=='initialize':
            if self.initialized:raise RuntimeError('MCP initialization replay held')
            self.initialized=True
            result={'protocolVersion':'2024-11-05','capabilities':{'tools':{}},'serverInfo':{'name':'root_gateway','version':'opencode-native-v1'}}
        elif not self.initialized:raise RuntimeError('MCP initialization required')
        elif method=='tools/list':
            if request.get('params',{})!={}:raise RuntimeError('fixed complete MCP inventory required')
            result={'tools':schemas()}
        elif method=='tools/call':result=self.tools.call(request)
        elif method=='ping':result={}
        else:raise RuntimeError('unsupported fixed MCP method')
        return {'jsonrpc':'2.0','id':request['id'],'result':result}
    def run(self,input_stream,output_stream):
        for line in input_stream:
            if len(line)>32768:raise RuntimeError('bounded MCP input exceeded')
            request=None
            try:
                request=json.loads(line);response=self.handle(request)
            except Exception:
                # Fixed public failure only. No local exception/config/header or
                # private helper result can leak into model/debug output.
                if type(request) is not dict or 'id' not in request:continue
                response={'jsonrpc':'2.0','id':request['id'],'error':{'code':-32602,'message':'fixed owned ROOT tool held'}}
            if response is not None:
                output_stream.write(json.dumps(response,separators=(',',':'))+'\n');output_stream.flush()
