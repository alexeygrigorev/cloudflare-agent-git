import types,unittest,copy
from opencode_guardian_runtime import Hooks,NativePending

class GuardianTests(unittest.TestCase):
    def test_plan_authorization_is_distinct_from_runtime_acceptance(self):
        from opencode_guardian_runtime import require_execution_plan
        plan={'authorization':'owned-opencode-root-cold-trial','controller_source_manifest_sha256':'a'*64,
              'execution_pin':'b'*64,'runtime_accepted':True}
        with self.assertRaises(RuntimeError):require_execution_plan(plan,'a'*64)
        plan.update(plan_execution_authorized=True,runtime_accepted=False)
        require_execution_plan(plan,'a'*64)
        with self.assertRaises(RuntimeError):require_execution_plan(plan,'c'*64)
        plan['execution_pin']=None
        with self.assertRaises(RuntimeError):require_execution_plan(plan,'a'*64)
    def test_scheduler_enabled_serialization_preserves_only_exact_task(self):
        from opencode_guardian_runtime import task_matches
        from test_opencode_task_adoption import task
        planned=task();actual=copy.deepcopy(planned)
        actual['xml']=actual['xml'].replace('<Settings><Enabled>true</Enabled>','<Settings>')
        self.assertTrue(task_matches(actual,planned))
        for field,value in [('arguments','foreign'),('execute','foreign'),('sid','foreign'),('enabled',False)]:
            changed=copy.deepcopy(actual);changed[field]=value
            self.assertFalse(task_matches(changed,planned))
        changed=copy.deepcopy(actual)
        changed['xml']=changed['xml'].replace('<TimeTrigger><Enabled>true</Enabled>','<TimeTrigger><Enabled>false</Enabled>')
        self.assertFalse(task_matches(changed,planned))
    def test_pending_native_turn_does_not_wait_for_its_own_completion(self):
        hooks=object.__new__(Hooks);events=[]
        hooks.current_profile=lambda:{'root_runtime_kind':'opencode-native-v1'}
        hooks.host=lambda op:events.append(op)
        hooks.observation=lambda:(_ for _ in ()).throw(NativePending('real native pending'))
        hooks.observe_live()
        self.assertEqual(events,['opencode-observe','opencode-activate','opencode-reply','root-luna-hold'])
    def test_unknown_kernel_is_not_normalized_to_pending_or_success(self):
        hooks=object.__new__(Hooks)
        hooks.current_profile=lambda:{'root_runtime_kind':'opencode-native-v1'}
        hooks.host=lambda op:None
        hooks.observation=lambda:(_ for _ in ()).throw(RuntimeError('foreign kernel'))
        with self.assertRaises(RuntimeError):hooks.observe_live()
    def test_pending_model_preserves_keeper_path(self):
        hooks=object.__new__(Hooks);events=[]
        hooks.current_profile=lambda:{'root_runtime_kind':'opencode-native-v1'}
        hooks.observe_live=lambda:events.append('outside-collect')
        hooks.observation=lambda:(_ for _ in ()).throw(NativePending('pending'))
        self.assertIsNone(hooks.server_preserving_authorization())
        self.assertEqual(events,['outside-collect'])

class CheckpointTests(unittest.TestCase):
    def test_native_session_is_not_a_codex_thread(self):
        from opencode_guardian_runtime import opencode_checkpoint
        result=opencode_checkpoint('ses_source_fixture','a'*64)
        self.assertEqual(result['discriminator'],'opencode-native-v1')
        self.assertEqual(result['session_id'],'ses_source_fixture')
        self.assertNotIn('thread_id',result)
        self.assertEqual(result['pending_tool_count'],0)

if __name__=='__main__':unittest.main()
