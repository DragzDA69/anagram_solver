"""Rebuild wordlist.txt -- the dictionary the solver reads.

Source: ENABLE1 (Enhanced North American Benchmark Lexicon), public domain,
compiled by Alan Beale. See DICTIONARY.md for why this list was chosen.

Usage:
    python build_wordlist.py              # download ENABLE1 and rebuild
    python build_wordlist.py --src enable1.txt

Note: the committed wordlist.txt was built from a different ENABLE1 copy that
carries three words this one does not (knickknack, razzmatazz, razzmatazzes),
so a rebuild from the network produces 151,334 words rather than 151,337.
"""

import argparse
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "wordlist.txt"

SOURCE = "https://norvig.com/ngrams/enable1.txt"

MIN_LEN = 4
MAX_LEN = 12


def fetch() -> str:
    try:
        with urllib.request.urlopen(SOURCE, timeout=60) as resp:
            return resp.read().decode("utf-8")
    except Exception as exc:  # noqa: BLE001 - there is no fallback to try
        sys.exit(
            f"Could not download ENABLE1 from {SOURCE}\n    {exc}\n"
            "Pass --src with a local copy to build without the network."
        )


def main() -> None:
    ap = argparse.ArgumentParser(description="Rebuild wordlist.txt from ENABLE1.")
    ap.add_argument("--src", type=Path, help="use a local ENABLE1 file instead of downloading")
    ap.add_argument("--min", type=int, default=MIN_LEN, dest="min_len")
    ap.add_argument("--max", type=int, default=MAX_LEN, dest="max_len")
    args = ap.parse_args()

    raw = args.src.read_text(encoding="utf-8") if args.src else fetch()

    words = sorted({
        w for w in (line.strip().lower() for line in raw.splitlines())
        if w.isalpha() and w.isascii() and args.min_len <= len(w) <= args.max_len
    })

    # CRLF line endings, one bare word per line, trailing newline.
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        f.write("\r\n".join(words) + "\r\n")

    print(f"wrote {OUT}  ({len(words):,} words, {args.min_len}-{args.max_len} letters)")


if __name__ == "__main__":
    main()
