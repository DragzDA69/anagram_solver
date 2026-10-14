"""Consistent command feedback, with plain text for redirected output."""

from __future__ import annotations

import argparse
import sys
from typing import NoReturn, TextIO

from cli.ansi import colored

SUCCESS = (115, 210, 145)
WARNING = (240, 180, 94)
ERROR = (255, 133, 133)


def info(message: str, stream: TextIO | None = None) -> None:
    print(message, file=sys.stdout if stream is None else stream, flush=True)


def success(message: str) -> None:
    print(colored(message, SUCCESS), flush=True)


def warning(message: str) -> None:
    print(colored("Warning: " + message, WARNING, stream=sys.stderr),
          file=sys.stderr, flush=True)


def error_text(message: str, stream: TextIO | None = None) -> str:
    return colored("Error: " + message, ERROR,
                   stream=sys.stderr if stream is None else stream)


def fail(message: str) -> NoReturn:
    raise SystemExit(error_text(message))


class ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        self.print_usage(sys.stderr)
        self.exit(2, error_text(message) + "\n")
