import unittest,tempfile,pathlib,sqlite3,os,json,types
from unittest.mock import patch
import install90 as m
class Tests(unittest.TestCase):
 def test_existing_any_table_row_change_denied(self):
  with tempfile.TemporaryDirectory() as d:
   p=pathlib.Path(d)/'db.sqlite'
   with sqlite3.connect(p) as db:db.execute('CREATE TABLE activation_receipts(id TEXT, receipt BLOB)');db.execute('INSERT INTO activation_receipts VALUES(?,?)',('owned',b'private'))
   before=m.snapshot(p)
   with sqlite3.connect(p) as db:db.execute('UPDATE activation_receipts SET receipt=?',(b'changed',))
   with self.assertRaisesRegex(RuntimeError,'custody changed'):m.preserve_rows(before,m.snapshot(p))
 def test_source_schema_initialization_only_empty_additions(self):
  with tempfile.TemporaryDirectory() as d:
   p=pathlib.Path(d)/'db.sqlite'
   with sqlite3.connect(p) as db:db.execute('CREATE TABLE roles(id INTEGER)');db.execute('INSERT INTO roles VALUES(11)')
   before=m.snapshot(p)
   with sqlite3.connect(p) as db:db.execute('CREATE TABLE root_response_cadence(id INTEGER)')
   m.preserve_rows(before,m.snapshot(p))
   with sqlite3.connect(p) as db:db.execute('INSERT INTO root_response_cadence VALUES(1)')
   with self.assertRaisesRegex(RuntimeError,'unexpected new table rows'):m.preserve_rows(before,m.snapshot(p))
 def test_schema_change_without_row_change_denied(self):
  with tempfile.TemporaryDirectory() as d:
   p=pathlib.Path(d)/'db.sqlite'
   with sqlite3.connect(p) as db:db.execute('CREATE TABLE roles(id INTEGER)')
   before=m.snapshot(p)
   with sqlite3.connect(p) as db:db.execute('ALTER TABLE roles ADD COLUMN foreign_field TEXT')
   with self.assertRaises(RuntimeError):m.preserve_rows(before,m.snapshot(p))
 def test_restart_pending_never_authorizes_replay(self):
  with self.assertRaisesRegex(RuntimeError,'never replay'):m.reconcile_stage({'phase':'restart-pending','plan_sha256':'owned'},'owned')
  self.assertEqual(m.reconcile_stage({'phase':'install-pending','plan_sha256':'owned'},'owned'),'install-pending')
  with self.assertRaises(RuntimeError):m.reconcile_stage({'phase':'completed','plan_sha256':'foreign'},'owned')
 def test_only_hostplan_profile_change_permitted(self):
  old={'authority_source':'owned','authority_sha256':'a','hold_policy':{'fixed':True},'host_recovery':{'old':True},'tls':{'kept':True}}
  new=dict(old,host_recovery={'new':True});m.profile_compare(old,new)
  for key in ('authority_source','authority_sha256','hold_policy','tls'):
   changed=dict(new);changed[key]='foreign'
   with self.assertRaises(RuntimeError):m.profile_compare(old,changed)

 def test_write_journal_reconciles_exact_once_and_preserves_backup(self):
  with tempfile.TemporaryDirectory() as d:
   original=m.HERE;m.HERE=pathlib.Path(d)
   try:
    target=m.HERE/'target';target.write_bytes(b'old');os.chmod(target,0o600)
    m.backup_and_write(target,b'new',m.hash_bytes(b'old'),m.hash_bytes(b'new'),'target')
    self.assertEqual((m.HERE/'target.before.private').read_bytes(),b'old')
    m.backup_and_write(target,b'new',m.hash_bytes(b'old'),m.hash_bytes(b'new'),'target')
    target.write_bytes(b'foreign')
    with self.assertRaises(RuntimeError):m.backup_and_write(target,b'new',m.hash_bytes(b'old'),m.hash_bytes(b'new'),'target')
   finally:m.HERE=original
 def test_symlink_target_and_broad_source_denied(self):
  with tempfile.TemporaryDirectory() as d:
   p=pathlib.Path(d)/'source';p.write_bytes(b'owned');os.chmod(p,0o666)
   with self.assertRaises(RuntimeError):m.regular(p)
   os.chmod(p,0o600);q=pathlib.Path(d)/'alias';q.symlink_to(p)
   with self.assertRaises(RuntimeError):m.sha(q)
 def test_group_writable_source_and_parent_denied(self):
  with tempfile.TemporaryDirectory() as d:
   root=pathlib.Path(d);p=root/'source';p.write_bytes(b'owned');os.chmod(p,0o660)
   with self.assertRaises(RuntimeError):m.regular(p)
   os.chmod(p,0o600);os.chmod(root,0o770)
   with self.assertRaises(RuntimeError):m.atomic(p,b'changed')
   os.chmod(root,0o700);self.assertEqual(p.read_bytes(),b'owned')
 def test_true_flag_without_exact_reviewed_receipt_denied(self):
  with tempfile.TemporaryDirectory() as d:
   old=m.PACKET;m.PACKET=pathlib.Path(d)
   try:
    plan={'execution_authorized':True,'authorization':'same-one8801-composed90-source-profile-adoption','installer_source_sha256':'source'}
    with self.assertRaises((RuntimeError,FileNotFoundError)):m.accepted_execution(plan,'source')
    reviewed=dict(plan,execution_authorized=False)
    receipt={'verdict':'ACCEPT_SOURCE_PLAN','installer_source_sha256':'source','reviewed_plan_sha256':m.hash_bytes(json.dumps(reviewed,sort_keys=True).encode()),'review_report_sha256':'report','genuine_acceptance_message_id':'real-message'}
    m.save(m.PACKET/'installer-acceptance.private.json',receipt)
    plan['acceptance_receipt_sha256']=m.sha(m.PACKET/'installer-acceptance.private.json')
    m.accepted_execution(plan,'source')
    with self.assertRaises(RuntimeError):m.accepted_execution(dict(plan,authorization='changed'),'source')
    with self.assertRaises(RuntimeError):m.accepted_execution(plan,'foreign-source')
   finally:m.PACKET=old
 def test_exact_preserved_dependency_foreign_group_writer_denied(self):
  with tempfile.TemporaryDirectory() as d:
   p=pathlib.Path(d)/'source';p.write_bytes(b'existing');os.chmod(p,0o664)
   key='bus_source';pin=m.hash_bytes(p.read_bytes());cfg={key:str(p),'bus_sha256':pin}
   owner=types.SimpleNamespace(pw_uid=1000,pw_gid=1000)
   foreign=types.SimpleNamespace(pw_uid=1001,pw_gid=1000)
   realstat=p.stat();fake=types.SimpleNamespace(st_mode=realstat.st_mode,st_uid=1000,st_gid=1000)
   with patch.dict(m.PRESERVED_DEPENDENCIES,{key:(str(p),pin)}),patch.object(m.os,'getuid',return_value=1000),patch.object(m.grp,'getgrgid',return_value=types.SimpleNamespace(gr_mem=[])),patch.object(m.pwd,'getpwall',return_value=[owner]),patch.object(pathlib.Path,'stat',return_value=fake):
    m.preserved_dependency(cfg,key)
    with patch.object(m.pwd,'getpwall',return_value=[owner,foreign]):
     with self.assertRaisesRegex(RuntimeError,'foreign'):m.preserved_dependency(cfg,key)
    with self.assertRaisesRegex(RuntimeError,'binding'):m.preserved_dependency(dict(cfg,bus_sha256='foreign'),key)
 def test_exact_alias_parent_single_writer_only(self):
  with tempfile.TemporaryDirectory() as d:
   root=pathlib.Path(d);p=root/'scripts/recovery';p.mkdir(parents=True);os.chmod(p,0o775)
   owner=types.SimpleNamespace(pw_uid=1000,pw_gid=1000);foreign=types.SimpleNamespace(pw_uid=1001,pw_gid=1000)
   with patch.object(m,'ROOT',root),patch.object(m.os,'getuid',return_value=1000),patch.object(m.pwd,'getpwall',return_value=[owner]),patch.object(m.grp,'getgrgid',return_value=types.SimpleNamespace(gr_mem=[])):
    m.parent_custody(p)
    with patch.object(m.pwd,'getpwall',return_value=[owner,foreign]):
     with self.assertRaisesRegex(RuntimeError,'foreign'):m.parent_custody(p)
    other=root/'foreign';other.mkdir();os.chmod(other,0o775)
    with self.assertRaises(RuntimeError):m.parent_custody(other)
    os.chmod(p,0o777)
    with self.assertRaises(RuntimeError):m.parent_custody(p)
 def test_existing_intent_refused_before_fresh_baseline(self):
  with tempfile.TemporaryDirectory() as d:
   root=pathlib.Path(d);(root/'install.lock').write_text('');os.chmod(root/'install.lock',0o600)
   (root/'install-progress.private.json').write_text('{}')
   plan={'authorization':'same-one8801-profile92-path-budget-correction','installer_source_sha256':m.sha(pathlib.Path(m.__file__))}
   p=root/'install-plan.private.json';p.write_text(json.dumps(plan));os.chmod(p,0o600);pin=m.sha(p)
   with patch.object(m,'AUTH',root),patch.object(m,'HERE',root),patch.object(m,'PACKET',root),patch.object(m.sys,'argv',['fixed','Validate',pin]),patch.object(m.sys,'flags',types.SimpleNamespace(isolated=True,no_site=True)),patch.object(m,'verify_baseline',side_effect=AssertionError('fresh baseline forbidden')):
    with self.assertRaisesRegex(RuntimeError,'reconcile only'):m.main()
 def test_real_source_clock_monotonic_only_and_boot_other_metadata_denied(self):
  with tempfile.TemporaryDirectory() as d:
   p=pathlib.Path(d)/'db.sqlite';boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
   with sqlite3.connect(p) as db:
    db.execute('CREATE TABLE authority_meta(key TEXT PRIMARY KEY,value TEXT NOT NULL)')
    db.executemany('INSERT INTO authority_meta VALUES(?,?)',[('boot',boot),('last_clock','100')])
   before=m.snapshot(p)
   with sqlite3.connect(p) as db:db.execute("UPDATE authority_meta SET value='200' WHERE key='last_clock'")
   after=m.snapshot(p);m.preserve_rows(before,after)
   with self.assertRaises(RuntimeError):m.preserve_rows(after,before)
   with sqlite3.connect(p) as db:db.execute("UPDATE authority_meta SET value='NaN' WHERE key='last_clock'")
   with self.assertRaises(RuntimeError):m.snapshot(p)
   with sqlite3.connect(p) as db:db.execute("UPDATE authority_meta SET value='100' WHERE key='last_clock'");db.execute("UPDATE authority_meta SET value='foreign' WHERE key='boot'")
   with self.assertRaises(RuntimeError):m.snapshot(p)
   with sqlite3.connect(p) as db:db.execute("UPDATE authority_meta SET value=? WHERE key='boot'",(boot,));db.execute("INSERT INTO authority_meta VALUES('foreign','value')")
   with self.assertRaises(RuntimeError):m.snapshot(p)
 def test_parent_custody_change_during_target_replace_holds_write_pending(self):
  with tempfile.TemporaryDirectory() as d:
   root=pathlib.Path(d);target=root/'target';target.write_bytes(b'old');os.chmod(target,0o600)
   old=m.HERE;m.HERE=root;real_replace=os.replace
   def changed_parent(source,destination):
    real_replace(source,destination)
    if pathlib.Path(destination)==target:os.chmod(root,0o770)
   try:
    with patch.object(m.os,'replace',side_effect=changed_parent):
     with self.assertRaisesRegex(RuntimeError,'owned fixed directory'):m.backup_and_write(target,b'new',m.hash_bytes(b'old'),m.hash_bytes(b'new'),'target')
    self.assertEqual(json.loads((root/'target.write.private.json').read_bytes())['phase'],'write-pending')
    self.assertEqual((root/'target.before.private').read_bytes(),b'old')
    self.assertEqual(target.read_bytes(),b'new')
   finally:os.chmod(root,0o700);m.HERE=old
if __name__=='__main__':unittest.main(verbosity=2)
