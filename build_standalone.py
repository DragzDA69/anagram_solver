#!/usr/bin/env python3
"""Build index.html -- a single self-contained solver with no server.

Takes web/standalone.template.html and injects wordlist.txt into it, front-coded
so the whole dictionary fits in a fraction of the space. The result is one file
that runs offline in any browser: open it from the Files app on iOS, or let
GitHub Pages serve it.

    python build_standalone.py
"""

import argparse
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE / "web" / "standalone.template.html"
WORDLIST = HERE / "wordlist.txt"
OUT = HERE / "index.html"

MARKER = "__WORDLIST__"


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
    if MARKER not in template:
        raise SystemExit("{} has no {} marker".format(TEMPLATE, MARKER))

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

    args.out.write_text(template.replace(MARKER, data), encoding="utf-8", newline="\n")

    kb = args.out.stat().st_size / 1024
    print("wrote {}  ({:,} words, {:.0f} KB)".format(args.out, len(words), kb))


if __name__ == "__main__":
    main()
