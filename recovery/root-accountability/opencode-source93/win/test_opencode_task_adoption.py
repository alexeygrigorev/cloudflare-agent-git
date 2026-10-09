import copy,unittest
import opencode_task_adoption as module

def task():
    return dict(arguments='old',enabled=True,execute='fixed-python',sid='own',
        xml='<Task xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task"><Triggers><TimeTrigger><Enabled>true</Enabled></TimeTrigger></Triggers><Settings><Enabled>true</Enabled><MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy></Settings><Actions><Exec><Arguments>old</Arguments></Exec></Actions></Task>')

class Tests(unittest.TestCase):
    def test_existing_powershell_action_gets_fixed_pinned_python_wrapper(self):
        import base64
        value=module.guardian_arguments('C:/owned/candidate','a'*64,'b'*64,'C:/owned/python.exe','c'*64)
        self.assertTrue(value.startswith('-NoProfile -NonInteractive -WindowStyle Hidden -EncodedCommand '))
        script=base64.b64decode(value.rsplit(' ',1)[1]).decode('utf-16-le')
        self.assertIn("& 'C:/owned/python.exe' -I -S",script)
        self.assertIn(' Guard '+'a'*64,script)
        self.assertIn("'"+'b'*64+"'",script)
        self.assertIn("'"+'c'*64+"'",script)
    def test_semantic_comparison_changes_only_action_and_top_enabled(self):
        old=task();new=copy.deepcopy(old);new['arguments']='new';new['enabled']=False
        new['xml']=new['xml'].replace('<Arguments>old</Arguments>','<Arguments>new</Arguments>').replace('<Settings><Enabled>true</Enabled>','<Settings><Enabled>false</Enabled>')
        self.assertEqual(module.normalized(old),module.normalized(new))
        new['xml']=new['xml'].replace('<TimeTrigger><Enabled>true</Enabled>','<TimeTrigger><Enabled>false</Enabled>')
        self.assertNotEqual(module.normalized(old),module.normalized(new))
    def test_retirement_denies_owned_child_before_obtaining_terminate_handle(self):
        h=object.__new__(module.WindowsHooks);h.old=task();h.exact=lambda *args:None
        h.verify_protected_family=lambda:None;h.old_alive=lambda:True;h.children=lambda:[{'ProcessId':234}]
        class Job:
            def kernel(self):raise AssertionError('must not obtain mutation handle')
        h.job=Job()
        with self.assertRaisesRegex(RuntimeError,'child work'):h.retire_exact_outside_guardian()
    def test_exact_exited_original_guardian_requires_no_process_mutation(self):
        h=object.__new__(module.WindowsHooks);h.old=task();h.exact=lambda *args:None
        h.verify_protected_family=lambda:None;h.old_alive=lambda:False
        class Job:
            def kernel(self):raise AssertionError('exited original has no mutation')
        h.job=Job();h.retire_exact_outside_guardian()
    def test_changed_task_denies_action_write(self):
        h=object.__new__(module.WindowsHooks);h.old=task();h.arguments='new'
        changed=task();changed['enabled']=False;changed['xml']=changed['xml'].replace('IgnoreNew','Parallel')
        h.task=lambda:changed
        with self.assertRaisesRegex(RuntimeError,'semantic conflict'):h.rebind_only_arguments_reconcile()

if __name__=='__main__':unittest.main()
