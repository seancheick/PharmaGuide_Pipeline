"""Real loopback HTTP: neither redirects nor slow/oversized bodies bypass limits."""
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from submission_review.extraction.bounded_http import request, TransportError


@pytest.fixture
def server():
    hits = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        def do_GET(self):
            hits.append(self.path)
            if self.path == "/redirect":
                self.send_response(307)
                self.send_header("Location", "/private")
                self.end_headers()
                return
            self.send_response(200)
            if self.path == "/big":
                self.send_header("Content-Length", "999999999")
            self.end_headers()
            try:
                if self.path == "/slow":
                    for _ in range(30):
                        self.wfile.write(b"x")
                        self.wfile.flush()
                        time.sleep(.05)
                else:
                    self.wfile.write(b"{}")
            except OSError:
                pass
    http = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{http.server_port}", hits
    http.shutdown()
    http.server_close()
    thread.join()


def test_does_not_follow_redirect_or_environment_proxy(server, monkeypatch):
    url, hits = server
    monkeypatch.setenv("HTTP_PROXY", "http://remote.invalid:8080")
    result = request("GET", url + "/redirect", timeout=1, max_bytes=100)
    assert result.status_code == 307
    assert hits == ["/redirect"]


def test_rejects_large_body_before_buffering(server):
    with pytest.raises(TransportError):
        request("GET", server[0] + "/big", timeout=1, max_bytes=100)


def test_slow_drip_cannot_extend_total_read_deadline(server):
    start = time.monotonic()
    with pytest.raises(TransportError):
        request("GET", server[0] + "/slow", timeout=.2, max_bytes=100)
    assert time.monotonic() - start < .8
