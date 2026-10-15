"""Exercise the public CLI's launch boundary without starting model turns."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class LaunchSettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="jamsession-codex-settings-")
        self.root = Path(self.temp.name)
        self.log = self.root / "calls.jsonl"
        self.config = self.root / "jamsession.conf"
        self.config.write_text("")
        binary = self.root / "codex"
        binary.write_text("#!" + sys.executable + '''
import json, os, sys
from pathlib import Path
args = sys.argv[1:]
with open(os.environ['LAUNCH_LOG'], 'a') as out:
    out.write(json.dumps(args) + '\\n')
if os.environ.get('NATIVE_CONFIG_ERROR'):
    print('Error: unsupported permission configuration', file=sys.stderr)
    sys.exit(17)
Path(args[args.index('-o') + 1]).write_text('DONE')
print(json.dumps({'type':'thread.started', 'thread_id':'owned-session'}))
''')
        binary.chmod(0o755)
        self.env = {key: value for key, value in os.environ.items()
                    if not key.startswith('JAMSESSION_') and key not in ('CODEX_THREAD_ID', 'CODEX_HOME')}
        self.env.update(HOME=str(self.root), CODEX_HOME=str(self.root / '.codex'),
                        JAMSESSION_CONFIG=str(self.config), JAMSESSION_CODEX_BIN=str(binary),
                        JAMSESSION_CWD=str(self.root), LAUNCH_LOG=str(self.log))
        (self.root / '.codex').mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def launch(self, session='new', access='edit'):
        return subprocess.run([str(ROOT / 'jamsession'), 'run', 'codex', session,
                               'gpt-6.1-sol', 'low', access, 'test prompt'],
                              env=self.env, text=True, capture_output=True, timeout=10)

    def args(self):
        return json.loads(self.log.read_text().splitlines()[-1])

    def test_fresh_and_native_resume_do_not_replace_configured_edit_policy(self):
        for sandbox in ('danger-full-access', 'workspace-write'):
            (self.root / '.codex/config.toml').write_text(
                f'sandbox_mode = "{sandbox}"\napproval_policy = "never"\n')
            for session in ('new', 'owned-session'):
                with self.subTest(sandbox=sandbox, session=session):
                    result = self.launch(session)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    args = self.args()
                    self.assertNotIn('-s', args)
                    self.assertFalse(any('sandbox_mode=' in a or 'approval_policy=' in a for a in args))
                    self.assertNotIn('--dangerously-bypass-approvals-and-sandbox', args)
                    self.assertIn('model_reasoning_effort=low', args)

    def test_profile_and_array_overrides_reach_fresh_and_resume_native_loader(self):
        (self.root / '.codex/automation.config.toml').write_text('sandbox_mode="danger-full-access"\n')
        self.config.write_text('JAMSESSION_CODEX_PROFILE=automation\n'
                               'JAMSESSION_CODEX_CONFIG=(\'sandbox_mode="danger-full-access"\' \'approval_policy="never"\')\n')
        for session in ('new', 'owned-session'):
            result = self.launch(session)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(self.args()[:6], ['--profile', 'automation', '-c',
                'sandbox_mode="danger-full-access"', '-c', 'approval_policy="never"'])

    def test_explicit_variables_follow_array_overrides(self):
        self.config.write_text('JAMSESSION_CODEX_CONFIG=(\'sandbox_mode="danger-full-access"\' \'approval_policy="on-request"\')\n')
        self.env.update(JAMSESSION_CODEX_SANDBOX='workspace-write')
        self.assertEqual(self.launch().returncode, 0)
        args = self.args()
        self.assertLess(args.index('sandbox_mode="danger-full-access"'), args.index('sandbox_mode="workspace-write"'))
        self.assertIn('approval_policy="on-request"', args)

    def test_read_always_wins_over_full_access_and_legacy_off(self):
        self.config.write_text('JAMSESSION_CODEX_CONFIG=(\'default_permissions=":danger-full-access"\')\n')
        for sandbox in ('off', 'danger-full-access'):
            self.env['JAMSESSION_CODEX_SANDBOX'] = sandbox
            for session in ('new', 'owned-session'):
                result = self.launch(session, 'read')
                self.assertEqual(result.returncode, 0, result.stderr)
                args = self.args()
                self.assertIn('default_permissions=":read-only"', args)
                self.assertIn('approval_policy="never"', args)
                if session == 'new':
                    self.assertEqual(args[args.index('-s') + 1], 'read-only')
                else:
                    self.assertIn('sandbox_mode="read-only"', args)
                self.assertNotIn('--dangerously-bypass-approvals-and-sandbox', args)

    def test_legacy_off_is_explicit_edit_config_not_a_bypass_flag(self):
        self.env['JAMSESSION_CODEX_SANDBOX'] = 'off'
        self.assertEqual(self.launch().returncode, 0)
        self.assertIn('sandbox_mode="danger-full-access"', self.args())
        self.assertIn('approval_policy="never"', self.args())
        self.assertNotIn('--dangerously-bypass-approvals-and-sandbox', self.args())

    def test_unknown_sandbox_setting_fails_before_launch(self):
        for name in ('JAMSESSION_CODEX_SANDBOX',):
            self.env[name] = 'unsupported'
            result = self.launch()
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertFalse(self.log.exists())
            self.env.pop(name)

    def test_missing_profile_is_not_silently_replaced_by_native_defaults(self):
        self.env['JAMSESSION_CODEX_PROFILE'] = 'missing'
        result = self.launch()
        self.assertEqual(result.returncode, 2)
        self.assertIn('refusing native default fallback', result.stderr)
        self.assertFalse(self.log.exists())

    def test_config_array_rejects_scalar_and_non_assignments(self):
        for config in ('JAMSESSION_CODEX_CONFIG="--dangerously-bypass-approvals-and-sandbox"',
                       'JAMSESSION_CODEX_CONFIG=("not-an-assignment")'):
            self.config.write_text(config + '\n')
            self.assertEqual(self.launch().returncode, 2)
            self.assertFalse(self.log.exists())

    def test_native_configuration_denial_is_final_for_new_and_resume(self):
        self.env['NATIVE_CONFIG_ERROR'] = '1'
        for session in ('new', 'owned-session'):
            self.log.unlink(missing_ok=True)
            result = self.launch(session)
            self.assertEqual(result.returncode, 17)
            self.assertIn('unsupported permission configuration', result.stderr)
            self.assertEqual(len(self.log.read_text().splitlines()), 1)


if __name__ == '__main__':
    unittest.main()
