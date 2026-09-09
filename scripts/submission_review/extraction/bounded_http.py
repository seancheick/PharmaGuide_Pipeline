"""One bounded HTTP boundary for private extraction traffic.

No redirects, environment proxies, automatic retries or response decompression.
The deadline includes connect, headers and body. DNS resolution is OS-managed;
the model endpoint uses a literal loopback address, avoiding DNS entirely.
"""
from __future__ import annotations

import http.client
import json
import math
import socket
import threading
import time
from dataclasses import dataclass
from urllib.parse import urlsplit


class TransportError(RuntimeError):
    """Sanitized transport failure; never embeds URLs, bodies or credentials."""


@dataclass(frozen=True)
class Response:
    status_code: int
    content: bytes


def request(method: str, url: str, *, timeout: float, max_bytes: int,
            headers: dict | None = None, body: dict | None = None) -> Response:
    connection = None
    timer = None
    started = time.monotonic()
    expired = threading.Event()
    try:
        if not math.isfinite(timeout) or timeout <= 0 or max_bytes < 1:
            raise ValueError()
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
            raise ValueError()
        factory = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
        connection = factory(parsed.hostname, parsed.port, timeout=timeout)
        connection.connect()
        remaining = timeout - (time.monotonic() - started)
        if remaining <= 0:
            raise TimeoutError()
        wire = connection.sock
        wire.settimeout(remaining)
        def abort():
            expired.set()
            try:
                wire.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        timer = threading.Timer(remaining, abort)
        timer.daemon = True
        timer.start()
        payload = None if body is None else json.dumps(body, allow_nan=False).encode()
        sent_headers = {**(headers or {}), "Accept-Encoding": "identity"}
        if payload is not None:
            sent_headers["Content-Type"] = "application/json"
        target = (parsed.path or "/") + (("?" + parsed.query) if parsed.query else "")
        connection.request(method, target, body=payload, headers=sent_headers)
        response = connection.getresponse()
        length = response.getheader("Content-Length")
        if length is not None and (int(length) < 0 or int(length) > max_bytes):
            raise ValueError()
        if response.getheader("Content-Encoding", "identity") != "identity":
            raise ValueError()
        data = bytearray()
        while True:
            chunk = response.read1(min(65536, max_bytes + 1 - len(data)))
            if expired.is_set() or time.monotonic() - started >= timeout:
                raise TimeoutError()
            if not chunk:
                break
            data.extend(chunk)
            if len(data) > max_bytes:
                raise ValueError()
        if length is not None and len(data) != int(length):
            raise ValueError()
        return Response(response.status, bytes(data))
    except (OSError, ValueError, http.client.HTTPException) as error:
        raise TransportError("request failed, exceeded deadline, or exceeded response limit") from None
    finally:
        if timer is not None:
            timer.cancel()
            timer.join()
        if connection is not None:
            connection.close()
