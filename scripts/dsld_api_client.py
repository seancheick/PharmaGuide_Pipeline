#!/usr/bin/env python3
"""Low-level DSLD API client for fetching supplement labels from NIH DSLD."""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import requests
import sys

logger = logging.getLogger(__name__)


def _load_env():
    """Load .env via env_loader (same pattern as supabase_client.py)."""
    script_dir = str(Path(__file__).resolve().parent)
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    import env_loader  # noqa: F401

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_BASE_URL = "https://api.ods.od.nih.gov/dsld/v9"
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_RATE_LIMIT_DELAY = 0.15  # ~6.6 req/sec
DEFAULT_CACHE_TTL_SECONDS = 60 * 60 * 24 * 7  # 7 days
MAX_RETRIES = 4
DEFAULT_FAILURE_LIMIT = 3

# Every key present in a raw DSLD label file (from manual download).
# The normalizer guarantees exactly these keys appear in output.
RAW_LABEL_KEYS = [
    "brandIpSymbol",
    "brandName",
    "bundleName",
    "claims",
    "contacts",
    "entryDate",
    "events",
    "fullName",
    "hasOuterCarton",
    "id",
    "ingredientRows",
    "labelRelationships",
    "netContents",
    "nhanesId",
    "offMarket",
    "otheringredients",
    "pdf",
    "percentDvFootnote",
    "physicalState",
    "productType",
    "productVersionCode",
    "servingSizes",
    "servingsPerContainer",
    "src",
    "statements",
    "targetGroups",
    "thumbnail",
    "upcSku",
    "userGroups",
]

# Keys whose default value should be an empty list.
_LIST_KEYS = frozenset({
    "claims",
    "contacts",
    "events",
    "ingredientRows",
    "labelRelationships",
    "netContents",
    "servingSizes",
    "statements",
    "targetGroups",
    "userGroups",
})

# Keys whose default value should be an empty dict.
_DICT_KEYS = frozenset({
    "otheringredients",
    "physicalState",
    "productType",
})

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class DSLDApiConfig:
    api_key: str = ""
    base_url: str = DEFAULT_BASE_URL
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    rate_limit_delay: float = DEFAULT_RATE_LIMIT_DELAY
    cache_path: Path | None = None
    cache_ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS


def load_dsld_config(env: Mapping[str, str] | None = None) -> DSLDApiConfig:
    """Build a :class:`DSLDApiConfig` from environment variables.

    Parameters
    ----------
    env:
        Optional mapping to read from instead of ``os.environ``.
    """
    if env is None:
        _load_env()
    source = env or os.environ
    cache_env = source.get("DSLD_CACHE_FILE")
    cache_path = Path(cache_env) if cache_env else None
    return DSLDApiConfig(
        api_key=source.get("DSLD_API_KEY", ""),
        cache_path=cache_path,
    )


# ---------------------------------------------------------------------------
# Normalizer
# ---------------------------------------------------------------------------


def normalize_api_label(api_response: dict) -> dict:
    """Normalize an API response into the canonical raw-label shape.

    Steps:
    1. Unwrap ``{"data": {...}}`` envelope if present.
    2. Raise ``ValueError`` if ``id`` is missing.
    3. Force ``otherIngredients`` -> ``otheringredients`` (lowercase).
    4. Build output with all 29 :data:`RAW_LABEL_KEYS`, filling missing keys
       with appropriate defaults (lists -> [], dicts -> {}, else None).
    5. Set ``_source`` to ``"api"`` and ``src`` to ``"api/label/{id}"``.
    6. Warn on unexpected keys.
    """
    data: dict = api_response

    # 1. Unwrap envelope
    if "data" in data and isinstance(data["data"], dict) and "id" in data["data"]:
        data = data["data"]

    # 2. Require id
    if "id" not in data:
        raise ValueError("API response missing required 'id' field")

    id_value = data["id"]

    # 3. otherIngredients -> otheringredients
    if "otherIngredients" in data and "otheringredients" not in data:
        data["otheringredients"] = data.pop("otherIngredients")
    elif "otherIngredients" in data:
        # Both present — drop the camelCase variant
        data.pop("otherIngredients")

    # 6. Warn on unexpected keys (before building output, so we log them)
    raw_key_set = set(RAW_LABEL_KEYS)
    for key in sorted(data.keys()):
        if key not in raw_key_set and key != "_source":
            logger.warning(
                "normalize_api_label: dropping unexpected key %r from label %s",
                key,
                id_value,
            )

    # 4. Build output with correct defaults
    output: dict[str, Any] = {}
    for key in RAW_LABEL_KEYS:
        if key in data:
            output[key] = data[key]
        elif key in _LIST_KEYS:
            output[key] = []
        elif key in _DICT_KEYS:
            output[key] = {}
        else:
            output[key] = None

    # 5. Provenance
    output["_source"] = "api"
    output["src"] = f"api/label/{id_value}"

    return output


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class DSLDApiClient:
    """Thin DSLD API client with retry, rate limit, circuit breaker, and optional disk cache."""

    def __init__(
        self,
        config: DSLDApiConfig | None = None,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        cache_path: Path | None = None,
        timeout_seconds: float | None = None,
        rate_limit_delay: float | None = None,
        cache_ttl_seconds: int | None = None,
        failure_limit: int | None = None,
    ) -> None:
        cfg = config or load_dsld_config()
        self.config = DSLDApiConfig(
            api_key=api_key if api_key is not None else cfg.api_key,
            base_url=base_url if base_url is not None else cfg.base_url,
            timeout_seconds=timeout_seconds if timeout_seconds is not None else cfg.timeout_seconds,
            rate_limit_delay=rate_limit_delay if rate_limit_delay is not None else cfg.rate_limit_delay,
            cache_path=cache_path if cache_path is not None else cfg.cache_path,
            cache_ttl_seconds=cache_ttl_seconds if cache_ttl_seconds is not None else cfg.cache_ttl_seconds,
        )
        self._last_request_at = 0.0
        self._consecutive_failures = 0
        self._failure_limit = failure_limit if failure_limit is not None else DEFAULT_FAILURE_LIMIT
        self.circuit_open = False
        self._cache = self._load_cache()

    # -- cache helpers -------------------------------------------------------

    def _load_cache(self) -> dict[str, Any]:
        path = self.config.cache_path
        if not path or not path.exists():
            return {}
        try:
            return json.loads(path.read_text())
        except Exception:
            return {}

    def _persist_cache(self) -> None:
        path = self.config.cache_path
        if not path:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self._cache, indent=2, ensure_ascii=True))

    def _cache_get(self, key: str) -> Any | None:
        record = self._cache.get(key)
        if not isinstance(record, dict):
            return None
        expires_at = record.get("expires_at")
        if isinstance(expires_at, (int, float)) and expires_at < time.time():
            return None
        return record.get("payload")

    def _cache_put(self, key: str, payload: Any) -> None:
        self._cache[key] = {
            "stored_at": time.time(),
            "expires_at": time.time() + self.config.cache_ttl_seconds,
            "payload": payload,
        }
        self._persist_cache()

    # -- rate limit ----------------------------------------------------------

    def _sleep_for_rate_limit(self) -> None:
        elapsed = time.time() - self._last_request_at
        if elapsed < self.config.rate_limit_delay:
            time.sleep(self.config.rate_limit_delay - elapsed)

    # -- core request --------------------------------------------------------

    def _request(
        self,
        endpoint: str,
        *,
        params: dict[str, Any] | None = None,
        method: str = "GET",
    ) -> Any:
        if self.circuit_open:
            raise RuntimeError(
                f"DSLD circuit breaker open after {self._failure_limit} consecutive failures. "
                "Check network connectivity or DSLD service status."
            )

        params = dict(params or {})

        headers: dict[str, str] = {}
        if self.config.api_key:
            headers["X-Api-Key"] = self.config.api_key

        cache_key = json.dumps(
            {"endpoint": endpoint, "method": method, "params": params},
            sort_keys=True,
        )
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        url = f"{self.config.base_url.rstrip('/')}/{endpoint}"
        response = None
        for attempt in range(1, MAX_RETRIES + 1):
            self._sleep_for_rate_limit()
            try:
                response = requests.request(
                    method,
                    url,
                    params=params,
                    headers=headers,
                    timeout=self.config.timeout_seconds,
                )
                self._last_request_at = time.time()
            except (requests.ConnectionError, requests.Timeout, OSError) as exc:
                self._consecutive_failures += 1
                if self._consecutive_failures >= self._failure_limit:
                    self.circuit_open = True
                    raise RuntimeError(
                        f"DSLD circuit breaker tripped: {self._consecutive_failures} consecutive failures"
                    ) from exc
                time.sleep(min(2 ** attempt, 8))
                continue

            if response.status_code != 429:
                self._consecutive_failures = 0
                break
            time.sleep(min(2 ** attempt, 8))

        if response is None:
            self._consecutive_failures += 1
            if self._consecutive_failures >= self._failure_limit:
                self.circuit_open = True
            raise RuntimeError("DSLD request did not return a response")

        # Detect HTML responses (API may return error pages as HTML)
        content_type = response.headers.get("content-type", "")
        body_text = response.text
        if "text/html" in content_type or body_text.lstrip().startswith("<"):
            raise RuntimeError(
                f"DSLD API returned HTML instead of JSON for {endpoint}. "
                f"Content-Type: {content_type}"
            )

        response.raise_for_status()

        payload = response.json()
        self._cache_put(cache_key, payload)
        return payload

    # -- public methods ------------------------------------------------------

    def fetch_label(self, dsld_id: int | str) -> dict:
        """Fetch a single label by DSLD ID and return normalized output."""
        raw = self._request(f"label/{dsld_id}")
        return normalize_api_label(raw)

    def search_brand(
        self,
        brand_name: str,
        *,
        size: int = 1000,
        from_: int = 0,
    ) -> Any:
        """Search labels by brand name via /brand-products endpoint.

        Returns raw API response with 'hits' list containing label summaries.
        Each hit has a '_source' dict with at minimum 'id' (the DSLD label ID).
        """
        return self._request(
            "brand-products",
            params={"q": brand_name, "size": size, "from": from_},
        )

    def search_query(
        self,
        query: str,
        *,
        size: int = 1000,
        from_: int = 0,
        status: int = 2,
    ) -> Any:
        """Search labels via /search-filter endpoint.

        Parameters
        ----------
        query : str
            Search term (searches all label fields).
        size : int
            Max results to return (default 1000).
        from_ : int
            Pagination offset.
        status : int
            Market status filter (2=all, 1=on market, 0=off market).

        Returns raw API response with 'hits' list.
        """
        return self._request(
            "search-filter",
            params={"q": query, "size": size, "from": from_, "status": status},
        )


__all__ = [
    "DEFAULT_BASE_URL",
    "DEFAULT_CACHE_TTL_SECONDS",
    "DEFAULT_FAILURE_LIMIT",
    "DEFAULT_RATE_LIMIT_DELAY",
    "DEFAULT_TIMEOUT_SECONDS",
    "DSLDApiClient",
    "DSLDApiConfig",
    "MAX_RETRIES",
    "RAW_LABEL_KEYS",
    "load_dsld_config",
    "normalize_api_label",
]
