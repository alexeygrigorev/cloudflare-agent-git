import sys
if not sys.flags.isolated or not sys.flags.no_site:raise SystemExit('requires isolation')
import importlib.util,pathlib,tempfile,unittest,json,os
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('installer',pathlib.Path(__file__).with_name('install_bridge.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class InstallTests(unittest.TestCase):
    def test_literal_authorization_matches_actual_candidate(self):
        p=pathlib.Path(__file__).with_name('install-plan.candidate.private.json')
        plan=json.loads(p.read_text())
        self.assertEqual(m.sha_bytes(p.read_bytes()),m.PLAN_PIN)
        self.assertEqual(plan['host_plan_sha256'],m.HOST_PLAN_PIN)
        self.assertEqual(plan['pending_recovery_sha256'],m.PENDING_PIN)
        self.assertEqual(plan['profile_after_sha256'],m.PROFILE_AFTER)
    def test_listener_readiness_does_not_restart_or_accept_new_invocation(self):
        current={'MainPID':'22','InvocationID':'new'}
        with patch.object(m,'service',return_value=current),patch.object(m,'listener',side_effect=[RuntimeError('not bound'),{'pid':22}]),patch.object(m.subprocess,'run') as restart:
            m.wait_existing_new_listener(current);restart.assert_not_called()
        with patch.object(m,'service',return_value={'MainPID':'33','InvocationID':'foreign'}),patch.object(m.subprocess,'run') as restart:
            with self.assertRaises(RuntimeError):m.wait_existing_new_listener(current)
            restart.assert_not_called()
    def test_actual_activation_receipt_changes_preservation_snapshot(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as d:
            db=pathlib.Path(d)/'authority.db'
            with sqlite3.connect(db) as connection:
                connection.execute('CREATE TABLE activation_receipts(id TEXT, proof TEXT)')
                connection.execute('INSERT INTO activation_receipts VALUES(?,?)',('actual-receipt','original-proof'))
            before=m.db_snapshot(db)
            with sqlite3.connect(db) as connection:connection.execute('UPDATE activation_receipts SET proof=?',('changed-proof',))
            self.assertNotEqual(before,m.db_snapshot(db))

    def test_existing_shared_source_hash_read_needs_no_acl_mutation(self):
        with tempfile.TemporaryDirectory() as d:
            target=pathlib.Path(d)/'shared';m.atomic(target,b'pinned');os.chmod(target,0o664)
            self.assertEqual(m.digest(target),m.sha_bytes(b'pinned'))
            with self.assertRaises(RuntimeError):m.regular(target,True)
            self.assertEqual(target.stat().st_mode&0o777,0o664)
            journal=pathlib.Path(d)/'journal'
            with self.assertRaises(RuntimeError):m.commit_target(target,b'new','foreign-hash',m.sha_bytes(b'new'),journal)
            self.assertEqual(target.read_bytes(),b'pinned')

    def test_no_concrete_authorization_no_effect(self):
        with patch.object(m,'PLAN_PIN',None),patch.object(m,'digest') as io:
            with self.assertRaises(RuntimeError):m.main()
            io.assert_not_called()
    def test_unknown_phase_matching_after_rejected(self):
        for previous in ({},{'phase':'foreign','before':'old','after':'new'},{'phase':'completed','before':'wrong','after':'new'}):
            with self.subTest(previous=previous),self.assertRaises(RuntimeError):m.phase(previous,'new','old','new')
    def test_pending_expected_before_or_after_only(self):
        p={'phase':'write-pending','before':'old','after':'new'}
        self.assertEqual(m.phase(p,'old','old','new'),'write');self.assertEqual(m.phase(p,'new','old','new'),'done')
        with self.assertRaises(RuntimeError):m.phase(p,'foreign','old','new')
        with self.assertRaises(RuntimeError):m.phase(None,'new','old','new')
    def test_actual_atomic_write_and_readback(self):
        with tempfile.TemporaryDirectory() as d:
            target=pathlib.Path(d)/'target';journal=pathlib.Path(d)/'journal';m.atomic(target,b'old')
            m.commit_target(target,b'new',m.sha_bytes(b'old'),m.sha_bytes(b'new'),journal)
            self.assertEqual(target.read_bytes(),b'new');self.assertEqual(m.load(journal)['phase'],'completed')
            m.commit_target(target,b'new',m.sha_bytes(b'old'),m.sha_bytes(b'new'),journal)
            self.assertEqual(target.read_bytes(),b'new')
    def test_known_after_write_crash_resumes_without_write(self):
        with tempfile.TemporaryDirectory() as d:
            target=pathlib.Path(d)/'target';journal=pathlib.Path(d)/'journal';m.atomic(target,b'new')
            m.save(journal,dict(phase='write-pending',before=None,after=m.sha_bytes(b'new')))
            with patch.object(m,'atomic',wraps=m.atomic) as effects:
                m.commit_target(target,b'new',None,m.sha_bytes(b'new'),journal)
                self.assertEqual([c.args[0] for c in effects.call_args_list],[journal])
    def test_present_null_and_empty_journal_no_write(self):
        with tempfile.TemporaryDirectory() as d:
            target=pathlib.Path(d)/'target';journal=pathlib.Path(d)/'journal'
            for value in (None,{}):
                m.save(journal,value)
                with self.assertRaises(RuntimeError):m.commit_target(target,b'new',None,m.sha_bytes(b'new'),journal)
                self.assertFalse(target.exists())
    def test_foreign_target_is_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            target=pathlib.Path(d)/'target';journal=pathlib.Path(d)/'journal';m.atomic(target,b'foreign')
            with self.assertRaises(RuntimeError):m.commit_target(target,b'new',None,m.sha_bytes(b'new'),journal)
            self.assertEqual(target.read_bytes(),b'foreign');self.assertFalse(journal.exists())
if __name__=='__main__':unittest.main()
