import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

import main


class CommandTests(unittest.TestCase):
    def test_bare_invocation_shows_top_level_help_without_loading_dictionary(self):
        output = io.StringIO()
        with redirect_stdout(output), patch("main.load_index") as load:
            with self.assertRaises(SystemExit) as result:
                main.main([])
        self.assertEqual(result.exception.code, 0)
        self.assertIn("Available Commands:", output.getvalue())
        self.assertIn('python main.py solve "he?lpf"', output.getvalue())
        self.assertNotIn("(default)", output.getvalue())
        load.assert_not_called()

    def test_letters_without_solve_are_rejected(self):
        errors = io.StringIO()
        with redirect_stderr(errors):
            with self.assertRaises(SystemExit) as result:
                main.parse_args(["abfds?"])
        self.assertEqual(result.exception.code, 2)
        self.assertIn("use 'solve <anagram>'", errors.getvalue())

    def test_explicit_solve_parses_anagram_and_options(self):
        args = main.parse_args(["solve", "abfds?", "--min", "2", "--flat"])
        self.assertEqual(args.command, "solve")
        self.assertEqual(args.letters, ["abfds?"])
        self.assertEqual(args.min_len, 2)
        self.assertTrue(args.flat)

    def test_explicit_solve_produces_results(self):
        index = {3: [("bad", 11, ((0, 1), (1, 1), (3, 1)))]}
        output = io.StringIO()
        with redirect_stdout(output), patch("main.load_index", return_value=index):
            main.main(["solve", "abfds?", "--min", "3", "--flat"])
        self.assertEqual(output.getvalue(), "bad\n")

    def test_solve_requires_letters(self):
        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as result:
                main.parse_args(["solve"])
        self.assertEqual(result.exception.code, 2)

    def test_help_pages_and_other_commands_still_work(self):
        for command in main.COMMANDS:
            with self.subTest(command=command):
                output = io.StringIO()
                with redirect_stdout(output):
                    with self.assertRaises(SystemExit) as result:
                        main.parse_args([command, "-h"])
                self.assertEqual(result.exception.code, 0)
                self.assertIn(command.upper(), output.getvalue())
                if command != "solve":
                    self.assertEqual(main.parse_args([command]).command, command)


if __name__ == "__main__":
    unittest.main()
