import io
import threading
import unittest

from cli.spinner import FRAMES, INTERVAL, spinner


class TerminalStream(io.StringIO):
    def __init__(self):
        super().__init__()
        self.cycle_done = threading.Event()

    def isatty(self):
        return True

    def write(self, text):
        result = super().write(text)
        if text == "\rLoading " + FRAMES[-1]:
            self.cycle_done.set()
        return result


class SpinnerTests(unittest.TestCase):
    def test_requested_frames_and_interval(self):
        self.assertEqual(FRAMES, (".  ", ".. ", "...", " ..", "  .", "   "))
        self.assertEqual(INTERVAL, 0.2)

    def test_redirected_output_is_plain_text(self):
        stream = io.StringIO()
        with spinner("Loading", stream):
            pass
        self.assertEqual(stream.getvalue(), "Loading...\n")

    def test_animation_clears_and_stops_on_error(self):
        stream = TerminalStream()
        before = set(threading.enumerate())
        with self.assertRaisesRegex(ValueError, "failed"):
            with spinner("Loading", stream):
                self.assertTrue(stream.cycle_done.wait(3))
                raise ValueError("failed")
        output = stream.getvalue()
        for frame in FRAMES:
            self.assertIn("\rLoading " + frame, output)
        self.assertTrue(output.endswith("\r" + " " * 11 + "\r"))
        self.assertEqual(set(threading.enumerate()), before)


if __name__ == "__main__":
    unittest.main()
