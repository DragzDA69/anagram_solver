#!/usr/bin/env python3
"""The help pages: the banner, the boxed command headers, and the option lists.

Ported from MiRTG Tool's utils/print_util.py, in this project's blue rather than
that one's green. Two things are done differently:

  * Box-drawing characters are swapped for ASCII when the stream cannot encode
    them. MiRTG Tool raises UnicodeEncodeError on a cp1252 pipe; `python main.py
    -h > help.txt` has to work.
  * The option lists are read off the argparse parser instead of being written
    out a second time, so a flag cannot appear in one and not the other.

Copy that the pages share with the web UI (the app name) comes from ui.py.
"""

from __future__ import annotations

import sys

import ui
from cli import font
from cli.ansi import (
    BRIGHT,
    PRIMARY,
    SECONDARY,
    TERTIARY,
    colored,
    hyperlink,
    repeat_filler,
    visible_length,
    wrap_items,
    wrap_text,
)

TITLE_WIDTH = 90          # even, so the two halves of a centred line match
MAX_TEXT_WIDTH = 70       # how wide a boxed command header lets prose run
MIN_LR_TEXT_PADDING = 2
BORDER_ATTRS = ["bold"]

DEVELOPERS = ["Zach Wilkin"]
PYTHON_DOCS_URL = "https://www.python.org/downloads/"


def _box_chars():
    """Box-drawing characters, or ASCII if this stream cannot encode them."""
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    try:
        "═║╔╗╚╝─".encode(encoding)
    except (UnicodeEncodeError, LookupError):
        return {"h": "-", "v": "|", "tl": "+", "tr": "+",
                "bl": "+", "br": "+", "rule": "-"}
    return {"h": "═", "v": "║", "tl": "╔", "tr": "╗",
            "bl": "╚", "br": "╝", "rule": "─"}


def get_tabs(count: int, tab_size: int = 4) -> str:
    return "\t" * (count // tab_size) + " " * (count % tab_size)


def normalize_lines(text):
    if text is None:
        return []
    if isinstance(text, str):
        return text.splitlines() or [text]
    lines = []
    for part in text:
        if part is None:
            continue
        lines.extend(str(part).splitlines() or [str(part)])
    return lines


def format_line_pacing(label, description, label_width=10, gap=2, indent="") -> str:
    """A label column and a description column, with continuation lines aligned."""
    lines = normalize_lines(description)
    if not lines:
        return "{}{}".format(indent, label)

    label_length = visible_length(label)
    content_width = max(label_width, label_length)
    first_padding = " " * (content_width - label_length + gap)
    continuation = indent + (" " * (content_width + gap))

    return "\n".join([
        "{}{}{}{}".format(indent, label, first_padding, lines[0]),
        *["{}{}".format(continuation, line) for line in lines[1:]],
    ])


# --------------------------------------------------------------------------- #
# The banner
# --------------------------------------------------------------------------- #

def title_border_line(start="", end="", filler="", text="", width=TITLE_WIDTH,
                      color=PRIMARY, attrs=None, text_color=None,
                      left_align=False, left_align_padding=""):
    """One row of the banner: borders, filler, and text centred or left-aligned."""
    left_min = MIN_LR_TEXT_PADDING if start else 0
    right_min = MIN_LR_TEXT_PADDING if end else 0
    left_padding = left_align_padding.expandtabs(4) if left_align else ""
    extra_left = visible_length(left_padding) if left_align else 0

    if text_color is None:
        text_color = color

    def border(value):
        return colored(value, color, attrs=BORDER_ATTRS) if value else ""

    lines = []
    wrap_width = max(1, width - left_min - right_min - extra_left)
    for raw_line in normalize_lines(text):
        lines.extend(wrap_text(raw_line, wrap_width))
    if not lines:
        return border(start) + border(repeat_filler(filler, width)) + border(end)

    pad = filler or " "
    widest = max(visible_length(line) for line in lines)

    if left_align:
        left = min(left_min, max(0, width - widest - right_min - extra_left))
        left_fill = repeat_filler(pad, left)
        return "\n".join(
            border(start)
            + border(left_fill)
            + left_padding
            + colored(line, text_color, attrs=attrs)
            + border(repeat_filler(pad, width - left - extra_left - visible_length(line)))
            + border(end)
            for line in lines
        )

    left = (width - visible_length(lines[0])) // 2
    left = max(left_min, min(left, width - widest - right_min))
    return "\n".join(
        border(start)
        + border(repeat_filler(pad, left))
        + colored(line, text_color, attrs=attrs)
        + border(repeat_filler(pad, width - left - visible_length(line)))
        + border(end)
        for line in lines
    )


def banner_rows(name, width=TITLE_WIDTH):
    """The name in block letters, stacked onto as few rows as fit the box.

    'Anagram Solver' is 94 columns on one line, wider than the box and wider
    than an 80-column terminal, so it splits at the space. A name whose words
    still do not fit falls back to plain text.
    """
    usable = width - (MIN_LR_TEXT_PADDING * 2)
    if font.width_of(name) <= usable:
        return list(font.for_string(name))

    rows, line = [], ""
    for word in name.split():
        candidate = "{} {}".format(line, word) if line else word
        if line and font.width_of(candidate) > usable:
            rows.append(line)
            line = word
        else:
            line = candidate
    if line:
        rows.append(line)

    if any(font.width_of(part) > usable for part in rows):
        return [name]

    out = []
    for part in rows:
        out.extend(font.for_string(part))
    return out


def get_help_header():
    box = _box_chars()
    name_art = banner_rows(ui.VALUES["app_name"])

    blank = title_border_line(box["v"], box["v"], " ")
    return "\n".join((
        title_border_line(box["tl"], box["tr"], box["h"]),
        blank,
        *[title_border_line(box["v"], box["v"], " ", row, attrs=["bold"]) for row in name_art],
        title_border_line(box["v"], box["v"], " ",
                          "Anagram solver with wildcard support"),
        title_border_line(box["v"], box["v"], " ",
                          "Developed by " + ", ".join(DEVELOPERS),
                          text_color=SECONDARY),
        blank,
        title_border_line(box["v"], box["v"], " ", [
            "Give it a pool of letters and it lists every word that can be spelled",
            "from them, grouped longest first. '?' stands for a tile you have not",
            "identified yet.",
            " ",
            "The same solver runs on the command line and behind the web page.",
            get_tabs(1) + "> python main.py \"he?lpf\"",
        ], text_color=SECONDARY, attrs=["italic"]),
        blank,
        title_border_line(box["v"], box["v"], " ", [
            colored("Requirements", PRIMARY),
            colored(box["rule"] * 12, PRIMARY),

            colored("- Python 3.8", PRIMARY)
            + colored(" or higher", SECONDARY)
            + colored(" [install ", SECONDARY)
            + colored(hyperlink("here", PYTHON_DOCS_URL), PRIMARY)
            + colored("]", SECONDARY),

            colored("- No third-party packages", PRIMARY)
            + colored(" -- the standard library only", SECONDARY, attrs=["italic"]),

            colored("- A browser", PRIMARY)
            + colored(" (for the", SECONDARY, attrs=["italic"])
            + colored(" run", PRIMARY, attrs=["italic"])
            + colored(" and", SECONDARY, attrs=["italic"])
            + colored(" open", PRIMARY, attrs=["italic"])
            + colored(" commands)", SECONDARY, attrs=["italic"]),
        ], text_color=SECONDARY, left_align=True, left_align_padding=get_tabs(5)),
        blank,
        blank,
        title_border_line(box["bl"], box["br"], box["h"]),
        "\n",
    ))


# --------------------------------------------------------------------------- #
# The boxed command header
# --------------------------------------------------------------------------- #

def get_command_header(command_name, action_name=None, summary=None,
                       sub_action_names=None, option_args=None):
    """The box that opens a command's own help page."""
    box = _box_chars()
    command_line = colored(command_name.upper(), PRIMARY, attrs=["bold"])
    if action_name:
        command_line += " - " + colored(action_name.title(), SECONDARY,
                                        attrs=["bold", "italic"])

    def wrap_group(line, text_color=None):
        wrapped = wrap_text(line, MAX_TEXT_WIDTH) if line else [""]
        if text_color is None:
            return wrapped
        return [colored(one, text_color) if one else one for one in wrapped]

    summary_lines = []
    for line in normalize_lines(summary):
        summary_lines.extend(wrap_group(line, SECONDARY))

    groups = [wrap_group(command_line)]
    if summary_lines:
        groups.append(summary_lines)

    sub_action_names = sub_action_names or []
    option_args = option_args or []

    def build_label_lines(label_text, items, separator):
        label = colored(label_text, SECONDARY)
        indent = visible_length(label)
        tokens = [colored(item, TERTIARY, attrs=["italic"]) for item in items]
        wrapped = wrap_items(tokens, max(1, MAX_TEXT_WIDTH - indent), separator)
        lines = [label + wrapped[0]]
        lines.extend((" " * indent) + one for one in wrapped[1:])
        return lines

    actions_lines = build_label_lines("Actions: ", sub_action_names, " > ") if sub_action_names else None
    options_lines = build_label_lines("Options: ", option_args, " ") if option_args else None

    # Two short label lines read better merged onto one row than stacked.
    merged_line = None
    if (
        len(sub_action_names) + len(option_args) <= 4
        and (actions_lines is None or len(actions_lines) == 1)
        and (options_lines is None or len(options_lines) == 1)
    ):
        segments = [lines[0] for lines in (actions_lines, options_lines) if lines is not None]
        if segments:
            candidate = (" " + colored("|", SECONDARY) + " ").join(segments)
            if visible_length(candidate) <= MAX_TEXT_WIDTH:
                merged_line = candidate

    if merged_line is not None:
        groups.append(wrap_group(merged_line))
    else:
        if actions_lines is not None:
            groups.append(actions_lines)
        if options_lines is not None:
            groups.append(options_lines)

    width = max(visible_length(line) for group in groups for line in group)

    def border(value):
        return colored(value, PRIMARY, attrs=BORDER_ATTRS)

    gutter = " " * MIN_LR_TEXT_PADDING
    inner_width = width + (MIN_LR_TEXT_PADDING * 2)

    rows = [border(box["tl"] + (box["h"] * inner_width) + box["tr"])]
    for group in groups:
        widest = max(visible_length(line) for line in group)
        left_pad = max(0, (width - widest) // 2)
        for line in group:
            right_pad = " " * max(0, width - left_pad - visible_length(line))
            rows.append(border(box["v"]) + gutter + (" " * left_pad) + line
                        + right_pad + gutter + border(box["v"]))
    rows.append(border(box["bl"] + (box["h"] * inner_width) + box["br"]))
    return "\n".join(rows)


def print_command_header(command_name, action_name=None, summary=None,
                         sub_action_names=None, option_args=None):
    print(get_command_header(command_name, action_name, summary,
                             sub_action_names, option_args))
    print("")


# --------------------------------------------------------------------------- #
# Option lists, read off the parser so they cannot drift
# --------------------------------------------------------------------------- #

GLOBAL_HELP_LABEL = "--help -h"
GLOBAL_HELP_DESCRIPTION = "View detailed help for a command."
GLOBAL_OPTION_WIDTH = 22


def option_rows(parser):
    """(label, help) for every flag on `parser`, in the order declared."""
    rows = []
    for action in parser._actions:  # noqa: SLF001 - argparse exposes no public view
        if not action.option_strings or action.help == "==SUPPRESS==":
            continue
        label = ", ".join(action.option_strings)
        if action.nargs != 0 and action.metavar:
            label += " " + action.metavar
        elif action.nargs != 0 and action.type is not None:
            label += " " + (action.dest or "").upper()
        elif action.nargs != 0:
            label += " " + (action.dest or "").upper()
        rows.append((label, action.help or ""))
    return rows


def pad_to(text, column: int) -> str:
    """Pad `text` out to `column` visible characters, always leaving a gap.

    Spaces, never tabs: a tab stop depends on the terminal, so a tab-padded
    column lines up in one and not the next.
    """
    return text + (" " * max(1, column - visible_length(text)))


def options_width(rows, minimum=GLOBAL_OPTION_WIDTH) -> int:
    """The label column wide enough for `rows`, and for the global block."""
    labels = [label for label, _ in rows] + [GLOBAL_HELP_LABEL]
    return max(minimum, max(len(label) for label in labels) + 2)


def print_options(rows, title="Options:", indent=None, width=None):
    if not rows:
        return
    indent = get_tabs(2) if indent is None else indent
    width = options_width(rows) if width is None else width
    print(title)
    for label, description in rows:
        print(indent + colored(pad_to(label, width), BRIGHT)
              + colored(description, SECONDARY))


def print_global_options(indent=None, width=None):
    """Always printed with the same column as the page's own options block."""
    print_options([(GLOBAL_HELP_LABEL, GLOBAL_HELP_DESCRIPTION)],
                  title="Global Options:", indent=indent,
                  width=width or GLOBAL_OPTION_WIDTH)


def print_lines(title, lines, indent=None):
    if not lines:
        return
    indent = get_tabs(2) if indent is None else indent
    print(title)
    for line in lines:
        print(indent + line)
    print("")


def usage_line(parts):
    """`> python main.py <command> ...`, each part in its own colour."""
    return get_tabs(2) + "> python main.py" + "".join(parts)
