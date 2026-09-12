"""The console launcher must reuse a console that is already running.

Starting a second copy fails on the port, which is what made a healthy console
look broken. These pin the two answers the launcher owes: reuse a live server,
and name the fix when the port is held by something that never answers.
"""

import socket
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "submission_review" / "start.sh"


class _Ok(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 - stdlib handler name
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"console")

    def log_message(self, *_args):
        pass


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def _run(port: int) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(SCRIPT), str(port), "--no-open"],
        capture_output=True, text=True, timeout=60,
    )


def test_a_running_console_is_reused_not_restarted():
    server = HTTPServer(("127.0.0.1", 0), _Ok)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        result = _run(server.server_address[1])
    finally:
        server.shutdown()
        server.server_close()

    assert result.returncode == 0, result.stderr
    assert "already running" in result.stdout


def test_a_port_held_by_a_silent_process_says_how_to_free_it():
    held = socket.socket()
    held.bind(("127.0.0.1", 0))
    held.listen(1)  # listening, never answering
    try:
        result = _run(held.getsockname()[1])
    finally:
        held.close()

    assert result.returncode == 1
    assert "not answering" in result.stderr
    assert "xargs kill" in result.stderr


def test_the_launcher_rejects_arguments_it_does_not_understand():
    result = subprocess.run(
        ["bash", str(SCRIPT), "--wipe-everything"],
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 2
    assert "usage" in result.stderr


def test_the_launcher_is_executable():
    assert SCRIPT.exists()
    assert SCRIPT.stat().st_mode & 0o111, "start.sh must be executable"
