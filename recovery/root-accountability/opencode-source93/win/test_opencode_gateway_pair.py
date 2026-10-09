"""Actual corrected server verifier with unchanged Win producer/native history."""
import copy,hashlib,importlib.util,pathlib,sys,unittest
import test_opencode_root_producer as fixtures
from opencode_native_proof import fixed_reader_context

SOURCE=pathlib.Path(__file__).with_name('opencode_native76.reference.py')
EXPECTED='e0bb320a5c0d502ac4848ad25698423a3ac279146370156f6b74ce0dc6ccf66e'
def actual_verifier():
    if hashlib.sha256(SOURCE.read_bytes()).hexdigest()!=EXPECTED:raise RuntimeError('actual paired verifier source drift')
    spec=importlib.util.spec_from_file_location('exact_native76',SOURCE);module=importlib.util.module_from_spec(spec)
    sys.modules[spec.name]=module;spec.loader.exec_module(module);return module.NativeVerifier
class PairTests(unittest.TestCase):
    def setUp(self):
        f=fixtures.RootProducerTests();f.setUp();self.history,h=f.proof_inputs()
        self.context=fixed_reader_context(f.context,h)
        self.verifier=actual_verifier()(lambda:copy.deepcopy(self.context),lambda c:copy.deepcopy(self.history),lambda c:True,lambda:2.5)
    def test_actual_prefixed_native_event_and_context_interoperate(self):
        observation=self.verifier.observe();self.assertEqual(observation.tool,'root_role_reply')
        self.assertEqual(observation.native_tool,'root_gateway_root_role_reply')
        self.assertEqual(observation.call_id,'provider-call');self.assertEqual(observation.part_id,'prt_tool')
    def test_logical_or_foreign_namespace_is_not_native_event(self):
        for name in ('root_role_reply','other_root_role_reply'):
            self.history[-1]['parts'][0]['tool']=name
            with self.assertRaises(ValueError):self.verifier.observe()
    def test_actual_context_drift_denied(self):
        def history(c):self.context['revision']+=1;return self.history
        self.verifier.history_reader=history
        with self.assertRaises(ValueError):self.verifier.observe()
    def test_completed_native_tool_does_not_require_assistant_final(self):
        self.history[-1]['info']['time'].pop('completed')
        self.assertEqual(self.verifier.observe().tool,'root_role_reply')
    def test_empty_reply_or_wrong_session_denied(self):
        self.context['helper']['args']['body']=''
        self.history[-1]['parts'][0]['state']['input']['body']=''
        with self.assertRaises(ValueError):self.verifier.observe()
        self.history[0]['info']['sessionID']='ses_foreign'
        with self.assertRaises(ValueError):self.verifier.observe()
if __name__=='__main__':unittest.main()
