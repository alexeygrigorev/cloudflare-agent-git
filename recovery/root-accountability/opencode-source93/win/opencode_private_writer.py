"""Owner-private bytes before write; unique temporaries do not block recovery."""
import base64,json,os,pathlib,subprocess,uuid
def ensure_private_directory(path):
    path=pathlib.Path(path)
    for component in (path,*path.parents):
        if component.exists() and (component.is_symlink() or getattr(component.stat(),'st_file_attributes',0)&0x400):
            raise RuntimeError('reparse private directory')
    fresh=not path.exists()
    if fresh:path.mkdir(mode=0o700)  # Only this fixed leaf; never alter parent directories.
    if not path.is_dir():raise RuntimeError('not a private directory')
    if os.name=='nt':
        if fresh:
            sid=subprocess.check_output(['powershell.exe','-NoProfile','-Command','[Security.Principal.WindowsIdentity]::GetCurrent().User.Value'],text=True,timeout=10).strip()
            if not sid.startswith('S-1-5-'):raise RuntimeError('private owner SID unknown')
            subprocess.run(['icacls.exe',str(path),'/setowner','*'+sid],capture_output=True,check=True,timeout=10)
            subprocess.run(['icacls.exe',str(path),'/inheritance:r','/grant:r','*'+sid+':(OI)(CI)(F)','*S-1-5-18:(OI)(CI)(F)','*S-1-5-32-544:(OI)(CI)(F)'],capture_output=True,check=True,timeout=10)
        script=r'''$ErrorActionPreference='Stop';$ProgressPreference='SilentlyContinue'
$f=Get-Item -LiteralPath $env:WIN35_ROOT_PRIVATE_DIRECTORY
if(-not $f.PSIsContainer -or ($f.Attributes -band [IO.FileAttributes]::ReparsePoint)){throw 'invalid private directory'}
$me=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$acl=[IO.Directory]::GetAccessControl($f.FullName)
if($acl.GetOwner([Security.Principal.SecurityIdentifier]).Value -ne $me){throw 'directory owner mismatch'}
foreach($rule in $acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier])){if($rule.AccessControlType -eq 'Allow' -and $rule.IdentityReference.Value -notin @($me,'S-1-5-18','S-1-5-32-544')){throw 'broad directory ACL'}}
'''
        encoded=base64.b64encode(script.encode('utf-16-le')).decode()
        environment=dict(os.environ,WIN35_ROOT_PRIVATE_DIRECTORY=str(path))
        environment.pop('PSModulePath',None)  # Native WindowsPowerShell modules, not parent pwsh overrides.
        subprocess.run(['powershell.exe','-NoProfile','-EncodedCommand',encoded],env=environment,capture_output=True,check=True,timeout=10)
    elif path.stat().st_uid!=os.getuid() or path.stat().st_mode&0o077:
        raise RuntimeError('directory owner/mode mismatch')
def save(path,value):
    path=pathlib.Path(path);temp=path.with_name(path.name+'.p-'+uuid.uuid4().hex)
    with temp.open('x',encoding='utf-8') as stream:
        if os.name=='nt':
            sid=subprocess.check_output(['powershell.exe','-NoProfile','-Command','[Security.Principal.WindowsIdentity]::GetCurrent().User.Value'],text=True,timeout=10).strip()
            if not sid.startswith('S-1-5-'):raise RuntimeError('private owner SID unknown')
            subprocess.run(['icacls.exe',str(temp),'/inheritance:r','/grant:r','*'+sid+':(F)','*S-1-5-18:(F)','*S-1-5-32-544:(F)'],capture_output=True,check=True,timeout=10)
        else:os.chmod(temp,0o600)
        json.dump(value,stream);stream.flush();os.fsync(stream.fileno())
    temp.replace(path)
