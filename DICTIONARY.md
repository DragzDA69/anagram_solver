# Which word list does this solver use?

`wordlist.txt` is ENABLE1, trimmed to 4–12 letters. That choice wasn't arbitrary: several
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

`build_wordlist.py` pulls ENABLE1 from
[dolph/dictionary](https://github.com/dolph/dictionary) and trims it to 4–12 letters
(151,337 words, down from 172,823).

The bounds keep the file small enough to embed in the standalone page while discarding
almost nothing useful. Words under 4 letters are mostly noise in anagram results, and a
rack of more than 12 tiles is unusual — the longest answer in the 8,816 harvested is
8 letters, so 12 is already a wide cushion. `python build_wordlist.py --min 3 --max 15`
widens the trim if you need it.

The ENABLE1 copy was cross-checked against Peter Norvig's mirror: they differ by
three words (`knickknack`, `razzmatazz`, `razzmatazzes`), all legitimate and all present in
both SOWPODS and NWL2023, so the larger copy is used.
