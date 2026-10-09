import sys
if not sys.flags.isolated or not sys.flags.no_site:raise SystemExit('requires -I -S')
import pathlib,tempfile,json,importlib.util,unittest
from unittest.mock import Mock
spec=importlib.util.spec_from_file_location('fixed',pathlib.Path(__file__).with_name('fixed_factory.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class HoldingCases(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.original={k:getattr(m,k) for k in ('BASE','HERE','PROFILE','CORE')}
        self.addCleanup(lambda:[setattr(m,k,v) for k,v in self.original.items()])
        m.BASE=pathlib.Path(self.tmp.name);m.HERE=m.BASE/'consumer';m.HERE.mkdir();m.PROFILE=m.BASE/'api-runtime.private.json';m.CORE=m.BASE/'next12'
        (m.BASE/'runtime/api-root').mkdir(parents=True)
        self.old=dict(actor='real-old',generation='actual-old-generation',owner={'epoch':3},credential={'private':'retained'},runtime_mode='api-root',instruction_read_files=[{'path':'owned-doc','sha256':'doc-pin'}],state_dir='old-state',root_tag='old-tag')
        m.PROFILE.write_text(json.dumps(self.old))
        self.oldraw=m.PROFILE.read_bytes();self.permit=dict(owner={'actor':'real-old','generation':'actual-old-generation'},profile_sha256=m.sha(m.PROFILE),challenge='server-nonce')
        self.load=lambda p:json.loads(p.read_text())
        self.write=lambda p,v:p.write_text(json.dumps(v))
        self.factory=m.FixedFactory(self.load,self.write,lambda p:p.mkdir(exist_ok=True),Mock(),Mock(),m.PROFILE)
    def test_new_state_no_cid_and_old_bytes_preserved(self):
        result=self.factory.prepare(self.permit);profile=self.load(m.PROFILE)
        self.assertIsNone(profile['actor']);self.assertIsNone(profile['owner']);self.assertIsNone(profile['credential'])
        self.assertNotEqual(profile['state_dir'],self.old['state_dir']);self.assertEqual(result['holding_profile_sha256'],m.sha(m.PROFILE))
        old=next(m.HERE.glob('predecessor-*.private.json'))
        self.assertEqual(m.base64.b64decode(self.load(old)['raw_base64']),self.oldraw)
        self.assertEqual(profile['instruction_read_files'][-1]['sha256'],m.AUDIT_PIN)
        self.assertEqual(profile['host_script'],str(m.CORE/'win35_root_host.py'))
        self.assertEqual(profile['control_script'],str(m.CORE/'win35_root_control.py'))
        self.assertEqual(len(profile['host_script_sha256']),64)
    def test_retry_after_profile_write_returns_same_holding(self):
        first=self.factory.prepare(self.permit);self.assertEqual(self.factory.prepare(self.permit),first)
    def test_crash_after_expected_holding_write_resumes_exact_before(self):
        save=self.factory.save
        def fail(p,v):
            if p==m.PROFILE:raise OSError('before profile commit')
            return save(p,v)
        self.factory.save=fail
        with self.assertRaises(OSError):self.factory.prepare(self.permit)
        self.assertEqual(m.PROFILE.read_bytes(),self.oldraw)
        self.factory.save=save
        self.factory.prepare(self.permit);self.assertIsNone(self.load(m.PROFILE)['actor'])
    def test_unknown_successor_file_holds_before_profile_write(self):
        key=m.hashlib.sha256(self.permit['challenge'].encode()).hexdigest();d=m.BASE/'runtime/api-root'/('recovery-'+key);d.mkdir();(d/'unknown-journal').write_text('unrelated')
        with self.assertRaisesRegex(RuntimeError,'unknown successor'):self.factory.prepare(self.permit)
        self.assertEqual(m.PROFILE.read_bytes(),self.oldraw)
    def test_foreign_profile_after_interruption_held(self):
        self.factory.prepare(self.permit);m.PROFILE.write_text('{"foreign":"profile"}')
        with self.assertRaisesRegex(RuntimeError,'foreign profile'):self.factory.prepare(self.permit)
    def test_wrong_predecessor_owner_held(self):
        self.permit['owner']['actor']='invented'
        with self.assertRaisesRegex(RuntimeError,'predecessor binding'):self.factory.prepare(self.permit)
        self.assertEqual(m.PROFILE.read_bytes(),self.oldraw)
    def test_later_genuine_successor_reuses_exact_audit_without_duplicate(self):
        self.old['instruction_read_files'].append(dict(path=str(m.HERE/'principal-accountability-input.md'),sha256=m.AUDIT_PIN))
        m.PROFILE.write_text(json.dumps(self.old));self.permit['profile_sha256']=m.sha(m.PROFILE)
        self.factory.prepare(self.permit)
        self.assertEqual(sum(e['path']==str(m.HERE/'principal-accountability-input.md') for e in self.load(m.PROFILE)['instruction_read_files']),1)
if __name__=='__main__':unittest.main()
