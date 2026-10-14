"""Shared terminal progress indicator with clean shutdown."""

from __future__ import annotations

import itertools
import sys
import threading
from contextlib import contextmanager
from typing import Iterator, TextIO

FRAMES = (".  ", ".. ", "...", " ..", "  .", "   ")
INTERVAL = 0.2


@contextmanager
def spinner(message: str, stream: TextIO | None = None) -> Iterator[None]:
    stream = sys.stderr if stream is None else stream
    if not stream.isatty():
        print(message + "...", file=stream, flush=True)
        yield
        return

    stop = threading.Event()
    prefix = message + " "

    def animate() -> None:
        for frame in itertools.cycle(FRAMES):
            stream.write("\r" + prefix + frame)
            stream.flush()
            if stop.wait(INTERVAL):
                break

    thread = threading.Thread(target=animate, daemon=True)
    thread.start()
    try:
        yield
    finally:
        stop.set()
        thread.join()
        stream.write("\r" + " " * (len(prefix) + len(FRAMES[0])) + "\r")
        stream.flush()
