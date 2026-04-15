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
import os
import re
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
    def is_loaded(self) -> bool:
        return self._loaded

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

    def bulk_lookup(self, names: list[str]) -> dict[str, Optional[str]]:
        """Look up multiple names at once. Returns {name: unii_or_none}."""
        return {name: self.lookup(name) for name in names}

    def lookup_for_iqm_entry(self, canonical_id: str, entry: dict) -> Optional[str]:
        """Resolve the PRIMARY (parent-level) UNII for an IQM entry.

        IQM identifier hierarchy:
          Parent level: cui (concept), rxcui (drug mapping), external_ids.unii (representative)
          Form level:   forms[name].external_ids.unii (form-specific chemical identity)

        This method resolves the PARENT UNII. For form-specific UNIIs,
        use lookup_for_iqm_form().

        Priority order:
        1. Already-verified UNII in parent external_ids.unii
        2. Canonical ID as readable name
        3. standard_name field
        4. Aliases (skip CUI codes)
        5. First matching form name (fallback — returns the form UNII as parent)

        Returns:
            UNII code or None
        """
        # 0. Already-verified parent UNII
        ext_ids = entry.get("external_ids", {})
        if isinstance(ext_ids, dict) and ext_ids.get("unii"):
            return ext_ids["unii"]

        # 1. Canonical ID as readable name
        readable = canonical_id.replace("_", " ")
        unii = self.lookup(readable)
        if unii:
            return unii

        # 2. standard_name field
        std = (entry.get("standard_name") or "").strip()
        if std:
            unii = self.lookup(std)
            if unii:
                return unii

        # 3. Aliases (skip CUI codes)
        for alias in entry.get("aliases", []):
            if isinstance(alias, str) and not re.match(r"^C\d{5,}$", alias):
                unii = self.lookup(alias)
                if unii:
                    return unii

        # 4. Form names (fallback — uses first matching form's UNII)
        forms = entry.get("forms", {})
        if isinstance(forms, dict):
            for form_name, form_data in forms.items():
                # Check form's own external_ids first
                if isinstance(form_data, dict):
                    fext = form_data.get("external_ids", {})
                    if isinstance(fext, dict) and fext.get("unii"):
                        return fext["unii"]
                # Then try cache lookup by form name
                unii = self.lookup(form_name)
                if unii:
                    return unii

        return None

    def lookup_for_iqm_form(self, form_name: str, form_data: dict) -> Optional[str]:
        """Resolve the UNII for a specific IQM form (chemical substance level).

        Each form (e.g., "calcium ascorbate", "thiamine mononitrate") is a
        distinct chemical substance with its own UNII, CAS, and PubChem CID.

        Priority:
        1. Already-verified form external_ids.unii
        2. Cache lookup by form name

        Args:
            form_name: e.g. "calcium ascorbate"
            form_data: the form's dict with bio_score, absorption, etc.

        Returns:
            UNII code or None
        """
        # 1. Already stored on form
        if isinstance(form_data, dict):
            fext = form_data.get("external_ids", {})
            if isinstance(fext, dict) and fext.get("unii"):
                return fext["unii"]

        # 2. Cache lookup
        return self.lookup(form_name)

    def resolve_all_form_uniis(self, entry: dict) -> dict[str, Optional[str]]:
        """Resolve UNIIs for all forms in an IQM entry.

        Returns {form_name: unii_or_none} for every form.
        Useful for enrichment matching — when a product ingredient name
        matches a form, we can confirm identity via UNII.
        """
        result = {}
        forms = entry.get("forms", {})
        if isinstance(forms, dict):
            for fname, fdata in forms.items():
                result[fname] = self.lookup_for_iqm_form(fname, fdata)
        return result

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
