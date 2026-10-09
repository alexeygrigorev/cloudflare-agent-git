import hashlib,json,pathlib,tempfile,unittest
import opencode_shell_runtime as shell

class PlanTests(unittest.TestCase):
    def test_missing_execution_binding_denies(self):
        with self.assertRaises(RuntimeError):shell.selected_plan({},lambda p:{},lambda p:None)
    def test_acyclic_fixed_plan_checks_all_actual_source(self):
        original=shell.HERE
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp);shell.HERE=root
            try:
                (root/'owned.py').write_text('owned source')
                (root/'source-pins.json').write_text(json.dumps(dict(entries=[dict(path='owned.py',sha256=shell.digest(root/'owned.py'))])))
                source=shell.digest(root/'source-pins.json')
                (root/'cold-plan.private.json').write_text(json.dumps(dict(controller_source_manifest_sha256=source)))
                profile=dict(execution_plan_sha256=shell.digest(root/'cold-plan.private.json'),controller_source_manifest_sha256=source)
                plan,guard=shell.selected_plan(profile,lambda p:json.loads(p.read_bytes()),lambda p:None)
                self.assertEqual(plan['controller_source_manifest_sha256'],source)
                (root/'owned.py').write_text('changed')
                with self.assertRaises(RuntimeError):guard()
            finally:shell.HERE=original
    def test_nonwindows_constructor_never_creates_runtime(self):
        # This portable test deliberately calls only the pre-effect host guard.
        old=shell.os.name;shell.os.name='posix'
        try:
            with self.assertRaises(RuntimeError):shell.build_runtime({}, {}, {})
        finally:shell.os.name=old

if __name__=='__main__':unittest.main()
