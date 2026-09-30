from __future__ import annotations
"""
unii_cache.py — Local-first UNII lookup with GSRS API fallback.

Loads the offline UNII cache (172K substances) and provides fast lookups.
Falls back to the GSRS API when a name is not found locally.

Usage:
    from unii_cache import UniiCache

    cache = UniiCache()
    unii = cache.lookup("ascorbic acid")        # → "PQ6CK8PD0R" (instant, offline)
    unii = cache.lookup("some rare compound")   # → tries GSRS API if not cached
    name = cache.reverse_lookup("PQ6CK8PD0R")  # → "ASCORBIC ACID"
"""

import json
import logging
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

CACHE_PATH = Path(__file__).parent / "data" / "fda_unii_cache.json"
GSRS_BASE = "https://gsrs.ncats.nih.gov/ginas/app/api/v1"


class UniiCache:
    """Local-first UNII substance registry with GSRS API fallback."""

    def __init__(self, cache_path: Optional[str] = None, enable_api_fallback: bool = True):
        self._path = Path(cache_path) if cache_path else CACHE_PATH
        self._name_to_unii: dict[str, str] = {}
        self._unii_to_name: dict[str, str] = {}
        self._api_fallback = enable_api_fallback
        self._api_hits: dict[str, str] = {}  # runtime cache for API results
        self._loaded = False
        self._load()

    def _load(self):
        if not self._path.exists():
            logger.warning("UNII cache not found at %s — API-only mode", self._path)
            return
        try:
            with open(self._path) as f:
                data = json.load(f)
            self._name_to_unii = data.get("name_to_unii", {})
            self._unii_to_name = data.get("unii_to_name", {})
            self._loaded = True
            logger.info("UNII cache loaded: %d substances", len(self._name_to_unii))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load UNII cache: %s", exc)

    @property
    def size(self) -> int:
        return len(self._name_to_unii)

    def lookup(self, name: str) -> Optional[str]:
        """Look up UNII code by substance name. Local cache first, API fallback."""
        if not name:
            return None

        key = name.strip().lower()

        # 1. Local cache (instant)
        unii = self._name_to_unii.get(key)
        if unii:
            return unii

        # 2. Runtime API cache
        unii = self._api_hits.get(key)
        if unii:
            return unii

        # 3. GSRS API fallback
        if self._api_fallback:
            unii = self._gsrs_search(name)
            if unii:
                self._api_hits[key] = unii
            return unii

        return None

    def reverse_lookup(self, unii: str) -> Optional[str]:
        """Look up substance name by UNII code."""
        if not unii:
            return None
        return self._unii_to_name.get(unii.strip())

    def _gsrs_search(self, name: str) -> Optional[str]:
        """Search GSRS API for a UNII by substance name."""
        try:
            encoded = urllib.parse.quote(name)
            url = f"{GSRS_BASE}/substances/search?q={encoded}&top=1"
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
            content = data.get("content", [])
            if content and content[0].get("approvalID"):
                unii = content[0]["approvalID"]
                logger.debug("GSRS hit: %s → %s", name, unii)
                return unii
        except Exception as exc:
            logger.debug("GSRS lookup failed for %s: %s", name, exc)
        return None

    def stats(self) -> dict:
        """Return cache statistics."""
        return {
            "loaded": self._loaded,
            "cache_substances": len(self._name_to_unii),
            "cache_uniis": len(self._unii_to_name),
            "api_hits_session": len(self._api_hits),
            "cache_path": str(self._path),
        }
