"""Fixed own CodingPlan monitor + physical cache; never submits a model.

Called only by the reviewed native pre-effect path, not a periodic quota probe.
Private balances remain in memory. Cache exposes booleans/digests only.
"""
import hashlib,http.client,json,math,pathlib,ssl,subprocess,time
from opencode_memory_provider import read_fixed_machine_slot

class OwnAdmission:
    def __init__(self,account_binding,source_guard,save_cache,resource_reader,clock=time.time):
        self.account=account_binding;self.guard=source_guard;self.save=save_cache
        self.resource=resource_reader;self.clock=clock
    def __call__(self):
        started=self.clock();self.guard()
        result={'provider':'zai-coding-plan','model':'glm-5.3-flash','account_binding':self.account,
            'launch_allowed':False,'physical_allowed':False,'source_ref':None,'resource_ref':None,
            'observed_at':started,'valid_until':started+30,'status':'READ_UNKNOWN','model_started':False}
        connection=None
        try:
            provider=read_fixed_machine_slot()
            if provider.account_binding_sha256!=self.account:raise RuntimeError('own provider account differs')
            # Existing same-machine key stays in the private child environment.
            # This process-private monitor never logs/configures the real key.
            environment=provider.private_environment({})
            token=environment.pop('ROOT_CODING_PLAN_KEY');environment.clear()
            connection=http.client.HTTPSConnection('api.z.ai',443,context=ssl.create_default_context(),timeout=10)
            connection.request('GET','/api/monitor/usage/quota/limit',headers={'Authorization':'Bearer '+token,'Accept':'application/json'})
            token=None
            response=connection.getresponse();raw=response.read(1048577)
            if response.status!=200 or len(raw)>1048576:raise RuntimeError('actual CodingPlan monitor unavailable')
            value=json.loads(raw);value=value.get('data',value)
            windows={}
            for row in value['limits']:
                if row.get('type')=='TOKENS_LIMIT' and row.get('unit') in (3,6):
                    used=row.get('percentage');unit=row['unit']
                    if unit in windows or type(used) not in (int,float) or not math.isfinite(used) or not 0<=used<=100:
                        raise RuntimeError('ambiguous/unknown actual CodingPlan windows')
                    windows[unit]=100-used
            if set(windows)!={3,6}:raise RuntimeError('required CodingPlan windows missing')
            resource=self.resource()
            if type(resource) is not dict or resource.get('allowed') is not True or not resource.get('source_ref'):
                raise RuntimeError('actual physical admission denied')
            self.guard()
            if not 0<=self.clock()-started<30:raise RuntimeError('admission collector timed out')
            result.update(status='ALLOWED' if all(v>0 for v in windows.values()) else 'PROVIDER_DENIED',
                launch_allowed=all(v>0 for v in windows.values()),physical_allowed=True,
                source_ref=hashlib.sha256(raw+self.account.encode()).hexdigest(),resource_ref=resource['source_ref'])
        except Exception:
            # Never return private HTTP/auth/config exceptions or raw balances.
            pass
        finally:
            if connection is not None:connection.close()
        self.save(result) # owned private cache BEFORE server/SQL consumers
        return result

def physical_reader(directory,source_guard):
    directory=pathlib.Path(directory);source_guard()
    if directory.is_symlink() or getattr(directory.stat(),'st_file_attributes',0)&0x400:
        raise RuntimeError('private scratch reparse held')
    total=0
    for path in directory.rglob('*'):
        if path.is_symlink() or getattr(path.stat(),'st_file_attributes',0)&0x400:raise RuntimeError('scratch reparse held')
        if path.is_file():total+=path.stat().st_size
        if total>512*1024**2:raise RuntimeError('owned scratch budget exceeded')
    script="$ErrorActionPreference='Stop';$o=Get-CimInstance Win32_OperatingSystem;$d=Get-CimInstance Win32_LogicalDisk -Filter \"DeviceID='C:'\";@{disk_free=[long]$d.FreeSpace;ram_free=[long]$o.FreePhysicalMemory*1024}|ConvertTo-Json -Compress"
    response=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',script],capture_output=True,text=True,timeout=10,check=True)
    resource=json.loads(response.stdout)
    if any(type(resource.get(k)) is not int or resource[k]<0 for k in ('disk_free','ram_free')):
        raise RuntimeError('actual host resource evidence unknown')
    allowed=resource['disk_free']-1024**3>=20*1024**3 and total<=512*1024**2
    source_guard()
    return {'allowed':allowed,'source_ref':hashlib.sha256(json.dumps(dict(resource,scratch=total),sort_keys=True).encode()).hexdigest()}
