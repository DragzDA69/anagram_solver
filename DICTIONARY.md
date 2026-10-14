# Which word list does this solver use?

`wordlist.txt` is the complete ENABLE1 list, with all word lengths. That choice wasn't arbitrary: several
candidate lists were tested against a corpus of real, known-good answers, and ENABLE1 won.
This file records the testing, so the choice can be re-checked rather than taken on faith.

## The test data

The ground truth is a public corpus of **8,816 answers harvested from real games** of a
live word puzzle, originally compiled by Reddit user u/BandedOtter and shipped as
`wos_dictionary.txt` in
[OnyxA314/words_on_stream_solver](https://github.com/OnyxA314/words_on_stream_solver).
Every entry is a word that was actually accepted in play, which makes it usable as a floor:
a good general word list must contain all of them.

## Coverage

| Candidate list | Size | Covers 8,816 real answers |
| --- | --- | --- |
| **ENABLE1** | 172,823 | **8,815 — 99.99%** |
| SOWPODS / CSW | 267,751 | 8,816 — 100% |
| NWL2023 | 196,601 | 8,808 — 99.91% |
| NWL2020 | 191,852 | 8,808 — 99.91% |
| `words_dictionary.json` (dwyl) | 370,101 | 8,760 — 99.36% |

Coverage alone favours SOWPODS, but coverage alone is the wrong test — a big enough list
covers everything while also admitting thousands of words no ordinary reader would accept.

## Ruling out the Scrabble lists

**NWL is out.** The eight answers it misses are `gila`, `gringo`, `hebe`, `nance`,
`popery`, `popish`, `spick`, `spics`. Seven of those are exactly the words NASPA
expurgated from the North American list in July 2020. The corpus contains them as
accepted answers, so NWL2020 and NWL2023 are both too narrow.

**SOWPODS/CSW is out**, on a base-rate argument. In the 4–8 letter band the answers
occupy, 29.9% of SOWPODS words are absent from ENABLE1. If the corpus had been drawn from
SOWPODS, roughly **2,638** of the 8,816 answers should have been SOWPODS-only words.
Exactly **one** was (`gila`). One outlier out of a predicted 2,638 is not a near miss.

**`words_dictionary.json` is out.** It misses 56 real answers — ordinary modern words
like `carbs`, `decaf`, `latte`, `futon`, `expat`, `foodie` — while being more than twice
the size of ENABLE1 with a large tail of junk entries. Worst of both.

That leaves ENABLE1: it covers 8,815 of 8,816, is public domain (NWL and CSW are both
copyrighted), and is the long-standing default for open word games.

## The one outlier

`gila` is in SOWPODS but not ENABLE1, and appears in the harvested answers. It is either
a one-off addition in the source list or a capture artifact in the harvest. At one word
in 8,816 it isn't worth corrupting a clean, reproducible source over, so `wordlist.txt`
is plain ENABLE1.

## Reproducing

Run `python main.py update` to download ENABLE1 from
[Peter Norvig's copy](https://norvig.com/ngrams/enable1.txt) and save all words
to `wordlist.txt`. `python build_wordlist.py` runs the same updater directly.

The updater does not trim by length: the solver's min/max options control the
results (the default minimum remains 4). Use `python main.py update --src enable1.txt`
to update from a local copy without internet. Failed updates leave the existing
list unchanged. Restart a running local server to reload it, and run
`python build_standalone.py` to include the new list in the standalone page.

### One caveat on reproducing

The copies of ENABLE1 in circulation are not quite identical. The original bundled
list was trimmed to 4–12 letters (151,337 words) and built from
[dolph/dictionary](https://github.com/dolph/dictionary), which carries three words
Norvig's copy does not: `knickknack`, `razzmatazz`, `razzmatazzes`. All three are
legitimate and present in both SOWPODS and NWL2023.

The updater uses Norvig's copy, so those three entries are not included in the
current bundled list. To use the dolph copy instead, supply it with `--src`.
