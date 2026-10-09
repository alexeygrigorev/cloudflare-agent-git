import sys
if not sys.flags.isolated or not sys.flags.no_site:raise SystemExit('requires -I -S')
import importlib.util,pathlib,unittest,copy
from unittest.mock import Mock
spec=importlib.util.spec_from_file_location('driver',pathlib.Path(__file__).with_name('recovery_driver.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class DriverRoutes(unittest.TestCase):
    def setUp(self):
        self.saved=None;self.h=Mock();self.h.read_recovery.side_effect=lambda:copy.deepcopy(self.saved)
        def write(record):self.saved=copy.deepcopy(record)
        self.h.write_recovery.side_effect=write
        self.h.current_profile.return_value={'actual':'root'};self.h.native_alive.return_value=False
        self.h.server_challenge.return_value={'nonce':'actual-server-nonce'}
        self.h.server_reconcile.return_value={'permit':{'challenge':'actual-server-nonce'},'expected':{'owner':'actual-old'}}
        self.h.perform_factory.return_value={'actor':'actual-new'};self.h.server_enroll.return_value={'root_only_handoff':'private'}
        self.h.prepare_credential_merge.return_value={'before':'holding','after':'bound'}
        self.d=m.Driver(self.h)
    def test_live_root_never_enters_factory(self):
        self.h.native_alive.return_value=True;self.d.step()
        self.h.server_challenge.assert_not_called();self.h.perform_factory.assert_not_called();self.h.supervise_recover.assert_called_once()
    def test_unknown_death_no_profile_factory_enrollment_effect(self):
        self.h.observe_death.side_effect=RuntimeError('protected/unknown Job')
        with self.assertRaises(RuntimeError):self.d.step()
        self.h.perform_factory.assert_not_called();self.h.server_enroll.assert_not_called();self.assertIsNone(self.saved)
    def test_real_sequence_factory_once_and_live_replay_only_keeper(self):
        self.d.step();self.h.successor_live.return_value=True;self.d.step()
        self.h.perform_factory.assert_called_once();self.h.server_enroll.assert_called_once()
        self.assertEqual(self.saved['phase'],'completed')
    def test_crash_after_factory_resume_does_not_spawn_again(self):
        self.h.server_enroll.side_effect=ConnectionError('lost response')
        with self.assertRaises(ConnectionError):self.d.step()
        self.assertEqual(self.saved['phase'],'factory-completed')
        self.h.server_enroll.side_effect=None;self.h.server_enroll.return_value={'private':'handoff'}
        self.d.step();self.h.perform_factory.assert_called_once()
    def test_merge_failure_pending_is_reconciled(self):
        self.h.complete_credential_merge.side_effect=OSError('after-profile-write')
        with self.assertRaises(OSError):self.d.step()
        self.assertEqual(self.saved['phase'],'credential-write-pending')
        self.h.complete_credential_merge.side_effect=None;self.d.step()
        self.h.perform_factory.assert_called_once();self.h.server_enroll.assert_called_once()
    def test_unknown_journal_matching_successor_held(self):
        self.saved={'phase':'unknown','successor':{'actor':'actual-new'}}
        with self.assertRaises(m.Held):self.d.step()
        self.h.supervise_recover.assert_not_called();self.h.perform_factory.assert_not_called()
    def test_dead_completed_successor_requires_new_challenge_not_same_attempt(self):
        self.d.step();self.h.successor_live.return_value=False;self.d.step()
        self.h.archive_completed.assert_called_once();self.h.perform_factory.assert_called_once()
if __name__=='__main__':unittest.main()
