#!/usr/bin/env python3
from __future__ import annotations
"""
FDA GSRS/UNII verification and enrichment for PharmaGuide data files.

Queries the FDA Global Substance Registration System (GSRS) to populate:
  - UNII codes (FDA's universal substance identifier)
  - 21 CFR sections (regulatory references)
  - Metabolic relationships (enzyme substrates, metabolites)
  - Salt/parent mappings
  - Active moiety
  - RxCUI (when available)
  - DSLD product count

Match validation gate (lesson from verify_pubchem.py):
  - NEVER auto-write without confirming the GSRS substance matches our entry.
  - Primary validation: CAS cross-reference (if we have CAS, GSRS must agree).
  - Secondary validation: name must appear in GSRS names list (case-insensitive).
  - Ambiguous or weak matches go to "rejected" bucket, not applied.

Operator runbook:
  1. Dry-run harmful_additives:
       python3 scripts/api_audit/verify_unii.py --file scripts/data/harmful_additives.json --list-key harmful_additives
  2. Dry-run banned_recalled:
       python3 scripts/api_audit/verify_unii.py --file scripts/data/banned_recalled_ingredients.json --list-key ingredients
  3. Dry-run IQM:
       python3 scripts/api_audit/verify_unii.py --file scripts/data/ingredient_quality_map.json --mode iqm
  4. Apply safe fills:
       python3 scripts/api_audit/verify_unii.py --file scripts/data/harmful_additives.json --list-key harmful_additives --apply
  5. Search a single substance:
       python3 scripts/api_audit/verify_unii.py --search "magnesium stearate"

No API key needed. GSRS is free and public.
Rate limit: self-imposed 2 req/s (GSRS has no documented limit but is a government service).
"""

import argparse
import json
import re
import ssl
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
SCRIPTS_ROOT = SCRIPT_DIR.parent
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

GSRS_BASE = "https://gsrs.ncats.nih.gov/ginas/app/api/v1"
RATE_LIMIT_DELAY = 0.5  # 2 req/s — conservative for government API
DEFAULT_CACHE_TTL_SECONDS = 60 * 60 * 24 * 30  # 30 days
CAS_RE = re.compile(r"^\d{2,7}-\d{2}-\d$")

def _load_gsrs_policies() -> dict | None:
    """Load GSRS policies from JSON file."""
    path = Path(__file__).resolve().parent.parent / "data" / "curated_overrides" / "gsrs_policies.json"
    if path.exists():
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return None

_GSRS_EXT = _load_gsrs_policies()

# Entries that should not be looked up — polymers, classes, umbrellas, multi-compound
SKIP_NAMES = set(_GSRS_EXT["skip_names"]) if _GSRS_EXT else {
    "unspecified colors", "synthetic vitamins", "synthetic b vitamins",
    "sugar alcohols", "sugar syrups", "syrups", "slimsweet",
    "purefruit select", "time-sorb", "artificial flavors",
    "synthetic antioxidants", "caramel color",
    "partially hydrogenated oils", "partially hydrogenated oils (phos)",
    "synthetic estrogens", "phthalates", "synthetic anabolic steroids",
    "contaminated glp-1 compounds", "metal fiber contamination",
    "cannabis/thc", "general probiotics",
    # Compound classes in harmful_additives
    "antimony & antimony compounds", "nickel & nickel compounds",
    "tin & tin compounds",
}

RAW_CURATED_GSRS_POLICIES = (_GSRS_EXT["entry_policies"] if _GSRS_EXT else {
    "Candurin Silver": {
        "reason": "proprietary mica-based pearlescent pigment system; GSRS resolves to component materials rather than one exact ingredient identity",
    },
    "Calcium Aluminum Phosphate": {
        "reason": "regulatory additive label does not currently resolve to an exact GSRS substance with the local CAS; GSRS falls back to aluminum phosphate",
    },
    "Carmine Red (Cochineal Extract)": {
        "reason": "color-additive label spans extract/lake variants; GSRS falls back to pigment red 5 instead of the exact local ingredient concept",
    },
    "Crospovidone": {
        "reason": "crosslinked polymer grade; GSRS returns an unspecified crospovidone variant with a different CAS lineage",
    },
    "Soy Monoglycerides": {
        "reason": "fatty-acid monoglyceride mixture; GSRS resolves to a narrower diacetylated monoglyceride substance instead of the local mixture concept",
    },
    "Fatty Acid Polyglycerol Esters": {
        "reason": "mixture / emulsifier family with no single authoritative GSRS ingredient record",
    },
    "Isomaltooligosaccharide": {
        "reason": "oligosaccharide mixture / syrup family with no single authoritative GSRS ingredient record",
    },
    "Maltotame": {
        "reason": "no trustworthy GSRS match found for this sweetener label in the current registry",
    },
    "7-Keto DHEA (7-Oxodehydroepiandrosterone)": {
        "reason": "current GSRS registry does not expose a trustworthy exact UNII record for this ingredient label",
    },
    "BMPEA": {
        "reason": "current GSRS registry does not expose a trustworthy exact UNII record for this stimulant ingredient label",
    },
    "Delta-8 Tetrahydrocannabinol (Delta-8 THC)": {
        "reason": "current GSRS registry does not expose a trustworthy exact UNII record for this cannabinoid label",
    },
    "DMAA": {
        "reason": "current GSRS registry does not expose a trustworthy exact UNII record for this stimulant ingredient label",
    },
    "9-Methyl-β-carboline": {
        "reason": "current GSRS registry does not expose a trustworthy exact UNII record for this research-chemical nootropic label",
    },
    "Flmodafinil": {
        "reason": "current GSRS registry does not expose a trustworthy exact UNII record for this research-chemical nootropic label",
    },
    "Ligandrol": {
        "reason": "current GSRS registry does not expose a trustworthy exact UNII record for this SARM label",
    },
    "RAD140": {
        "reason": "current GSRS registry does not expose a trustworthy exact UNII record for this SARM label",
    },
    "7-Methylkratom": {
        "reason": "current GSRS registry does not expose a trustworthy exact UNII record for this kratom-derived analogue label",
    },
    "α-PHP": {
        "reason": "current GSRS registry does not expose a trustworthy exact UNII record for this stimulant analogue label",
    },
    "Dymethazine": {
        "reason": "current GSRS registry does not expose a trustworthy exact UNII record for this anabolic-agent label",
    },
    "3,5-Diiodo-L-Thyronine (T2)": {
        "reason": "current GSRS registry does not expose a trustworthy exact UNII record for this thyroid-hormone analogue label",
    },
    "Hexadrone (6-Chloro-androst-4-ene-3-one-17b-ol)": {
        "reason": "current GSRS registry does not expose a trustworthy exact UNII record for this prohormone label",
    },
    "Alpha GPC": {
        "reason": "current GSRS search collapses Alpha GPC to choline-related records rather than one reviewed exact alpha-glycerophosphocholine substance identity",
    },
    "Alpha-Carotene": {
        "reason": "current GSRS registry does not expose a trustworthy exact UNII record for this carotenoid label",
    },
    "Apoaequorin": {
        "reason": "proprietary jellyfish-derived protein ingredient does not currently have one reviewed exact GSRS substance identity in this workflow",
    },
    "Alkamides": {
        "reason": "class entry spanning multiple alkamide compounds; no single GSRS substance is accurate",
    },
    "Bacillus Indicus": {
        "reason": "current GSRS registry does not expose a trustworthy exact UNII record for this probiotic species/ingredient label",
    },
    "Birch Polypore": {
        "reason": "mushroom ingredient label does not currently resolve to one reviewed exact GSRS substance identity",
    },
    "Black Seed Oil (Nigella Sativa)": {
        "reason": "GSRS resolves to thymoquinone, a constituent, instead of the supplement-market black seed oil ingredient",
    },
    "Butterbur (Petasites hybridus)": {
        "reason": "GSRS resolves to isopetasin, a constituent, instead of the reviewed butterbur supplement ingredient",
    },
    "Calamari Oil": {
        "reason": "marine oil ingredient does not have a trustworthy exact GSRS substance match beyond broader or adjacent lipid records",
    },
    "Calanus Oil": {
        "reason": "marine oil ingredient does not have a trustworthy exact GSRS substance match in the current registry",
    },
    "Ceramides": {
        "reason": "class entry spanning multiple plant- and wheat-derived ceramide systems; GSRS resolves to narrower source materials instead of one exact ingredient identity",
    },
    "CGF (Chlorella Growth Factor)": {
        "reason": "proprietary chlorella fraction with no reviewed exact GSRS ingredient identity",
    },
    "Coenzymated Complex": {
        "reason": "branded/co-formulated B-vitamin complex without one exact GSRS substance identity",
    },
    "Cyanidin-3-Glucoside": {
        "reason": "current GSRS registry does not expose a trustworthy exact UNII record for this supplement ingredient label",
    },
    "Deer Antler Velvet": {
        "reason": "animal tissue ingredient spans multiple proteins, lipids, and growth factors; no single GSRS substance is accurate",
    },
    "Digestive Enzymes": {
        "reason": "class entry spanning multiple digestive enzyme blends; GSRS resolves to specific enzymes instead of one exact ingredient identity",
    },
    "Elderberry": {
        "reason": "supplement label spans Sambucus berry powder, juice, syrup, and extract forms without one reviewed exact GSRS ingredient identity",
    },
    "EPA/DHA": {
        "reason": "combined omega-3 pair spans two distinct fatty-acid substances and should not be collapsed to one GSRS identity",
    },
    "Fiber": {
        "reason": "class entry spanning multiple fiber types; GSRS resolves to specific fibers instead of one exact ingredient identity",
    },
    "Flavones": {
        "reason": "class entry spanning multiple flavone compounds; no single GSRS substance is accurate",
    },
    "Flavonols": {
        "reason": "class entry spanning multiple flavonol compounds; no single GSRS substance is accurate",
    },
    "French Oak Wood Extract": {
        "reason": "botanical extract label does not currently resolve to one reviewed exact GSRS ingredient identity",
    },
    "GABA (Gamma-Aminobutyric Acid)": {
        "reason": "current GSRS registry does not expose a trustworthy exact UNII record for the supplement-market GABA label",
    },
    "Galactolipids": {
        "reason": "class entry spanning multiple galactolipid compounds; no single GSRS substance is accurate",
    },
    "Herring Roe Extract": {
        "reason": "marine extract label does not currently resolve to one reviewed exact GSRS ingredient identity",
    },
    "Horsetail": {
        "reason": "supplement label spans equisetum species and plant parts while GSRS resolves to a narrower botanical record",
    },
    "Humic Acid": {
        "reason": "broad humic-substance mixture with no single trustworthy exact GSRS ingredient identity",
    },
    "Maca": {
        "reason": "supplement label spans maca root powders and extracts without one reviewed exact GSRS ingredient identity",
    },
    "Manuka Honey": {
        "reason": "GSRS exposes generic honey but not one reviewed exact manuka-honey ingredient identity",
    },
    "Mucilage": {
        "reason": "class entry spanning multiple mucilage polysaccharide systems; no single GSRS substance is accurate",
    },
    "Omega-7 Fatty Acids": {
        "reason": "class entry spanning multiple omega-7 fatty acids and sources; no single GSRS substance is accurate",
    },
    "OptiBerry": {
        "reason": "proprietary botanical blend with no single exact GSRS substance identity",
    },
    "Phytosterols": {
        "reason": "class entry spanning multiple plant sterols; GSRS resolves to individual sterols instead of one exact ingredient identity",
    },
    "Probiotic (Unspecified)": {
        "reason": "class entry spanning multiple probiotic species and strain blends; no single GSRS substance is accurate",
    },
    "Purple Tea Extract": {
        "reason": "botanical extract label does not currently resolve to one reviewed exact GSRS ingredient identity",
    },
    "Seal Oil": {
        "reason": "marine oil ingredient does not have a trustworthy exact GSRS substance match in the current registry",
    },
    "Sesquiterpenes": {
        "reason": "class entry spanning multiple sesquiterpene compounds; no single GSRS substance is accurate",
    },
    "Shuddha Laksha": {
        "reason": "Ayurvedic resin/preparation name does not currently resolve to one reviewed exact GSRS ingredient identity",
    },
    "Spirulina": {
        "reason": "GSRS resolves to phycocyanobilin, a constituent, instead of the supplement-market spirulina biomass ingredient",
    },
    "Tannins": {
        "reason": "class entry spanning multiple tannin compounds; no single GSRS substance is accurate",
    },
    "Triterpene Glycosides": {
        "reason": "class entry spanning multiple triterpene glycosides; no single GSRS substance is accurate",
    },
    "Tuna Oil": {
        "reason": "marine oil ingredient does not have a trustworthy exact GSRS substance match in the current registry",
    },
    "β-Hydroxy β-Methylbutyrate": {
        "reason": "current GSRS registry does not expose one reviewed exact UNII record for the supplement-market HMB ingredient label without collapsing to constituent or salt variants",
    },
})

# Relationship types worth extracting
METABOLIC_REL_TYPES = {
    "METABOLIC ENZYME->SUBSTRATE", "METABOLIC ENZYME->INHIBITOR",
    "METABOLIC ENZYME->INDUCER", "TARGET->INHIBITOR",
    "TARGET->AGONIST", "TARGET->ANTAGONIST",
    "TARGET->WEAK INHIBITOR",
}
SALT_REL_TYPES = {
    "SALT/SOLVATE->PARENT", "PARENT->SALT/SOLVATE",
}
MOIETY_REL_TYPES = {
    "ACTIVE MOIETY",
}
METABOLITE_REL_TYPES = {
    "METABOLITE->PARENT", "METABOLITE ACTIVE->PARENT",
    "PARENT->METABOLITE ACTIVE",
}

# ---------------------------------------------------------------------------
# SSL fallback
# ---------------------------------------------------------------------------

def _make_ssl_ctx() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    try:
        req = urllib.request.Request(GSRS_BASE, method="HEAD")
        urllib.request.urlopen(req, timeout=5, context=ctx)
        return ctx
    except ssl.SSLCertVerificationError:
        return ssl._create_unverified_context()
    except urllib.error.URLError as exc:
        if isinstance(getattr(exc, "reason", None), ssl.SSLCertVerificationError):
            return ssl._create_unverified_context()
        return ctx
    except Exception:
        return ctx

_SSL_CTX = _make_ssl_ctx()


# ---------------------------------------------------------------------------
# GSRS Client
# ---------------------------------------------------------------------------

class GSRSClient:
    """Thin stdlib wrapper around the FDA GSRS REST API."""

    def __init__(
        self,
        *,
        timeout_seconds: float = 20.0,
        failure_limit: int = 3,
        cache_path: Path | None = None,
        cache_ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS,
    ):
        self.timeout_seconds = timeout_seconds
        self.failure_limit = max(1, failure_limit)
        self.cache_path = cache_path
        self.cache_ttl_seconds = max(0, cache_ttl_seconds)
        self._request_count = 0
        self._consecutive_failures = 0
        self.circuit_open = False
        self._cache: dict[str, dict] = {}
        if self.cache_path and self.cache_path.exists():
            try:
                self._cache = json.loads(self.cache_path.read_text())
            except (json.JSONDecodeError, OSError):
                self._cache = {}

    # ── Cache ──────────────────────────────────────────────────────────────

    def _cache_get(self, key: str) -> dict | None:
        cached = self._cache.get(key)
        if not isinstance(cached, dict):
            return None
        expires_at = cached.get("expires_at")
        if isinstance(expires_at, str):
            try:
                if datetime.fromisoformat(expires_at) <= datetime.now(timezone.utc):
                    self._cache.pop(key, None)
                    return None
            except ValueError:
                self._cache.pop(key, None)
                return None
        return cached.get("payload")

    def _cache_set(self, key: str, payload: dict) -> None:
        self._cache[key] = {
            "payload": payload,
            "expires_at": (
                datetime.now(timezone.utc) + timedelta(seconds=self.cache_ttl_seconds)
            ).isoformat(),
        }

    def save_cache(self) -> None:
        if self.cache_path:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.cache_path.write_text(json.dumps(self._cache, indent=1))

    # ── HTTP ───────────────────────────────────────────────────────────────

    def _get(self, url: str) -> dict | None:
        if self.circuit_open:
            return None

        cached = self._cache_get(url)
        if cached is not None:
            return cached

        for attempt in range(1, 4):
            try:
                self._request_count += 1
                time.sleep(RATE_LIMIT_DELAY)
                req = urllib.request.Request(url, headers={
                    "Accept": "application/json",
                    "User-Agent": "PharmaGuide-verify-unii/1.0",
                })
                with urllib.request.urlopen(req, timeout=self.timeout_seconds, context=_SSL_CTX) as resp:
                    data = json.loads(resp.read().decode())
                    self._consecutive_failures = 0
                    self._cache_set(url, data)
                    return data
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    empty = {"content": [], "total": 0, "_not_found": True}
                    self._cache_set(url, empty)
                    self._consecutive_failures = 0
                    return empty
                if e.code in (429, 500, 502, 503, 504):
                    wait = RATE_LIMIT_DELAY * (2 ** attempt)
                    print(f"  [RETRY {attempt}/3] HTTP {e.code}, waiting {wait:.1f}s...",
                          file=sys.stderr)
                    time.sleep(wait)
                    continue
                print(f"  [ERROR] HTTP {e.code} for {url}", file=sys.stderr)
                return None
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                self._consecutive_failures += 1
                if self._consecutive_failures >= self.failure_limit:
                    print(f"  [CIRCUIT OPEN] {self._consecutive_failures} consecutive "
                          f"failures — stopping API calls", file=sys.stderr)
                    self.circuit_open = True
                    return None
                wait = RATE_LIMIT_DELAY * (2 ** attempt)
                print(f"  [RETRY {attempt}/3] {e}, waiting {wait:.1f}s...",
                      file=sys.stderr)
                time.sleep(wait)
        return None

    @property
    def request_count(self) -> int:
        return self._request_count

    # ── Search methods ─────────────────────────────────────────────────────

    def search_by_name(self, name: str, top: int = 3) -> list[dict]:
        """Search GSRS by substance name. Returns list of substance summaries."""
        encoded = urllib.request.quote(name, safe="")
        data = self._get(f"{GSRS_BASE}/substances/search?q={encoded}&top={top}")
        if data and data.get("content"):
            return data["content"]
        return []

    def search_by_cas(self, cas: str) -> list[dict]:
        """Search GSRS by CAS number — most reliable match method."""
        encoded = urllib.request.quote(cas, safe="")
        data = self._get(
            f"{GSRS_BASE}/substances/search?q=root_codes_CAS:%22{encoded}%22&top=1"
        )
        if data and data.get("content"):
            return data["content"]
        return []

    def get_full_substance(self, unii: str) -> dict | None:
        """Get full substance record by UNII code."""
        data = self._get(f"{GSRS_BASE}/substances({unii})?view=full")
        if data and not data.get("_not_found"):
            return data
        return None

    def search_substance(self, name: str, cas: str | None = None) -> dict | None:
        """Search for a substance with match validation.

        Strategy:
          1. If CAS available → search by CAS (deterministic)
          2. If no CAS → search by name, validate result
          3. Fetch full record for enrichment data

        Returns full substance dict or None.
        """
        # Strategy 1: CAS lookup (most reliable)
        if cas and CAS_RE.match(cas):
            results = self.search_by_cas(cas)
            if results:
                substance = results[0]
                unii = substance.get("approvalID")
                if unii:
                    return self.get_full_substance(unii)

        # Strategy 2: Name search with strict validation
        results = self.search_by_name(name, top=5)
        if not results:
            return None

        name_lower = name.lower().strip()
        name_words = set(name_lower.split())

        for r in results:
            gsrs_name = (r.get("_name") or "").lower().strip()

            # Reject if our name is just a substring fragment of a longer compound
            # e.g., "PEG" matching "MPEG-5000-HISTIDINE" or "PVP" matching "MFPVP"
            if len(name_lower) < 5 and gsrs_name != name_lower:
                continue

            # Strong match: exact or one fully contains the other
            # But require word-boundary alignment — "peg" must not match "mpeg"
            if name_lower == gsrs_name:
                pass  # exact match — accept
            elif name_lower in gsrs_name:
                # Verify it's at a word boundary, not mid-word
                idx = gsrs_name.find(name_lower)
                before = gsrs_name[idx - 1] if idx > 0 else " "
                after_idx = idx + len(name_lower)
                after = gsrs_name[after_idx] if after_idx < len(gsrs_name) else " "
                if before.isalpha() or after.isalpha():
                    continue  # mid-word match like "peg" in "mpeg" — reject
            elif gsrs_name in name_lower:
                idx = name_lower.find(gsrs_name)
                before = name_lower[idx - 1] if idx > 0 else " "
                after_idx = idx + len(gsrs_name)
                after = name_lower[after_idx] if after_idx < len(name_lower) else " "
                if before.isalpha() or after.isalpha():
                    continue
            else:
                continue  # no substring match at all

            unii = r.get("approvalID")
            if unii:
                return self.get_full_substance(unii)

        # Strategy 3: Fetch full record of best candidate and check names list
        # Only for multi-word names (reduces false positives on short terms)
        if len(name_lower.split()) >= 2 and len(name_lower) >= 6:
            first = results[0]
            unii = first.get("approvalID")
            if unii:
                full = self.get_full_substance(unii)
                if full:
                    gsrs_names = {
                        n.get("name", "").lower()
                        for n in full.get("names", [])
                    }
                    gsrs_names.add(full.get("_name", "").lower())
                    # Require our full name to appear in their names list
                    if any(name_lower == gn or name_lower in gn
                           for gn in gsrs_names if gn):
                        return full

        return None


# ---------------------------------------------------------------------------
# Data extraction from GSRS substance record
# ---------------------------------------------------------------------------

def extract_enrichment(substance: dict) -> dict:
    """Extract all enrichment data from a full GSRS substance record.

    Returns a dict with:
      unii, cfr_sections, rxcui, dsld_count, cas, pubchem_cid,
      active_moiety, salt_parents, metabolic_relationships, metabolites
    """
    result: dict[str, Any] = {
        "unii": substance.get("approvalID"),
        "substance_name": substance.get("_name"),
        "substance_class": substance.get("substanceClass"),
    }

    # Extract from codes
    codes = substance.get("codes", [])
    cfr_sections = []
    rxcui = None
    dsld_info_raw = None
    cas_primary = None
    cas_all = []
    pubchem_from_gsrs = None

    for c in codes:
        cs = (c.get("codeSystem") or "").upper()
        code = c.get("code", "")
        comments = c.get("comments", "") or ""
        code_type = (c.get("type") or "").upper()

        if cs == "CFR" and code.startswith("21 CFR"):
            cfr_sections.append(code)
        elif cs == "RXCUI":
            rxcui = code
        elif cs == "DSLD":
            dsld_info_raw = comments.strip() if comments else code
            if code and comments:
                dsld_info_raw = f"{comments.strip()} | {code}"
        elif cs == "CAS":
            if code and code not in cas_all:
                cas_all.append(code)
            if code and code_type == "PRIMARY":
                cas_primary = code
            elif code and cas_primary is None and code_type != "SUPERSEDED":
                cas_primary = code
        elif cs == "PUBCHEM":
            pubchem_from_gsrs = code

    result["cfr_sections"] = list(dict.fromkeys(cfr_sections))
    result["rxcui"] = rxcui
    result["dsld_info"] = dsld_info_raw
    result["cas"] = cas_primary or (cas_all[0] if cas_all else None)
    result["cas_all"] = cas_all
    result["pubchem_cid"] = pubchem_from_gsrs

    # Extract relationships
    rels = substance.get("relationships", [])
    active_moiety = None
    salt_parents = []
    metabolic = []
    metabolites = []

    for r in rels:
        rel_type = r.get("type", "")
        related = r.get("relatedSubstance", {})
        rel_name = related.get("name", "")
        rel_unii = related.get("approvalID", "")

        if rel_type in MOIETY_REL_TYPES:
            # Skip self-referential active moiety
            if rel_unii != substance.get("approvalID"):
                active_moiety = {"name": rel_name, "unii": rel_unii}
        elif rel_type in SALT_REL_TYPES:
            if rel_unii != substance.get("approvalID"):
                salt_parents.append({
                    "type": rel_type, "name": rel_name, "unii": rel_unii,
                })
        elif rel_type in METABOLIC_REL_TYPES:
            metabolic.append({
                "type": rel_type, "name": rel_name, "unii": rel_unii,
            })
        elif rel_type in METABOLITE_REL_TYPES:
            metabolites.append({
                "type": rel_type, "name": rel_name, "unii": rel_unii,
            })

    # Deduplicate by UNII
    seen = set()
    unique_metabolic = []
    for m in metabolic:
        key = (m["type"], m["unii"])
        if key not in seen:
            seen.add(key)
            unique_metabolic.append(m)

    seen_met = set()
    unique_metabolites = []
    for m in metabolites:
        if m["unii"] not in seen_met:
            seen_met.add(m["unii"])
            unique_metabolites.append(m)

    unique_salts = []
    seen_salts = set()
    for salt in salt_parents:
        key = (salt["type"], salt["unii"], salt["name"])
        if key not in seen_salts:
            seen_salts.add(key)
            unique_salts.append(salt)

    result["active_moiety"] = active_moiety
    result["salt_parents"] = unique_salts
    result["metabolic_relationships"] = unique_metabolic
    result["metabolites"] = unique_metabolites[:10]  # Cap at 10 most relevant

    return result


def _normalize_name(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _parse_dsld_count(value: str | None) -> int | None:
    if not value:
        return None
    explicit = re.search(r"number of products\s*:\s*(\d[\d,]*)", value, re.I)
    if explicit:
        return int(explicit.group(1).replace(",", ""))
    match = re.search(r"\d[\d,]*", value)
    if not match:
        return None
    return int(match.group(0).replace(",", ""))


def _candidate_names(primary_name: str, aliases: list[str] | None = None) -> set[str]:
    raw_sources = [primary_name] + (aliases or [])
    names: set[str] = set()
    for raw in raw_sources:
        if not isinstance(raw, str) or not raw.strip():
            continue
        normalized = _normalize_name(raw)
        if normalized:
            names.add(normalized)
        # Extract parenthetical content as separate candidate
        # "Vitamin B1 (Thiamine)" → also add "thiamine"
        paren_match = re.search(r"\(([^)]{3,})\)", raw)
        if paren_match:
            inner = _normalize_name(paren_match.group(1))
            if inner and len(inner) >= 3:
                names.add(inner)
            # Also add the name without the parenthetical
            stripped = re.sub(r"\s*\([^)]*\)\s*", " ", raw).strip()
            stripped_norm = _normalize_name(stripped)
            if stripped_norm and stripped_norm != normalized:
                names.add(stripped_norm)
    return {name for name in names if name}


def _gsrs_names(substance: dict) -> set[str]:
    names = {_normalize_name(substance.get("_name"))}
    for item in substance.get("names", []):
        names.add(_normalize_name(item.get("name")))
    return {name for name in names if name}


BOTANICAL_SPECIFICITY_TOKENS = {
    "extract", "powder", "oil", "juice", "gel", "concentrate", "root", "leaf",
    "seed", "bark", "fruit", "flower", "herb", "berry", "stem", "rhizome",
    "peel", "rind", "resin", "gum", "pollen", "husk", "hull", "kernel",
    "mycelium", "fruiting", "body", "sclerotium", "thallus", "aerial",
}


def _matching_allowed_name(candidate: str, allowed_names: set[str]) -> str | None:
    descriptor_tokens = {
        # Preparation/form descriptors
        "extract", "powder", "oil", "concentrate", "standardized",
        "unspecified", "liquid", "juice", "derived", "hydrolysate",
        "soluble", "immature", "processed", "purified", "refined",
        "oxidized", "fermented", "hydrolyzed", "enzymatic",
        # Botanical part descriptors (GSRS appends these to genus+species)
        "fruit", "root", "leaf", "seed", "bark", "top", "flower",
        "herb", "whole", "berry", "plant", "stem", "rhizome", "bulb",
        "peel", "rind", "husk", "hull", "kernel", "pollen", "resin",
        "gum", "mycelium", "fruiting", "body", "sclerotium", "thallus",
        # Animal source descriptors
        "bovine", "porcine", "marine", "chicken", "egg", "yolk",
        # Taxonomic qualifiers GSRS commonly adds after genus+species
        "var", "subsp", "ssp", "dl",
    }
    if not candidate:
        return None
    if candidate in allowed_names:
        return candidate
    candidate_tokens = set(candidate.split())
    for allowed in allowed_names:
        if not allowed:
            continue
        if candidate == allowed:
            return allowed
        if candidate_tokens and candidate_tokens == set(allowed.split()):
            return allowed
        allowed_tokens = set(allowed.split())
        if (
            len(candidate_tokens) >= 2
            and len(allowed_tokens) >= 2
            and len(allowed) >= 6
            and len(candidate) >= 6
        ):
            if allowed in candidate:
                extra = candidate_tokens - allowed_tokens
                if extra.issubset(descriptor_tokens):
                    return allowed
            elif candidate in allowed:
                extra = allowed_tokens - candidate_tokens
                if extra.issubset(descriptor_tokens):
                    return allowed

    return None


def _matches_allowed_name(candidate: str, allowed_names: set[str]) -> bool:
    return _matching_allowed_name(candidate, allowed_names) is not None


def _has_specificity_conflict(
    candidate_name: str,
    matched_allowed: str,
    primary_name: str,
    entry_latin_name: str | None,
) -> bool:
    candidate_tokens = set(candidate_name.split())
    allowed_tokens = set(matched_allowed.split())
    primary_tokens = set(_normalize_name(primary_name).split())
    latin_tokens = set(_normalize_name(entry_latin_name).split()) if entry_latin_name else set()
    extra_specific_tokens = (
        (candidate_tokens & BOTANICAL_SPECIFICITY_TOKENS)
        - allowed_tokens
        - primary_tokens
        - latin_tokens
    )
    return bool(extra_specific_tokens)


def _collect_flat_aliases(entry: dict) -> list[str]:
    aliases = [alias for alias in entry.get("aliases", []) if isinstance(alias, str)]
    latin_name = entry.get("latin_name")
    if isinstance(latin_name, str) and latin_name.strip():
        aliases.append(latin_name.strip())
    return aliases


def _collect_iqm_aliases(entry: dict, key_name: str) -> list[str]:
    aliases = []
    if key_name:
        aliases.append(key_name)
    for alias in entry.get("aliases", []):
        if isinstance(alias, str):
            aliases.append(alias)
    return aliases


def _is_viable_iqm_lookup_term(value: str) -> bool:
    normalized = _normalize_name(value)
    if not normalized:
        return False
    compact = normalized.replace(" ", "")
    if len(compact) >= 5:
        return True
    return any(ch in value for ch in (" ", "-", ",", "(", ")", "/"))


def _collect_iqm_search_terms(entry: dict, key_name: str) -> list[str]:
    candidates: list[str] = []

    def add(value: str | None) -> None:
        if not isinstance(value, str):
            return
        stripped = value.strip()
        if not stripped:
            return
        candidates.append(stripped)

    for alias in entry.get("aliases", []):
        add(alias)

    forms = entry.get("forms", {})
    for form_data in forms.values():
        if not isinstance(form_data, dict):
            continue
        for alias in form_data.get("aliases", []):
            add(alias)

    marketing_tokens = {
        "supplement", "extract", "powder", "capsules", "capsule", "tablets",
        "tablet", "softgels", "softgel", "liquid", "blend", "standardized",
        "stabilized", "concentrate", "premium", "complex", "formula",
    }

    def sort_key(value: str) -> tuple[int, int, int, str]:
        normalized = _normalize_name(value)
        tokens = normalized.split()
        marketing_penalty = sum(1 for token in tokens if token in marketing_tokens)
        token_count_penalty = len(tokens)
        length_bonus = -len(normalized)
        return (
            0 if _is_viable_iqm_lookup_term(value) else 1,
            marketing_penalty,
            token_count_penalty,
            length_bonus,
        )

    prioritized = []
    seen = set()
    for candidate in sorted(candidates, key=sort_key):
        normalized = _normalize_name(candidate)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        prioritized.append(candidate)

    return prioritized[:8]


def _collect_iqm_cas_values(entry: dict) -> set[str]:
    cas_values = set()
    forms = entry.get("forms", {})
    for form_data in forms.values():
        if not isinstance(form_data, dict):
            continue
        form_ext = form_data.get("external_ids", {})
        cas = form_ext.get("cas") if isinstance(form_ext, dict) else None
        if isinstance(cas, str) and CAS_RE.match(cas):
            cas_values.add(cas)
    ext = entry.get("external_ids", {})
    cas = ext.get("cas") if isinstance(ext, dict) else None
    if isinstance(cas, str) and CAS_RE.match(cas):
        cas_values.add(cas)
    return cas_values


def _validate_substance_match(
    substance: dict,
    *,
    primary_name: str,
    aliases: list[str] | None = None,
    allowed_cas: set[str] | None = None,
    entry_latin_name: str | None = None,
) -> tuple[bool, str | None, dict]:
    enrichment = extract_enrichment(substance)
    gsrs_name = enrichment.get("substance_name") or substance.get("_name") or "?"

    allowed_names = _candidate_names(primary_name, aliases)
    gsrs_names = _gsrs_names(substance)
    matched_allowed_name = None
    for gsrs_candidate in gsrs_names:
        matched_allowed_name = _matching_allowed_name(gsrs_candidate, allowed_names)
        if matched_allowed_name:
            if _has_specificity_conflict(gsrs_candidate, matched_allowed_name, primary_name, entry_latin_name):
                matched_allowed_name = None
                continue
            break
    if not matched_allowed_name:
        return False, f"name mismatch: entry={primary_name} GSRS={gsrs_name}", enrichment
    if _has_specificity_conflict(_normalize_name(gsrs_name), matched_allowed_name, primary_name, entry_latin_name):
        return False, f"name mismatch: entry={primary_name} GSRS={gsrs_name}", enrichment

    gsrs_cas = enrichment.get("cas")
    gsrs_cas_all = {
        value for value in (enrichment.get("cas_all") or [])
        if isinstance(value, str) and CAS_RE.match(value)
    }
    if gsrs_cas and CAS_RE.match(gsrs_cas):
        gsrs_cas_all.add(gsrs_cas)
    normalized_allowed_cas = {
        value for value in (allowed_cas or set())
        if isinstance(value, str) and CAS_RE.match(value)
    }
    if normalized_allowed_cas and gsrs_cas_all and not (normalized_allowed_cas & gsrs_cas_all):
        return False, (
            "CAS mismatch: ours="
            f"{','.join(sorted(normalized_allowed_cas))} GSRS="
            f"{','.join(sorted(gsrs_cas_all))}"
        ), enrichment

    return True, None, enrichment


def _build_gsrs_payload(enrichment: dict) -> dict:
    payload: dict[str, Any] = {
        "substance_name": enrichment.get("substance_name"),
        "substance_class": enrichment.get("substance_class"),
        "cfr_sections": enrichment.get("cfr_sections", []),
        "dsld_count": _parse_dsld_count(enrichment.get("dsld_info")),
        "dsld_info_raw": enrichment.get("dsld_info"),
        "active_moiety": enrichment.get("active_moiety"),
        "salt_parents": enrichment.get("salt_parents", []),
        "metabolic_relationships": enrichment.get("metabolic_relationships", []),
        "metabolites": enrichment.get("metabolites", []),
    }
    return payload


def _apply_gsrs_enrichment(entry: dict, enrichment: dict) -> bool:
    changed = False
    ext = entry.setdefault("external_ids", {})
    if enrichment.get("unii") and ext.get("unii") != enrichment["unii"]:
        ext["unii"] = enrichment["unii"]
        changed = True

    if enrichment.get("rxcui") and entry.get("rxcui") != enrichment["rxcui"]:
        entry["rxcui"] = enrichment["rxcui"]
        changed = True
    if enrichment.get("rxcui"):
        if entry.get("rxcui_note") is not None:
            entry["rxcui_note"] = None
            changed = True

    gsrs_payload = _build_gsrs_payload(enrichment)
    if entry.get("gsrs") != gsrs_payload:
        entry["gsrs"] = gsrs_payload
        changed = True

    return changed


def _clear_gsrs_enrichment(entry: dict) -> int:
    changes = 0
    ext = entry.get("external_ids")
    if isinstance(ext, dict) and ext.get("unii") is not None:
        ext.pop("unii", None)
        changes += 1
    if entry.get("rxcui") is not None:
        entry["rxcui"] = None
        changes += 1
    if entry.get("gsrs") is not None:
        entry["gsrs"] = None
        changes += 1
    return changes


def _should_skip(name: str) -> bool:
    return name.lower().strip() in SKIP_NAMES


CURATED_GSRS_POLICIES = {
    _normalize_name(name): policy
    for name, policy in RAW_CURATED_GSRS_POLICIES.items()
}


def _get_curated_gsrs_policy(name: str) -> dict | None:
    return CURATED_GSRS_POLICIES.get(_normalize_name(name))


def _get_entry_governed_null_reason(entry: dict) -> str | None:
    name = entry.get("standard_name", "")
    curated = _get_curated_gsrs_policy(name)
    if curated is not None:
        return curated["reason"]

    entity_type = (entry.get("entity_type") or "").lower()
    cui_status = entry.get("cui_status")
    cui_note = entry.get("cui_note")
    unii_status = entry.get("unii_status")
    unii_note = entry.get("unii_note")

    if unii_status == "no_single_gsrs_concept":
        return (
            unii_note
            or "record spans multiple substances or a broader class and should not be collapsed to one GSRS substance"
        )
    if unii_status == "no_confirmed_gsrs_match":
        return (
            unii_note
            or "no trustworthy exact GSRS substance match has been confirmed for this ingredient label"
        )

    if entity_type == "class":
        return (
            cui_note
            or "class/policy record spans multiple substances; a single GSRS ingredient identifier would be misleading"
        )
    if entity_type == "product":
        return (
            cui_note
            or "product/brand recall record is intentionally not mapped to a single GSRS ingredient identity"
        )
    if cui_status == "no_single_umls_concept":
        return (
            cui_note
            or "record is intentionally multi-concept and should not be collapsed to a single GSRS substance"
        )

    return None


# ---------------------------------------------------------------------------
# Flat file verification
# ---------------------------------------------------------------------------

def verify_flat_file(
    data: dict, list_key: str, client: GSRSClient, apply: bool = False
) -> dict:
    entries = data.get(list_key, [])
    results = {
        "verified": [], "filled": [], "rejected": [],
        "governed_null": [],
        "not_found": [], "skipped": [], "errors": [],
    }
    changes_made = 0

    for i, entry in enumerate(entries):
        eid = entry.get("id", f"entry_{i}")
        name = entry.get("standard_name", "")
        ext = entry.get("external_ids", {})
        existing_cas = ext.get("cas")
        existing_unii = ext.get("unii")
        aliases = _collect_flat_aliases(entry)

        if _should_skip(name):
            results["skipped"].append({"id": eid, "name": name})
            continue
        governed_reason = _get_entry_governed_null_reason(entry)
        if governed_reason is not None:
            results["governed_null"].append({
                "id": eid,
                "name": name,
                "reason": governed_reason,
            })
            if apply:
                changes_made += _clear_gsrs_enrichment(entry)
            continue

        if existing_unii:
            substance = client.get_full_substance(existing_unii)
            if substance is None:
                results["rejected"].append({
                    "id": eid, "name": name,
                    "reason": f"Existing UNII not found in GSRS: {existing_unii}",
                    "gsrs_name": existing_unii,
                })
                continue
            is_valid, reason, enrichment = _validate_substance_match(
                substance,
                primary_name=name,
                aliases=aliases,
                allowed_cas={existing_cas} if existing_cas else set(),
                entry_latin_name=entry.get("latin_name"),
            )
            if not is_valid:
                results["rejected"].append({
                    "id": eid, "name": name, "reason": reason,
                    "gsrs_name": enrichment.get("substance_name"),
                })
                if apply:
                    changes_made += _clear_gsrs_enrichment(entry)
                continue
            results["verified"].append({"id": eid, "name": name, **enrichment})
            if apply and _apply_gsrs_enrichment(entry, enrichment):
                changes_made += 1
            continue

        # Search GSRS — try standard_name first, then aliases
        substance = client.search_substance(name, cas=existing_cas)
        if substance is None:
            for alias in aliases[:3]:
                if len(alias) >= 6:
                    substance = client.search_substance(alias)
                    if substance is not None:
                        break
        if substance is None:
            results["not_found"].append({"id": eid, "name": name})
            continue

        is_valid, reason, enrichment = _validate_substance_match(
            substance,
            primary_name=name,
            aliases=aliases,
            allowed_cas={existing_cas} if existing_cas else set(),
            entry_latin_name=entry.get("latin_name"),
        )
        if not is_valid:
            results["rejected"].append({
                "id": eid, "name": name,
                "reason": reason,
                "gsrs_name": enrichment.get("substance_name"),
            })
            if apply:
                changes_made += _clear_gsrs_enrichment(entry)
            continue

        record = {"id": eid, "name": name, **enrichment}
        results["filled"].append(record)

        if apply and _apply_gsrs_enrichment(entry, enrichment):
            changes_made += 1

        total = len(entries)
        done = i + 1
        if done % 10 == 0 or done == total:
            print(f"  [{done}/{total}] {name}", file=sys.stderr)

    results["total"] = len(entries)
    results["changes_applied"] = changes_made
    return results


# ---------------------------------------------------------------------------
# IQM verification (ingredient-level UNII)
# ---------------------------------------------------------------------------

def verify_iqm_file(
    data: dict, client: GSRSClient, apply: bool = False
) -> dict:
    results = {
        "filled": [], "verified": [], "rejected": [],
        "governed_null": [],
        "not_found": [], "skipped": [],
    }
    changes_made = 0

    keys = [k for k in data.keys() if k != "_metadata"]
    total = len(keys)

    for idx, key in enumerate(keys):
        entry = data[key]
        if not isinstance(entry, dict):
            continue

        name = entry.get("standard_name", key)
        key_name = key.replace("_", " ")
        existing_unii = (entry.get("external_ids") or {}).get("unii")
        aliases = _collect_iqm_aliases(entry, key_name)
        cas_values = _collect_iqm_cas_values(entry)

        if _should_skip(name):
            results["skipped"].append({"key": key, "name": name})
            continue
        governed_reason = _get_entry_governed_null_reason(entry)
        if governed_reason is not None:
            results["governed_null"].append({
                "key": key,
                "name": name,
                "reason": governed_reason,
            })
            if apply:
                changes_made += _clear_gsrs_enrichment(entry)
            continue

        if existing_unii:
            substance = client.get_full_substance(existing_unii)
            if substance is None:
                results["rejected"].append({
                    "key": key, "name": name,
                    "reason": f"Existing UNII not found in GSRS: {existing_unii}",
                    "gsrs_name": existing_unii,
                })
                continue
            is_valid, reason, enrichment = _validate_substance_match(
                substance,
                primary_name=name,
                aliases=aliases,
                allowed_cas=cas_values,
                entry_latin_name=entry.get("latin_name"),
            )
            if not is_valid:
                results["rejected"].append({
                    "key": key, "name": name, "reason": reason,
                    "gsrs_name": enrichment.get("substance_name"),
                })
                if apply:
                    changes_made += _clear_gsrs_enrichment(entry)
                continue
            results["verified"].append({"key": key, "name": name, **enrichment})
            if apply and _apply_gsrs_enrichment(entry, enrichment):
                changes_made += 1
            continue

        cas_for_validation = next(iter(cas_values), None)
        forms = entry.get("forms", {})
        lookup_terms = _collect_iqm_search_terms(entry, key_name)

        # Search strategy: try name, key, entry-level aliases, then form-level terms.
        # For each hit, validate. If validation rejects, keep trying next term.
        search_candidates = [name]
        if key_name.lower() != name.lower():
            search_candidates.append(key_name)
        # Add entry-level aliases (e.g., "Withania somnifera" for ashwagandha)
        for alias in aliases:
            if alias.lower() not in {c.lower() for c in search_candidates}:
                search_candidates.append(alias)
        # Add form-level terms last
        for term in lookup_terms:
            if _is_viable_iqm_lookup_term(term) and term.lower() not in {c.lower() for c in search_candidates}:
                search_candidates.append(term)

        # Combine entry-level aliases + form-level terms for validation
        all_validation_aliases = aliases + [
            t for t in lookup_terms if t.lower() not in {a.lower() for a in aliases}
        ]

        best_substance = None
        best_rejection = None
        for term in search_candidates:
            substance = client.search_substance(term, cas=cas_for_validation if term == name else None)
            if substance is None:
                continue
            is_valid, reason, enrichment = _validate_substance_match(
                substance,
                primary_name=name,
                aliases=all_validation_aliases,
                allowed_cas=cas_values,
                entry_latin_name=entry.get("latin_name"),
            )
            if is_valid:
                best_substance = substance
                break
            # Keep the first rejection for reporting
            if best_rejection is None:
                best_rejection = (reason, enrichment)

        if best_substance is None and best_rejection is None:
            results["not_found"].append({"key": key, "name": name})
            continue
        if best_substance is None:
            reason, enrichment = best_rejection
            results["rejected"].append({
                "key": key, "name": name,
                "reason": reason,
                "gsrs_name": enrichment.get("substance_name"),
            })
            if apply:
                changes_made += _clear_gsrs_enrichment(entry)
            continue

        enrichment = extract_enrichment(best_substance)

        record = {"key": key, "name": name, **enrichment}
        results["filled"].append(record)

        if apply and _apply_gsrs_enrichment(entry, enrichment):
            changes_made += 1

        if (idx + 1) % 20 == 0 or idx + 1 == total:
            print(f"  [{idx+1}/{total}] {name}", file=sys.stderr)

    results["total_ingredients"] = total
    results["changes_applied"] = changes_made
    return results


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def _print_enrichment_sample(records: list, label: str, limit: int = 25) -> None:
    if not records:
        return
    print(f"\n--- {label} ({len(records)}) ---")
    for r in records[:limit]:
        ident = r.get("id") or r.get("key", "?")
        name = r.get("name", "?")
        unii = r.get("unii", "?")
        cfr = r.get("cfr_sections", [])
        rxcui = r.get("rxcui")
        moiety = r.get("active_moiety")
        metab = r.get("metabolic_relationships", [])
        salts = r.get("salt_parents", [])
        dsld = r.get("dsld_info")

        parts = [f"UNII={unii}"]
        if cfr:
            parts.append(f"CFR={','.join(cfr)}")
        if rxcui:
            parts.append(f"RxCUI={rxcui}")
        if moiety:
            parts.append(f"moiety={moiety['name']}")
        if salts:
            parts.append(f"salts={len(salts)}")
        if metab:
            parts.append(f"metab={len(metab)}")
        if dsld:
            parts.append(f"DSLD={dsld[:40]}")

        print(f"  {ident}: {name} | {' | '.join(parts)}")

    if len(records) > limit:
        print(f"  ... and {len(records) - limit} more")


def print_flat_report(results: dict) -> None:
    total = results["total"]
    print(f"\n{'='*60}")
    print(f"GSRS/UNII Verification Report")
    print(f"{'='*60}")
    print(f"Total entries:    {total}")
    print(f"Already had UNII: {len(results['verified'])}")
    print(f"Filled:           {len(results['filled'])}")
    print(f"Rejected (bad match): {len(results['rejected'])}")
    print(f"Governed null:    {len(results['governed_null'])}")
    print(f"Not found:        {len(results['not_found'])}")
    print(f"Skipped:          {len(results['skipped'])}")

    if results.get("changes_applied", 0):
        print(f"\nChanges applied:  {results['changes_applied']}")

    _print_enrichment_sample(results["filled"], "Filled")

    if results["rejected"]:
        print(f"\n--- Rejected ({len(results['rejected'])}) ---")
        for r in results["rejected"]:
            print(f"  {r['id']}: {r['name']}")
            print(f"    reason: {r['reason']}")
            print(f"    GSRS returned: {r.get('gsrs_name', '?')}")

    if results["governed_null"]:
        print(f"\n--- Governed Null ({len(results['governed_null'])}) ---")
        for r in results["governed_null"]:
            print(f"  {r['id']}: {r['name']}")
            print(f"    reason: {r['reason']}")

    if results["not_found"]:
        print(f"\n--- Not Found ({len(results['not_found'])}) ---")
        for r in results["not_found"][:20]:
            print(f"  {r['id']}: {r['name']}")
        if len(results["not_found"]) > 20:
            print(f"  ... and {len(results['not_found']) - 20} more")


def print_iqm_report(results: dict) -> None:
    total = results["total_ingredients"]
    print(f"\n{'='*60}")
    print(f"GSRS/UNII IQM Verification Report")
    print(f"{'='*60}")
    print(f"Total ingredients: {total}")
    print(f"Already had UNII:  {len(results['verified'])}")
    print(f"Filled:            {len(results['filled'])}")
    print(f"Rejected:          {len(results['rejected'])}")
    print(f"Governed null:     {len(results['governed_null'])}")
    print(f"Not found:         {len(results['not_found'])}")
    print(f"Skipped:           {len(results['skipped'])}")

    if results.get("changes_applied", 0):
        print(f"\nChanges applied:   {results['changes_applied']}")

    _print_enrichment_sample(results["filled"], "Filled")

    if results["not_found"]:
        print(f"\n--- Not Found ({len(results['not_found'])}) ---")
        for r in results["not_found"][:20]:
            print(f"  {r['key']}: {r['name']}")
        if len(results["not_found"]) > 20:
            print(f"  ... and {len(results['not_found']) - 20} more")
    if results["governed_null"]:
        print(f"\n--- Governed Null ({len(results['governed_null'])}) ---")
        for r in results["governed_null"][:20]:
            print(f"  {r['key']}: {r['name']}")
            print(f"    reason: {r['reason']}")


# ---------------------------------------------------------------------------
# Single lookups
# ---------------------------------------------------------------------------

def do_search(client: GSRSClient, query: str) -> None:
    print(f"Searching GSRS for: {query}")
    substance = client.search_substance(query)
    if substance is None:
        print("  NOT FOUND in GSRS")
        return

    enrichment = extract_enrichment(substance)

    print(f"  Name:       {enrichment['substance_name']}")
    print(f"  UNII:       {enrichment['unii']}")
    print(f"  Class:      {enrichment['substance_class']}")
    print(f"  CAS:        {enrichment['cas'] or 'none'}")
    print(f"  RxCUI:      {enrichment['rxcui'] or 'none'}")
    print(f"  PubChem:    {enrichment['pubchem_cid'] or 'none'}")
    if enrichment["cfr_sections"]:
        print(f"  CFR:        {', '.join(enrichment['cfr_sections'])}")
    if enrichment["dsld_info"]:
        print(f"  DSLD:       {enrichment['dsld_info']}")
    if enrichment["active_moiety"]:
        m = enrichment["active_moiety"]
        print(f"  Moiety:     {m['name']} (UNII: {m['unii']})")
    if enrichment["salt_parents"]:
        print(f"  Salt/parent forms ({len(enrichment['salt_parents'])}):")
        for s in enrichment["salt_parents"][:5]:
            print(f"    {s['type']}: {s['name']} (UNII: {s['unii']})")
    if enrichment["metabolic_relationships"]:
        print(f"  Metabolic ({len(enrichment['metabolic_relationships'])}):")
        for m in enrichment["metabolic_relationships"][:8]:
            print(f"    {m['type']}: {m['name']}")
    if enrichment["metabolites"]:
        print(f"  Metabolites ({len(enrichment['metabolites'])}):")
        for m in enrichment["metabolites"][:5]:
            print(f"    {m['name']} (UNII: {m['unii']})")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="FDA GSRS/UNII verification & enrichment for PharmaGuide",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  Dry-run harmful_additives:
    python3 scripts/api_audit/verify_unii.py --file scripts/data/harmful_additives.json --list-key harmful_additives

  Apply safe fills:
    python3 scripts/api_audit/verify_unii.py --file scripts/data/harmful_additives.json --list-key harmful_additives --apply

  IQM mode:
    python3 scripts/api_audit/verify_unii.py --file scripts/data/ingredient_quality_map.json --mode iqm

  Search a substance:
    python3 scripts/api_audit/verify_unii.py --search "curcumin"
""",
    )
    parser.add_argument("--file", type=str, help="JSON data file to verify")
    parser.add_argument("--list-key", type=str,
                        help="JSON key containing the entry list (flat mode)")
    parser.add_argument("--mode", choices=["flat", "iqm"], default="flat",
                        help="File structure: flat or iqm")
    parser.add_argument("--apply", action="store_true",
                        help="Apply safe UNII fills to the file")
    parser.add_argument("--search", type=str, help="Search GSRS by substance name")
    parser.add_argument("--no-cache", action="store_true",
                        help="Disable response caching")
    args = parser.parse_args()

    cache_dir = SCRIPTS_ROOT / ".cache"
    cache_path = None if args.no_cache else cache_dir / "gsrs_cache.json"
    client = GSRSClient(cache_path=cache_path)

    if args.search:
        do_search(client, args.search)
        client.save_cache()
        return 0

    if not args.file:
        parser.print_help()
        return 1

    file_path = Path(args.file)
    if not file_path.exists():
        print(f"[ERROR] File not found: {file_path}", file=sys.stderr)
        return 1

    print(f"[GSRS] Loading {file_path.name}...")
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if args.mode == "iqm":
        print(f"[GSRS] IQM mode — verifying ingredients...")
        results = verify_iqm_file(data, client, apply=args.apply)
        print_iqm_report(results)
    else:
        if not args.list_key:
            print("[ERROR] --list-key required for flat mode", file=sys.stderr)
            return 1
        print(f"[GSRS] Flat mode — verifying {args.list_key}...")
        results = verify_flat_file(data, args.list_key, client, apply=args.apply)
        print_flat_report(results)

    if args.apply and results.get("changes_applied", 0) > 0:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print(f"\n[GSRS] Wrote {results['changes_applied']} changes to {file_path.name}")

    client.save_cache()
    print(f"[GSRS] Done. ({client.request_count} API requests)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
