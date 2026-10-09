"""Candidate memory-only machine-local CodingPlan configuration.

No process/model launch, auth write, quota override or ROOT admission is offered.
The fixed gateway/event verifier and authority plan remain separate prerequisites.
"""
import hashlib,json,os,pathlib

AUTH=pathlib.Path('C:/Users/User/.zcode/cli/config.json')
PROVIDER='zai-coding-plan'
NATIVE_ORIGIN='https://api.z.ai/api/anthropic'
CODING_ORIGIN='https://api.z.ai/api/coding/paas/v4'
MODEL='glm-5.3-flash'
ENV_KEY='ROOT_CODING_PLAN_KEY'

def native_slot(config):
    if type(config) is not dict:raise ValueError('native config unknown')
    provider=config.get('provider',{}).get(PROVIDER)
    if type(provider) is not dict or type(provider.get('options')) is not dict:
        raise ValueError('fixed native CodingPlan slot absent')
    options=provider['options']
    if options.get('baseURL')!=NATIVE_ORIGIN:raise ValueError('native provider route changed')
    key=options.get('apiKey')
    if type(key) is not str or not key.strip() or '\n' in key or '\r' in key:
        raise ValueError('native CodingPlan auth unknown')
    return key

class MemoryProvider:
    def __init__(self,key):
        self.__key=key
        # This domain separation matches the already inspected own monitor.
        self.account_binding_sha256=hashlib.sha256(('own-ZCode-CodingPlan:'+key).encode()).hexdigest()
    def __repr__(self):return '<MemoryProvider fixed CodingPlan; secret redacted; no launch authority>'
    def config(self):
        return {'permission':{'*':'deny'},'plugin':[],'mcp':{},
            'provider':{PROVIDER:{'npm':'@ai-sdk/openai-compatible','name':'Fixed machine-local CodingPlan',
                'options':{'baseURL':CODING_ORIGIN,'apiKey':'{env:'+ENV_KEY+'}'},
                'models':{MODEL:{'name':'Fixed GLM 5.3 Flash'}}}},
            'agent':{'root_contingency':{'mode':'primary','description':'Candidate only; gateway absent',
                'permission':{'*':'deny'}}}}
    def private_environment(self,base):
        # Caller must keep this in a private owned child environment. Never log.
        clean={k:v for k,v in base.items() if not any(x in k.upper() for x in
            ('TOKEN','API_KEY','PROXY','OPENAI','ANTHROPIC','ROOT_CODING_PLAN_KEY','OPENCODE_CONFIG'))}
        clean[ENV_KEY]=self.__key
        clean['OPENCODE_CONFIG_CONTENT']=json.dumps(self.config(),sort_keys=True)
        return clean

def read_fixed_machine_slot():
    if os.name!='nt':raise RuntimeError('wrong native host')
    for p in (AUTH,*AUTH.parents):
        if p.is_symlink() or getattr(p.stat(),'st_file_attributes',0)&0x400:
            raise RuntimeError('native auth reparse held')
    if not AUTH.is_file() or AUTH.stat().st_size>1048576:raise RuntimeError('native auth unavailable')
    return MemoryProvider(native_slot(json.loads(AUTH.read_bytes())))
