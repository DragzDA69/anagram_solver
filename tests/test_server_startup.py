import io
import errno
import subprocess
import threading
import unittest
import urllib.request
from contextlib import ExitStack, redirect_stdout
from unittest.mock import Mock, patch

import main
import server


class ServerStartupTests(unittest.TestCase):
    def test_occupied_port_replacement_requires_confirmation(self):
        processes = [server.PortProcess(12345, "python", 123)]
        for answer in (True, False):
            with self.subTest(answer=answer), ExitStack() as stack:
                httpd = Mock()
                bind = stack.enter_context(patch(
                    "server.LocalHTTPServer",
                    side_effect=[OSError(errno.EADDRINUSE, "occupied"), httpd]))
                stack.enter_context(patch("server.sys.platform", "win32"))
                stack.enter_context(patch("server.has_console_keyboard", return_value=True))
                stack.enter_context(patch("server.port_processes", return_value=processes))
                confirm = stack.enter_context(patch("server.confirm_port_replacement",
                                                     return_value=answer))
                stop = stack.enter_context(patch("server.stop_port_processes"))
                if answer:
                    self.assertIs(server.start_http_server(8000), httpd)
                    stop.assert_called_once_with(8000, processes)
                    self.assertEqual(bind.call_count, 2)
                else:
                    with self.assertRaises(SystemExit) as result:
                        server.start_http_server(8000)
                    self.assertEqual(result.exception.code, 0)
                    stop.assert_not_called()
                    self.assertEqual(bind.call_count, 1)
                confirm.assert_called_once_with(8000, processes)

    def test_confirmation_yes_no_escape_and_invalid_keys(self):
        for keys, expected in [
            (["y"], True), (["Y"], True), (["n"], False),
            (["N"], False), (["\x1b"], False), (["x", "y"], True),
            (["\x00", "y", "n"], False),
        ]:
            with self.subTest(keys=keys), redirect_stdout(io.StringIO()), \
                    patch("server.warning"), patch("server.msvcrt") as keyboard:
                keyboard.getwch.side_effect = keys
                self.assertEqual(server.confirm_port_replacement(
                    8000, [server.PortProcess(12345, "python", 123)]), expected)

    def test_noninteractive_conflict_does_not_prompt_or_stop(self):
        with patch("server.LocalHTTPServer",
                   side_effect=OSError(errno.EADDRINUSE, "occupied")), \
                patch("server.has_console_keyboard", return_value=False), \
                patch("server.port_processes") as owners, \
                patch("server.stop_port_processes") as stop:
            with self.assertRaisesRegex(SystemExit, "Could not start"):
                server.start_http_server(8000)
        owners.assert_not_called()
        stop.assert_not_called()

    def test_confirmation_response_stays_inline(self):
        prompt = "Stop them and start a fresh server here? [Y/N] (Esc cancels): "
        for key, response in [("y", "Y"), ("n", "N"), ("\x1b", "")]:
            with self.subTest(key=key), patch("server.warning"), \
                    patch("server.msvcrt") as keyboard:
                output = io.StringIO()
                keyboard.getwch.return_value = key
                with redirect_stdout(output):
                    server.confirm_port_replacement(
                        8000, [server.PortProcess(12345, "python", 123)])
                self.assertTrue(output.getvalue().startswith(prompt + response + "\n"))

    def test_termination_script_checks_identity_and_uses_specific_pid(self):
        with redirect_stdout(io.StringIO()), patch("server._powershell") as run:
            server.stop_port_processes(8000, [server.PortProcess(12345, "python", 987654)])
        script = run.call_args.args[0]
        self.assertIn("$owners -notcontains $p.Id", script)
        self.assertIn("Ticks -ne 987654", script)
        self.assertIn("Stop-Process -Id $p.Id", script)
        self.assertNotIn("Stop-Process -Name", script)

    def test_http_page_recovers_from_old_labels_without_a_server_restart(self):
        httpd = server.LocalHTTPServer(("127.0.0.1", 0), server.Handler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            with patch.object(server.ui, "VALUES", {}), \
                    patch.object(server, "_ui_stamp", None):
                for route in ("/", "/app.js", "/style.css"):
                    with urllib.request.urlopen(
                        "http://127.0.0.1:{}{}".format(httpd.server_port, route), timeout=5,
                    ) as response:
                        self.assertEqual(response.status, 200)
                        body = response.read().decode("utf-8")
                        self.assertNotIn("{{", body)
                        if route == "/":
                            self.assertIn("Developed by Dragz", body)
                            self.assertIn('id="clearDialog"', body)
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join()

    def test_served_page_reloads_stale_in_memory_labels(self):
        template = (server.WEB / "index.html").read_text(encoding="utf-8")
        with patch.object(server.ui, "VALUES", {}), patch.object(server, "_ui_stamp", None):
            rendered = server.render_ui(template, "index.html")
        self.assertIn("Developed by Dragz", rendered)
        self.assertIn('id="clearDialog"', rendered)
        self.assertNotIn("{{", rendered)

    def test_ui_reload_only_when_source_changes(self):
        with patch.object(server, "_ui_stamp", None), \
                patch("server.importlib.reload", wraps=server.importlib.reload) as reload:
            server.render_ui("{{btn_cancel}}", "test")
            server.render_ui("{{developer_credit}}", "test")
            reload.assert_called_once_with(server.ui)
            with patch("server.Path.stat") as stat:
                stat.return_value.st_mtime_ns = -1
                stat.return_value.st_size = 1
                server.render_ui("{{btn_cancel}}", "test")
            self.assertEqual(reload.call_count, 2)

    def test_unknown_ui_label_stops_startup_before_build_or_browser(self):
        with ExitStack() as stack:
            stack.enter_context(patch("server.get_index", return_value={4: ["help"]}))
            stack.enter_context(patch("server.has_console_keyboard", return_value=False))
            stack.enter_context(patch("server.validate_ui", side_effect=KeyError("missing label")))
            build = stack.enter_context(patch("server.rebuild_standalone"))
            http = stack.enter_context(patch("server.LocalHTTPServer"))
            browser = stack.enter_context(patch("server.webbrowser.open"))
            with self.assertRaisesRegex(SystemExit, "Could not load the page; server not started"):
                server.run([])
            build.assert_not_called()
            http.assert_not_called()
            browser.assert_not_called()

    def test_builder_uses_current_interpreter_and_project_directory(self):
        with redirect_stdout(io.StringIO()), patch("server.subprocess.run") as run:
            server.rebuild_standalone()
        run.assert_called_once_with(
            [server.sys.executable, str(server.HERE / "build_standalone.py")],
            cwd=server.HERE, check=True,
        )

    def test_failed_build_stops_startup(self):
        for error in (OSError("missing Python"), subprocess.CalledProcessError(1, "build")):
            with self.subTest(error=error), ExitStack() as stack:
                stack.enter_context(redirect_stdout(io.StringIO()))
                stack.enter_context(patch("server.get_index", return_value={4: ["help"]}))
                stack.enter_context(patch("server.has_console_keyboard", return_value=False))
                stack.enter_context(patch("server.subprocess.run", side_effect=error))
                http = stack.enter_context(patch("server.LocalHTTPServer"))
                browser = stack.enter_context(patch("server.webbrowser.open"))
                with self.assertRaisesRegex(SystemExit, "server not started"):
                    server.run([])
                http.assert_not_called()
                browser.assert_not_called()

    def test_startup_and_restart_build_before_serving_and_opening_browser(self):
        order = []
        httpd = Mock()
        httpd.serve_forever.side_effect = lambda: order.append("serve")

        def thread(*args, **kwargs):
            instance = Mock()
            instance.start.side_effect = kwargs["target"]
            return instance

        def timer(delay, callback, args):
            instance = Mock()
            instance.start.side_effect = lambda: callback(*args)
            return instance

        with ExitStack() as stack:
            stack.enter_context(redirect_stdout(io.StringIO()))
            stack.enter_context(patch("server.get_index", return_value={4: ["help"]}))
            stack.enter_context(patch("server.has_console_keyboard", return_value=False))
            stack.enter_context(patch("server.validate_ui",
                                     side_effect=lambda: order.append("validate")))
            stack.enter_context(patch("server.rebuild_standalone",
                                     side_effect=lambda: order.append("build")))
            stack.enter_context(patch("server.LocalHTTPServer",
                                     side_effect=lambda *args: order.append("bind") or httpd))
            stack.enter_context(patch("server.threading.Thread", side_effect=thread))
            stack.enter_context(patch("server.threading.Timer", side_effect=timer))
            stack.enter_context(patch("server.webbrowser.open",
                                     side_effect=lambda url: order.append("browser")))
            stack.enter_context(patch("server._wait_forever", side_effect=["reopen", "stop"]))
            reload = stack.enter_context(patch("server.reload_sources"))
            server.run([])
        self.assertEqual(order, [
            "validate", "build", "bind", "serve", "browser",
            "validate", "build", "bind", "serve", "browser",
        ])
        reload.assert_called_once_with()
        self.assertEqual(httpd.shutdown.call_count, 2)
        self.assertEqual(httpd.server_close.call_count, 2)

    def test_main_run_uses_server_startup(self):
        with patch("server.run") as run:
            main.main(["run"])
        run.assert_called_once_with([])

    def test_second_server_cannot_share_a_live_port(self):
        httpd = server.LocalHTTPServer(("127.0.0.1", 0), server.Handler)
        try:
            with self.assertRaises(OSError):
                server.LocalHTTPServer(httpd.server_address, server.Handler)
        finally:
            httpd.server_close()


if __name__ == "__main__":
    unittest.main()
