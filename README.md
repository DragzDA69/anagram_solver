# anagram_solver

A general-purpose anagram solver, with wildcard support for letters you do not
know yet. Runs as a local web page or from the command line.

Give it a pool of letters and it lists every word that can be spelled from them,
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
`https://dragzda69.github.io/anagram_solver/`, and Safari's **Share →
Add to Home Screen** gives it an icon that opens fullscreen.

Its JavaScript is a direct port of the Python and is tested against it for
identical output, so results match the CLI exactly.

## Command line

```
python main.py "he?ll"
```

The letters are the first argument. `?` is a wildcard standing for any one letter,
for a tile you have not identified yet. So `he?ll` finds `hell`, `help` and `hello`,
among others.

Quote the letters. In bash an unquoted `?` is a shell glob; PowerShell is fine either way.

### Options

| Option | What it does |
| --- | --- |
| `-l, --length 4,5,7` | Only these word lengths |
| `-m, --min N` | Minimum length (default 4) |
| `-M, --max N` | Maximum length (default: number of tiles) |
| `-e, --exact` | Only words using every tile — the "big word" |
| `-p, --pattern` | Positional filter, e.g. `..t..n` for a slot showing `_ _ t _ _ n` |
| `-n, --limit N` | Show at most N words per length group |
| `-c, --count` | Counts only, no words |
| `--flat` | One word per line, no headers — for piping |

`python main.py -h` shows the same list with examples. The web page exposes all of
them too — the view switcher there covers `--flat` and `--count`.

## The word list

`wordlist.txt` is **ENABLE1**, trimmed to words of 4–12 letters — 151,337 words,
one per line, CRLF. It is bundled with the repo and is the only list the solver
reads: there is nothing to pick, download or configure at runtime.

ENABLE1 is a public-domain word list, and it holds up well against real puzzle
answers — [DICTIONARY.md](DICTIONARY.md) has the testing behind the choice. The
4–12 letter trim is what keeps the file small enough to embed in the standalone
page; a rack of more than 12 tiles is unusual, and below 4 letters the results are
mostly noise.

To rebuild the file:

```
python build_wordlist.py
```

## Files

| File | |
| --- | --- |
| `main.py` | The solver, and the CLI |
| `index.html` | Standalone single-file solver — no server, works offline |
| `serve.py` | Local web server for the desktop page |
| `web/` | Desktop page assets, plus the standalone template |
| `wordlist.txt` | ENABLE1, 4–12 letters — the solver's only word list |
| `build_wordlist.py` | Regenerates `wordlist.txt` from source |
| `build_standalone.py` | Regenerates `index.html` from the template + word list |
| `DICTIONARY.md` | Why ENABLE1, and how it was verified |
