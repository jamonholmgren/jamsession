"""Provider cleanup must stay bounded even when the native process cannot exit."""

import contextlib
import importlib.util
import io
from pathlib import Path
import subprocess
import unittest
from unittest.mock import Mock, call, patch


spec = importlib.util.spec_from_file_location(
    "usage_reader", Path(__file__).resolve().parents[1] / "usage/jamsession_tui_usage.py"
)
reader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)


class AntigravityQuotaTests(unittest.TestCase):
    def test_native_quota_keeps_independent_buckets_and_literal_resets(self):
        text = 'Gemini Models\tWeekly Limit Remaining\t88%\t2026-10-20T06:59:20Z\nClaude and GPT models\tWeekly Limit Remaining\t100%\t2026-10-20T07:24:31Z\n'
        result = reader.antigravity_usage_text(text)
        self.assertIn('Model quota: Gemini Models\n12% used', result)
        self.assertIn('Model quota: Claude and GPT models\n0% used', result)
        self.assertIn('Resets: 2026-10-20T06:59:20Z', result)

    def test_invalid_quota_is_not_reported(self):
        for percent in ('101%', '-1%', 'nan%', 'unknown'):
            self.assertIsNone(reader.antigravity_usage_text(f'Gemini Models\tWeekly Limit Remaining\t{percent}\t2026-10-20T06:59:20Z'))

    def test_session_tokens_are_not_quota(self):
        self.assertIsNone(reader.antigravity_usage_text('Total tokens: 12345'))

    def test_invalid_reset_is_not_reported(self):
        self.assertIsNone(reader.antigravity_usage_text('Gemini Models\tWeekly Limit Remaining\t88%\tnot-a-date'))

    def test_headless_reader_uses_only_native_usage_in_disposable_cwd(self):
        process = Mock(returncode=0)
        process.communicate.return_value = ('Gemini Models\tWeekly Limit Remaining\t88%\t2026-10-20T06:59:20Z', '')
        with patch.object(reader.subprocess, 'Popen', return_value=process) as launch, patch.object(reader, 'stop_process') as stop, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(reader.antigravity_usage('agy', 5), 0)
        self.assertEqual(launch.call_args.args[0], ['agy', '-p', '/usage', '--print-timeout', '5s'])
        self.assertEqual(launch.call_args.kwargs['stdin'], subprocess.DEVNULL)
        self.assertIn('jamsession-agy-usage-', launch.call_args.kwargs['cwd'])
        process.communicate.assert_called_once_with(timeout=5)
        stop.assert_called_once_with(process)

    def test_headless_timeout_cleans_up_and_never_guesses_quota(self):
        process = Mock()
        process.communicate.side_effect = subprocess.TimeoutExpired('agy', 5)
        with patch.object(reader.subprocess, 'Popen', return_value=process), patch.object(reader, 'stop_process') as stop:
            self.assertEqual(reader.antigravity_usage('agy', 5), 1)
        stop.assert_called_once_with(process)


class ProcessCleanupTests(unittest.TestCase):
    def test_already_exited_process_is_not_signalled(self):
        process = Mock()
        process.poll.return_value = 0
        reader.stop_process(process)
        process.terminate.assert_not_called()
        process.kill.assert_not_called()

    def test_normal_exit_is_reaped_with_a_deadline(self):
        process = Mock()
        process.poll.return_value = None
        reader.stop_process(process)
        process.terminate.assert_called_once_with()
        process.wait.assert_called_once_with(timeout=2)
        process.kill.assert_not_called()

    def test_term_timeout_kills_and_reaps_with_a_deadline(self):
        process = Mock()
        process.poll.return_value = None
        process.wait.side_effect = [subprocess.TimeoutExpired("provider", 2), 0]
        reader.stop_process(process)
        process.kill.assert_called_once_with()
        self.assertEqual(process.wait.call_args_list, [call(timeout=2), call(timeout=2)])

    def test_unreapable_native_process_does_not_hold_the_reader(self):
        process = Mock()
        process.poll.return_value = None
        process.wait.side_effect = subprocess.TimeoutExpired("provider", 2)
        errors = io.StringIO()
        with contextlib.redirect_stderr(errors):
            reader.stop_process(process)
        process.terminate.assert_called_once_with()
        process.kill.assert_called_once_with()
        self.assertEqual(process.wait.call_args_list, [call(timeout=2), call(timeout=2)])
        self.assertIn("did not finish exiting", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
