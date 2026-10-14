#!/usr/bin/env python3
"""What each help page says: the top-level page, and one per command.

The option tables are not written here -- they are read off the argparse parser
that main.py already builds, so a flag added there shows up here on its own.
"""

from __future__ import annotations

from cli.ansi import BRIGHT, PRIMARY, SECONDARY, colored
from cli.help import (
    format_line_pacing,
    options_width,
    pad_to,
    get_help_header,
    get_tabs,
    option_rows,
    print_command_header,
    print_global_options,
    print_lines,
    print_options,
)

# Summaries do double duty: the list on the top-level page, and the line inside
# each command's own header box.
SUMMARIES = {
    "solve": "Find every word spellable from the board letters.",
    "run": "Start the local web server and open the page in a browser.",
    "open": "Open the hosted page in a browser.",
    "update": "Update the dictionary and rebuild the standalone HTML page.",
}

USAGE = {
    "solve": "<letters> [--args]",
    "run": "",
    "open": "",
    "update": "[-d] [-b] [--src <file>]",
}


def _command_list():
    rows = []
    for name, summary in SUMMARIES.items():
        label = colored(name, PRIMARY)
        rows.append(format_line_pacing(
            label, summary,
            indent=get_tabs(2)))
    return rows


def print_top_level(site_url):
    """`python main.py -h`, and the page a bare invocation lands on."""
    print(get_help_header())

    print("Available Commands:")
    for row in _command_list():
        print(row)
    print("")

    print("Usage:")
    print(get_tabs(2) + "> python main.py"
          + colored(" <command>", PRIMARY)
          + colored(" [letters]", SECONDARY)
          + colored(" [--args] [-h]", BRIGHT))
    print("")
    print(get_tabs(2) + colored(
        "Use solve followed by the anagram. Without a command, this help is shown.",
        SECONDARY, attrs=["italic"]))
    print("")

    print_global_options()
    print("")

    print_lines("Examples:", [
        colored('> python main.py solve "he?lpf"', BRIGHT),
        colored('> python main.py solve "caution" -l 4,5,7', BRIGHT),
        colored("> python main.py run", BRIGHT),
        colored("> python main.py open", BRIGHT),
        colored("> python main.py update", BRIGHT),
        colored("> python main.py update -d", BRIGHT),
        colored("> python main.py update -b", BRIGHT),
    ])

    print_lines("Help Examples:", [
        colored("> python main.py -h", BRIGHT),
        colored("> python main.py solve -h", BRIGHT),
        colored("> python main.py run -h", BRIGHT),
        colored("> python main.py open -h", BRIGHT),
        colored("> python main.py update -h", BRIGHT),
    ])


def print_solve(parser):
    rows = option_rows(parser)
    print_command_header("solve", summary=[
        SUMMARIES["solve"],
        "Each letter is a tile and may be used only as many times as it appears.",
    ], option_args=[label.split(",")[0] for label, _ in rows] + ["-h"])

    print("Usage:")
    print(get_tabs(2) + "> python main.py"
          + colored(" solve", PRIMARY)
          + colored(" <letters>", SECONDARY)
          + colored(" [--args]", BRIGHT))
    print("")
    print(get_tabs(2) + colored(
        "The solve command is required before the anagram letters.",
        SECONDARY, attrs=["italic"]))
    print("")

    width = options_width(rows)
    print_options(rows, width=width)
    print("")
    print_global_options(width=width)
    print("")

    # One column for the command, one for what it shows -- padded, not tabbed.
    examples = [
        ('> python main.py solve "he?lpf"', "every word from  h e ? l p f"),
        ('> python main.py solve "caution" -l 4,5,7', "only the word lengths you need"),
        ('> python main.py solve "caution" -e', "the big word (uses every letter)"),
        ('> python main.py solve "ca?tion" -p "..t..n"', "a pattern showing  _ _ t _ _ n"),
        ("> python main.py solve open", "letters that spell a command name"),
    ]
    column = max(len(command) for command, _ in examples) + 2
    print_lines("Examples:", [
        pad_to(colored(command, BRIGHT), column) + colored(note, SECONDARY)
        for command, note in examples
    ])

    print(colored(
        "Quote the letters: in bash an unquoted ? is a shell glob.",
        SECONDARY, attrs=["italic"]))
    print("")


def print_run(parser):
    print_command_header("run", summary=[
        SUMMARIES["run"],
        "Rebuilds the standalone page before starting the server.",
        "Solves as you type, using this same solver behind the page.",
    ], option_args=["-h"])

    print("Usage:")
    print(get_tabs(2) + "> python main.py" + colored(" run", PRIMARY))
    print("")

    print_global_options()
    print("")

    print_lines("Notes:", [
        colored("Rebuilds index.html on startup and each server restart.", SECONDARY),
        colored("Serves http://127.0.0.1:8000 and opens it in your browser.", SECONDARY),
        colored("Binds to localhost only -- nothing is exposed off this machine.", SECONDARY),
        colored("If the port is busy on Windows: Y replaces the process; N/Esc cancels.", SECONDARY),
        "",
        colored("While it runs:", SECONDARY),
        colored("Ctrl+R", BRIGHT) + colored("   restart -- reloads ui.py, main.py and the word list",
                                            SECONDARY),
        colored("Ctrl+O", BRIGHT) + colored("   the same, and reopen the page in a browser",
                                            SECONDARY),
        colored("Ctrl+C", BRIGHT) + colored("   stop", SECONDARY),
        "",
        colored("For a different port, or to skip the browser, call the server direct:", SECONDARY),
        colored("> python server.py --port 9000 --no-browser", BRIGHT),
    ])


def print_open(parser, site_url):
    print_command_header("open", summary=[
        SUMMARIES["open"],
        "An errand, not a search: nothing is solved and no letters are needed.",
    ], option_args=["-h"])

    print("Usage:")
    print(get_tabs(2) + "> python main.py" + colored(" open", PRIMARY))
    print("")

    print_global_options()
    print("")

    print_lines("Notes:", [
        colored("Opens ", SECONDARY) + colored(site_url, BRIGHT, attrs=["underline"]),
        colored("That page is the standalone build -- it needs no server and", SECONDARY),
        colored("works offline once loaded.", SECONDARY),
        "",
        colored("For the local copy instead:", SECONDARY),
        colored("> python main.py run", BRIGHT),
    ])


def print_update(parser):
    rows = option_rows(parser)
    print_command_header("update", summary=[
        SUMMARIES["update"],
        "Keeps every word length; use solve's min/max options to filter results.",
    ], option_args=[label.split(",")[0] for label, _ in rows] + ["-h"])

    print_lines("Usage:", [
        colored("> python main.py update", BRIGHT),
        colored("> python main.py update -d", BRIGHT),
        colored("> python main.py update -b", BRIGHT),
        colored("> python main.py update --src enable1.txt", BRIGHT),
    ])
    width = options_width(rows)
    print_options(rows, width=width)
    print("")
    print_global_options(width=width)
    print("")
    print_lines("Notes:", [
        colored("No selection flags: update the dictionary, then rebuild the HTML.", SECONDARY),
        colored("Dictionary updates need internet unless --src supplies a local file.", SECONDARY),
        colored("A failed update leaves the existing word list unchanged.", SECONDARY),
        colored("Restart the local server to reload the updated dictionary.", SECONDARY),
        colored("Build-only updates use the existing dictionary and work offline.", SECONDARY),
    ])
