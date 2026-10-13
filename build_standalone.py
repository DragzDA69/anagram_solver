#!/usr/bin/env python3
"""Build index.html -- a single self-contained solver with no server.

Takes web/standalone.template.html and injects two things into it: the styles
from web/standalone.css, and wordlist.txt, front-coded so the whole dictionary
fits in a fraction of the space. The result is one file that runs offline in any
browser: open it from the Files app on iOS, or let GitHub Pages serve it.

The CSS is inlined rather than linked for the same reason: a <link> would be a
second file to carry around, and the page would not be self-contained.

    python build_standalone.py
"""

import argparse
import base64
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import ui  # noqa: E402

TEMPLATE = HERE / "web" / "standalone.template.html"
STYLES = HERE / "web" / "standalone.css"
# A 64px copy of icon.png. The 512px original would add a third of a
# megabyte of base64 to a page whose whole point is being small.
ICON = HERE / "web" / "icon-small.png"
WORDLIST = HERE / "wordlist.txt"
OUT = HERE / "index.html"

WORDLIST_MARKER = "__WORDLIST__"
STYLES_MARKER = "__STYLES__"
ICON_MARKER = "__ICON__"


def front_code(words: list[str]) -> str:
    """One line per word: a single char giving the prefix shared with the previous
    word (as chr(48 + n)), then the rest of it. Roughly 44% of the plain size."""
    lines = []
    previous = ""
    for word in words:
        shared = 0
        for a, b in zip(previous, word):
            if a != b:
                break
            shared += 1
        shared = min(shared, 35)  # keep the marker a single printable char
        lines.append(chr(48 + shared) + word[shared:])
        previous = word
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description="Build the standalone single-file solver.")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()

    template = TEMPLATE.read_text(encoding="utf-8")
    for marker in (STYLES_MARKER, WORDLIST_MARKER, ICON_MARKER):
        if marker not in template:
            raise SystemExit("{} has no {} marker".format(TEMPLATE, marker))

    try:
        styles = STYLES.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise SystemExit("Stylesheet not found: {}".format(STYLES)) from None

    try:
        icon = "data:image/png;base64," + base64.b64encode(
            ICON.read_bytes()).decode("ascii")
    except FileNotFoundError:
        raise SystemExit("Icon not found: {}".format(ICON)) from None
    # Copy and timings go in before the payloads do, so neither the word
    # list nor the stylesheet is scanned for the other's placeholders.
    try:
        template = ui.render(template, TEMPLATE.name)
        styles = ui.render(styles, STYLES.name)
    except KeyError as exc:
        raise SystemExit(str(exc)) from None

    # It lands in a <style> block, which only a literal closing tag could escape.
    if "</" in styles:
        raise SystemExit("{} contains '</', which would close the style block".format(STYLES))

    words = WORDLIST.read_text(encoding="utf-8").split()
    if not words:
        raise SystemExit("{} is empty".format(WORDLIST))

    bad = [w for w in words if not (w.isalpha() and w.isascii() and w.islower())]
    if bad:
        raise SystemExit("word list must be lowercase a-z only; found {!r}".format(bad[:3]))

    data = front_code(sorted(words))
    # The data sits in a <script type="text/plain"> block, so only a literal
    # closing tag could break out of it. a-z and newlines cannot.
    assert "</" not in data

    # One pass over the template, so neither injected payload is rescanned for
    # the other's marker.
    fill = {STYLES_MARKER: styles, WORDLIST_MARKER: data, ICON_MARKER: icon}
    page = re.sub("|".join(fill), lambda m: fill[m.group()], template)
    args.out.write_text(page, encoding="utf-8", newline="\n")

    kb = args.out.stat().st_size / 1024
    print("wrote {}  ({:,} words, {:,} lines of CSS, {:,} B icon, {:.0f} KB)".format(
        args.out, len(words), styles.count("\n") + 1, ICON.stat().st_size, kb))


if __name__ == "__main__":
    main()
