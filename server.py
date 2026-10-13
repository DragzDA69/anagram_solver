#!/usr/bin/env python3
"""Local web UI for the Anagram Solver.

Serves web/index.html and answers its requests by calling the very same
functions main.py uses, so the page and the CLI can never drift apart.

    python serve.py              ->  http://127.0.0.1:8000
    python serve.py --port 9000 --no-browser

Standard library only, and it binds to localhost: nothing is exposed off
this machine.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
WEB = HERE / "web"
WORDLIST = HERE / "wordlist.txt"
sys.path.insert(0, str(HERE))

import main as solver  # noqa: E402  (needs HERE on sys.path first)

# Explicit allowlist: the server never resolves a client-supplied path.
STATIC = {
    "/": (WEB / "index.html", "text/html; charset=utf-8"),
    "/index.html": (WEB / "index.html", "text/html; charset=utf-8"),
    "/style.css": (WEB / "style.css", "text/css; charset=utf-8"),
    "/app.js": (WEB / "app.js", "text/javascript; charset=utf-8"),
}

MAX_BODY = 64 * 1024
MAX_WORDS = 5000  # cap the payload; '????????????' would otherwise return 151k

_index: dict | None = None
_lock = threading.Lock()


def get_index() -> dict:
    """Load and cache the bundled word list."""
    global _index
    with _lock:
        if _index is None:
            _index = solver.load_index(WORDLIST)
        return _index


def run_solve(req: dict) -> dict:
    """Validate a request and solve it. Raises ValueError for anything bad."""
    rack, wildcards = solver.parse_rack(str(req.get("letters", "")))
    tiles = sum(rack) + wildcards
    if tiles == 0:
        raise ValueError("No letters given.")

    by_length = get_index()

    def as_int(key, default=0):
        raw = str(req.get(key, "")).strip()
        if not raw:
            return default
        try:
            return int(raw)
        except ValueError:
            raise ValueError("{} must be a whole number".format(key)) from None

    args = SimpleNamespace(
        exact=bool(req.get("exact")),
        length=str(req.get("length", "")).strip(),
        min_len=as_int("min", 4),
        max_len=as_int("max", 0) or None,
    )
    lengths, notes = choose(args, tiles, by_length)
    found = solver.solve(by_length, rack, wildcards, lengths)

    pattern = str(req.get("pattern", "")).strip()
    if pattern:
        import re
        regex = re.compile("^" + re.sub(r"[?.]", ".", pattern.lower()) + "$")
        found = {L: kept for L, words in found.items()
                 if (kept := [w for w in words if regex.match(w)])}

    limit = as_int("limit", 0)
    total = sum(len(v) for v in found.values())

    groups, shown, truncated = [], 0, False
    for length in sorted(found, reverse=True):
        words = found[length]
        take = words[:limit] if limit > 0 else words
        if shown + len(take) > MAX_WORDS:
            take = take[: max(0, MAX_WORDS - shown)]
            truncated = True
        shown += len(take)
        groups.append({"length": length, "count": len(words), "words": take})
        if truncated:
            break

    if truncated:
        notes = notes + ["output capped at {:,}".format(MAX_WORDS)]

    return {
        "ok": True,
        "rack": {"letters": tiles - wildcards, "wildcards": wildcards, "tiles": tiles},
        "groups": groups,
        "total": total,
        "truncated": truncated,
        "notes": notes,
        "dictSize": sum(len(v) for v in by_length.values()),
    }


def choose(args, tiles: int, by_length: dict):
    return solver.choose_lengths(args, tiles, max(by_length) if by_length else 0)


class Handler(BaseHTTPRequestHandler):
    server_version = "AnagramSolver"

    def log_message(self, fmt, *a):  # quieter console
        pass

    # -- helpers --
    def send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, code: int, obj: dict) -> None:
        self.send(code, json.dumps(obj).encode("utf-8"), "application/json")

    # -- routes --
    def do_GET(self) -> None:
        route = self.path.split("?", 1)[0]

        entry = STATIC.get(route)
        if entry is None:
            return self.send(404, b"Not found", "text/plain; charset=utf-8")
        path, ctype = entry
        try:
            return self.send(200, path.read_bytes(), ctype)
        except FileNotFoundError:
            return self.send(500, b"Missing file: " + path.name.encode(),
                             "text/plain; charset=utf-8")

    def do_POST(self) -> None:
        if self.path.split("?", 1)[0] != "/api/solve":
            return self.send(404, b"Not found", "text/plain; charset=utf-8")

        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            return self.send_json(413, {"ok": False, "error": "Request too large."})

        try:
            try:
                req = json.loads(self.rfile.read(length) or b"{}")
            except json.JSONDecodeError:
                raise ValueError("Malformed request body.") from None
            if not isinstance(req, dict):
                raise ValueError("Malformed request body.")
            return self.send_json(200, run_solve(req))
        except (ValueError, FileNotFoundError) as exc:
            return self.send_json(200, {"ok": False, "error": str(exc)})
        except Exception as exc:  # noqa: BLE001 - never kill the server on one request
            return self.send_json(200, {"ok": False, "error": "Solver error: {}".format(exc)})


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="Local web UI for the solver.")
    ap.add_argument("-p", "--port", type=int, default=8000)
    ap.add_argument("--no-browser", action="store_true", help="don't open a browser")
    return ap.parse_args(argv)


def run(argv=None) -> None:
    args = parse_args(argv)

    missing = [p.name for _, (p, _) in STATIC.items() if not p.exists()]
    if missing:
        sys.exit("Missing web files: {}".format(", ".join(sorted(set(missing)))))

    try:
        size = sum(len(v) for v in get_index().values())
    except (ValueError, FileNotFoundError) as exc:
        sys.exit(str(exc))

    url = "http://127.0.0.1:{}".format(args.port)
    try:
        httpd = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    except OSError as exc:
        sys.exit("Could not start on port {}: {}\nTry --port 8001.".format(args.port, exc))

    print("Anagram Solver  ->  {}".format(url), flush=True)
    print("{:,} words loaded. Ctrl+C to stop.".format(size), flush=True)
    if not args.no_browser:
        threading.Timer(0.4, webbrowser.open, (url,)).start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    run()
