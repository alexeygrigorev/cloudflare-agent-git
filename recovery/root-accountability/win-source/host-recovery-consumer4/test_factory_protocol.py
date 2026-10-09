import sys
if not sys.flags.isolated or not sys.flags.no_site:raise SystemExit('requires -I -S')
import pathlib,importlib.util,copy,unittest
from unittest.mock import Mock
spec=importlib.util.spec_from_file_location('factory',pathlib.Path(__file__).with_name('factory_protocol.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Store:
    def __init__(self):self.value=None;self.fail=None
    def read(self):return copy.deepcopy(self.value)
    def write(self,value):
        self.value=copy.deepcopy(value)
        if self.fail==value['phase']:self.fail=None;raise OSError('injected after durable commit')
class FactoryCases(unittest.TestCase):
    def setUp(self):
        self.expected=dict(challenge='server-nonce',owner=dict(actor='actual-old',epoch=3),profile_sha256='a'*64)
        self.permit=dict(self.expected,v=1,operation='fixed-native-factory')
        self.store=Store();self.prepare=Mock(return_value={'fixed_holding':True});self.spawn=Mock(return_value={'id':'actual-new'})
        self.reconcile=Mock(return_value={'actual_leaf_verified':True,'actor':'actual-new'})
    def runfactory(self):return m.perform(self.permit,self.expected,self.store,self.prepare,self.spawn,self.reconcile)
    def test_success_and_replay_no_second_spawn(self):
        self.assertEqual(self.runfactory()['actor'],'actual-new');self.runfactory();self.spawn.assert_called_once()
    def test_foreign_permit_no_writes_or_effect(self):
        self.permit['owner']={'actor':'foreign','epoch':3}
        with self.assertRaises(m.Held):self.runfactory()
        self.assertIsNone(self.store.value);self.spawn.assert_not_called()
    def test_unknown_phase_matching_permit_held(self):
        self.store.value=dict(v=1,phase='unknown',permit_sha256=m.digest(self.permit),owner=self.expected['owner'],challenge=self.expected['challenge'])
        with self.assertRaises(m.Held):self.runfactory()
        self.spawn.assert_not_called()
    def test_after_profile_commit_resumes_idempotent_prepare(self):
        self.store.fail='factory-ready'
        with self.assertRaises(OSError):self.runfactory()
        self.runfactory();self.prepare.assert_called_once();self.spawn.assert_called_once()
    def test_after_factory_pending_commit_never_spawns_on_retry(self):
        self.store.fail='factory-pending-reconcile-only'
        with self.assertRaises(OSError):self.runfactory()
        self.runfactory();self.spawn.assert_not_called();self.reconcile.assert_called_once()
    def test_spawn_timeout_preserves_pending_and_never_resends(self):
        self.spawn.side_effect=TimeoutError('ambiguous actual native start')
        with self.assertRaises(TimeoutError):self.runfactory()
        self.reconcile.return_value={'actual_leaf_verified':False}
        with self.assertRaises(m.Held):self.runfactory()
        self.spawn.assert_called_once()
    def test_after_completed_commit_replay_has_no_effect(self):
        self.store.fail='completed'
        with self.assertRaises(OSError):self.runfactory()
        self.runfactory();self.spawn.assert_called_once();self.reconcile.assert_called_once()
if __name__=='__main__':unittest.main()
