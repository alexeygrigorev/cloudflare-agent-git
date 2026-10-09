"""Source-bound retained-old versus new API ACK routing; no native Bus effects."""
import ast,hashlib,json,pathlib,tempfile,unittest
from unittest.mock import MagicMock,patch
import win35_root_host as host
import win35_root_control as control
class ProfileIsolation(unittest.TestCase):
    def test_api_fixed_profile_is_distinct_from_retained_source7(self):
        old=pathlib.Path(__file__).parent.parent/'next7/win35_root_control.py'
        tree=ast.parse(old.read_text())
        assignment=next(n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='PROFILE' for t in n.targets))
        namespace={'pathlib':pathlib};exec(compile(ast.Module(body=[assignment],type_ignores=[]),'retained-control7','exec'),namespace)
        self.assertNotEqual(control.PROFILE,namespace['PROFILE'])
        self.assertEqual(control.PROFILE,host.PROFILE)
        self.assertEqual(control.PROFILE.name,'api-runtime.private.json')
    def test_late_old_ack_never_reads_or_sends_as_new_owner(self):
        with tempfile.TemporaryDirectory() as directory:
            base=pathlib.Path(directory);old_dir=base/'old';new_dir=base/'api';old_dir.mkdir();new_dir.mkdir()
            old_owner=dict(project='fixture',role='root',actor='retained-old',generation='old-generation',epoch=2)
            new_owner=dict(project='fixture',role='root',actor='new-api',generation='new-generation',epoch=3)
            old_profile=dict(actor=old_owner['actor'],generation=old_owner['generation'],state_dir=str(old_dir),credential={'token':'old-fixture'})
            new_profile=dict(actor=new_owner['actor'],generation=new_owner['generation'],state_dir=str(new_dir),credential={'token':'new-fixture'})
            new_profile.update(aplexer_exe='pinned-fixture',aplexer_sha256='fixture-hash',root_tag='fixture-api-tag',workspace='fixture-workspace')
            for target,owner,cid in ((old_dir,old_owner,'old-cid'),(new_dir,new_owner,'new-cid')):
                (target/'root-runtime.json').write_text(json.dumps(dict(thread_owner=owner,conversation_id=cid)))
            original=pathlib.Path(__file__).parent.parent/'next7/win35_root_control.py'
            old_tree=ast.parse(original.read_text());new_tree=ast.parse(pathlib.Path(control.__file__).read_text())
            calls=[]
            def request(profile,body):
                calls.append((profile['credential']['token'],body['actor'],body['model_thread_id']))
                if profile is old_profile:raise RuntimeError('fixture retired old binding fenced')
                return {'result':{'message_id':'fixture-native-receipt'}}
            for tree,label,profile,expected in ((old_tree,'retained',old_profile,old_owner),(new_tree,'api',new_profile,new_owner)):
                scope=dict(PROFILE=label,load_private_profile=lambda p:old_profile if p=='retained' else new_profile,json=json,pathlib=pathlib,hashlib=hashlib,request=request,current_process_binding=lambda:{'pid':1,'creation_filetime':2},save=MagicMock(),recorded_api_custody=lambda *a:True,recorded_process_state=MagicMock(),pin=lambda *a:'pinned-fixture',subprocess=MagicMock())
                scope['subprocess'].check_output.return_value=json.dumps(dict(id='new-api',tag='fixture-api-tag',workspace='fixture-workspace'))
                func=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='model_ack')
                exec(compile(ast.Module(body=[func],type_ignores=[]),label,'exec'),scope)
                if label=='retained':
                    with self.assertRaises(RuntimeError):scope['model_ack']()
                else:scope['model_ack']()
            self.assertEqual(calls,[('old-fixture','retained-old','old-cid'),('new-fixture','new-api','new-cid')])
    def test_wrong_native_caller_or_unknown_live_custody_denies_before_bus(self):
        with tempfile.TemporaryDirectory() as directory:
            owner=dict(project='fixture',role='root',actor='new-api',generation='new-generation',epoch=3)
            (pathlib.Path(directory)/'root-runtime.json').write_text(json.dumps(dict(thread_owner=owner,conversation_id='new-cid')))
            profile=dict(actor='new-api',generation='new-generation',state_dir=directory,aplexer_exe='pinned-fixture',aplexer_sha256='fixture-hash',root_tag='fixture-api-tag',workspace='fixture-workspace')
            for known in (False,True):
                with patch.object(control,'load_private_profile',return_value=profile),patch.object(control,'recorded_api_custody',return_value=known),patch.object(control,'pin',return_value='fixture'),patch.object(control.subprocess,'check_output',return_value=json.dumps(dict(id='retained-old',tag='fixture-api-tag',workspace='fixture-workspace'))),patch.object(control,'request') as send:
                    with self.assertRaises(RuntimeError):control.model_ack()
                    send.assert_not_called()
if __name__=='__main__':unittest.main()
