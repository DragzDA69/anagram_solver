# Which dictionary does Words on Stream use?

Onrizon, who make the game, don't publish the answer, and their FAQ explicitly declines
to expose answer lists. So it was settled empirically instead.

## The test data

[OnyxA314/words_on_stream_solver](https://github.com/OnyxA314/words_on_stream_solver)
ships `wos_dictionary.txt`, a list of **8,816 answers harvested from real Words on Stream
games** (originally compiled by Reddit user u/BandedOtter). Every entry is a word the game
actually accepted, which makes it a usable ground truth: the real dictionary must contain
all of them.

## Coverage

| Candidate list | Size | Covers 8,816 real answers |
| --- | --- | --- |
| **ENABLE1** | 172,823 | **8,815 — 99.99%** |
| SOWPODS / CSW | 267,751 | 8,816 — 100% |
| NWL2023 | 196,601 | 8,808 — 99.91% |
| NWL2020 | 191,852 | 8,808 — 99.91% |
| `words_dictionary.json` (dwyl) | 370,101 | 8,760 — 99.36% |

Coverage alone favours SOWPODS, but coverage alone is the wrong test — a big enough list
covers everything while also admitting thousands of words the game would reject.

## Ruling out the Scrabble lists

**NWL is out.** The eight answers it misses are `gila`, `gringo`, `hebe`, `nance`,
`popery`, `popish`, `spick`, `spics`. Seven of those are exactly the words NASPA
expurgated from the North American list in July 2020. Words on Stream serves them as
answers, so it isn't using NWL2020 or NWL2023.

**SOWPODS/CSW is out**, on a base-rate argument. In the 4–8 letter band the answers
occupy, 29.9% of SOWPODS words are absent from ENABLE1. If the game drew from SOWPODS,
roughly **2,638** of the 8,816 observed answers should have been SOWPODS-only words.
Exactly **one** was (`gila`). One outlier out of a predicted 2,638 is not a near miss.

**`words_dictionary.json` is out.** It misses 56 real answers — ordinary modern words
like `carbs`, `decaf`, `latte`, `futon`, `expat`, `foodie` — while being more than twice
the size of ENABLE1 with a large tail of junk entries. Worst of both.

That leaves ENABLE1: it covers 8,815 of 8,816, is public domain (NWL and CSW are both
copyrighted, which matters to a commercial game), and is the long-standing default for
open word games.

## Corroborating detail

[clarkio/wos-plus](https://github.com/clarkio/wos-plus), an actively maintained companion
tool for the game, independently confirms the mechanics this solver is built around:

- "Words on Stream only uses words of 4 or more letters."
- A board's valid letters are exactly the letters of its big word, 4–12 letters long.
- A `?` in the available letters "is treated as a wildcard that matches any single
  letter, which is how a level's still-hidden letters (level 19+) appear before they're
  revealed" — the same semantics this solver implements.
- Boards also carry *false letters* that belong to no answer.

## The one outlier

`gila` is in SOWPODS but not ENABLE1, and appears in the harvested answers. It is either
a small Words on Stream addition or a capture artifact in the harvested list. At one word
in 8,816 it isn't worth corrupting a clean, reproducible source over, so `wordlist.txt`
is plain ENABLE1.

## Reproducing

`build_wordlist.py` pulls ENABLE1 from
[dolph/dictionary](https://github.com/dolph/dictionary) and trims it to 4–12 letters
(151,337 words, down from 172,823).

The bounds are chosen to discard only words the game could never use. Nothing under
4 letters is ever an answer, and a board holds at most 12 letters, so a 13-letter word
has no board that could spell it. The longest answer in the 8,816 harvested is 8 letters,
and `wos-plus` likewise reports 8 as the longest in its live database, so 12 is already a
wide cushion. `python build_wordlist.py --min 3 --max 15` widens it again if a board ever
contradicts this.

The ENABLE1 copy was cross-checked against Peter Norvig's mirror: they differ by
three words (`knickknack`, `razzmatazz`, `razzmatazzes`), all legitimate and all present in
both SOWPODS and NWL2023, so the larger copy is used.
