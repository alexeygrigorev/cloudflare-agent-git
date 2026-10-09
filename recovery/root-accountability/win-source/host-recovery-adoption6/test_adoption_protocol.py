import sys
if not sys.flags.isolated or not sys.flags.no_site:raise SystemExit('requires isolation')
import importlib.util,pathlib,unittest,copy
from unittest.mock import Mock
spec=importlib.util.spec_from_file_location('adopt',pathlib.Path(__file__).with_name('adoption_protocol.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Cases(unittest.TestCase):
    def setUp(self):
        self.h=Mock(unsafe=True);self.h.plan_sha256='plan';self.record=None
        self.h.read_journal.side_effect=lambda:copy.deepcopy(self.record)
        self.h.save.side_effect=lambda value:setattr(self,'record',copy.deepcopy(value))
        self.h.actual_one_instance.return_value=False;self.h.reconcile_actual_guardian.return_value={'actual':'new-kernel'}
    def test_conflict_before_any_task_effect(self):
        self.h.verify_all_source_and_private_inputs.side_effect=RuntimeError('credential/source conflict')
        with self.assertRaises(RuntimeError):m.transition(self.h)
        self.h.disable_only_exact_old_task.assert_not_called();self.h.stop_exact_mechanical_task_and_wait_dead.assert_not_called()
    def test_retained_legacy_unknown_before_effect(self):
        self.h.assert_legacy_and_dead_predecessor.side_effect=RuntimeError('unknown peer')
        with self.assertRaises(RuntimeError):m.transition(self.h)
        self.h.disable_only_exact_old_task.assert_not_called()
    def test_intent_precedes_enable_trigger_race(self):
        self.h.actual_one_instance.return_value=True
        self.h.enable_exact_task.side_effect=lambda:self.assertEqual(self.record['phase'],'start-intent')
        self.assertEqual(m.transition(self.h)['phase'],'completed');self.h.start_exact_task_once.assert_not_called()
    def test_one_explicit_start_only(self):
        m.transition(self.h);m.transition(self.h)
        self.h.start_exact_task_once.assert_called_once();self.h.stop_exact_mechanical_task_and_wait_dead.assert_called_once()
    def test_resume_start_intent_never_replays_start_or_enable(self):
        self.record={'phase':'start-intent','plan_sha256':'plan'}
        m.transition(self.h);self.h.enable_exact_task.assert_not_called();self.h.start_exact_task_once.assert_not_called()
    def test_dead_guardian_unknown_preserves_disabled_task(self):
        self.h.stop_exact_mechanical_task_and_wait_dead.side_effect=RuntimeError('kernel still alive')
        with self.assertRaises(RuntimeError):m.transition(self.h)
        self.assertEqual(self.record['phase'],'retire-pending');self.h.rebind_only_action_and_readback.assert_not_called()
    def test_unknown_phase_matching_plan_held(self):
        self.record={'phase':'tampered','plan_sha256':'plan'}
        with self.assertRaises(m.Held):m.transition(self.h)
        self.h.disable_only_exact_old_task.assert_not_called()
if __name__=='__main__':unittest.main()
