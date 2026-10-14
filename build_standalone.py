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

import base64
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import ui  # noqa: E402
from cli.messages import ArgumentParser, fail, success  # noqa: E402

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
DOCTYPE = "<!doctype html>"

# Stamped at the top of the output. A generated file sitting in the repo root
# looks exactly like a source file, and an edit made here is destroyed by the
# next build without warning -- so the file says so itself.
BANNER = """<!--
  GENERATED FILE -- DO NOT EDIT.

  Built by build_standalone.py from:
      web/index.html   markup        web/app.js     UI code
      web/style.css    styles        web/solver.js  solver
      ui.py            every label, hint and timing

  Edit those, then run:  python build_standalone.py
-->
"""


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


def _build(argv=None) -> None:
    ap = ArgumentParser(description="Build the standalone single-file solver.")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args(argv)

    page = TEMPLATE.read_text(encoding="utf-8")
    for tag in (STYLESHEET_TAG, SCRIPT_TAG, ICON_URL, DOCTYPE):
        if tag not in page:
            fail("Could not rebuild the page: {} is missing {}.".format(TEMPLATE.name, tag))

    try:
        styles = STYLES.read_text(encoding="utf-8")
        app = APP.read_text(encoding="utf-8")
        solver = SOLVER.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        fail("Could not read a file needed to rebuild the page.\nDetails: {}".format(exc))

    # Copy and timings go in before the payloads do, so neither the word list
    # nor the inlined files are scanned for the other's placeholders.
    try:
        page = ui.render(page, TEMPLATE.name)
        styles = ui.render(styles, STYLES.name)
        app = ui.render(app, APP.name)
        solver = ui.render(solver, SOLVER.name)
    except KeyError as exc:
        fail("Could not rebuild the page because a UI label is missing.\nDetails: {}".format(exc))

    for name, text in (("stylesheet", styles), ("app.js", app), ("solver.js", solver)):
        if "</" in text and name == "stylesheet":
            fail("Could not rebuild the page: {} contains invalid HTML closing text.".format(name))
        if "</script" in text.lower():
            fail("Could not rebuild the page: {} contains invalid script closing text.".format(name))

    try:
        icon = "data:image/png;base64," + base64.b64encode(
            ICON.read_bytes()).decode("ascii")
    except FileNotFoundError:
        fail("Could not rebuild the page: the app icon is missing.")

    words = WORDLIST.read_text(encoding="utf-8").split()
    if not words:
        fail("The dictionary is empty. Run 'python main.py update -d' and try again.")

    bad = [w for w in words if not (w.isalpha() and w.isascii() and w.islower())]
    if bad:
        fail("The dictionary contains invalid entries: {!r}. "
             "Run 'python main.py update -d' and try again.".format(bad[:3]))

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
    # The banner goes in last, so nothing above can scan it for tags.
    page = page.replace(DOCTYPE, DOCTYPE + "\n" + BANNER, 1)

    args.out.write_text(page, encoding="utf-8", newline="\n")

    success("{} has been recompiled with the latest changes.".format(args.out.name))


def main(argv=None) -> None:
    try:
        _build(argv)
    except (OSError, UnicodeError) as exc:
        fail("Could not rebuild the page. Check that the required files are available "
             "and the output file can be saved.\nDetails: {}".format(exc))


if __name__ == "__main__":
    main()
