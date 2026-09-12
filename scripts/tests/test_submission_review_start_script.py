"""The console launcher must reuse a console that is already running.

Starting a second copy fails on the port, which is what made a healthy console
look broken. These pin the two answers the launcher owes: reuse a live server,
and name the fix when the port is held by something that never answers.
"""

import socket
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent.parent / "submission_review" / "start.sh"


class _Ok(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 - stdlib handler name
        self.send_response(200)
        self.end_headers()
        self.wfile.write(json.dumps({
            "service": "pharmaguide-submission-review", "version": 1,
            "server_sha256": hashlib.sha256(SCRIPT.with_name("serve.py").read_bytes()).hexdigest(),
        }).encode())

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
    assert "xargs kill" not in result.stderr


@pytest.mark.parametrize("body", [b"unrelated web server", b'{"service":"pharmaguide-submission-review","version":1,"server_sha256":"old"}'])
def test_unrelated_or_stale_servers_are_not_reported_as_our_console(body):
    class Other(_Ok):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(body)

    server = HTTPServer(("127.0.0.1", 0), Other)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        result = _run(server.server_port)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    assert result.returncode == 1
    assert "already running" not in result.stdout


@pytest.mark.parametrize("port", ["0", "65536", "999999999999999999", "8765/other", "8765abc"])
def test_invalid_ports_are_rejected_before_starting_any_process(port):
    result = _run(port)
    assert result.returncode == 2
    assert "usage" in result.stderr


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


def test_failed_start_reports_the_child_error_without_leaving_it_running(tmp_path):
    console = tmp_path / "scripts" / "submission_review"
    console.mkdir(parents=True)
    launcher = console / "start.sh"
    shutil.copyfile(SCRIPT, launcher)
    (console.parent / "python_env.sh").write_text(
        f"PG_PYTHON={shlex.quote(sys.executable)}\n"
    )
    (console / "serve.py").write_text(
        "import os,sys\nprint('startup-pid=' + str(os.getpid()), flush=True)\n"
        "sys.exit('fixture initialization failed')\n"
    )
    result = subprocess.run(
        ["bash", str(launcher), str(_free_port()), "--no-open"],
        capture_output=True, text=True, timeout=20,
        env={**os.environ, "TMPDIR": str(tmp_path)},
    )
    assert result.returncode == 1
    assert "fixture initialization failed" in result.stderr
    assert "console exited while starting" in result.stderr
    logs = list(tmp_path.glob("pharmaguide-review.*/console.log"))
    assert len(logs) == 1
    assert logs[0].stat().st_mode & 0o077 == 0
    assert logs[0].parent.stat().st_mode & 0o077 == 0
    pid = int(logs[0].read_text().splitlines()[0].split("=")[1])
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)
