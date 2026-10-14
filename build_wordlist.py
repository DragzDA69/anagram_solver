"""Rebuild wordlist.txt -- the dictionary the solver reads.

Source: ENABLE1 (Enhanced North American Benchmark Lexicon), public domain,
compiled by Alan Beale. See DICTIONARY.md for why this list was chosen.

Usage:
    python main.py update                # download the complete ENABLE1 list
    python build_wordlist.py              # download ENABLE1 and rebuild
    python build_wordlist.py --src enable1.txt

All word lengths are retained; the solver's min/max options filter results.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
import urllib.error
import urllib.request
from http.client import HTTPException
from pathlib import Path

from cli.spinner import spinner

HERE = Path(__file__).resolve().parent
OUT = HERE / "wordlist.txt"

SOURCE = "https://norvig.com/ngrams/enable1.txt"

def fetch() -> str:
    try:
        with urllib.request.urlopen(SOURCE, timeout=60) as resp:
            return resp.read().decode("utf-8")
    except (urllib.error.URLError, OSError, HTTPException, UnicodeError) as exc:
        raise RuntimeError(
            f"Could not download ENABLE1 from {SOURCE}\n    {exc}\n"
            "Pass --src with a local copy to build without the network."
        ) from exc


def create_parser(prog=None, add_help=True) -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog=prog, add_help=add_help,
        description="Update wordlist.txt with the complete ENABLE1 dictionary.")
    ap.add_argument("--src", type=Path, help="use a local ENABLE1 file instead of downloading")
    return ap


def update_dictionary(src: Path | None = None) -> None:
    temporary = None
    try:
        with spinner("Updating ENABLE1 dictionary"):
            raw = src.read_text(encoding="utf-8") if src is not None else fetch()
            words = sorted({
                w for w in (line.strip().lower() for line in raw.splitlines())
                if w.isalpha() and w.isascii()
            })
            if not words:
                raise ValueError("Dictionary source contains no valid words.")

            # Replace only after a complete write; a failed update keeps the old list.
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", newline="", dir=OUT.parent,
                prefix="wordlist-", suffix=".tmp", delete=False,
            ) as f:
                temporary = Path(f.name)
                f.write("\r\n".join(words) + "\r\n")
            os.replace(temporary, OUT)
    except (OSError, UnicodeError, RuntimeError, ValueError) as exc:
        sys.exit(f"Dictionary update failed; existing word list unchanged.\n{exc}")
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()

    print(f"Updated {OUT} ({len(words):,} words, all word lengths).")


def main(argv=None) -> None:
    args = create_parser().parse_args(argv)
    update_dictionary(args.src)


if __name__ == "__main__":
    main()
