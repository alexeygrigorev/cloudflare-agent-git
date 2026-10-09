import json,pathlib,tempfile,threading,unittest
from unittest.mock import patch
import opencode_controller_store as module

class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=pathlib.Path(self.temp.name);self.override=patch.object(module,'BASE',self.base)
        self.override.start();self.addCleanup(self.override.stop)
        self.directory=self.base/('preserving-'+'a'*64);self.directory.mkdir()
        self.verified=[];self.saved=[];self.events=[];outer=self
        class Api:
            LK_NBLCK=1;LK_UNLCK=2
            def locking(self,fd,mode,n):outer.events.append(mode)
        self.store=module.ControllerStore(self.directory,lambda p:json.loads(p.read_text()),
            self.save,lambda p:self.verified.append(p),Api())
        self.store.lock_path.write_bytes(b'0')
    def save(self,p,v):self.saved.append(v);p.write_text(json.dumps(v))
    def test_one_file_transaction_and_readback(self):
        lock=module.JournalLock(self.store)
        with lock:
            self.assertIsNone(self.store.read());self.store.save({'phase':'selected','v':1})
            self.assertEqual(self.store.read()['v'],1)
        self.assertEqual(self.events,[1,2]);self.assertIn(self.store.lock_path,self.verified)
    def test_unknown_present_journal_never_fresh(self):
        self.store.path.write_text('null')
        with self.assertRaises(RuntimeError):self.store.read()
        with self.assertRaises(RuntimeError):self.store.save({'phase':'unknown'})
        self.assertFalse(self.saved)
    def test_missing_factory_lock_or_wrong_incarnation_holds(self):
        self.store.lock_path.unlink()
        with self.assertRaises(RuntimeError):
            with self.store.transaction():pass
        with self.assertRaises(ValueError):module.ControllerStore(self.base/'arbitrary',None,None,None)
    def test_exception_unlocks_only_acquired_lock(self):
        with self.assertRaises(ValueError):
            with self.store.transaction():raise ValueError('fixture')
        self.assertEqual(self.events,[1,2])
    def test_concurrent_journal_lock_contexts_are_thread_local(self):
        lock=module.JournalLock(self.store);entered=threading.Event();release=threading.Event();errors=[]
        def first():
            try:
                with lock:entered.set();release.wait(1)
            except Exception as e:errors.append(e)
        def second():
            try:
                with lock:pass
            except Exception as e:errors.append(e)
        a=threading.Thread(target=first);a.start();self.assertTrue(entered.wait(1))
        b=threading.Thread(target=second);b.start();release.set();a.join(1);b.join(1)
        self.assertFalse(errors);self.assertEqual(self.events,[1,2,1,2])

if __name__=='__main__':unittest.main()
