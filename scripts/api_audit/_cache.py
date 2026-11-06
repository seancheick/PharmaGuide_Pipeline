"""Freshness checks for the research clients' existing ISO-dated cache envelope."""

from datetime import datetime, timezone
from typing import Any


def _get_fresh_payload(cache: dict, key: str) -> Any | None:
    """Return only responses with a proved, unexpired timezone-aware expiry.

    Undated legacy responses require a refresh. This helper does not renew
    timestamps or decide vendor payload, HTTP, or clinical-review policy.
    """
    entry = cache.get(key)
    if isinstance(entry, dict) and isinstance(entry.get("expires_at"), str):
        try:
            expiry = datetime.fromisoformat(entry["expires_at"])
            if expiry.utcoffset() is not None and expiry > datetime.now(timezone.utc):
                return entry.get("payload")
        except ValueError:
            pass
    cache.pop(key, None)
    return None
