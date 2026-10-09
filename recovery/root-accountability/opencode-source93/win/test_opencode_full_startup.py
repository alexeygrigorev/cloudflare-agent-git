import pathlib,shutil,tempfile,unittest
from opencode_full_startup import FullStartup,MANIFEST_SHA
from opencode_fixed_binder import FixedBinder

class StartupTests(unittest.TestCase):
    def setUp(self):self.root=pathlib.Path(__file__).parent/'startup-full81'
    def test_actual_twelve_pinned_source_files_are_served(self):
        bundle=FullStartup(self.root);docs=bundle.documents()
        self.assertEqual(len(docs),12)
        self.assertIn('AGENTS.md',[d['name'] for d in docs])
        self.assertIn('latest-human-steering.private.json',[d['name'] for d in docs])
        self.assertEqual(bundle.manifest_sha256,MANIFEST_SHA)
    def test_changed_actual_document_holds_before_read_result(self):
        with tempfile.TemporaryDirectory() as temp:
            copy=pathlib.Path(temp)/'bundle';shutil.copytree(self.root,copy)
            (copy/'AGENTS.md').write_text('changed')
            with self.assertRaises(RuntimeError):FullStartup(copy).documents()
    def test_binder_ack_uses_full_bundle_digest_not_old_three_docs(self):
        bundle=FullStartup(self.root)
        journal=type('FixtureJournal',(),{'write':lambda *args:None})()
        binder=FixedBinder({'role':'root'},'fixture',None,None,journal,self.root,
            self.root/'unused','unused',None,lambda:100,startup_bundle=bundle)
        result=binder.instructions({'owner':{},'kernel':{},'session_id':'ses_fixture','user_message_id':'msg_fixture'})
        self.assertEqual(result['instructions_sha256'],bundle.instructions_sha256)
        self.assertEqual(len(result['documents']),12)
        with self.assertRaises(RuntimeError):binder.helper({},'root_ack_instructions',{'instructions_sha256':'old'})

if __name__=='__main__':unittest.main()
