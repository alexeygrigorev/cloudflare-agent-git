import sys
if not sys.flags.isolated or not sys.flags.no_site:raise SystemExit('isolation required')
import unittest,pathlib,tempfile,sqlite3,json,hashlib,importlib.util
spec=importlib.util.spec_from_file_location('postcondition',pathlib.Path(__file__).with_name('recovery_postcondition.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class RecoveryPostconditionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.path=pathlib.Path(self.tmp.name)/'db'
        self.owner=dict(project='p',role='root',actor='old',generation='g',epoch=7)
        baseline=json.dumps(dict(self.owner,digest='immutable'))
        self.guard=dict(nonce='server-nonce',baseline_json_sha256=hashlib.sha256(baseline.encode()).hexdigest(),owner=self.owner)
        with sqlite3.connect(self.path) as db:
            db.execute('CREATE TABLE roles(project,role,holder,generation,epoch,expires,activation_due,suspect_since,check_due)')
            db.execute('INSERT INTO roles VALUES(?,?,?,?,?,?,?,?,?)',('p','root','old','g',7,11,12,None,900))
            db.execute('INSERT INTO roles VALUES(?,?,?,?,?,?,?,?,?)',('other','head','peer','z',3,88,99,None,999))
            for t in ('agents','candidates','activation_receipts'):db.execute('CREATE TABLE '+t+'(id,value)');db.execute('INSERT INTO '+t+' VALUES(?,?)',('preserved','value'))
            db.execute('CREATE TABLE host_recovery_attempts(nonce,baseline_json,phase,drain_receipt_ref,kernel_proof_ref)')
            db.execute('INSERT INTO host_recovery_attempts VALUES(?,?,?,?,?)',('server-nonce',baseline,'challenged',None,None))
        self.before=m.capture(self.path)
    def execute(self,sql,args=()):
        with sqlite3.connect(self.path) as db:db.execute(sql,args)
    def drain(self):
        self.execute('UPDATE roles SET holder=NULL,generation=NULL,epoch=8,expires=0,activation_due=0,suspect_since=NULL WHERE project=?',('p',))
        self.execute('UPDATE host_recovery_attempts SET phase=?,drain_receipt_ref=?,kernel_proof_ref=?',('drained','a'*64,'a'*64))
    def test_unchanged_challenged(self):self.assertEqual(m.preserved_or_drain(self.path,self.before,self.guard),'unchanged')
    def test_exact_current_nonce_drain(self):
        self.drain();self.assertEqual(m.preserved_or_drain(self.path,self.before,self.guard),'expected-recovery-drain')
        for phase in ('factory-pending','factory-receipted','enrollment-pending'):
            self.execute('UPDATE host_recovery_attempts SET phase=?',(phase,));self.assertEqual(m.preserved_or_drain(self.path,self.before,self.guard),'expected-recovery-drain')
    def test_missing_or_foreign_nonce(self):
        for key,value in (('nonce','foreign'),('baseline_json_sha256','b'*64),('owner',dict(self.owner,actor='foreign'))):
            with self.subTest(key=key),self.assertRaises(RuntimeError):m.preserved_or_drain(self.path,self.before,dict(self.guard,**{key:value}))
    def test_unrelated_tables_preserved(self):
        self.drain()
        for table in ('agents','candidates','activation_receipts'):
            self.execute('UPDATE '+table+' SET value=?',('changed',))
            with self.subTest(table=table),self.assertRaises(RuntimeError):m.preserved_or_drain(self.path,self.before,self.guard)
            self.execute('UPDATE '+table+' SET value=?',('value',))
    def test_unrelated_role_and_deadline_denied(self):
        self.drain()
        self.execute('UPDATE roles SET expires=111 WHERE project=?',('other',))
        with self.assertRaises(RuntimeError):m.preserved_or_drain(self.path,self.before,self.guard)
        self.execute('UPDATE roles SET expires=88 WHERE project=?',('other',));self.execute('UPDATE roles SET check_due=901 WHERE project=?',('p',))
        with self.assertRaises(RuntimeError):m.preserved_or_drain(self.path,self.before,self.guard)
    def test_unexpected_new_owner_denied(self):
        self.drain();self.execute('UPDATE roles SET holder=?,generation=?,epoch=9 WHERE project=?',('new','newg','p'))
        with self.assertRaises(RuntimeError):m.preserved_or_drain(self.path,self.before,self.guard)
    def test_unknown_phase_or_missing_authenticated_receipt_denied(self):
        self.drain()
        for phase,ref,kernel in (('unknown','a'*64,'a'*64),('drained',None,None),('drained','a'*64,'b'*64),('held-completed','a'*64,'a'*64)):
            self.execute('UPDATE host_recovery_attempts SET phase=?,drain_receipt_ref=?,kernel_proof_ref=?',(phase,ref,kernel))
            with self.subTest(phase=phase,ref=ref),self.assertRaises(RuntimeError):m.preserved_or_drain(self.path,self.before,self.guard)
    def test_no_cas_with_advanced_attempt_denied(self):
        self.execute('UPDATE host_recovery_attempts SET phase=?',('drained',))
        with self.assertRaises(RuntimeError):m.preserved_or_drain(self.path,self.before,self.guard)
    def test_boolean_epoch_unknown_guard_denied(self):
        for guard in ({},dict(self.guard,owner=dict(self.owner,epoch=True))):
            with self.assertRaises(RuntimeError):m.preserved_or_drain(self.path,self.before,guard)
    def test_already_foreign_role_before_install_denied(self):
        self.execute('UPDATE roles SET holder=? WHERE project=?',('foreign','p'))
        with self.assertRaises(RuntimeError):m.preserved_or_drain(self.path,m.capture(self.path),self.guard)
if __name__=='__main__':unittest.main()
