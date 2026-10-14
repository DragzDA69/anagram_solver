import io
import tempfile
import unittest
import urllib.error
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

import build_wordlist
import main


class DictionaryUpdateTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.out = self.root / "wordlist.txt"
        self.out.write_text("original\n", encoding="utf-8")
        output_path = patch("build_wordlist.OUT", self.out)
        output_path.start()
        self.addCleanup(output_path.stop)
        build = patch("build_standalone.main")
        self.build = build.start()
        self.addCleanup(build.stop)
        self.stdout = io.StringIO()
        self.stderr = io.StringIO()
        for redirect in (redirect_stdout(self.stdout), redirect_stderr(self.stderr)):
            redirect.__enter__()
            self.addCleanup(redirect.__exit__, None, None, None)

    def test_download_keeps_all_lengths_and_normalizes_words(self):
        with patch("build_wordlist.fetch", return_value=(
            "a\nAN\ncat\ncats\nextraordinary\ncounterrevolutionaries\nCAT\nbad-word\n123\n"
        )) as fetch:
            main.main(["update"])
        fetch.assert_called_once_with()
        self.assertEqual(self.out.read_bytes(),
                         b"a\r\nan\r\ncat\r\ncats\r\ncounterrevolutionaries\r\nextraordinary\r\n")
        self.assertIn("6 words. All word lengths are included.", self.stdout.getvalue())
        index = main.load_index(self.out)
        for letters, minimum, maximum, expected in [
            ("cat", 1, 3, {1: ["a"], 3: ["cat"]}),
            ("cats", 4, None, {4: ["cats"]}),
            ("extraordinary", 13, 13, {13: ["extraordinary"]}),
            ("counterrevolutionaries", 16, None, {22: ["counterrevolutionaries"]}),
            ("counterrevolutionaries", 22, 22, {22: ["counterrevolutionaries"]}),
        ]:
            args = main.parse_args(["solve", letters, "--min", str(minimum)])
            args.max_len = maximum
            rack, wildcards = main.parse_rack(letters)
            lengths, _ = main.choose_lengths(args, len(letters), max(index))
            self.assertEqual(main.solve(index, rack, wildcards, lengths), expected)

        args = main.parse_args(["solve", "counterrevolutionaries", "--length", "22"])
        lengths, _ = main.choose_lengths(args, 22, max(index))
        rack, wildcards = main.parse_rack("counterrevolutionaries")
        self.assertEqual(main.solve(index, rack, wildcards, lengths),
                         {22: ["counterrevolutionaries"]})

    def test_local_source_needs_no_network(self):
        source = self.root / "enable1.txt"
        source.write_text("at\ncat\n", encoding="utf-8")
        with patch("build_wordlist.fetch") as fetch:
            main.main(["update", "--src", str(source)])
        fetch.assert_not_called()
        self.assertEqual(self.out.read_text(encoding="utf-8"), "at\ncat\n")

    def test_direct_script_uses_same_updater(self):
        with patch("build_wordlist.update_dictionary") as update:
            build_wordlist.main(["--src", "enable1.txt"])
        update.assert_called_once_with(Path("enable1.txt"))

    def test_failed_download_keeps_existing_list(self):
        with patch("build_wordlist.urllib.request.urlopen",
                   side_effect=urllib.error.URLError("offline")):
            with self.assertRaisesRegex(SystemExit, "existing word list unchanged"):
                main.main(["update"])
        self.assertEqual(self.out.read_text(encoding="utf-8"), "original\n")
        self.assertEqual(list(self.root.glob("*.tmp")), [])

    def test_empty_source_keeps_existing_list(self):
        with patch("build_wordlist.fetch", return_value="123\n---\n"):
            with self.assertRaisesRegex(SystemExit, "no valid words"):
                main.main(["update"])
        self.assertEqual(self.out.read_text(encoding="utf-8"), "original\n")

    def test_failed_replace_cleans_temporary_file(self):
        with patch("build_wordlist.fetch", return_value="at\n"), \
                patch("build_wordlist.os.replace", side_effect=PermissionError("locked")):
            with self.assertRaisesRegex(SystemExit, "locked"):
                main.main(["update"])
        self.assertEqual(self.out.read_text(encoding="utf-8"), "original\n")
        self.assertEqual(list(self.root.glob("*.tmp")), [])

    def test_update_help_does_not_download(self):
        with patch("build_wordlist.fetch") as fetch:
            with self.assertRaises(SystemExit) as result:
                main.main(["update", "-h"])
        self.assertEqual(result.exception.code, 0)
        fetch.assert_not_called()
        self.assertIn("--src", self.stdout.getvalue())
        self.assertIn("every word length", self.stdout.getvalue())

    def test_top_level_help_lists_update(self):
        with self.assertRaises(SystemExit):
            main.main(["-h"])
        self.assertIn("python main.py update", self.stdout.getvalue())

    def test_update_rejects_solve_options(self):
        with self.assertRaises(SystemExit) as result:
            main.parse_args(["update", "--min", "4"])
        self.assertEqual(result.exception.code, 2)

    def test_command_name_can_still_be_solved(self):
        args = main.parse_args(["solve", "update"])
        self.assertEqual(args.command, "solve")
        self.assertEqual(args.letters, ["update"])

    def test_default_updates_dictionary_before_build(self):
        order = []
        with patch("build_wordlist.update_dictionary",
                   side_effect=lambda src: order.append("dictionary")):
            self.build.side_effect = lambda argv: order.append("build")
            main.main(["update"])
        self.assertEqual(order, ["dictionary", "build"])
        self.build.assert_called_once_with([])

    def test_selection_flags(self):
        for flags, dictionary, build in [
            (["-d"], True, False), (["--dictionary"], True, False),
            (["-b"], False, True), (["--build"], False, True),
            (["-d", "-b"], True, True),
        ]:
            with self.subTest(flags=flags), patch("build_wordlist.update_dictionary") as update:
                self.build.reset_mock()
                main.main(["update"] + flags)
                self.assertEqual(update.called, dictionary)
                self.assertEqual(self.build.called, build)

    def test_failed_dictionary_update_does_not_build(self):
        with patch("build_wordlist.update_dictionary", side_effect=SystemExit("failed")):
            with self.assertRaises(SystemExit):
                main.main(["update"])
        self.build.assert_not_called()

    def test_build_failure_is_reported(self):
        self.build.side_effect = SystemExit("build failed")
        with self.assertRaisesRegex(SystemExit, "build failed"):
            main.main(["update", "-b"])

    def test_build_only_rejects_dictionary_source(self):
        with self.assertRaises(SystemExit) as result:
            main.parse_args(["update", "-b", "--src", "enable1.txt"])
        self.assertEqual(result.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
