import sys
if not sys.flags.isolated or not sys.flags.no_site:raise SystemExit('requires isolation')
import pathlib,importlib.util,unittest,json,types,copy
from unittest.mock import Mock,patch
spec=importlib.util.spec_from_file_location('adapter6',pathlib.Path(__file__).with_name('adopt_guardian.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Cases(unittest.TestCase):
    def setUp(self):
        self.k=dict(pid=10,creation_filetime=20,session_id=2,user_sid='fixture',image='python',command='python -I -S own Guard')
        self.h=m.Hooks.__new__(m.Hooks);self.h.before={'guardian_kernel':self.k};self.h.plan={'deployment':{'python_exe':'python'}}
        self.h.guardian=Mock();self.h.guardian.native_context.return_value=self.k
    def scan(self,rows,status):
        dep=types.SimpleNamespace(recorded_process_state=Mock(return_value=status))
        with patch.dict(sys.modules,{'win35_root_job':dep}),patch.object(m,'ps',return_value=json.dumps(rows)):
            return self.h.mechanical_processes()
    def test_exact_current_mechanical_kernel(self):self.assertEqual(self.scan([{'ProcessId':10}],'alive'),[self.k])
    def test_missing_scan_not_death(self):
        with self.assertRaises(RuntimeError):self.scan([],'alive')
        with self.assertRaises(RuntimeError):self.scan([],'unknown')
        self.assertEqual(self.scan([],'exited'),[])
    def test_duplicate_or_foreign_kernel_hold(self):
        with self.assertRaises(RuntimeError):self.scan([{'ProcessId':10},{'ProcessId':11}],'alive')
        for field,value in [('pid',11),('creation_filetime',21),('session_id',0),('user_sid','foreign'),('command','python -I -S foreign Guard')]:
            self.h.guardian.native_context.return_value=dict(self.k,**{field:value})
            with self.assertRaises(RuntimeError):self.scan([{'ProcessId':10}],'alive')
    def test_missing_journal_is_fresh_but_present_empty_is_not(self):
        self.h.load=Mock(return_value={})
        with patch.object(pathlib.Path,'exists',return_value=False):self.assertIsNone(self.h.read_journal())
        with patch.object(pathlib.Path,'exists',return_value=True):self.assertEqual(self.h.read_journal(),{})
    def test_repair_boundary_exact_original_guardian_and_actual_death(self):
        r=dict(source_sha256='99380eb28690f0d52e7f30aded2c14274947115e7e3d770117bb3e35971038cb',owner={'epoch':7},guardian_alive=True,job_drained={'active_processes':0,'source':'QueryInformationJobObject'},dead={n:True for n in ('native','worker','workload','backend')},observations={'guardian':self.k})
        m.verify_repair_boundary(r,self.k)
        for field,value in [('pid',11),('creation_filetime',21),('session_id',0),('user_sid','foreign')]:
            bad=copy.deepcopy(r);bad['observations']['guardian'][field]=value
            with self.assertRaises(RuntimeError):m.verify_repair_boundary(bad,self.k)
        for mutate in [lambda b:b['dead'].update(backend=False),lambda b:b['job_drained'].update(active_processes=1),lambda b:b.update(guardian_alive=False),lambda b:b.update(source_sha256='foreign')]:
            bad=copy.deepcopy(r);mutate(bad)
            with self.assertRaises(RuntimeError):m.verify_repair_boundary(bad,self.k)
    def test_enabled_normalization_never_ignores_trigger_or_action(self):
        xml='<Task xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task"><Triggers><TimeTrigger><Enabled>true</Enabled></TimeTrigger></Triggers><Settings><Enabled>true</Enabled></Settings><Actions><Exec><Arguments>old</Arguments></Exec></Actions></Task>'
        old=dict(xml=xml,enabled=True,arguments='old',sid='same',execute='same')
        changed=dict(old,xml=xml.replace('<Settings><Enabled>true','<Settings><Enabled>false'),enabled=False)
        self.assertEqual(m.normalized_task(old),m.normalized_task(changed))
        for value in [dict(old,sid='foreign'),dict(old,execute='foreign'),dict(old,xml=xml.replace('<TimeTrigger><Enabled>true','<TimeTrigger><Enabled>false'))]:
            self.assertNotEqual(m.normalized_task(old),m.normalized_task(value))
if __name__=='__main__':unittest.main()
