import unittest,sqlite3,tempfile,pathlib,json
from opencode_usage import read_usage,DB_REL
class OpenCodeUsageTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.temp.name);p=self.root/DB_REL;p.parent.mkdir(parents=True)
  self.c=sqlite3.connect(p);self.c.executescript('CREATE TABLE session(id TEXT PRIMARY KEY,parent_id TEXT,directory TEXT);CREATE TABLE message(id TEXT PRIMARY KEY,session_id TEXT,time_created INTEGER,data TEXT);')
  self.c.execute('INSERT INTO session VALUES(?,?,?)',('ses_a',None,str(self.root)));self.c.commit()
  self.assign=[{'conversation_id':'ses_a','tag':'muse','team_id':'review'}]
 def tearDown(self):self.c.close();self.temp.cleanup()
 def msg(self,id='m1',sid='ses_a',created=20,total=115,completed=21,**kw):
  data={'role':'assistant','providerID':'go','modelID':'muse','time':{'completed':completed},'tokens':{'total':total,'input':10,'output':5,'reasoning':5,'cache':{'read':100,'write':0}},'cost':0};data.update(kw)
  self.c.execute('INSERT OR REPLACE INTO message VALUES(?,?,?,?)',(id,sid,created,json.dumps(data)));self.c.commit()
 def read(self,**kw):return read_usage(self.root,self.assign,15,**kw)
 def test_raw_total_never_recomputed_with_reasoning(self):
  self.msg();r=self.read()['sessions'][0]['interval'];self.assertEqual(r['total_tokens'],115);self.assertEqual(r['reasoning_output_tokens'],5);self.assertEqual(r['output_tokens'],5);self.assertEqual(r['reported_cost'],0)
 def test_pending_stays_unknown_then_update_not_duplicate(self):
  self.msg(total=None,completed=None);r=self.read()['sessions'][0]['interval'];self.assertIsNone(r['total_tokens']);self.assertEqual(r['pending_or_missing_records'],1)
  self.msg();self.assertEqual(self.read()['sessions'][0]['interval']['total_tokens'],115);self.assertEqual(self.read()['unique_assistant_records'],1)
 def test_interval_vs_cumulative(self):
  self.msg(created=10);self.msg('m2');r=self.read()['sessions'][0];self.assertEqual(r['cumulative']['total_tokens'],230);self.assertEqual(r['interval']['total_tokens'],115)
 def test_resumed_identity_dedup(self):
  self.msg();self.assign*=2;r=self.read();self.assertEqual(len(r['sessions']),1);self.assertEqual(r['by_team']['review']['total_tokens'],115)
 def test_child_counted_separately_not_in_head(self):
  self.msg();self.c.execute('INSERT INTO session VALUES(?,?,?)',('ses_child','ses_a',str(self.root)));self.c.commit();self.msg('m2','ses_child');r=self.read();self.assertEqual(len(r['sessions']),2);self.assertEqual(r['by_model'][0]['interval']['total_tokens'],230);self.assertEqual(r['sessions'][0]['cumulative']['total_tokens'],115)
 def test_foreign_child_not_attributed(self):
  self.c.execute('INSERT INTO session VALUES(?,?,?)',('ses_foreign','ses_a','/elsewhere'));self.c.commit();self.msg('m2','ses_foreign');self.assertEqual(self.read()['unique_assistant_records'],0)
 def test_conflicting_team_not_duplicated(self):
  self.msg();self.assign.append({'conversation_id':'ses_a','tag':'other','team_id':'another'});r=self.read();self.assertEqual(r['by_team']['unassigned-conflicting-ownership']['total_tokens'],115)
 def test_bounds_fail_closed(self):
  self.msg();self.assertEqual(self.read(max_messages=0)['status'],'unavailable-or-bound-exceeded');self.assertEqual(self.read(max_sessions=0)['status'],'unavailable-or-bound-exceeded')
 def test_no_prompt_or_secret_projected(self):
  self.msg(prompt='SECRET',credentials='SECRET');self.assertNotIn('SECRET',json.dumps(self.read()))
 def test_missing_field_partial_and_invalid_number_unknown(self):
  self.msg(tokens={'total':115,'input':-1});r=self.read()['sessions'][0]['interval'];self.assertIsNone(r['input_tokens']);self.assertEqual(r['coverage'],'partial');self.assertEqual(r['total_tokens'],115)
 def test_missing_db_unknown_and_no_creation(self):
  p=self.root/DB_REL;self.c.close();p.unlink();r=self.read();self.assertEqual(r['status'],'unknown');self.assertFalse(p.exists())
 def test_read_only_keeps_source(self):
  self.msg();p=self.root/DB_REL;before=p.read_bytes();self.read();self.assertEqual(before,p.read_bytes())
if __name__=='__main__':unittest.main()
