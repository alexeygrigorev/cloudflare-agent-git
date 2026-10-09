"""Installed CLI tool-schema capture at a localhost-only non-model responder.

No user auth, upstream provider, root profile/CID or role effects. Only tools
are retained; request input/headers are discarded. No model response exists.
"""
import sys
if not sys.flags.isolated or not sys.flags.no_site:raise SystemExit('isolated no-site required')
import pathlib,hashlib,json,os,http.server,threading,time,uuid,ctypes,msvcrt,socket,secrets,subprocess
BASE=pathlib.Path('C:/Users/User/git/cloudflare-agent-git/.local/win35-root-bootstrap')
sys.path.insert(0,str(BASE/'next12'))
from win35_root_job import WindowsJob
from win35_root_rpc import AppServerRPC
sys.path.insert(0,str(BASE/'api-adoption5'))
from private_writer import ensure_private_directory,save
EXE=pathlib.Path('C:/Users/User/AppData/Local/OpenAI/Codex/bin/9691020b546a15b2/codex.exe')
EXE_SHA='3553cd6e7df5a093d8cb8301cd8088a57e0971aba71ddbe0e67f7f44a15cdf68'
if hashlib.sha256(EXE.read_bytes()).hexdigest()!=EXE_SHA:raise SystemExit('CLI source drift')
out=BASE/'operational-runtime1'/'offline-managed-surface-replay'
ensure_private_directory(out)
home=out/('home-'+uuid.uuid4().hex)
ensure_private_directory(home)
workspace=home/'workspace';ensure_private_directory(workspace)
seen=threading.Event();captured={}; posts=[]; events=[]; tool_requests=[]
additional=home/'additional-root';ensure_private_directory(additional)
control=home/'private-control-source.py'
save(control,{'fixture':'owned private controller source, no live authority'})
control_before=hashlib.sha256(control.read_bytes()).hexdigest()
targets=[workspace/'readonly-repo-probe.txt',additional/'readonly-additional-probe.txt',control]
class Capture(http.server.BaseHTTPRequestHandler):
    def log_message(self,*a):pass
    def do_POST(self):
        length=int(self.headers.get('Content-Length','0'))
        if not 0<length<=4*1024*1024:self.send_error(413);return
        body=json.loads(self.rfile.read(length));tools=body.get('tools')
        captured['additional_tools']=[item for item in body.get('input',[]) if isinstance(item,dict) and item.get('type')=='additional_tools']
        captured.update(request_keys=sorted(body),tools_container_type=type(tools).__name__,
                        method='POST',path=self.path,content_type=self.headers.get('Content-Type'),
                        text_shape=sorted(body.get('text',{})))
        def markers(value,parents=()):
            if isinstance(value,str):
                if 'spawn_agent' in value and len(value)<=16384:
                    if not value.startswith('<multi_agent_role>'):
                        captured.setdefault('spawn_definition_texts',[]).append(value)
                return [{'length':len(value),'spawn_agent':value.find('spawn_agent'),
                         'multi_agent':value.find('multi_agent'),'namespace_functions':value.find('namespace functions')}]
            if isinstance(value,list):return [x for v in value for x in markers(v,parents)]
            if isinstance(value,dict):
                if value.get('type') in ('function','custom') and isinstance(value.get('name'),str):
                    captured.setdefault('native_function_names',[]).append(value['name'])
                    captured.setdefault('native_function_definitions',[]).append(value)
                if value.get('name')=='spawn_agent':
                    captured.setdefault('spawn_definitions',[]).append(value)
                    captured.setdefault('spawn_catalog_parent_shapes',[]).append(parents)
                if value.get('name')=='wait_agent':captured.setdefault('wait_definitions',[]).append(value)
                shape={k:value[k] for k in ('type','name') if k in value and isinstance(value[k],str)}
                return [x for v in value.values() for x in markers(v,(*parents,shape))]
            return []
        captured['input_string_markers']=markers(body.get('input'))
        seen.set()
        if isinstance(tools,list):
            # Only exact tool definitions, never request messages/auth/metadata.
            captured.update(tools=tools,model=body.get('model'),path=self.path)
            seen.set()
        posts.append(body)
        if len(posts)>1:captured['tool_result_items']=[item for item in body.get('input',[]) if isinstance(item,dict) and item.get('type') in ('function_call_output','custom_tool_call_output')]
        if len(posts)>1:
            self.send_response(503);self.end_headers();self.wfile.write(b'{"error":{"message":"offline replay completed"}}');return
        scripts=[]
        for target in targets:
            patch='*** Begin Patch\n*** Add File: '+str(target).replace('\\','/')+'\n+offline owned denial fixture\n*** End Patch'
            scripts.append('try { await tools.apply_patch('+json.dumps(patch)+'); } catch(e) { text(String(e)); }')
        for name,args in [('exec_command',{'cmd':'echo owned_offline_fixture'}),('write_stdin',{'session_id':0,'chars':''}),('view_image',{'path':str(control)}),('create_goal',{'objective':'offline forbidden fixture'}),('spawn_agent',{'task_name':'offline-forbidden-child','message':'No action','model':'gpt-6-luna','reasoning_effort':'max','fork_turns':'none'})]:
            scripts.append('try { await tools.'+name+'('+json.dumps(args)+'); } catch(e) { text(String(e)); }')
        scripts.append('await tools.root_spawn_check({});')
        call={'id':'ctc_offline_owned','type':'custom_tool_call','call_id':'offline_owned_call','name':'exec','namespace':'functions','input':'\n'.join(scripts)}
        response={'id':'resp_offline_owned','object':'response','created_at':int(time.time()),'status':'completed','output':[call]}
        frames=[{'type':'response.created','response':dict(response,status='in_progress',output=[])},
                {'type':'response.output_item.added','output_index':0,'item':dict(call,input='')},
                {'type':'response.custom_tool_call_input.delta','output_index':0,'item_id':call['id'],'delta':call['input']},
                {'type':'response.custom_tool_call_input.done','output_index':0,'item_id':call['id'],'input':call['input']},
                {'type':'response.output_item.done','output_index':0,'item':call},
                {'type':'response.completed','response':response}]
        raw=''.join('event: '+f['type']+'\ndata: '+json.dumps(f)+'\n\n' for f in frames).encode()
        self.send_response(200);self.send_header('Content-Type','text/event-stream');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw);self.wfile.flush()
    def do_GET(self):self.send_error(503)
server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Capture)
threading.Thread(target=server.serve_forever,daemon=True).start()
port=server.server_port
config=f'''model = "gpt-6-sol"
model_provider = "offline_schema"
web_search = "disabled"
project_root_markers = []
model_reasoning_effort = "low"
[model_providers.offline_schema]
name = "Offline schema only"
base_url = "http://127.0.0.1:{port}/v1"
wire_api = "responses"
requires_openai_auth = false
supports_websockets = false
request_max_retries = 0
stream_max_retries = 0
[features]
multi_agent = false
shell_tool = false
goals = false
view_image = false
unified_exec = false
code_mode_host = true
code_mode = false
code_mode_only = false
web_search = false
browser_use = false
browser_use_external = false
browser_use_full_cdp_access = false
computer_use = false
in_app_browser = false
apps = false
plugins = false
remote_plugin = false
plugin_sharing = false
skill_mcp_dependency_install = false
workspace_dependencies = false
[agents]
enabled = false
default_subagent_model = "gpt-6-luna"
default_subagent_reasoning_effort = "max"
'''
# File ACL before bytes; config has no secret or external URL.
cfg=home/'config.toml'
save(cfg,{'schema_only':True})
cfg.write_text(config,encoding='utf-8')
env={k:v for k,v in os.environ.items() if not any(x in k.upper() for x in ('TOKEN','API_KEY','PROXY','CODEX','OPENAI'))}
env['CODEX_HOME']=str(home)
job=WindowsJob();process=None
rpc=None
null_input=open(os.devnull,'rb')
os.set_handle_inheritable(msvcrt.get_osfhandle(null_input.fileno()),True)
ctypes.windll.kernel32.GetStdHandle.restype=ctypes.c_void_p
ctypes.windll.kernel32.SetStdHandle.argtypes=[ctypes.c_ulong,ctypes.c_void_p]
stdin_before=ctypes.windll.kernel32.GetStdHandle(-10)
ctypes.windll.kernel32.SetStdHandle(0xfffffff6,msvcrt.get_osfhandle(null_input.fileno()))
try:
    sock=socket.socket();sock.bind(('127.0.0.1',0));backend_port=sock.getsockname()[1];sock.close()
    token=secrets.token_urlsafe(32);endpoint='ws://127.0.0.1:'+str(backend_port)
    process=job.start([str(EXE),'--ask-for-approval','never','--sandbox','read-only','app-server',
                       '--listen',endpoint,'--ws-auth','capability-token','--ws-token-sha256',
                       hashlib.sha256(token.encode()).hexdigest()],str(workspace),env=env)
    def verify_socket(sock):
        # Only this private probe listener's exact PID may own the connection.
        script=f"(Get-NetTCPConnection -LocalPort {backend_port} -State Listen -ErrorAction Stop).OwningProcess"
        owner=int(subprocess.check_output(['powershell.exe','-NoProfile','-NonInteractive','-Command',script],text=True).strip())
        if owner!=process.pid or process.poll() is not None:raise RuntimeError('offline listener owner mismatch')
    until=time.monotonic()+10
    while time.monotonic()<until:
        try:rpc=AppServerRPC(endpoint,token,verify_socket,timeout=5);break
        except (ConnectionError,OSError):time.sleep(.1)
    if rpc is None:raise RuntimeError('offline app-server absent')
    config_read=rpc.call('config/read',{'cwd':str(workspace),'includeLayers':False})['config']
    captured['effective_features']=config_read.get('features',{})
    captured['effective_agents']=config_read.get('agents',{})
    thread=rpc.call('thread/start',{'cwd':str(workspace),'modelProvider':'offline_schema','model':'gpt-6-sol',
        'sandbox':'read-only','approvalPolicy':'never','historyMode':'legacy','config':{'features':{'multi_agent':False,'unified_exec':False,'goals':False,'view_image':False},'web_search':'disabled'},'runtimeWorkspaceRoots':[str(workspace),str(additional)],'dynamicTools':[{'type':'function','name':'root_spawn_check','description':'Managed read-only check request; host verifies current owner and fresh reserve before child creation.','inputSchema':{'type':'object','properties':{},'additionalProperties':False}}]})['thread']
    rpc.start_reader(lambda m: events.append(m),lambda m: (tool_requests.append({'method':m.get('method'),'params':m.get('params')}) or {'success':False,'contentItems':[{'type':'inputText','text':'Managed probe only: pre-spend denied, no child created.'}]}))
    rpc.call('turn/start',{'threadId':thread['id'],'input':[{'type':'text','text':'Offline schema capture only. Do not call tools.'}]})
    seen.wait(10)
    until=time.monotonic()+25
    while time.monotonic()<until and len(posts)<2:time.sleep(.1)
    # No provider response is ever returned; any remaining process is owned
    # probe-only and cannot have produced a model child.
finally:
    job.kill();job.wait_empty();
    if rpc is not None:rpc.close()
    job.close();server.shutdown();server.server_close()
    ctypes.windll.kernel32.SetStdHandle(0xfffffff6,stdin_before);null_input.close()
names=[]
for tool in captured.get('tools',[]):
    name=tool.get('name') or tool.get('function',{}).get('name')
    if name:names.append(name)
save(out/'tool-definitions.private.json',captured)
summary={'v':1,'schema_only':True,'provider_spend':False,'upstream_connected':False,
         'existing_role_or_profile_changed':False,'request_captured':seen.is_set(),
         'tool_names':names,'cli_source_sha256':EXE_SHA,
         'definitions_sha256':hashlib.sha256((out/'tool-definitions.private.json').read_bytes()).hexdigest(),
         'owned_probe_job_drained':True,'offline_scripted_tool_replay':True,'provider_request_count':len(posts),'write_occurred':any(t.exists() for t in targets[:2]) or hashlib.sha256(control.read_bytes()).hexdigest()!=control_before,'write_targets_unchanged':[not targets[0].exists(),not targets[1].exists(),hashlib.sha256(control.read_bytes()).hexdigest()==control_before],'managed_tool_requests':tool_requests,'native_events':[{'method':m.get('method'),'params':m.get('params')} for m in events]}
save(out/'result.private.json',summary)
print(json.dumps({k:v for k,v in summary.items() if k not in ('native_events','managed_tool_requests')}))
