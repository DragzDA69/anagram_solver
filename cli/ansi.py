#!/usr/bin/env python3
"""Coloured terminal output, and the text measuring that goes with it.

MiRTG Tool bundles a vendored termcolor for this. Nothing here is downloaded or
vendored: the escape codes are four lines of string formatting, and this project
is standard library only everywhere else, so it stays that way here too.

Colour is dropped automatically when it would be noise rather than signal --
piped output, NO_COLOR set, TERM=dumb -- so `python main.py -h | less` and a
redirect to a file both come out clean.

    from cli.ansi import colored, PRIMARY
    print(colored("hello", PRIMARY, attrs=["bold"]))
"""

from __future__ import annotations

import os
import re
import sys

# The palette is the web UI's, so the terminal and the page agree: PRIMARY is
# --accent from style.css (#6ea8fe), and the other two step down from it the way
# --ink-dim and --ink-faint step down from --ink.
PRIMARY = (110, 168, 254)    # #6ea8fe
SECONDARY = (122, 150, 196)  # dimmer slate blue, for supporting prose
TERTIARY = (96, 118, 156)    # dimmest, for incidental tokens
BRIGHT = (173, 203, 255)     # a lift above PRIMARY, for the few things it marks

NAMED = {
    "black": 30, "red": 31, "green": 32, "yellow": 33,
    "blue": 34, "magenta": 35, "cyan": 36, "white": 37,
    "light_red": 91, "light_green": 92, "light_yellow": 93,
    "light_blue": 94, "light_magenta": 95, "light_cyan": 96,
}
ATTRS = {"bold": 1, "dark": 2, "italic": 3, "underline": 4, "reverse": 7}

# Colour codes, plus the two forms of OSC-8 hyperlink, which are zero width.
ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m|\x1b\]8;;[^\x1b]*\x1b\\|\x1b\]8;;\x1b\\")

RESET = "\x1b[0m"


def _enable_windows_vt() -> bool:
    """Turn on virtual terminal processing for this console.

    Windows consoles print escape codes literally until this is set. Windows
    Terminal and VS Code already have it on; the legacy conhost does not.
    """
    if os.name != "nt":
        return True
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        mode = ctypes.c_uint32()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        return bool(kernel32.SetConsoleMode(handle, mode.value | 0x0004))
    except Exception:  # noqa: BLE001 - a console we cannot query gets no colour
        return False


def supports_color(stream=None) -> bool:
    """Whether to emit escape codes at all.

    Checked once per call rather than cached, so a test can redirect stdout and
    get plain text without reimporting the module.
    """
    stream = stream or sys.stdout
    if os.environ.get("NO_COLOR") is not None:
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    if os.environ.get("TERM") == "dumb":
        return False
    if not hasattr(stream, "isatty") or not stream.isatty():
        return False
    return _enable_windows_vt()


def colored(text, color=None, attrs=None, on_color=None, stream=None) -> str:
    """Wrap `text` in escape codes. `color` is a NAMED key or an (r, g, b)."""
    text = str(text)
    if not text or not supports_color(stream):
        return text

    codes = []
    for attr in attrs or ():
        if attr in ATTRS:
            codes.append(str(ATTRS[attr]))
    if isinstance(color, (tuple, list)) and len(color) == 3:
        codes.append("38;2;{};{};{}".format(*color))
    elif color in NAMED:
        codes.append(str(NAMED[color]))
    if isinstance(on_color, (tuple, list)) and len(on_color) == 3:
        codes.append("48;2;{};{};{}".format(*on_color))

    if not codes:
        return text
    return "\x1b[" + ";".join(codes) + "m" + text + RESET


def hyperlink(text: str, url: str) -> str:
    """An OSC-8 link. Terminals that do not support it just show the text."""
    if not supports_color():
        return text
    return "\x1b]8;;{}\x1b\\{}\x1b]8;;\x1b\\".format(url, text)


# --------------------------------------------------------------------------- #
# Measuring and wrapping, all of which must ignore escape codes
# --------------------------------------------------------------------------- #

def visible_length(value: str) -> int:
    """Width on screen: escape codes and hyperlink wrappers take no columns."""
    return len(ANSI_ESCAPE.sub("", value))


def repeat_filler(filler: str, length: int) -> str:
    if length <= 0 or not filler:
        return ""
    repeats = -(-length // len(filler))
    return (filler * repeats)[:length]


def split_at_column(value: str, columns: int):
    """Cut `value` after `columns` visible characters, keeping escapes intact."""
    head, used, index = [], 0, 0
    while index < len(value) and used < columns:
        escape = ANSI_ESCAPE.match(value, index)
        if escape:
            head.append(escape.group())
            index = escape.end()
            continue
        head.append(value[index])
        used += 1
        index += 1
    return "".join(head), value[index:]


def wrap_text(text: str, width: int) -> list:
    """Word-wrap to `width` visible columns, breaking a word only if it cannot fit."""
    if not text:
        return []
    if width < 1 or visible_length(text) <= width:
        return [text]

    lines, current = [], ""
    for word in text.split():
        candidate = "{} {}".format(current, word) if current else word
        if visible_length(candidate) <= width:
            current = candidate
            continue
        if current:
            lines.append(current)
        while visible_length(word) > width:
            head, word = split_at_column(word, width)
            lines.append(head)
        current = word
    if current:
        lines.append(current)
    return lines


def wrap_items(items, width: int, separator: str = " ") -> list:
    """Pack `items` onto as few lines as fit, never splitting one."""
    if not items:
        return []
    lines, current = [], ""
    for item in items:
        candidate = item if not current else "{}{}{}".format(current, separator, item)
        if not current or visible_length(candidate) <= width:
            current = candidate
            continue
        lines.append(current)
        current = item
    if current:
        lines.append(current)
    return lines
