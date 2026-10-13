#!/usr/bin/env python3
"""Build index.html -- a single self-contained solver with no server.

Takes web/index.html -- the same page server.py serves -- and inlines what it
would otherwise fetch: style.css, app.js, solver.js (the solver in JavaScript,
which only this build needs), icon.png, and wordlist.txt front-coded so the whole
dictionary fits in a fraction of the space. The result is one file that runs
offline in any browser: open it from the Files app on iOS, or let GitHub Pages
serve it.

Building from the served page rather than a second template is deliberate: the
two used to be separate documents, and they drifted.

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

TEMPLATE = HERE / "web" / "index.html"
STYLES = HERE / "web" / "style.css"
APP = HERE / "web" / "app.js"
SOLVER = HERE / "web" / "solver.js"
# A 64px copy of icon.png. The 512px original would add a third of a
# megabyte of base64 to a page whose whole point is being small.
ICON = HERE / "web" / "icon-small.png"
WORDLIST = HERE / "wordlist.txt"
OUT = HERE / "index.html"

# The served page's own tags are what gets swapped out, so there are no
# build markers to keep in sync -- and nothing for a browser to choke on if
# web/index.html is opened directly.
STYLESHEET_TAG = '<link rel="stylesheet" href="/style.css">'
SCRIPT_TAG = '<script src="/app.js"></script>'
ICON_URL = "/icon.png"


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

    page = TEMPLATE.read_text(encoding="utf-8")
    for tag in (STYLESHEET_TAG, SCRIPT_TAG, ICON_URL):
        if tag not in page:
            raise SystemExit("{} no longer contains {}".format(TEMPLATE, tag))

    try:
        styles = STYLES.read_text(encoding="utf-8")
        app = APP.read_text(encoding="utf-8")
        solver = SOLVER.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise SystemExit(str(exc)) from None

    # Copy and timings go in before the payloads do, so neither the word list
    # nor the inlined files are scanned for the other's placeholders.
    try:
        page = ui.render(page, TEMPLATE.name)
        styles = ui.render(styles, STYLES.name)
        app = ui.render(app, APP.name)
        solver = ui.render(solver, SOLVER.name)
    except KeyError as exc:
        raise SystemExit(str(exc)) from None

    for name, text in (("stylesheet", styles), ("app.js", app), ("solver.js", solver)):
        if "</" in text and name == "stylesheet":
            raise SystemExit("{} contains '</', which would close the style block".format(name))
        if "</script" in text.lower():
            raise SystemExit("{} contains '</script', which would close its block".format(name))

    try:
        icon = "data:image/png;base64," + base64.b64encode(
            ICON.read_bytes()).decode("ascii")
    except FileNotFoundError:
        raise SystemExit("Icon not found: {}".format(ICON)) from None

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

    scripts = (
        '<script id="wl" type="text/plain">' + data + "</script>"
        + "<script>" + solver + "</script>"
        + "<script>" + app + "</script>"
    )
    page = page.replace(STYLESHEET_TAG, "<style>" + styles + "</style>", 1)
    page = page.replace(SCRIPT_TAG, scripts, 1)
    page = page.replace(ICON_URL, icon)   # favicon and the mark beside the title

    args.out.write_text(page, encoding="utf-8", newline="\n")

    kb = args.out.stat().st_size / 1024
    print("wrote {}  ({:,} words, {:,} B icon, {:.0f} KB)".format(
        args.out, len(words), ICON.stat().st_size, kb))


if __name__ == "__main__":
    main()
