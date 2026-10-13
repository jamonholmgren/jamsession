"""Provider cleanup must stay bounded even when the native process cannot exit."""

import contextlib
import importlib.util
import io
from pathlib import Path
import subprocess
import unittest
from unittest.mock import Mock, call


spec = importlib.util.spec_from_file_location(
    "usage_reader", Path(__file__).resolve().parents[1] / "usage/jamsession_tui_usage.py"
)
reader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)


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
