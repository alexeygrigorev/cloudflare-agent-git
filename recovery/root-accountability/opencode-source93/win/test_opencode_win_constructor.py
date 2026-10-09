import pathlib,types,unittest
from unittest.mock import patch
import opencode_win_constructor as module

class ConstructorTests(unittest.TestCase):
    def test_actual_pinned_snapshot_bundle_is_readable_by_binder(self):
        from opencode_fixed_binder import FixedBinder
        snapshot=module.HERE/'principal-observation-20261009T043726Z.private.json'
        binder=object.__new__(FixedBinder)
        binder.snapshot_path=snapshot
        binder.snapshot_sha256='0d30c9782f01e5331532f8b33bef6033927b395803b0fae71f16dd244ed76135'
        binder.reparse=lambda path:False
        binder.clock=lambda:1
        result=binder.snapshot({'owner':{'fixture':True},'kernel':{},'session_id':'ses_fixture','user_message_id':'msg_fixture'})
        self.assertEqual(result['source_kind'],'operator-audit')
        self.assertFalse(result['principal_authored'])
        self.assertEqual(result['facts']['source_event_at'],1791520646.863557)
    def test_wrong_platform_holds_before_any_private_read_or_identity_call(self):
        with patch.object(module.os,'name','posix'),patch.object(module,'load_private',side_effect=AssertionError('private read forbidden')):
            with self.assertRaisesRegex(RuntimeError,'native Windows constructor required'):
                module.construct(module.LEAVES/('preserving-'+'a'*64),'b'*64,'c'*64)
    def test_job_reopen_has_query_only_rights_and_no_create_or_terminate(self):
        calls=[]
        api=types.SimpleNamespace(OpenJobObjectW=lambda *args:calls.append(args) or 123,
                                  CloseHandle=lambda handle:calls.append(('close',handle)))
        dependency=types.SimpleNamespace(kernel=lambda:api,require=lambda result:None)
        name='Local\\Win35Root-'+'a'*32
        job=module.QueryJob(dependency,name)
        self.assertEqual(calls,[(4,False,name)])
        self.assertFalse(hasattr(job,'kill'));self.assertFalse(hasattr(job,'start'))
        job.close();self.assertEqual(calls[-1],('close',123))
    def test_unrelated_job_name_denied_without_open(self):
        dependency=types.SimpleNamespace(kernel=lambda:(_ for _ in ()).throw(AssertionError('open forbidden')))
        with self.assertRaises(RuntimeError):module.QueryJob(dependency,'foreign-peer')

if __name__=='__main__':unittest.main()
