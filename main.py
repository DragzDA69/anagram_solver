#!/usr/bin/env python3
"""Words on Stream anagram solver, with wildcard ('?') support.

Finds every dictionary word spellable from a pool of letters. Each letter is a
tile and may be used only as many times as it appears; '?' is a wildcard that
stands for any one letter, which is how Words on Stream shows a board letter
that has not been revealed yet.

    python main.py "he?ll"        ->  hell, help, hello, ...

Dictionary: ENABLE1, 4-12 letters (see DICTIONARY.md).
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_DICT = HERE / "wordlist.txt"

A = ord("a")
WILDCARD = "?"

try:
    _popcount = int.bit_count  # Python 3.10+
except AttributeError:  # pragma: no cover - older interpreters
    def _popcount(n: int) -> int:
        return bin(n).count("1")


# --------------------------------------------------------------------------- #
# Dictionary
# --------------------------------------------------------------------------- #

def load_index(path: Path) -> dict:
    """Read the word list into {length: [(word, letter_mask, letter_counts)]}.

    letter_mask is a 26-bit set of the distinct letters in the word; it drives a
    cheap rejection test before the exact per-letter count comparison.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise FileNotFoundError(
            "Dictionary not found: {}\n"
            "Run 'python build_wordlist.py' to create it.".format(path)
        ) from None

    by_length: dict = {}
    for word in text.split():
        counts: dict = {}
        mask = 0
        for ch in word:
            i = ord(ch) - A
            counts[i] = counts.get(i, 0) + 1
            mask |= 1 << i
        by_length.setdefault(len(word), []).append((word, mask, tuple(counts.items())))
    return by_length


# --------------------------------------------------------------------------- #
# Solving
# --------------------------------------------------------------------------- #

def parse_rack(raw: str):
    """Turn the input into (per-letter counts indexed a..z, wildcard count).

    Raises ValueError on anything that isn't a letter or a wildcard.
    """
    counts = [0] * 26
    wildcards = 0
    for ch in raw.lower():
        if ch == WILDCARD:
            wildcards += 1
        elif ch.isspace() or ch in ",.-_":
            continue
        elif "a" <= ch <= "z":
            counts[ord(ch) - A] += 1
        else:
            raise ValueError("Invalid character in letters: {!r} (use a-z and '?')".format(ch))
    return counts, wildcards


def solve(by_length: dict, rack: list, wildcards: int, lengths: list) -> dict:
    """All words of the given lengths that are spellable from the rack."""
    rack_mask = 0
    for i, n in enumerate(rack):
        if n:
            rack_mask |= 1 << i
    unavailable = ~rack_mask

    found: dict = {}
    for length in lengths:
        hits = []
        for word, word_mask, counts in by_length.get(length, ()):
            # Every distinct letter the rack lacks costs at least one wildcard.
            if _popcount(word_mask & unavailable) > wildcards:
                continue
            deficit = 0
            for i, needed in counts:
                short = needed - rack[i]
                if short > 0:
                    deficit += short
                    if deficit > wildcards:
                        break
            else:
                hits.append(word)
        if hits:
            found[length] = hits
    return found


# --------------------------------------------------------------------------- #
# Output
# --------------------------------------------------------------------------- #

def columns(words: list, width: int) -> list:
    """Lay words out in aligned columns that fit `width`."""
    if not words:
        return []
    cell = max(len(w) for w in words) + 2
    per_row = max(1, width // cell)
    return [
        "".join(w.ljust(cell) for w in words[i:i + per_row]).rstrip()
        for i in range(0, len(words), per_row)
    ]


def render(found: dict, args, rack_desc: str, dict_size: int) -> None:
    total = sum(len(v) for v in found.values())

    if args.flat:
        for length in sorted(found, reverse=True):
            for word in found[length]:
                print(word)
        return

    if args.count:
        for length in sorted(found, reverse=True):
            print("{:2d} letters  {:5d}".format(length, len(found[length])))
        print("{:>10}  {:5d}".format("total", total))
        return

    width = shutil.get_terminal_size((100, 24)).columns
    print("\nRack: {}".format(rack_desc))
    print("Dictionary: {:,} words\n".format(dict_size))

    if not found:
        print("No words found.\n")
        return

    for length in sorted(found, reverse=True):
        words = found[length]
        shown = words[:args.limit] if args.limit else words
        header = "-- {} letters ({}".format(length, len(words))
        header += ", showing {}) ".format(len(shown)) if len(shown) < len(words) else ") "
        print(header + "-" * max(0, width - len(header)))
        for line in columns(shown, width):
            print(line)
        print()

    print("{} word{} total\n".format(total, "" if total == 1 else "s"))


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

EPILOG = """examples:
  python main.py "he?ll"                every word from  h e ? l l
  python main.py "caution" -l 4,5,7     only the lengths this level needs
  python main.py "caution" -e           the big word (uses every tile)
  python main.py "ca?tion" -p "..t..n"  a slot showing  _ _ t _ _ n

Quote the letters: in bash an unquoted ? is a shell glob.
"""


def parse_args(argv=None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        prog="main.py",
        description="Words on Stream anagram solver. '?' is a wildcard letter.",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("letters", nargs="+",
                    help="the board letters; '?' = an unrevealed letter")
    ap.add_argument("-l", "--length", help="only these word lengths, e.g. 4,5,7")
    ap.add_argument("-m", "--min", type=int, default=4, dest="min_len",
                    help="minimum length (default 4, the shortest WOS answer)")
    ap.add_argument("-M", "--max", type=int, dest="max_len",
                    help="maximum length (default: number of tiles)")
    ap.add_argument("-e", "--exact", action="store_true",
                    help="only words using every tile (the board's big word)")
    ap.add_argument("-p", "--pattern",
                    help="positional filter; '.' or '?' is any letter, e.g. 'h.ll.'")
    ap.add_argument("-n", "--limit", type=int, default=0, metavar="N",
                    help="show at most N words per length group")
    ap.add_argument("--flat", action="store_true",
                    help="one word per line, no headers (for piping)")
    ap.add_argument("-c", "--count", action="store_true", help="show counts only")
    ap.add_argument("-d", "--dict", type=Path, default=DEFAULT_DICT, metavar="PATH",
                    help="alternate word list")
    return ap.parse_args(argv)


def choose_lengths(args, tiles: int, longest: int):
    """Decide which word lengths to search.

    Returns (lengths, notes); notes are advisory messages for the caller to show.
    Raises ValueError on an unparseable --length.
    """
    if args.exact:
        if tiles > longest:
            return [], ["no word in the list is {} letters long".format(tiles)]
        return [tiles], []

    if args.length:
        try:
            wanted = sorted({int(n) for n in args.length.replace(" ", ",").split(",") if n})
        except ValueError:
            raise ValueError(
                "Invalid length value: {!r} (expected e.g. 4,5,7)".format(args.length)
            ) from None
        notes = []
        over = [n for n in wanted if n > tiles]
        if over:
            notes.append("{} exceeds the {} tiles available".format(
                ", ".join(map(str, over)), tiles))
        return [n for n in wanted if 1 <= n <= tiles], notes

    upper = min(args.max_len if args.max_len else tiles, tiles, longest)
    return list(range(max(args.min_len, 1), upper + 1)), []


def main(argv=None) -> None:
    args = parse_args(argv)

    raw = "".join(args.letters)
    try:
        rack, wildcards = parse_rack(raw)
        tiles = sum(rack) + wildcards
        if tiles == 0:
            raise ValueError("No letters given.")
        by_length = load_index(args.dict)
        lengths, notes = choose_lengths(args, tiles, max(by_length) if by_length else 0)
    except (ValueError, FileNotFoundError) as exc:
        sys.exit(str(exc))

    for note in notes:
        print("note: " + note, file=sys.stderr)

    dict_size = sum(len(v) for v in by_length.values())
    found = solve(by_length, rack, wildcards, lengths)

    if args.pattern:
        regex = re.compile("^" + re.sub(r"[?.]", ".", args.pattern.lower().strip()) + "$")
        matched = {}
        for length, words in found.items():
            kept = [w for w in words if regex.match(w)]
            if kept:
                matched[length] = kept
        found = matched

    letters_only = tiles - wildcards
    rack_desc = " ".join(raw.lower().replace(" ", ""))
    if wildcards:
        rack_desc += "   ({} letters + {} wildcard{})".format(
            letters_only, wildcards, "" if wildcards == 1 else "s")
    else:
        rack_desc += "   ({} letters)".format(letters_only)

    render(found, args, rack_desc, dict_size)


if __name__ == "__main__":
    main()
