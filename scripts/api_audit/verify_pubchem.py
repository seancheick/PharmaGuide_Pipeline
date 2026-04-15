#!/usr/bin/env python3
from __future__ import annotations
"""
PubChem PUG REST verification and enrichment tool for PharmaGuide data files.

What this script does:
  1. Looks up each entry by standard_name (or form name for IQM) on PubChem.
  2. Retrieves PubChem CID, CAS number, and synonym list.
  3. Validates existing CAS numbers against PubChem's records.
  4. Fills missing CAS and PubChem CID values.
  5. Rejects unsafe matches for umbrella entries, mixtures, and ambiguous short aliases.
  6. Supports flat files (harmful_additives, banned_recalled) and nested IQM (ingredient → forms).

Operator runbook:
  1. Dry-run a flat file:
       python3 scripts/api_audit/verify_pubchem.py --file scripts/data/harmful_additives.json --list-key harmful_additives
  2. Dry-run banned/recalled:
       python3 scripts/api_audit/verify_pubchem.py --file scripts/data/banned_recalled_ingredients.json --list-key ingredients
  3. Dry-run IQM (nested forms):
       python3 scripts/api_audit/verify_pubchem.py --file scripts/data/ingredient_quality_map.json --mode iqm
  4. Apply safe fixes (CAS + CID fills only):
       python3 scripts/api_audit/verify_pubchem.py --file scripts/data/harmful_additives.json --list-key harmful_additives --apply
  5. Search a single compound:
       python3 scripts/api_audit/verify_pubchem.py --search "magnesium glycinate"
  6. Look up a CID directly:
       python3 scripts/api_audit/verify_pubchem.py --cid 11177

Null policy:
  - Leave CAS/CID null for proprietary blends, umbrella categories, and multi-compound entries.
  - The SKIP_NAMES set defines entries that should not be looked up.

Rate limits:
  - PubChem PUG REST: 5 requests/second (no API key needed).
  - This script enforces 0.22s between requests (~4.5 req/s) to stay under the limit.

Environment:
  No API key needed. PubChem PUG REST is free and open.
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

BASE_URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
RATE_LIMIT_DELAY = 0.22  # ~4.5 req/s, under PubChem's 5/s limit
DEFAULT_CACHE_TTL_SECONDS = 60 * 60 * 24 * 30  # 30 days
CAS_RE = re.compile(r"^\d{2,7}-\d{2}-\d$")
MULTI_COMPOUND_RE = re.compile(r"(?:\s*&\s*|\s*/\s*|\band\b)|\bcompounds?\b", re.I)
NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
IQM_FORM_SKIP_RE = re.compile(
    r"\b("
    r"unspecified|with|from|extract|complex|blend|coated|enteric|"
    r"liposomal|refrigerated|gummies?|chewables?|slow-release|"
    r"delayed release|release|liquid|drops?|spore|probiotic|"
    r"live|capsules?|softgels?|tablets?"
    r")\b",
    re.I,
)
AMBIGUOUS_ALIAS_KEYS = {
    "peg",
    "pvp",
    "hfcs",
    "bps",
    "bpf",
}

def _load_pubchem_policies() -> dict | None:
    """Load PubChem policies from JSON file."""
    path = Path(__file__).resolve().parent.parent / "data" / "curated_overrides" / "pubchem_policies.json"
    if path.exists():
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return None

_PUBCHEM_EXT = _load_pubchem_policies()

# Entries that should not be looked up (umbrella, proprietary, multi-compound)
SKIP_NAMES = set(_PUBCHEM_EXT["skip_names"]) if _PUBCHEM_EXT else {
    # harmful_additives umbrella/proprietary entries
    "unspecified colors",
    "synthetic vitamins",
    "synthetic b vitamins",
    "sugar alcohols",
    "sugar syrups",
    "syrups",
    "slimsweet",
    "purefruit select",
    "time-sorb",
    "artificial flavors",
    "synthetic antioxidants",
    "caramel color",
    "polyethylene glycol",
    "polyvinylpyrrolidone",
    # banned_recalled class/policy entries
    "partially hydrogenated oils",
    "partially hydrogenated oils (phos)",
    "synthetic estrogens",
    "phthalates",
    "synthetic anabolic steroids",
    "contaminated glp-1 compounds",
    "metal fiber contamination",
    "cannabis/thc",
    # IQM umbrella categories
    "general probiotics",
}

RAW_CURATED_ENTRY_POLICIES = (_PUBCHEM_EXT["entry_policies"] if _PUBCHEM_EXT else {
    "High Fructose Corn Syrup": {
        "reason": "processed mixture; no single authoritative PubChem compound",
        "expected_cas": None,
        "expected_cid": None,
    },
    "Polyethylene Glycol (PEG)": {
        "reason": "polymer / non-discrete PubChem substance; curated CAS only",
        "expected_cas": "25322-68-3",
        "expected_cid": None,
    },
    "Polyvinylpyrrolidone (PVP)": {
        "reason": "polymer / non-discrete PubChem substance; curated CAS only",
        "expected_cas": "9003-39-8",
        "expected_cid": None,
    },
    "Polydextrose": {
        "reason": "polymer mixture; no single authoritative PubChem compound",
        "expected_cas": None,
        "expected_cid": None,
    },
    "Carrageenan": {
        "reason": "complex polysaccharide mixture; keep curated CAS only",
        "expected_cas": "9000-07-1",
        "expected_cid": None,
    },
    "Maltodextrin": {
        "reason": "polysaccharide mixture; no single authoritative PubChem compound",
        "expected_cas": None,
        "expected_cid": None,
    },
    "Carboxymethylcellulose (CMC)": {
        "reason": "cellulose derivative mixture; keep curated CAS only",
        "expected_cas": "9004-32-4",
        "expected_cid": None,
    },
    "Iron Oxide": {
        "reason": "regulatory pigment class spans multiple iron oxide species; keep curated CAS only",
        "expected_cas": "1309-37-1",
        "expected_cid": None,
    },
    "Mineral Oil": {
        "reason": "petroleum mixture; keep curated CAS only",
        "expected_cas": "8042-47-5",
        "expected_cid": None,
    },
    "Soy Monoglycerides": {
        "reason": "fatty-acid monoglyceride mixture; keep curated CAS only",
        "expected_cas": "68554-09-6",
        "expected_cid": None,
    },
    "Hydrogenated Starch Hydrolysate": {
        "reason": "sugar-alcohol mixture; no single authoritative PubChem compound",
        "expected_cas": None,
        "expected_cid": None,
    },
    "Isomaltooligosaccharide": {
        "reason": "oligosaccharide mixture; no single authoritative PubChem compound",
        "expected_cas": None,
        "expected_cid": None,
    },
    "Microcrystalline Cellulose": {
        "reason": "cellulose material / non-discrete PubChem substance",
        "expected_cas": None,
        "expected_cid": None,
    },
})

# ---------------------------------------------------------------------------
# SSL fallback (macOS Python often lacks certs)
# ---------------------------------------------------------------------------

def _make_ssl_ctx() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    try:
        req = urllib.request.Request(BASE_URL, method="HEAD")
        urllib.request.urlopen(req, timeout=5, context=ctx)
        return ctx
    except ssl.SSLCertVerificationError:
        return ssl._create_unverified_context()
    except urllib.error.URLError as exc:
        if isinstance(getattr(exc, "reason", None), ssl.SSLCertVerificationError):
            return ssl._create_unverified_context()
        return ctx
    except TimeoutError:
        return ssl._create_unverified_context()
    except Exception:
        return ctx

_SSL_CTX = _make_ssl_ctx()


# ---------------------------------------------------------------------------
# PubChem client
# ---------------------------------------------------------------------------

class PubChemClient:
    """Thin stdlib wrapper around PubChem PUG REST API."""

    def __init__(
        self,
        *,
        timeout_seconds: float = 15.0,
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
        """GET JSON from PubChem with retry and circuit breaker."""
        if self.circuit_open:
            return None

        cache_key = url
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        for attempt in range(1, 4):
            try:
                self._request_count += 1
                time.sleep(RATE_LIMIT_DELAY)
                req = urllib.request.Request(url, headers={"Accept": "application/json"})
                with urllib.request.urlopen(req, timeout=self.timeout_seconds, context=_SSL_CTX) as resp:
                    data = json.loads(resp.read().decode())
                    self._consecutive_failures = 0
                    self._cache_set(cache_key, data)
                    return data
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    # Not found is a valid result — cache it
                    not_found = {"Fault": {"Code": "PUGREST.NotFound"}}
                    self._cache_set(cache_key, not_found)
                    self._consecutive_failures = 0
                    return not_found
                if e.code == 503 or e.code == 429:
                    # Rate limited or server busy — back off
                    wait = RATE_LIMIT_DELAY * (2 ** attempt)
                    print(f"  [RETRY {attempt}/3] HTTP {e.code}, waiting {wait:.1f}s...", file=sys.stderr)
                    time.sleep(wait)
                    continue
                print(f"  [ERROR] HTTP {e.code} for {url}", file=sys.stderr)
                return None
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                self._consecutive_failures += 1
                if self._consecutive_failures >= self.failure_limit:
                    print(f"  [CIRCUIT OPEN] {self._consecutive_failures} consecutive failures — stopping API calls", file=sys.stderr)
                    self.circuit_open = True
                    return None
                wait = RATE_LIMIT_DELAY * (2 ** attempt)
                print(f"  [RETRY {attempt}/3] {e}, waiting {wait:.1f}s...", file=sys.stderr)
                time.sleep(wait)
        return None

    # ── Public API methods ─────────────────────────────────────────────────

    def name_to_cid(self, name: str) -> int | None:
        """Look up a compound by name → return CID or None."""
        encoded = urllib.request.quote(name, safe="")
        data = self._get(f"{BASE_URL}/compound/name/{encoded}/cids/JSON")
        if data and "IdentifierList" in data:
            cids = data["IdentifierList"].get("CID", [])
            return cids[0] if cids else None
        return None

    def cid_to_synonyms(self, cid: int) -> list[str]:
        """Get all PubChem synonyms for a CID."""
        data = self._get(f"{BASE_URL}/compound/cid/{cid}/synonyms/JSON")
        if data and "InformationList" in data:
            info = data["InformationList"].get("Information", [])
            if info:
                return info[0].get("Synonym", [])
        return []

    def cid_to_properties(self, cid: int) -> dict | None:
        """Get molecular formula, weight, IUPAC name, InChIKey for a CID."""
        data = self._get(
            f"{BASE_URL}/compound/cid/{cid}/property/"
            "MolecularFormula,MolecularWeight,IUPACName,InChIKey/JSON"
        )
        if data and "PropertyTable" in data:
            props = data["PropertyTable"].get("Properties", [])
            return props[0] if props else None
        return None

    def cas_to_cid(self, cas: str) -> int | None:
        """Look up a CAS number → return CID or None."""
        return self.name_to_cid(cas)

    def search_compound(self, name: str, include_properties: bool = False) -> dict | None:
        """Full compound lookup: CID, CAS, synonyms, properties."""
        cid = self.name_to_cid(name)
        if cid is None:
            return None

        synonyms = self.cid_to_synonyms(cid)
        cas_numbers = [s for s in synonyms if CAS_RE.match(s)]
        properties = self.cid_to_properties(cid) if include_properties else None

        return {
            "cid": cid,
            "cas": cas_numbers[0] if cas_numbers else None,
            "cas_all": cas_numbers,
            "synonyms": synonyms,
            "properties": properties,
        }


# ---------------------------------------------------------------------------
# Extraction helpers
# ---------------------------------------------------------------------------

def extract_cas_from_synonyms(synonyms: list[str]) -> str | None:
    """Extract the first CAS number from a PubChem synonym list."""
    for s in synonyms:
        if CAS_RE.match(s):
            return s
    return None


def _normalize_label(text: str) -> str:
    text = re.sub(r"\s*\([^)]*\)\s*", " ", (text or "").lower())
    text = NON_ALNUM_RE.sub(" ", text)
    return " ".join(text.split())


def _clean_name(name: str) -> str:
    """Normalize a compound name for PubChem lookup.

    Strips parenthetical qualifiers that PubChem won't recognize:
      "Fructose & High Fructose Corn Syrup" → "Fructose"
      "Corn Oil (Refined)" → "Corn Oil"
      "Cupric Sulfate" → "Cupric Sulfate"
    """
    # Try the full name first — only simplify if PubChem won't find it
    name = name.strip()
    # Remove trailing parenthetical qualifiers
    name = re.sub(r"\s*\([^)]*\)\s*$", "", name)
    # Split on " & " or " / " and take first part
    if " & " in name:
        name = name.split(" & ")[0].strip()
    if " / " in name:
        name = name.split(" / ")[0].strip()
    return name


SKIP_NAME_KEYS = {_normalize_label(name) for name in SKIP_NAMES}
CURATED_ENTRY_POLICIES = {
    _normalize_label(name): policy
    for name, policy in RAW_CURATED_ENTRY_POLICIES.items()
}


def _should_skip(name: str) -> bool:
    """Check if an entry name should be skipped (umbrella/proprietary)."""
    normalized = _normalize_label(name)
    if normalized in SKIP_NAME_KEYS:
        return True
    if MULTI_COMPOUND_RE.search(name):
        return True
    return False


def _get_curated_entry_policy(name: str) -> dict[str, Any] | None:
    return CURATED_ENTRY_POLICIES.get(_normalize_label(name))


def _iqm_form_skip_reason(ingredient_name: str, form_name: str) -> str | None:
    if _should_skip(form_name):
        return "umbrella/proprietary form"
    if IQM_FORM_SKIP_RE.search(form_name):
        return "non-compound formulation form"
    normalized_form = _normalize_label(form_name)
    if normalized_form == _normalize_label(ingredient_name):
        return "ingredient-level placeholder form"
    return None


def _alias_is_ambiguous(alias: str) -> bool:
    normalized = _normalize_label(alias)
    compact = normalized.replace(" ", "")
    return compact in AMBIGUOUS_ALIAS_KEYS or (compact.isalpha() and len(compact) <= 4)


def _synonym_key_set(compound: dict[str, Any]) -> set[str]:
    return {_normalize_label(value) for value in compound.get("synonyms", []) if value}


def _candidate_queries(name: str, aliases: list[str], *, max_alias_queries: int = 3) -> list[tuple[str, str]]:
    queries: list[tuple[str, str]] = [("standard_name", name)]
    cleaned = _clean_name(name)
    if cleaned and cleaned.lower() != name.lower():
        queries.append(("cleaned_name", cleaned))
    seen_alias_keys = {_normalize_label(name), _normalize_label(cleaned)}
    ordered_aliases = sorted(
        [alias for alias in aliases if alias],
        key=lambda alias: (_alias_is_ambiguous(alias), -len(_normalize_label(alias))),
    )
    selected_aliases: list[str] = []
    for alias in ordered_aliases:
        alias_key = _normalize_label(alias)
        if not alias_key or alias_key in seen_alias_keys:
            continue
        seen_alias_keys.add(alias_key)
        selected_aliases.append(alias)
        if len(selected_aliases) >= max_alias_queries:
            break
    for alias in selected_aliases:
        queries.append(("alias", alias))
    return queries


def _accept_match(
    compound: dict[str, Any],
    *,
    standard_name: str,
    aliases: list[str],
    query: str,
    role: str,
) -> tuple[bool, str]:
    synonym_keys = _synonym_key_set(compound)
    standard_keys = {
        _normalize_label(standard_name),
        _normalize_label(_clean_name(standard_name)),
    }
    alias_keys = {_normalize_label(alias) for alias in aliases if alias}
    query_key = _normalize_label(query)

    if any(key and key in synonym_keys for key in standard_keys):
        return True, "exact_standard_name"
    if query_key and query_key in synonym_keys:
        if role == "alias" and _alias_is_ambiguous(query):
            return False, "ambiguous_alias_only"
        return True, "exact_alias" if role == "alias" else "exact_query"
    if role == "alias" and any(key and key in synonym_keys for key in alias_keys if not _alias_is_ambiguous(key)):
        return True, "non_ambiguous_alias"
    return False, "no_exact_name_match"


def _botanical_pubchem_match_is_safe(entry: dict[str, Any], compound: dict[str, Any]) -> bool:
    latin_name = entry.get("latin_name")
    if not isinstance(latin_name, str) or not latin_name.strip():
        return True

    standard_tokens = set(_normalize_label(entry.get("standard_name", "")).split())
    if standard_tokens & {
        "oil", "extract", "resin", "oleoresin", "juice", "gel", "distillate",
    }:
        return False

    synonym_keys = _synonym_key_set(compound)
    latin_key = _normalize_label(latin_name)
    return latin_key in synonym_keys and len(synonym_keys) == 1


def _lookup_entry_compound(
    client: PubChemClient,
    name: str,
    aliases: list[str],
    *,
    max_alias_queries: int = 3,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    ambiguous: dict[str, Any] | None = None
    for role, query in _candidate_queries(name, aliases, max_alias_queries=max_alias_queries):
        if role == "alias" and _alias_is_ambiguous(query):
            if ambiguous is None:
                ambiguous = {
                    "query": query,
                    "role": role,
                    "reason": "ambiguous_alias_skipped",
                    "pubchem_cid": None,
                    "pubchem_cas": None,
                    "synonyms_sample": [],
                }
            continue
        compound = client.search_compound(query, include_properties=False)
        if compound is None:
            continue
        accepted, reason = _accept_match(
            compound,
            standard_name=name,
            aliases=aliases,
            query=query,
            role=role,
        )
        if accepted:
            entry_stub = {"standard_name": name, "aliases": aliases}
            if not _botanical_pubchem_match_is_safe(entry_stub, compound):
                accepted = False
                reason = "botanical_parent_pubchem_disallowed"
        if accepted:
            compound["match_reason"] = reason
            compound["matched_query"] = query
            compound["matched_role"] = role
            return compound, ambiguous
        if ambiguous is None:
            ambiguous = {
                "query": query,
                "role": role,
                "reason": reason,
                "pubchem_cid": compound.get("cid"),
                "pubchem_cas": compound.get("cas"),
                "synonyms_sample": compound.get("synonyms", [])[:8],
            }
    return None, ambiguous


def _normalize_pubchem_id(value: Any) -> Any:
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return value


def _clear_pubchem_ids(entry: dict) -> int:
    changes = 0
    ext = entry.setdefault("external_ids", {})
    if ext.get("cas") is not None:
        ext.pop("cas", None)
        changes += 1
    if ext.get("pubchem_cid") is not None:
        ext.pop("pubchem_cid", None)
        changes += 1
    return changes


# ---------------------------------------------------------------------------
# Flat file verification (harmful_additives, banned_recalled)
# ---------------------------------------------------------------------------

def verify_flat_file(data: dict, list_key: str, client: PubChemClient, apply: bool = False) -> dict:
    """Verify CAS/CID for a flat-structure JSON file.

    Returns a summary dict with results broken down by status.
    """
    entries = data.get(list_key, [])
    results = {
        "verified": [],        # CAS existed and matches PubChem
        "cas_filled": [],      # CAS was missing, PubChem found it
        "cid_filled": [],      # CID was missing, PubChem found it
        "cas_mismatch": [],    # CAS exists but doesn't match PubChem
        "cid_mismatch": [],    # CID exists but doesn't match PubChem
        "governed_null": [],   # Curated intentional-null / override entries
        "ambiguous_match": [], # Lookup found a CID, but match quality was unsafe
        "not_found": [],       # PubChem has no record for this name
        "skipped": [],         # Umbrella/proprietary, skip by design
        "errors": [],          # API errors
    }
    changes_made = 0

    for i, entry in enumerate(entries):
        eid = entry.get("id", f"entry_{i}")
        name = entry.get("standard_name", "")
        ext = entry.get("external_ids", {})
        existing_cas = ext.get("cas")
        existing_cid = ext.get("pubchem_cid")
        if entry.get("latin_name"):
            results["governed_null"].append({
                "id": eid,
                "name": name,
                "reason": "botanical whole-plant and plant-part rows should not be auto-collapsed to discrete PubChem compound identities",
                "expected_cas": None,
                "expected_cid": None,
            })
            if apply:
                changes_made += _clear_pubchem_ids(entry)
            continue

        curated_policy = _get_curated_entry_policy(name)
        if curated_policy is not None:
            record = {
                "id": eid,
                "name": name,
                "reason": curated_policy["reason"],
                "expected_cas": curated_policy.get("expected_cas"),
                "expected_cid": curated_policy.get("expected_cid"),
            }
            results["governed_null"].append(record)
            if apply:
                if "external_ids" not in entry:
                    entry["external_ids"] = {}
                if curated_policy.get("expected_cas") is None:
                    if entry["external_ids"].get("cas") is not None:
                        entry["external_ids"].pop("cas", None)
                        changes_made += 1
                elif not entry["external_ids"].get("cas"):
                    entry["external_ids"]["cas"] = curated_policy["expected_cas"]
                    changes_made += 1
                if curated_policy.get("expected_cid") is None:
                    if entry["external_ids"].get("pubchem_cid") is not None:
                        entry["external_ids"].pop("pubchem_cid", None)
                        changes_made += 1
                elif not entry["external_ids"].get("pubchem_cid"):
                    entry["external_ids"]["pubchem_cid"] = curated_policy["expected_cid"]
                    changes_made += 1
            continue

        if _should_skip(name):
            results["skipped"].append({"id": eid, "name": name, "reason": "umbrella/proprietary"})
            continue

        # Try full name first, then cleaned name
        aliases = entry.get("aliases", [])
        compound, ambiguous = _lookup_entry_compound(client, name, aliases)
        if compound is None:
            if ambiguous:
                results["ambiguous_match"].append({"id": eid, "name": name, **ambiguous})
                continue
            results["not_found"].append({"id": eid, "name": name})
            continue

        pc_cid = compound["cid"]
        pc_cas = compound["cas"]
        record = {"id": eid, "name": name, "pubchem_cid": pc_cid, "pubchem_cas": pc_cas}

        # Validate existing CAS
        if existing_cas and pc_cas:
            if existing_cas == pc_cas:
                record["cas_status"] = "verified"
                results["verified"].append(record)
            else:
                # Check if existing CAS is in the full CAS list (some compounds have multiple)
                if existing_cas in compound.get("cas_all", []):
                    record["cas_status"] = "verified (secondary CAS)"
                    results["verified"].append(record)
                else:
                    record["cas_status"] = "mismatch"
                    record["existing_cas"] = existing_cas
                    results["cas_mismatch"].append(record)
        elif not existing_cas and pc_cas:
            record["cas_status"] = "filled"
            results["cas_filled"].append(record)
            if apply:
                if "external_ids" not in entry:
                    entry["external_ids"] = {}
                entry["external_ids"]["cas"] = pc_cas
                changes_made += 1
        else:
            results["verified"].append(record)

        # Fill PubChem CID
        if not existing_cid and pc_cid:
            results["cid_filled"].append({"id": eid, "name": name, "cid": pc_cid})
            if apply:
                if "external_ids" not in entry:
                    entry["external_ids"] = {}
                entry["external_ids"]["pubchem_cid"] = pc_cid
                changes_made += 1
        elif existing_cid and _normalize_pubchem_id(existing_cid) != _normalize_pubchem_id(pc_cid):
            # CID mismatch — log but don't auto-fix
            results["cid_mismatch"].append({
                "id": eid,
                "name": name,
                "existing_cid": existing_cid,
                "pubchem_cid": pc_cid,
            })

        # Progress
        total = len(entries)
        done = i + 1
        if done % 10 == 0 or done == total:
            print(f"  [{done}/{total}] {name}", file=sys.stderr)

    results["total"] = len(entries)
    results["changes_applied"] = changes_made
    return results


# ---------------------------------------------------------------------------
# IQM verification (ingredient → forms → aliases)
# ---------------------------------------------------------------------------

def verify_iqm_file(data: dict, client: PubChemClient, apply: bool = False) -> dict:
    """Verify CAS/CID for the ingredient_quality_map.json (nested forms structure).

    IQM entries don't have external_ids — this adds them at the form level.
    """
    results = {
        "forms_found": [],
        "forms_not_found": [],
        "form_cas_mismatch": [],
        "form_cid_mismatch": [],
        "ambiguous_match": [],
        "ingredients_skipped": [],
        "forms_skipped": [],
        "errors": [],
    }
    changes_made = 0

    # IQM keys are ingredient names (plus _metadata)
    ingredient_keys = [k for k in data.keys() if k != "_metadata"]
    total = len(ingredient_keys)

    for idx, key in enumerate(ingredient_keys):
        entry = data[key]
        if not isinstance(entry, dict):
            continue

        std_name = entry.get("standard_name", key)

        if _should_skip(std_name):
            results["ingredients_skipped"].append({"key": key, "name": std_name})
            continue

        forms = entry.get("forms", {})
        if not forms:
            continue

        for form_name, form_data in forms.items():
            if not isinstance(form_data, dict):
                continue

            form_skip_reason = _iqm_form_skip_reason(std_name, form_name)
            if form_skip_reason:
                results["forms_skipped"].append({
                    "ingredient": std_name,
                    "form": form_name,
                    "reason": form_skip_reason,
                })
                continue

            # Check if form already has external_ids
            ext = form_data.get("external_ids", {})
            existing_cas = ext.get("cas") if ext else None
            existing_cid = ext.get("pubchem_cid") if ext else None

            aliases = form_data.get("aliases", [])
            query_aliases = list(aliases)
            compound, ambiguous = _lookup_entry_compound(
                client,
                form_name,
                query_aliases,
                max_alias_queries=1,
            )
            if compound is None:
                if ambiguous:
                    results["ambiguous_match"].append({
                        "ingredient": std_name,
                        "form": form_name,
                        **ambiguous,
                    })
                    continue
                results["forms_not_found"].append({
                    "ingredient": std_name,
                    "form": form_name,
                })
                continue

            results["forms_found"].append({
                "ingredient": std_name,
                "form": form_name,
                "cid": compound["cid"],
                "cas": compound["cas"],
                "status": "verified" if existing_cas or existing_cid else "found",
            })

            if existing_cas and compound["cas"] and existing_cas != compound["cas"] and existing_cas not in compound.get("cas_all", []):
                results["form_cas_mismatch"].append({
                    "ingredient": std_name,
                    "form": form_name,
                    "existing_cas": existing_cas,
                    "pubchem_cas": compound["cas"],
                })
            if existing_cid and _normalize_pubchem_id(existing_cid) != _normalize_pubchem_id(compound["cid"]):
                results["form_cid_mismatch"].append({
                    "ingredient": std_name,
                    "form": form_name,
                    "existing_cid": existing_cid,
                    "pubchem_cid": compound["cid"],
                })

            if apply:
                if "external_ids" not in form_data:
                    form_data["external_ids"] = {}
                if not existing_cas and compound["cas"]:
                    form_data["external_ids"]["cas"] = compound["cas"]
                    changes_made += 1
                if not existing_cid and compound["cid"]:
                    form_data["external_ids"]["pubchem_cid"] = compound["cid"]
                    changes_made += 1

        if (idx + 1) % 20 == 0 or idx + 1 == total:
            print(f"  [{idx+1}/{total}] {std_name}", file=sys.stderr)

    results["total_ingredients"] = total
    results["changes_applied"] = changes_made
    return results


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def print_flat_report(results: dict) -> None:
    """Print a human-readable report for flat file verification."""
    total = results["total"]
    print(f"\n{'='*60}")
    print(f"PubChem Verification Report")
    print(f"{'='*60}")
    print(f"Total entries:     {total}")
    print(f"Verified (CAS OK): {len(results['verified'])}")
    print(f"CAS filled:        {len(results['cas_filled'])}")
    print(f"CID filled:        {len(results['cid_filled'])}")
    print(f"CAS mismatch:      {len(results['cas_mismatch'])}")
    print(f"CID mismatch:      {len(results['cid_mismatch'])}")
    print(f"Governed null:     {len(results['governed_null'])}")
    print(f"Ambiguous match:   {len(results['ambiguous_match'])}")
    print(f"Not found:         {len(results['not_found'])}")
    print(f"Skipped:           {len(results['skipped'])}")

    if results.get("changes_applied", 0):
        print(f"\nChanges applied:   {results['changes_applied']}")

    if results["cas_filled"]:
        print(f"\n--- CAS Numbers Filled ({len(results['cas_filled'])}) ---")
        for r in results["cas_filled"]:
            print(f"  {r['id']}: {r['name']} → CAS {r['pubchem_cas']}")

    if results["cid_filled"]:
        print(f"\n--- PubChem CIDs Filled ({len(results['cid_filled'])}) ---")
        for r in results["cid_filled"][:20]:
            print(f"  {r['id']}: {r['name']} → CID {r['cid']}")
        if len(results["cid_filled"]) > 20:
            print(f"  ... and {len(results['cid_filled'])-20} more")

    if results["cas_mismatch"]:
        print(f"\n--- CAS Mismatches ({len(results['cas_mismatch'])}) ---")
        for r in results["cas_mismatch"]:
            print(f"  {r['id']}: {r['name']}")
            print(f"    Ours: {r['existing_cas']} | PubChem: {r['pubchem_cas']}")

    if results["cid_mismatch"]:
        print(f"\n--- CID Mismatches ({len(results['cid_mismatch'])}) ---")
        for r in results["cid_mismatch"]:
            print(f"  {r['id']}: {r['name']}")
            print(f"    Ours: {r['existing_cid']} | PubChem: {r['pubchem_cid']}")

    if results["governed_null"]:
        print(f"\n--- Governed Null / Curated Overrides ({len(results['governed_null'])}) ---")
        for r in results["governed_null"]:
            print(f"  {r['id']}: {r['name']}")
            print(f"    {r['reason']} | CAS {r['expected_cas']} | CID {r['expected_cid']}")

    if results["ambiguous_match"]:
        print(f"\n--- Ambiguous Matches ({len(results['ambiguous_match'])}) ---")
        for r in results["ambiguous_match"][:20]:
            print(f"  {r['id']}: {r['name']}")
            print(f"    Query: {r['query']} ({r['role']}) | CID {r['pubchem_cid']} | CAS {r['pubchem_cas']}")
        if len(results["ambiguous_match"]) > 20:
            print(f"  ... and {len(results['ambiguous_match'])-20} more")

    if results["not_found"]:
        print(f"\n--- Not Found ({len(results['not_found'])}) ---")
        for r in results["not_found"]:
            print(f"  {r['id']}: {r['name']}")

    if results["skipped"]:
        print(f"\n--- Skipped ({len(results['skipped'])}) ---")
        for r in results["skipped"]:
            print(f"  {r['id']}: {r['name']} ({r['reason']})")


def print_iqm_report(results: dict) -> None:
    """Print a human-readable report for IQM verification."""
    print(f"\n{'='*60}")
    print(f"PubChem IQM Verification Report")
    print(f"{'='*60}")
    print(f"Total ingredients: {results['total_ingredients']}")
    found = [r for r in results["forms_found"] if r.get("status") == "found"]
    verified = [r for r in results["forms_found"] if r.get("status") == "verified"]
    print(f"Forms found:       {len(found)}")
    print(f"Forms verified:    {len(verified)}")
    print(f"Forms not found:   {len(results['forms_not_found'])}")
    print(f"CAS mismatch:      {len(results['form_cas_mismatch'])}")
    print(f"CID mismatch:      {len(results['form_cid_mismatch'])}")
    print(f"Ambiguous match:   {len(results['ambiguous_match'])}")
    print(f"Forms skipped:     {len(results['forms_skipped'])}")
    print(f"Ingredients skip:  {len(results['ingredients_skipped'])}")

    if results.get("changes_applied", 0):
        print(f"\nChanges applied:   {results['changes_applied']}")

    if found:
        print(f"\n--- Forms Found ({len(found)}) ---")
        for r in found[:30]:
            cas_str = f" CAS {r['cas']}" if r.get("cas") else ""
            print(f"  {r['ingredient']} → {r['form']}: CID {r['cid']}{cas_str}")
        if len(found) > 30:
            print(f"  ... and {len(found)-30} more")

    if results["forms_not_found"]:
        print(f"\n--- Forms Not Found ({len(results['forms_not_found'])}) ---")
        for r in results["forms_not_found"][:20]:
            print(f"  {r['ingredient']} → {r['form']}")
        if len(results["forms_not_found"]) > 20:
            print(f"  ... and {len(results['forms_not_found'])-20} more")

    if results["forms_skipped"]:
        print(f"\n--- Forms Skipped ({len(results['forms_skipped'])}) ---")
        for r in results["forms_skipped"][:20]:
            print(f"  {r['ingredient']} → {r['form']} ({r['reason']})")
        if len(results["forms_skipped"]) > 20:
            print(f"  ... and {len(results['forms_skipped'])-20} more")

    if results["form_cid_mismatch"]:
        print(f"\n--- Form CID Mismatches ({len(results['form_cid_mismatch'])}) ---")
        for r in results["form_cid_mismatch"][:20]:
            print(f"  {r['ingredient']} → {r['form']}: ours {r['existing_cid']} | PubChem {r['pubchem_cid']}")

    if results["ambiguous_match"]:
        print(f"\n--- Ambiguous Form Matches ({len(results['ambiguous_match'])}) ---")
        for r in results["ambiguous_match"][:20]:
            print(f"  {r['ingredient']} → {r['form']}: query {r['query']} ({r['role']})")


# ---------------------------------------------------------------------------
# Single lookups
# ---------------------------------------------------------------------------

def do_search(client: PubChemClient, query: str) -> None:
    """Search PubChem for a compound by name and print detailed results."""
    print(f"Searching PubChem for: {query}")
    result = client.search_compound(query, include_properties=True)
    if result is None:
        print("  NOT FOUND in PubChem")
        return

    print(f"  PubChem CID:  {result['cid']}")
    print(f"  Primary CAS:  {result['cas'] or 'none found'}")
    if len(result.get("cas_all", [])) > 1:
        print(f"  All CAS:      {result['cas_all']}")

    props = result.get("properties")
    if props:
        print(f"  Formula:      {props.get('MolecularFormula', '?')}")
        print(f"  Weight:       {props.get('MolecularWeight', '?')}")
        print(f"  IUPAC:        {props.get('IUPACName', '?')}")
        print(f"  InChIKey:     {props.get('InChIKey', '?')}")

    synonyms = result.get("synonyms", [])
    if synonyms:
        print(f"  Synonyms ({len(synonyms)} total):")
        for s in synonyms[:15]:
            print(f"    {s}")
        if len(synonyms) > 15:
            print(f"    ... and {len(synonyms)-15} more")


def do_cid_lookup(client: PubChemClient, cid: int) -> None:
    """Look up a PubChem CID and print details."""
    print(f"Looking up PubChem CID: {cid}")

    synonyms = client.cid_to_synonyms(cid)
    if not synonyms:
        print("  NOT FOUND")
        return

    cas_numbers = [s for s in synonyms if CAS_RE.match(s)]
    props = client.cid_to_properties(cid)

    print(f"  Name:         {synonyms[0] if synonyms else '?'}")
    print(f"  CAS:          {cas_numbers[0] if cas_numbers else 'none'}")
    if props:
        print(f"  Formula:      {props.get('MolecularFormula', '?')}")
        print(f"  Weight:       {props.get('MolecularWeight', '?')}")
        print(f"  IUPAC:        {props.get('IUPACName', '?')}")

    if synonyms:
        print(f"  Synonyms ({len(synonyms)} total):")
        for s in synonyms[:15]:
            print(f"    {s}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="PubChem CAS/CID verification & enrichment for PharmaGuide data files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  Dry-run harmful_additives:
    python3 scripts/api_audit/verify_pubchem.py --file scripts/data/harmful_additives.json --list-key harmful_additives

  Apply safe fills:
    python3 scripts/api_audit/verify_pubchem.py --file scripts/data/harmful_additives.json --list-key harmful_additives --apply

  IQM mode:
    python3 scripts/api_audit/verify_pubchem.py --file scripts/data/ingredient_quality_map.json --mode iqm

  Search a compound:
    python3 scripts/api_audit/verify_pubchem.py --search "magnesium glycinate"

  Look up a CID:
    python3 scripts/api_audit/verify_pubchem.py --cid 11177
""",
    )
    parser.add_argument("--file", type=str, help="JSON data file to verify")
    parser.add_argument("--list-key", type=str, help="JSON key containing the entry list (for flat files)")
    parser.add_argument("--mode", choices=["flat", "iqm"], default="flat",
                        help="File structure: flat (harmful_additives, banned_recalled) or iqm")
    parser.add_argument("--apply", action="store_true",
                        help="Apply safe CAS/CID fills to the file")
    parser.add_argument("--search", type=str, help="Search PubChem by compound name")
    parser.add_argument("--cid", type=int, help="Look up a PubChem CID")
    parser.add_argument("--no-cache", action="store_true", help="Disable response caching")
    args = parser.parse_args()

    # Cache setup
    cache_dir = SCRIPTS_ROOT / ".cache"
    cache_path = None if args.no_cache else cache_dir / "pubchem_cache.json"

    client = PubChemClient(cache_path=cache_path)

    # Single lookups
    if args.search:
        do_search(client, args.search)
        client.save_cache()
        return 0

    if args.cid:
        do_cid_lookup(client, args.cid)
        client.save_cache()
        return 0

    # File verification
    if not args.file:
        parser.print_help()
        return 1

    file_path = Path(args.file)
    if not file_path.exists():
        print(f"[ERROR] File not found: {file_path}", file=sys.stderr)
        return 1

    print(f"[PubChem] Loading {file_path.name}...")
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if args.mode == "iqm":
        print(f"[PubChem] IQM mode — verifying forms across ingredients...")
        results = verify_iqm_file(data, client, apply=args.apply)
        print_iqm_report(results)
    else:
        if not args.list_key:
            print("[ERROR] --list-key required for flat mode", file=sys.stderr)
            return 1
        print(f"[PubChem] Flat mode — verifying {args.list_key}...")
        results = verify_flat_file(data, args.list_key, client, apply=args.apply)
        print_flat_report(results)

    # Write back if apply
    if args.apply and results.get("changes_applied", 0) > 0:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print(f"\n[PubChem] Wrote {results['changes_applied']} changes to {file_path.name}")

    client.save_cache()
    print(f"[PubChem] Done. ({client._request_count} API requests)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
