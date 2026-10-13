# words_on_stream_solver

An anagram solver for the Twitch/YouTube game **Words on Stream**, with wildcard
support for letters the board hasn't revealed yet. Runs as a local web page or
from the command line.

Give it the board letters and it lists every word that can be spelled from them,
grouped longest-first.

## Web page

```
python serve.py
```

Opens a local page at `http://127.0.0.1:8000` with a letters box, every option
below as a toggle or field, and a live results panel. It solves as you type.

The page calls straight into the same solver the CLI uses, so the two can't drift
apart. Standard library only, nothing downloaded at runtime, and it binds to
localhost — nothing is exposed off your machine. `--port` moves it, `--no-browser`
stops it opening a tab.

## On a phone, or anywhere without Python

`index.html` is the whole solver in a single self-contained file — the dictionary
and the matching code are embedded, so it needs no server, no install and no
network once loaded. Open it in any browser and it works offline.

```
python build_standalone.py
```

rebuilds it from `wordlist.txt` (633 KB, ~25 ms to start, a few ms per solve).

The easiest way onto a phone is GitHub Pages: in the repo's **Settings → Pages**,
set the source to the `main` branch, root folder. The page is then live at
`https://dragzda69.github.io/words_on_stream_solver/`, and Safari's **Share →
Add to Home Screen** gives it an icon that opens fullscreen.

Its JavaScript is a direct port of the Python and is tested against it for
identical output, so results match the CLI exactly.

## Command line

```
python main.py "he?ll"
```

The letters are the first argument. `?` is a wildcard standing for any one letter —
the same way Words on Stream displays an unrevealed tile from level 19 onward. So
`he?ll` finds `hell`, `help` and `hello`, among others.

Quote the letters. In bash an unquoted `?` is a shell glob; PowerShell is fine either way.

### Options

| Option | What it does |
| --- | --- |
| `-l, --length 4,5,7` | Only these word lengths — match them to the level's slots |
| `-m, --min N` | Minimum length (default 4) |
| `-M, --max N` | Maximum length (default: number of tiles) |
| `-e, --exact` | Only words using every tile — the board's "big word" |
| `-p, --pattern` | Positional filter, e.g. `..t..n` for a slot showing `_ _ t _ _ n` |
| `-n, --limit N` | Show at most N words per length group |
| `-c, --count` | Counts only, no words |
| `--flat` | One word per line, no headers — for piping |
| `-d, --dict PATH` | Use a different word list |

`python main.py -h` shows the same list with examples. The web page exposes all of
them too — the view switcher there covers `--flat` and `--count`.

## The dictionary

`wordlist.txt` is **ENABLE1**, trimmed to words of 4–12 letters — 151,337 words,
one per line, CRLF.

The trim is lossless for this game. Words on Stream never uses words shorter than
4 letters, and a board carries at most 12 letters, so a 13-letter word could never
be spelled from one. The longest answer ever observed in real games is 8 letters,
which leaves 12 a generous ceiling.

ENABLE1 is a public-domain word list and, on the evidence, the list Words on Stream
actually uses for English. Checked against 8,816 answers harvested from real games it
scores 99.99%, where the Scrabble lists (NWL, CSW) and the generic `words_dictionary.json`
each get measurably worse results. [DICTIONARY.md](DICTIONARY.md) has the testing behind that.

To rebuild the file:

```
python build_wordlist.py
```

## Notes on the game

A few things worth knowing, since they affect how you'd use the flags:

- A board's letters are exactly the letters of its **big word**, so `-e` finds it.
- Levels show you how many words of each length to look for. Feed those to `-l`.
- Higher levels mix in **false letters** that belong to no answer. Once one is
  revealed, drop it from the input and re-run.

## Files

| File | |
| --- | --- |
| `main.py` | The solver, and the CLI |
| `index.html` | Standalone single-file solver — no server, works offline |
| `serve.py` | Local web server for the desktop page |
| `web/` | Desktop page assets, plus the standalone template |
| `wordlist.txt` | ENABLE1, 4–12 letters |
| `build_wordlist.py` | Regenerates `wordlist.txt` from source |
| `build_standalone.py` | Regenerates `index.html` from the template + word list |
| `DICTIONARY.md` | Why ENABLE1, and how it was verified |
