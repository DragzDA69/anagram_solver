import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

import main
from cli import messages


class TerminalStream(io.StringIO):
    def isatty(self):
        return True


class MessageTests(unittest.TestCase):
    def test_redirected_messages_stay_plain(self):
        output, errors = io.StringIO(), io.StringIO()
        with patch.dict("os.environ", {}, clear=True), \
                redirect_stdout(output), redirect_stderr(errors):
            messages.info("Working...")
            messages.success("Done.")
            messages.warning("Try again.")
            with self.assertRaises(SystemExit) as result:
                messages.fail("Could not save.")
        self.assertEqual(output.getvalue(), "Working...\nDone.\n")
        self.assertEqual(errors.getvalue(), "Warning: Try again.\n")
        self.assertEqual(str(result.exception), "Error: Could not save.")

    def test_terminal_messages_use_severity_colors(self):
        output, errors = TerminalStream(), TerminalStream()
        with patch.dict("os.environ", {}, clear=True), \
                patch("cli.ansi._enable_windows_vt", return_value=True), \
                redirect_stdout(output), redirect_stderr(errors):
            messages.success("Done.")
            messages.warning("Try again.")
            messages.info("Working...")
            with self.assertRaises(SystemExit) as result:
                messages.fail("Could not save.")
        self.assertIn("\x1b[38;2;115;210;145mDone.\x1b[0m", output.getvalue())
        self.assertIn("\x1b[38;2;240;180;94mWarning: Try again.\x1b[0m", errors.getvalue())
        self.assertIn("\x1b[38;2;255;133;133mError: Could not save.", str(result.exception))
        self.assertTrue(output.getvalue().endswith("Working...\n"))

    def test_error_colors_follow_stderr_not_stdout(self):
        with patch.dict("os.environ", {}, clear=True), \
                patch("cli.ansi._enable_windows_vt", return_value=True), \
                redirect_stdout(io.StringIO()), redirect_stderr(TerminalStream()):
            self.assertIn("\x1b[", messages.error_text("Failed."))

    def test_no_color_disables_severity_colors(self):
        output = TerminalStream()
        with patch.dict("os.environ", {"NO_COLOR": "1"}, clear=True), \
                redirect_stdout(output):
            messages.success("Done.")
        self.assertEqual(output.getvalue(), "Done.\n")

    def test_parser_errors_are_red_and_exit_with_code_two(self):
        errors = TerminalStream()
        with patch.dict("os.environ", {}, clear=True), \
                patch("cli.ansi._enable_windows_vt", return_value=True), \
                redirect_stderr(errors):
            with self.assertRaises(SystemExit) as result:
                main.parse_args(["unknown"])
        self.assertEqual(result.exception.code, 2)
        self.assertIn("\x1b[38;2;255;133;133mError:", errors.getvalue())

    def test_flat_output_does_not_include_command_feedback(self):
        output, errors = io.StringIO(), io.StringIO()
        index = {3: [("bad", 11, ((0, 1), (1, 1), (3, 1)))]}
        with redirect_stdout(output), redirect_stderr(errors), \
                patch("main.load_index", return_value=index):
            main.main(["solve", "bad", "-m", "3", "--flat", "-x", "q"])
        self.assertEqual(output.getvalue(), "bad\n")
        self.assertIn("Excluding words containing: q.", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
