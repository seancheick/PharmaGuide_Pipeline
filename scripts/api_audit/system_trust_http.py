"""HTTPS fallback that uses the operating system's verified trust store.

Some macOS Python installations do not inherit certificates trusted by the
System Keychain. The system ``curl`` client does. This module provides a narrow
fallback for certificate-verification failures without disabling TLS checks or
putting API keys in the process argument list.
"""

from __future__ import annotations

import shutil
import subprocess
from typing import Any, Mapping
from urllib.parse import urlencode, urlsplit


class SystemTrustHTTPError(RuntimeError):
    """The system-trust HTTPS request could not return a usable response."""


def _curl_config_quote(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "")


def fetch_text_with_system_trust(
    *,
    url: str,
    params: Mapping[str, Any] | None = None,
    method: str = "GET",
    timeout_seconds: float = 20.0,
    user_agent: str = "pharmaguide-audit/1.0",
) -> str:
    """Fetch HTTPS text with system curl while retaining certificate checks.

    Request details are supplied through curl's standard-input configuration so
    credentials such as an NCBI API key are not exposed in the process list.
    """
    parsed = urlsplit(url)
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        raise ValueError("system-trust fallback accepts only absolute HTTPS URLs")

    method = method.upper()
    if method not in {"GET", "POST"}:
        raise ValueError(f"unsupported system-trust HTTP method: {method}")

    encoded_params = urlencode(params or {}, doseq=True)
    request_url = url
    config_lines = [
        f'url = "{_curl_config_quote(request_url)}"',
        "fail-with-body",
        "silent",
        "show-error",
        "location",
        f'max-time = "{max(float(timeout_seconds), 1.0):g}"',
        f'user-agent = "{_curl_config_quote(user_agent)}"',
        'proto = "=https"',
    ]
    if method == "GET":
        if encoded_params:
            separator = "&" if parsed.query else "?"
            config_lines[0] = (
                f'url = "{_curl_config_quote(request_url + separator + encoded_params)}"'
            )
    else:
        config_lines.extend(
            [
                'request = "POST"',
                'header = "Content-Type: application/x-www-form-urlencoded"',
                f'data = "{_curl_config_quote(encoded_params)}"',
            ]
        )

    curl = shutil.which("curl")
    if not curl:
        raise SystemTrustHTTPError("system curl is unavailable")

    completed = subprocess.run(
        [curl, "--config", "-"],
        input="\n".join(config_lines) + "\n",
        text=True,
        capture_output=True,
        timeout=max(float(timeout_seconds), 1.0) + 5.0,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or f"curl exit {completed.returncode}"
        raise SystemTrustHTTPError(detail)
    return completed.stdout
