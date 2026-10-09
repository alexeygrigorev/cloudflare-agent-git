import hashlib,pathlib,tempfile,unittest
from opencode_startup_bundle import StartupBundle,DOCS

class StartupTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
  self.path=pathlib.Path(self.temp.name)/'fixture-steering.md';self.path.write_bytes(b'SOURCE FIXTURE ONLY, not current steering or runtime approval.\n')
  self.sha=hashlib.sha256(self.path.read_bytes()).hexdigest()
  self.root=pathlib.Path(__file__).parent/'startup-canonical80'
 def test_all_six_actual_canonical_files_plus_explicit_addendum_read(self):
  bundle=StartupBundle(self.root,self.path,self.sha);result=bundle({})
  self.assertEqual(len(result['documents']),7);self.assertTrue(result['complete_startup_ready'])
  self.assertEqual({d['path'] for d in result['documents'][:-1]},set(DOCS))
  self.assertFalse(result['authority_effect'])
 def test_missing_or_changed_steering_holds(self):
  with self.assertRaises(RuntimeError):StartupBundle(self.root,None,None)
  self.path.write_bytes(b'changed')
  with self.assertRaises(RuntimeError):StartupBundle(self.root,self.path,self.sha)({})

if __name__=='__main__':unittest.main()
