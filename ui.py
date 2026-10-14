#!/usr/bin/env python3
"""Every user-facing string and UI setting for both pages, in one place.

The desktop page and the standalone single-file build are separate documents,
so a label or a timing written into each of them drifts the moment one is
edited. Instead both carry `{{key}}` placeholders, and the values live here:

    server.py             fills them in as it serves a file
    build_standalone.py   fills them in once, when it builds index.html

Change a value here and both pages follow. HTML is allowed in a value -- it is
substituted before the browser ever sees it -- which is what lets a hint keep
its <kbd> tag. Numbers are substituted bare, so a key can be dropped straight
into CSS or JS: `}, {{toast_ms}});`.

Templated files keep their placeholders on disk, so opening web/index.html
straight from the filesystem shows `{{...}}` rather than the copy. Serve it
with server.py, or use the built index.html.

    python ui.py          print every key and its value
"""

from __future__ import annotations

import re

# The two halves of the name are separate because the standalone's header
# styles them differently; app_name joins them for the title bars.
BRAND_LEAD = "Anagram"
BRAND_TAIL = "Solver"

# How long a copy toast sits on screen, and how long it takes to slide in or
# out. The fade drives both the CSS transition and the JS that removes the
# element afterwards, so the two can never fall out of step.
TOAST_MS = 2000
TOAST_FADE_MS = 220

VALUES: dict[str, object] = {
    # -- identity ----------------------------------------------------------
    "app_name": "{} {}".format(BRAND_LEAD, BRAND_TAIL),
    "brand_lead": BRAND_LEAD,
    "brand_tail": BRAND_TAIL,
    # Two sentences, kept apart: the header puts each in its own inline-block,
    # so a line break lands between them rather than mid-sentence.
    "dict_info_source": "Finds all possible words that can be made from an anagram.",
    "dict_info_wildcards": "Use <kbd>?</kbd> wildcard for unknown letters.",
    "meta_loading": "loading dictionary&hellip;",

    # -- panels ------------------------------------------------------------
    "panel_search": "Search",
    "panel_options": "Options",

    # -- the letters field -------------------------------------------------
    "label_letters": "Anagram Input",
    "ph_letters": "he?lpf",
    "hint_letters": "Letters only. Use <kbd>?</kbd> for any letters that haven't been revealed.",
    "title_wildcard": "Insert a wildcard",
    "title_clear": "Clear",

    # -- options -----------------------------------------------------------
    "label_lengths": "Word length<small>s</small>",
    "ph_lengths": "4,5,7",
    "hint_lengths": "Only these lengths",

    "label_min": "Min length",
    "hint_min": "Shortest word to look for",

    "label_max": "Max length",
    "ph_max": "letters",
    "hint_max": "Defaults to letter count",

    "label_pattern": "Pattern",
    "ph_pattern": "..t..n",
    "hint_pattern": "Position filter, <kbd>.</kbd> = any letter, <kbd>?</kbd> = wildcard",

    "label_exclude": "Exclude letters",
    "ph_exclude": "xyz",
    "hint_exclude": "Drop words using any of these",

    "label_limit": "Limit per group",
    "ph_limit": "all",
    "hint_limit": "0 or blank shows all",

    "toggle_exact": "Use Maximum Letters",
    "toggle_exact_note": "word requires every letter to be used *",

    # -- controls ----------------------------------------------------------
    "view_grouped": "Grouped",
    "view_flat": "Flat",
    "view_counts": "Counts",
    "btn_solve": "Solve",

    # -- messages the scripts show ----------------------------------------
    "msg_prompt": "Enter the anagram letters to begin.",
    "hint_click_copy": "Click any word to copy it to the clipboard.",
    "msg_no_match": "No words match.",
    "msg_loading_dict": "Loading dictionary&hellip;",
    "msg_copy_failed": "Clipboard blocked by the browser",
    "toast_copied_suffix": " was copied to the clipboard",

    # -- timings (milliseconds; used by both the CSS and the scripts) ------
    "toast_ms": TOAST_MS,
    "toast_fade_ms": TOAST_FADE_MS,
}

PLACEHOLDER = re.compile("[{]{2}([a-z0-9_]+)[}]{2}")


def render(text: str, where: str = "") -> str:
    """Replace every {{key}} in `text`. An unknown key is an error, so a typo
    fails the build instead of shipping a literal `{{key}}` to the page."""
    missing = sorted({m.group(1) for m in PLACEHOLDER.finditer(text)} - set(VALUES))
    if missing:
        raise KeyError("{}: no such value{}: {}".format(
            where or "template", "" if len(missing) == 1 else "s", ", ".join(missing)))
    return PLACEHOLDER.sub(lambda m: str(VALUES[m.group(1)]), text)


if __name__ == "__main__":
    for key, value in VALUES.items():
        print("{:<22} {}".format(key, value))
