"""Regression over captured installed definitions and actual offline tool output.

This verifies bounded no-upstream native negative evidence; it does not prove
paid child execution or operating root check completion.
"""
import json,pathlib,re,unittest
HERE=pathlib.Path(__file__).parent

class EffectivePolicy(unittest.TestCase):
    def test_captured_native_surface_not_top_level_tool_names_only(self):
        data=json.loads((HERE/'native-managed-surface-definitions.private.json').read_text())
        features=data['effective_features']
        for name in ('multi_agent','unified_exec','shell_tool','goals','view_image'):
            self.assertIs(features[name],False)
        definition=next(d for d in data['native_function_definitions'] if d['name']=='exec')
        declared=re.findall(r'^### `([^`]+)`',definition['description'],re.M)
        self.assertIn('root_spawn_check',declared)
        self.assertIn('apply_patch',declared)  # Advertised; sandbox must deny it.
        for name in ('exec_command','write_stdin','spawn_agent','create_goal','view_image'):
            self.assertNotIn(name,declared)
        texts=[b.get('text','') for item in data['tool_result_items'] for b in item['output']]
        self.assertEqual(sum('writing is blocked by read-only sandbox' in s for s in texts),3)
        for name in ('exec_command','write_stdin','spawn_agent','create_goal','view_image'):
            self.assertTrue(any('tools.'+name+' is not a function' in s for s in texts))

    def test_actual_sdk_custom_request_and_all_owned_targets_unchanged(self):
        r=json.loads((HERE/'offline-managed-surface-result.private.json').read_text())
        self.assertIs(r['provider_spend'],False);self.assertIs(r['upstream_connected'],False)
        self.assertIs(r['existing_role_or_profile_changed'],False)
        self.assertEqual(r['write_targets_unchanged'],[True,True,True])
        self.assertIs(r['owned_probe_job_drained'],True)
        calls=r['managed_tool_requests'];self.assertEqual(len(calls),1)
        self.assertEqual(calls[0]['method'],'item/tool/call')
        p=calls[0]['params'];self.assertEqual(p['tool'],'root_spawn_check')
        self.assertEqual(p['arguments'],{})
        for field in ('threadId','turnId','callId'):self.assertTrue(p[field])

if __name__=='__main__':unittest.main()
