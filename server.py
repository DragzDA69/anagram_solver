#!/usr/bin/env python3
"""Local web UI for the Anagram Solver.

Serves web/index.html and answers its requests by calling the very same
functions main.py uses, so the page and the CLI can never drift apart.

    python server.py             ->  http://127.0.0.1:8000
    python server.py --port 9000 --no-browser

While it is running:

    Ctrl+R   restart -- reloads ui.py, main.py and wordlist.txt
    Ctrl+O   the same, and reopen the page in a browser
    Ctrl+C   stop

Standard library only, and it binds to localhost: nothing is exposed off
this machine.
"""

from __future__ import annotations

import importlib
import errno
import json
import os
import queue
import socket
import subprocess
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from dataclasses import dataclass

try:
    import msvcrt
except ImportError:   # not Windows: the hotkeys are skipped, Ctrl+C still works
    msvcrt = None

HERE = Path(__file__).resolve().parent
WEB = HERE / "web"
WORDLIST = HERE / "wordlist.txt"
sys.path.insert(0, str(HERE))

import main as solver  # noqa: E402  (needs HERE on sys.path first)
import ui  # noqa: E402
from cli.messages import ArgumentParser, fail, info, success, warning  # noqa: E402


class LocalHTTPServer(ThreadingHTTPServer):
    # Windows SO_REUSEADDR can bind over a live listener and serve stale pages.
    allow_reuse_address = sys.platform != "win32"

    def server_bind(self) -> None:
        if sys.platform == "win32":
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()

# Explicit allowlist: the server never resolves a client-supplied path.
# The flag says whether the file carries {{...}} placeholders for ui.py
# to fill in on the way out.
STATIC = {
    "/": (WEB / "index.html", "text/html; charset=utf-8", True),
    "/index.html": (WEB / "index.html", "text/html; charset=utf-8", True),
    "/style.css": (WEB / "style.css", "text/css; charset=utf-8", True),
    "/app.js": (WEB / "app.js", "text/javascript; charset=utf-8", True),
    "/icon.png": (HERE / "icon.png", "image/png", False),
}

MAX_BODY = 64 * 1024
MAX_WORDS = 5000  # cap the payload; '????????????' would otherwise return 151k

_index: dict | None = None
_lock = threading.Lock()
_ui_lock = threading.Lock()
_ui_stamp: tuple[int, int] | None = None

# Hotkeys, as MiRTG Tool's npm watch does them: a daemon thread blocking on
# getwch() and posting to a queue, so the main thread can wait on one place.
CTRL_C_KEY = "\x03"
CTRL_O_KEY = "\x0f"
CTRL_R_KEY = "\x12"
SPECIAL_KEY_PREFIXES = {"\x00", "\xe0"}   # first half of an arrow/function key


def has_console_keyboard() -> bool:
    """Whether keys can be read at all -- not on a pipe, and not off Windows."""
    return msvcrt is not None and sys.stdin.isatty()


def keyboard_listener(events: "queue.Queue", stop: threading.Event) -> None:
    while not stop.is_set():
        if not msvcrt.kbhit():
            stop.wait(0.05)
            continue
        try:
            key = msvcrt.getwch()
        except OSError:
            break
        if stop.is_set():
            break
        if not key or key in SPECIAL_KEY_PREFIXES:
            continue   # drop the scan-code half, so an arrow key is not a command
        if key == CTRL_R_KEY:
            events.put("restart")
        elif key == CTRL_O_KEY:
            events.put("reopen")
        elif key == CTRL_C_KEY:
            # getwch() swallows the interrupt, so it is forwarded by hand.
            events.put("stop")


@dataclass(frozen=True)
class PortProcess:
    pid: int
    name: str
    started: int


def _port_query(port: int) -> str:
    return (
        "$owners = @(Get-NetTCPConnection -State Listen -ErrorAction Stop | "
        "Where-Object { $_.LocalPort -eq " + str(port) +
        " -and $_.LocalAddress -in @('127.0.0.1', '0.0.0.0', '::') } | "
        "Select-Object -ExpandProperty OwningProcess -Unique); "
    )


def _powershell(script: str) -> str:
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
             "$ErrorActionPreference = 'Stop'; "
             "[Console]::OutputEncoding = [Text.UTF8Encoding]::new(); " + script],
            capture_output=True, text=True, encoding="utf-8", check=True,
        )
    except subprocess.CalledProcessError as exc:
        fail("Could not manage the process using this port. "
             "Stop it in its original terminal, or use another port.\nDetails: " +
             (exc.stderr or str(exc)).strip())
    except OSError as exc:
        fail("Could not check the occupied port.\nDetails: {}".format(exc))
    return result.stdout


def port_processes(port: int) -> list[PortProcess]:
    raw = _powershell(_port_query(port) +
        "$items = @($owners | ForEach-Object { $p = Get-Process -Id $_; "
        "@{pid=$p.Id; name=$p.ProcessName; started=$p.StartTime.ToUniversalTime().Ticks} }); "
        "ConvertTo-Json -InputObject $items -Compress")
    try:
        return [PortProcess(int(p["pid"]), str(p["name"]), int(p["started"]))
                for p in json.loads(raw)]
    except (ValueError, KeyError, TypeError) as exc:
        fail("Could not identify the process using this port.\nDetails: {}".format(exc))


def confirm_port_replacement(port: int, processes: list[PortProcess]) -> bool:
    warning("Port {} is already in use by {}.".format(
        port, ", ".join("{} (PID {})".format(p.name, p.pid) for p in processes)))
    warning("Stopping these processes will end any other work they are doing.")
    print("Stop them and start a fresh server here? [Y/N] (Esc cancels): ",
          end="", flush=True)
    while True:
        key = msvcrt.getwch()
        if key in SPECIAL_KEY_PREFIXES:
            msvcrt.getwch()
            continue
        if key.lower() == "y":
            info("Y")
            return True
        if key.lower() == "n" or key in ("\x1b", CTRL_C_KEY):
            info("N" if key.lower() == "n" else "")
            info("Startup cancelled. The existing process was left running.")
            return False


def stop_port_processes(port: int, processes: list[PortProcess]) -> None:
    # Recheck port ownership and process start time, so a reused PID is not killed.
    for process in processes:
        if process.pid == os.getpid() or process.pid <= 4:
            fail("This process cannot safely be stopped automatically.")
        _powershell(_port_query(port) +
            "$p = Get-Process -Id " + str(process.pid) + " -ErrorAction SilentlyContinue; "
            "if ($null -ne $p) { "
            "if ($owners -notcontains $p.Id -or "
            "$p.StartTime.ToUniversalTime().Ticks -ne " + str(process.started) + ") { "
            "throw 'The process using the port changed. No process was stopped.' }; "
            "Stop-Process -Id $p.Id -ErrorAction Stop; "
            "if (-not $p.WaitForExit(5000)) { throw 'The process did not stop in time.' } }")
    success("The previous process has stopped.")


def start_http_server(port: int) -> LocalHTTPServer:
    try:
        return LocalHTTPServer(("127.0.0.1", port), Handler)
    except OSError as exc:
        occupied = exc.errno == errno.EADDRINUSE or getattr(exc, "winerror", None) == 10048
        if not occupied or sys.platform != "win32" or not has_console_keyboard():
            fail("Could not start the server on port {}. Stop any earlier server, "
                 "or use 'python server.py --port 8001'.\nDetails: {}".format(port, exc))

    processes = port_processes(port)
    if not processes:
        fail("Port {} is unavailable, but no listening process could be identified. "
             "Try again or use another port.".format(port))
    if not confirm_port_replacement(port, processes):
        raise SystemExit(0)
    stop_port_processes(port, processes)
    try:
        return LocalHTTPServer(("127.0.0.1", port), Handler)
    except OSError as exc:
        fail("The previous process was stopped, but the server could not start. "
             "Try another port.\nDetails: {}".format(exc))


def rebuild_standalone() -> None:
    """Use a fresh process so the builder reads the current UI copy from disk."""
    info("Recompiling the web page...")
    try:
        subprocess.run(
            [sys.executable, str(HERE / "build_standalone.py")],
            cwd=HERE, check=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        fail("Could not rebuild the page; server not started.\nDetails: {}".format(exc))


def reload_sources() -> None:
    """Pick up edits to the solver and the shared copy without a fresh process.

    The word index is cached and ui.VALUES lives in memory, so neither notices a
    file change on its own -- which is the whole reason Ctrl+R is worth having.
    """
    global _index
    with _lock:
        _index = None
    importlib.reload(solver)
    global _ui_stamp
    with _ui_lock:
        _ui_stamp = None


def render_ui(text: str, where: str) -> str:
    """Keep labels in step with templates served from disk, across requests."""
    global _ui_stamp
    with _ui_lock:
        source = Path(ui.__file__)
        stat = source.stat()
        stamp = (stat.st_mtime_ns, stat.st_size)
        if stamp != _ui_stamp:
            importlib.invalidate_caches()
            importlib.reload(ui)
            _ui_stamp = stamp
        return ui.render(text, where)


def validate_ui() -> None:
    for path, _, templated in set(STATIC.values()):
        if templated:
            render_ui(path.read_text(encoding="utf-8"), path.name)


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

    excluded = solver.parse_exclusions(str(req.get("exclude", "")))
    if excluded:
        found = solver.filter_excluded(found, excluded)
        notes = notes + ["excluding " + ", ".join(sorted(excluded))]

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
        path, ctype, templated = entry
        try:
            body = path.read_bytes()
        except FileNotFoundError:
            return self.send(500, b"Missing file: " + path.name.encode(),
                             "text/plain; charset=utf-8")
        if templated:
            # Rendered per request, so an edit to ui.py shows up on reload.
            try:
                body = render_ui(body.decode("utf-8"), path.name).encode("utf-8")
            except (KeyError, OSError, UnicodeError, SyntaxError) as exc:
                return self.send(500, str(exc).encode(), "text/plain; charset=utf-8")
        return self.send(200, body, ctype)

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
    ap = ArgumentParser(description="Local web UI for the solver.")
    ap.add_argument("-p", "--port", type=int, default=8000)
    ap.add_argument("--no-browser", action="store_true", help="don't open a browser")
    return ap.parse_args(argv)


def run(argv=None) -> None:
    args = parse_args(argv)

    missing = [p.name for _, (p, _, _) in STATIC.items() if not p.exists()]
    if missing:
        fail("The server cannot start because these app files are missing: {}.".format(
            ", ".join(sorted(set(missing)))))

    try:
        get_index()
    except (ValueError, FileNotFoundError) as exc:
        fail(str(exc))

    url = "http://127.0.0.1:{}".format(args.port)
    events: "queue.Queue[str]" = queue.Queue()
    stop_keys = threading.Event()
    hotkeys = has_console_keyboard()
    key_thread = None

    open_browser = not args.no_browser
    try:
        while True:
            try:
                validate_ui()
            except (KeyError, OSError, UnicodeError, SyntaxError) as exc:
                fail("Could not load the page; server not started.\nDetails: {}".format(exc))
            rebuild_standalone()
            httpd = start_http_server(args.port)
            if hotkeys:
                stop_keys.clear()
                key_thread = threading.Thread(
                    target=keyboard_listener, args=(events, stop_keys), daemon=True)
                key_thread.start()

            # serve_forever() on its own thread leaves this one free to wait on a
            # keypress; shutdown() is what stops it, and must come from elsewhere.
            threading.Thread(target=httpd.serve_forever, daemon=True).start()

            success("The app is ready at {}.".format(url))
            info(
                "Ctrl+R restarts, Ctrl+O reopens, Ctrl+C stops."
                if hotkeys else "Press Ctrl+C to stop the server.")
            if open_browser:
                threading.Timer(0.4, webbrowser.open, (url,)).start()
                open_browser = False   # a restart reuses the tab already open

            try:
                action = events.get() if hotkeys else _wait_forever()
            except KeyboardInterrupt:
                action = "stop"

            httpd.shutdown()
            httpd.server_close()
            stop_keys.set()
            if key_thread is not None:
                key_thread.join()

            if action not in ("restart", "reopen"):
                info("The server has stopped.")
                return

            # Ctrl+O is Ctrl+R plus the browser hand-off the first run does.
            open_browser = action == "reopen"
            info("Restarting the app...")
            try:
                reload_sources()
                get_index()
            except (ValueError, FileNotFoundError) as exc:
                fail(str(exc))
    finally:
        stop_keys.set()
        if key_thread is not None:
            key_thread.join()


def _wait_forever() -> str:
    """Block until Ctrl+C when there is no keyboard to read."""
    threading.Event().wait()
    return "stop"


if __name__ == "__main__":
    run()
