#!/usr/bin/env python3
"""
UMLS CUI verification and lookup tool for PharmaGuide data files.

What this script does:
  1. Verifies whether an existing CUI still resolves to the intended concept.
  2. Looks up missing CUIs by exact standard name, exact alias, curated override, then word search.
  3. Produces actionable output for invalid CUIs, mismatches, missing exact matches, and true not-found cases.
  4. Optionally applies only safe fixes directly to the JSON file.

Operator runbook:
  1. Dry-run the whole file first:
       python3 scripts/verify_cui.py --file scripts/data/banned_recalled_ingredients.json --list-key ingredients --id-field id --cui-field cui
  2. Inspect a single missing or suspicious concept:
       python3 scripts/verify_cui.py --search "sildenafil"
       python3 scripts/verify_cui.py --cui C0529793
  3. Apply only safe exact fills for genuinely missing CUIs:
       python3 scripts/verify_cui.py --file scripts/data/banned_recalled_ingredients.json --list-key ingredients --id-field id --cui-field cui --apply
  4. Only use --apply-mismatches after manual review of the FDA/UMLS evidence:
       python3 scripts/verify_cui.py --file scripts/data/banned_recalled_ingredients.json --list-key ingredients --id-field id --cui-field cui --apply --apply-mismatches

Null-CUI policy:
  - Leave CUI null when the entry is a class/policy/multi-substance record and no single UMLS concept is correct.
  - Leave CUI null when the name is a supplement-market analogue or research-chemical label with no confirmed exact UMLS concept.
  - In both cases, record the reason in `cui_status` and `cui_note`.
  - If a CUI is null only because an exact alias is missing, add the alias first and rerun this script before annotating the null.

Matching order and safety rules:
  - Exact alias and curated override matches are preferred over broad word-search suggestions.
  - Broad search results are informational and are not safe to auto-apply.
  - Entries with an approved `cui_status` and null CUI are treated as intentional nulls unless an exact standard/alias match proves the null should be revisited.
  - `--apply` is intentionally conservative and will not overwrite existing mismatched CUIs.
  - `--apply-mismatches` is the explicit override for reviewed mismatch corrections.

Environment:
  Set UMLS_API_KEY or pass --api-key. Falls back to the loaded environment default.
"""

import argparse
import json
import os
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Optional
from urllib.parse import quote

import env_loader  # noqa: F401 — loads .env into os.environ
import ssl
import urllib.request
import urllib.error

# macOS Python often lacks certs — probe once, use unverified context as fallback
def _make_ssl_ctx() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    try:
        req = urllib.request.Request("https://uts-ws.nlm.nih.gov", method="HEAD")
        urllib.request.urlopen(req, timeout=5, context=ctx)
        return ctx
    except (ssl.SSLCertVerificationError, urllib.error.URLError):
        return ssl._create_unverified_context()
    except Exception:
        return ctx

_SSL_CTX = _make_ssl_ctx()

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DEFAULT_API_KEY = os.environ.get("UMLS_API_KEY", "")
BASE_URL = "https://uts-ws.nlm.nih.gov/rest"
VERSION = "current"
RATE_LIMIT_DELAY = 0.12  # seconds between requests (~8 req/s, well under limit)
DEFAULT_CACHE_TTL_SECONDS = 60 * 60 * 24 * 30
VERIFY_CUI_HELP_EPILOG = """Examples:
  Dry-run the banned/recalled file:
    .venv/bin/python scripts/verify_cui.py --file scripts/data/banned_recalled_ingredients.json --list-key ingredients --id-field id --cui-field cui

  Search a concept manually:
    .venv/bin/python scripts/verify_cui.py --search "sildenafil"

  Safe exact-match apply only:
    .venv/bin/python scripts/verify_cui.py --file scripts/data/banned_recalled_ingredients.json --list-key ingredients --id-field id --cui-field cui --apply

  Reviewed mismatch overwrite:
    .venv/bin/python scripts/verify_cui.py --file scripts/data/banned_recalled_ingredients.json --list-key ingredients --id-field id --cui-field cui --apply --apply-mismatches
"""

CURATED_CUI_OVERRIDES = {
    "policy watchlist: synthetic food acids": {
        "cui": None,
        "name": None,
        "note": "Curated override: policy/class entry spans multiple synthetic food acids, so no single ingredient-level UMLS concept is appropriate.",
    },
    "synthetic food acids": {
        "cui": None,
        "name": None,
        "note": "Curated override: policy/class entry spans multiple synthetic food acids, so no single ingredient-level UMLS concept is appropriate.",
    },
    "antimony & antimony compounds": {
        "cui": None,
        "name": None,
        "note": "Curated override: grouped contaminant entry spans elemental antimony plus multiple compounds, not one exact ingredient-level concept.",
    },
    "tapioca filler": {
        "cui": None,
        "name": None,
        "note": "Curated override: formulation/filler concern should not be auto-collapsed into the cassava plant concept alone.",
    },
    "nitrites": {
        "cui": None,
        "name": None,
        "note": "Curated override: umbrella nitrites record routes to atomic child salts and should not resolve to one preservative compound.",
    },
    "sodium nitrite/nitrate": {
        "cui": None,
        "name": None,
        "note": "Curated override: umbrella nitrites record routes to atomic child salts and should not resolve to one preservative compound.",
    },
    "synthetic antioxidants": {
        "cui": None,
        "name": None,
        "note": "Curated override: umbrella antioxidant record routes to BHA/BHT/TBHQ child entries and should not resolve to one compound like ethoxyquin.",
    },
    "synthetic vitamins": {
        "cui": None,
        "name": None,
        "note": "Curated override: grouped synthetic-vitamin record spans many vitamin compounds and should not resolve to one example such as alpha tocopherol.",
    },
    "synthetic b vitamins": {
        "cui": None,
        "name": None,
        "note": "Curated override: grouped B-vitamin record spans many compounds and should not resolve to one ingredient-level concept.",
    },
    "syrups": {
        "cui": None,
        "name": None,
        "note": "Curated override: syrup record is a formulation class and should not be collapsed to one specific syrup concept such as corn syrup.",
    },
    "sugar syrups": {
        "cui": None,
        "name": None,
        "note": "Curated override: syrup record is a formulation class and should not be collapsed to one specific syrup concept such as corn syrup.",
    },
    "unspecified colors": {
        "cui": None,
        "name": None,
        "note": "Curated override: disclosure-quality category should not be mapped to one symptom or dye concept.",
    },
    "tapioca (refined starch filler)": {
        "cui": None,
        "name": None,
        "note": "Curated override: filler formulation concern should not be auto-collapsed into the cassava plant concept alone.",
    },
    "7-keto dhea": {"cui": "C0525091", "name": "7-keto-dehydroepiandrosterone"},
    "7-keto dhea (7-oxodehydroepiandrosterone)": {"cui": "C0525091", "name": "7-keto-dehydroepiandrosterone"},
    "bmpea": {"cui": "C4041589", "name": "beta-methylphenyl-ethylamine"},
    "beta-methylphenyl-ethylamine": {"cui": "C4041589", "name": "beta-methylphenyl-ethylamine"},
    "contaminated glp-1 compounds": {
        "cui": None,
        "name": None,
        "note": "Curated override: contamination watchlist entry spans multiple GLP-1 compounds and quality defects, not one ingredient concept.",
    },
    "metal fiber contamination": {
        "cui": None,
        "name": None,
        "note": "Curated override: contamination category covers multiple metal fiber/particle variants, not one ingredient-level concept.",
    },
    "fluoride supplements (children)": {
        "cui": None,
        "name": None,
        "note": "Curated override: pediatric fluoride supplement entry spans multiple product forms and salts, not one ingredient-level concept.",
    },
    "pediatric fluoride supplements": {
        "cui": None,
        "name": None,
        "note": "Curated override: pediatric fluoride supplement entry spans multiple product forms and salts, not one ingredient-level concept.",
    },
    "partially hydrogenated oils (phos)": {
        "cui": None,
        "name": None,
        "note": "Curated override: partially hydrogenated oils are a class entry and the PHO abbreviation collides with unrelated UMLS concepts.",
    },
    "partially hydrogenated oils": {
        "cui": None,
        "name": None,
        "note": "Curated override: partially hydrogenated oils are a class entry and should not resolve to one unrelated PHO concept.",
    },
    "pho": {
        "cui": None,
        "name": None,
        "note": "Curated override: PHO is ambiguous and should not be auto-mapped without a specific oil/salt concept.",
    },
    "phos": {
        "cui": None,
        "name": None,
        "note": "Curated override: PHOs are a class entry and should not be auto-mapped to a single unrelated concept.",
    },
    "dmaa": {"cui": "C3492032", "name": "1,3-dimethylamylamine"},
    "1,3-dimethylamylamine": {"cui": "C3492032", "name": "1,3-dimethylamylamine"},
    "dmba": {"cui": "C4076845", "name": "1,3-dimethylbutylamine"},
    "1,3-dimethylbutylamine": {"cui": "C4076845", "name": "1,3-dimethylbutylamine"},
    "dmsa (succimer)": {"cui": "C0012384", "name": "Succimer"},
    "succimer": {"cui": "C0012384", "name": "Succimer"},
    "sildenafil": {"cui": "C0529793", "name": "Sildenafil"},
    "sildenafil citrate": {"cui": "C0529793", "name": "Sildenafil"},
    "tb-500 (thymosin beta-4)": {
        "cui": None,
        "name": None,
        "note": "Curated override: TB-500 is marketed as a peptide analogue/brand term and should not be auto-collapsed into thymosin beta-4 without explicit review.",
    },
    "tb500": {
        "cui": None,
        "name": None,
        "note": "Curated override: TB-500 is marketed as a peptide analogue/brand term and should not be auto-collapsed into thymosin beta-4 without explicit review.",
    },
    "germanium (inorganic)": {
        "cui": None,
        "name": None,
        "note": "Curated override: inorganic germanium entry spans multiple salts and oxides, not one exact ingredient-level UMLS concept.",
    },
    "green tea extract (high dose)": {
        "cui": None,
        "name": None,
        "note": "Curated override: dose-conditioned green tea extract risk entry is broader than a single UMLS ingredient concept.",
    },
    "amanita muscaria / muscimol": {
        "cui": None,
        "name": None,
        "note": "Curated override: entry combines mushroom species and active constituents, so no single UMLS concept is exact.",
    },
    "policy watchlist: cardarine derivatives": {
        "cui": None,
        "name": None,
        "note": "Curated override: derivative watchlist spans multiple analogues, not one ingredient-level UMLS concept.",
    },
    "policy watchlist: synthetic anabolic steroids": {
        "cui": None,
        "name": None,
        "note": "Curated override: steroid watchlist spans many different compounds, not one ingredient-level UMLS concept.",
    },
    "synthetic anabolic steroids": {
        "cui": None,
        "name": None,
        "note": "Curated override: steroid watchlist spans many different compounds, not one ingredient-level UMLS concept.",
    },
    "policy watchlist: tianeptine analogues": {
        "cui": None,
        "name": None,
        "note": "Curated override: analogue watchlist spans multiple compounds, not one ingredient-level UMLS concept.",
    },
    "policy watchlist: dmaa analogs": {
        "cui": None,
        "name": None,
        "note": "Curated override: stimulant analogue watchlist spans multiple compounds, not one ingredient-level UMLS concept.",
    },
    "dmaa analogs": {
        "cui": None,
        "name": None,
        "note": "Curated override: stimulant analogue watchlist spans multiple compounds, not one ingredient-level UMLS concept.",
    },
    "cannabis/thc": {
        "cui": None,
        "name": None,
        "note": "Curated override: combined cannabis/THC policy entry should not be forced into a single plant or constituent concept.",
    },
    "thyrogen (thyrotropin alfa)": {"cui": "C2587204", "name": "thyrotropin alfa"},
    "thyrotropin alfa": {"cui": "C2587204", "name": "thyrotropin alfa"},
    "5a-hydroxy laxogenin": {
        "cui": None,
        "name": None,
        "note": "Curated override: supplement-market derivative name does not have a confirmed exact UMLS concept distinct from broader laxogenin entries.",
    },
    "igf-1 lr3": {
        "cui": None,
        "name": None,
        "note": "Curated override: no confirmed exact UMLS concept was found for the marketed peptide analogue name IGF-1 LR3.",
    },
    "igf-1 lr3 (long r3 insulin-like growth factor 1)": {
        "cui": None,
        "name": None,
        "note": "Curated override: no confirmed exact UMLS concept was found for the marketed peptide analogue name IGF-1 LR3.",
    },
    "yk-11": {
        "cui": None,
        "name": None,
        "note": "Curated override: no confirmed exact UMLS concept was found for the investigational SARM name YK-11.",
    },
    "flmodafinil": {
        "cui": None,
        "name": None,
        "note": "Curated override: no confirmed exact UMLS concept was found for the research-chemical nootropic name flmodafinil.",
    },
    "chloropretadalafil": {
        "cui": None,
        "name": None,
        "note": "Curated override: no confirmed exact UMLS concept was found for the undeclared PDE-5 analogue chloropretadalafil.",
    },
    "7-methylkratom": {
        "cui": None,
        "name": None,
        "note": "Curated override: no confirmed exact UMLS concept was found for the kratom-derived analogue 7-methylkratom.",
    },
    "propoxyphenylsildenafil": {
        "cui": None,
        "name": None,
        "note": "Curated override: no confirmed exact UMLS concept was found for the undeclared PDE-5 analogue propoxyphenylsildenafil.",
    },
    "n-phenethyl dimethylamine": {
        "cui": None,
        "name": None,
        "note": "Curated override: no confirmed exact UMLS concept was found for the stimulant analogue N-phenethyl dimethylamine.",
    },
    "hexadrone (6-chloro-androst-4-ene-3-one-17b-ol)": {
        "cui": None,
        "name": None,
        "note": "Curated override: no confirmed exact UMLS concept was found for the designer steroid name Hexadrone.",
    },
    "carob color (e153 / vegetable carbon)": {
        "cui": None,
        "name": None,
        "note": "Curated override: food-color entry maps to a formulation/coloring class and should not be auto-collapsed into generic carbon black.",
    },
    "dmha": {
        "cui": None,
        "name": None,
        "note": "Curated override: no confirmed exact UMLS concept for the supplement stimulant synonym DMHA/2-aminoisoheptane.",
    },
    "2-aminoisoheptane": {
        "cui": None,
        "name": None,
        "note": "Curated override: no confirmed exact UMLS concept for the supplement stimulant synonym DMHA/2-aminoisoheptane.",
    },
}

DEFAULT_FILE = Path(__file__).parent / "data" / "harmful_additives.json"
APPROVED_NULL_CUI_STATUSES = {"no_confirmed_umls_match", "no_single_umls_concept"}


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

class UMLSClient:
    """Thin wrapper around the UMLS REST API (stdlib only — no requests dependency)."""

    def __init__(
        self,
        api_key: str,
        *,
        timeout_seconds: float = 5.0,
        failure_limit: int = 2,
        cache_path: Path | None = None,
        cache_ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS,
        emit_errors: bool = True,
    ):
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.failure_limit = max(1, failure_limit)
        self.cache_path = Path(cache_path) if cache_path else None
        self.cache_ttl_seconds = max(0, cache_ttl_seconds)
        self.emit_errors = emit_errors
        self._request_count = 0
        self._consecutive_transport_failures = 0
        self.circuit_open = False
        self._cache: dict[str, dict] = {}
        if self.cache_path and self.cache_path.exists():
            try:
                loaded = json.loads(self.cache_path.read_text())
                if isinstance(loaded, dict):
                    self._cache = loaded
            except json.JSONDecodeError:
                self._cache = {}

    def _cache_get(self, key: str) -> dict | None:
        cached = self._cache.get(key)
        if not isinstance(cached, dict):
            return None

        payload = cached.get("payload")
        if isinstance(payload, dict):
            expires_at = cached.get("expires_at")
            if isinstance(expires_at, str):
                try:
                    if datetime.fromisoformat(expires_at) <= datetime.now(UTC):
                        self._cache.pop(key, None)
                        return None
                except ValueError:
                    self._cache.pop(key, None)
                    return None
            return payload

        return cached

    def _cache_set(self, key: str, value: dict) -> None:
        now = datetime.now(UTC)
        expires_at = now + timedelta(seconds=self.cache_ttl_seconds)
        self._cache[key] = {
            "stored_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
            "payload": value,
        }
        if not self.cache_path:
            return
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(json.dumps(self._cache, indent=2, ensure_ascii=True) + "\n")

    def _get(self, endpoint: str, params: dict | None = None) -> dict | None:
        params = params or {}
        cache_params = dict(params)
        cache_query = "&".join(f"{k}={quote(str(v))}" for k, v in cache_params.items())
        cache_key = f"{BASE_URL}{endpoint}?{cache_query}"

        request_params = dict(params)
        request_params["apiKey"] = self.api_key
        query = "&".join(f"{k}={quote(str(v))}" for k, v in request_params.items())
        url = f"{BASE_URL}{endpoint}?{query}"

        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        if not self.api_key or self.circuit_open:
            return None

        time.sleep(RATE_LIMIT_DELAY)
        self._request_count += 1
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=self.timeout_seconds, context=_SSL_CTX) as resp:
                payload = json.loads(resp.read().decode())
                self._consecutive_transport_failures = 0
                self._cache_set(cache_key, payload)
                return payload
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if self.emit_errors:
                print(f"  API error: HTTP {e.code} — {e.reason}", file=sys.stderr)
            return None
        except (urllib.error.URLError, TimeoutError) as e:
            self._consecutive_transport_failures += 1
            if self._consecutive_transport_failures >= self.failure_limit:
                self.circuit_open = True
            if self.emit_errors:
                print(f"  API error: {e}", file=sys.stderr)
            return None

    def probe(self, term: str = "Sildenafil") -> bool:
        probe = self.search_exact(term)
        return bool(probe and probe.get("cui"))

    def lookup_cui(self, cui: str) -> dict | None:
        """Look up a CUI and return its preferred name + semantic types."""
        data = self._get(f"/content/{VERSION}/CUI/{cui}")
        if not data or "result" not in data:
            return None
        result = data["result"]
        return {
            "cui": result.get("ui"),
            "name": result.get("name"),
            "semantic_types": [st["name"] for st in result.get("semanticTypes", [])],
            "atom_count": result.get("atomCount", 0),
            "status": result.get("status"),
        }

    def search(self, term: str, max_results: int = 5) -> list[dict]:
        """Search UMLS by name and return top matches."""
        data = self._get(f"/search/{VERSION}", params={
            "string": term,
            "pageSize": max_results,
            "searchType": "words",
        })
        if not data or "result" not in data:
            return []
        results = data["result"].get("results", [])
        # Filter out the "NO RESULTS" sentinel
        return [
            {
                "cui": r["ui"],
                "name": r["name"],
                "source": r.get("rootSource", ""),
                "semantic_types": r.get("semanticTypes", []),
            }
            for r in results
            if r.get("ui") != "NONE"
        ]

    def search_exact(self, term: str) -> dict | None:
        """Search for exact match and return top result."""
        data = self._get(f"/search/{VERSION}", params={
            "string": term,
            "pageSize": 1,
            "searchType": "exact",
        })
        if not data or "result" not in data:
            return None
        results = data["result"].get("results", [])
        if not results or results[0].get("ui") == "NONE":
            return None
        r = results[0]
        return {
            "cui": r["ui"],
            "name": r["name"],
            "source": r.get("rootSource", ""),
        }

    @property
    def request_count(self) -> int:
        return self._request_count


def _normalize_term(term: str) -> str:
    return " ".join(term.strip().lower().split())


def find_curated_override(standard_name: str, aliases: list[str]) -> dict | None:
    for term in [standard_name, *aliases]:
        if not isinstance(term, str) or not term.strip():
            continue
        override = CURATED_CUI_OVERRIDES.get(_normalize_term(term))
        if override:
            return override
    return None


# ---------------------------------------------------------------------------
# Verification logic
# ---------------------------------------------------------------------------

def verify_cui_for_entry(
    client: UMLSClient,
    entry_id: str,
    standard_name: str,
    current_cui: Optional[str],
    aliases: list[str],
    cui_status: Optional[str] = None,
) -> dict:
    """Verify a single entry's CUI. Returns a report dict."""
    report = {
        "id": entry_id,
        "standard_name": standard_name,
        "current_cui": current_cui,
        "status": "unknown",
        "umls_name": None,
        "suggested_cui": None,
        "suggested_name": None,
        "action": None,
        "match_source": None,
        "cui_status": cui_status,
    }
    has_approved_null = (
        not current_cui
        and isinstance(cui_status, str)
        and cui_status in APPROVED_NULL_CUI_STATUSES
    )

    # Step 1: If CUI exists, verify it
    if current_cui:
        info = client.lookup_cui(current_cui)
        if info is None:
            report["status"] = "INVALID_CUI"
            report["action"] = f"CUI {current_cui} not found in UMLS"
        else:
            report["umls_name"] = info["name"]
            # Check if the UMLS name reasonably matches
            name_lower = standard_name.lower()
            umls_lower = info["name"].lower()
            if (name_lower in umls_lower or umls_lower in name_lower
                    or any(a.lower() in umls_lower or umls_lower in a.lower()
                           for a in aliases)):
                report["status"] = "VERIFIED"
                report["action"] = None
                report["match_source"] = "existing_cui"
            else:
                report["status"] = "MISMATCH"
                report["action"] = (
                    f"CUI {current_cui} maps to '{info['name']}' "
                    f"but entry is '{standard_name}'"
                )

    # Step 2: If CUI is missing or mismatched, search for the right one
    if report["status"] in ("unknown", "INVALID_CUI", "MISMATCH") or not current_cui:
        curated = find_curated_override(standard_name, aliases)
        block_further_search = False
        if curated:
            if curated.get("cui"):
                report["suggested_cui"] = curated["cui"]
                report["suggested_name"] = curated["name"]
                report["match_source"] = "curated_override"
                if not current_cui:
                    report["status"] = "MISSING_CUI"
                    report["action"] = f"Suggest curated CUI {curated['cui']} ({curated['name']})"
            elif not current_cui:
                report["status"] = "NOT_FOUND"
                report["action"] = curated.get("note") or "Curated override indicates no confirmed UMLS match"
                report["match_source"] = "curated_override_none"
                block_further_search = True

        if not block_further_search:
            exact = client.search_exact(standard_name)
            if exact and not report["suggested_cui"]:
                report["suggested_cui"] = exact["cui"]
                report["suggested_name"] = exact["name"]
                report["match_source"] = "exact_standard"
                if has_approved_null:
                    report["status"] = "ANNOTATED_NULL_REVIEW"
                    report["action"] = (
                        f"Annotated null should be reviewed; exact standard match found: "
                        f"{exact['cui']} ({exact['name']})"
                    )
                elif not current_cui:
                    report["status"] = "MISSING_CUI"
                    report["action"] = f"Suggest CUI {exact['cui']} ({exact['name']})"
            elif not report["suggested_cui"] and report["status"] != "NOT_FOUND":
                for alias in aliases:
                    if not isinstance(alias, str) or not alias.strip():
                        continue
                    alias_match = client.search_exact(alias)
                    if not alias_match:
                        continue
                    report["suggested_cui"] = alias_match["cui"]
                    report["suggested_name"] = alias_match["name"]
                    report["match_source"] = "exact_alias"
                    if has_approved_null:
                        report["status"] = "ANNOTATED_NULL_REVIEW"
                        report["action"] = (
                            f"Annotated null should be reviewed; exact alias match found: "
                            f"{alias_match['cui']} ({alias_match['name']})"
                        )
                    elif not current_cui:
                        report["status"] = "MISSING_CUI"
                        report["action"] = f"Suggest CUI {alias_match['cui']} ({alias_match['name']})"
                    break

            if not report["suggested_cui"] and report["status"] != "NOT_FOUND":
                results = client.search(standard_name, max_results=3)
                if results:
                    top = results[0]
                    report["suggested_cui"] = top["cui"]
                    report["suggested_name"] = top["name"]
                    report["match_source"] = "search"
                    if not current_cui:
                        report["status"] = "MISSING_CUI"
                        report["action"] = f"Suggest CUI {top['cui']} ({top['name']})"
                elif not current_cui:
                    report["status"] = "NOT_FOUND"
                    report["action"] = "No UMLS match found — may need manual lookup"

    if has_approved_null and report["status"] in {"MISSING_CUI", "NOT_FOUND"}:
        report["status"] = "ANNOTATED_NULL"
        report["action"] = None

    if (
        current_cui
        and report["status"] == "MISMATCH"
        and report.get("suggested_cui") == current_cui
        and report.get("match_source") in {"exact_standard", "exact_alias", "curated_override"}
    ):
        report["status"] = "VERIFIED"
        report["action"] = None

    return report


def should_apply_cui_fix(report: dict, *, allow_mismatch_overwrite: bool = False) -> bool:
    """Return True only for safe exact-match updates by default."""
    if not report.get("suggested_cui"):
        return False

    match_source = report.get("match_source")
    if report.get("status") == "MISSING_CUI":
        return match_source in {"exact_standard", "exact_alias", "curated_override"}

    if report.get("status") == "MISMATCH" and allow_mismatch_overwrite:
        return match_source in {"exact_standard", "exact_alias", "curated_override"}

    return False


def load_entries(file_path: Path, list_key: str, id_field: str, cui_field: str) -> list[dict]:
    """Load entries from a JSON data file."""
    data = json.loads(file_path.read_text())

    # Try the list_key, or common alternatives
    entries = data.get(list_key)
    if entries is None:
        for key in ["harmful_additives", "ingredients", "additives"]:
            if key in data:
                entries = data[key]
                break
    if entries is None:
        print(f"ERROR: Could not find entry list in {file_path}")
        sys.exit(1)

    return entries


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_verify(args):
    """Verify all CUIs in a data file."""
    client = UMLSClient(
        args.api_key,
        timeout_seconds=args.timeout_seconds,
        failure_limit=args.failure_limit,
        cache_path=Path(args.cache_file) if args.cache_file else None,
        cache_ttl_seconds=args.cache_ttl_seconds,
    )
    file_path = Path(args.file)
    entries = load_entries(file_path, args.list_key, args.id_field, args.cui_field)

    print(f"Verifying {len(entries)} entries in {file_path.name}...")
    print(f"CUI field: {args.cui_field} | ID field: {args.id_field}")
    print()

    reports = []
    for i, entry in enumerate(entries):
        entry_id = entry.get(args.id_field, f"entry_{i}")
        standard_name = entry.get("standard_name", entry.get("name", ""))
        current_cui = entry.get(args.cui_field)
        aliases = entry.get("aliases", [])
        cui_status = entry.get("cui_status")

        # Skip empty/null CUIs for "verify-only" mode if not looking up missing
        report = verify_cui_for_entry(
            client,
            entry_id,
            standard_name,
            current_cui,
            aliases,
            cui_status=cui_status,
        )
        reports.append(report)

        # Progress indicator
        status_icon = {"VERIFIED": "✅", "MISMATCH": "❌", "MISSING_CUI": "🔍",
                       "INVALID_CUI": "⚠️", "NOT_FOUND": "—", "ANNOTATED_NULL": "ℹ️",
                       "ANNOTATED_NULL_REVIEW": "📝"}.get(report["status"], "?")
        print(f"  [{i+1:3d}/{len(entries)}] {status_icon} {entry_id}: {report['status']}"
              + (f" → {report['action']}" if report['action'] else ""))

    # Summary
    print(f"\n{'='*60}")
    print(f"SUMMARY — {len(entries)} entries, {client.request_count} API requests")
    print(f"{'='*60}")
    counts = {}
    for r in reports:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    for status, count in sorted(counts.items()):
        print(f"  {status}: {count}")

    # Actionable items
    actionable = [r for r in reports if r["action"]]
    if actionable:
        print(f"\n{'='*60}")
        print(f"ACTIONABLE ITEMS ({len(actionable)})")
        print(f"{'='*60}")
        for r in actionable:
            print(f"  {r['id']}:")
            print(f"    Current: cui={r['current_cui']}")
            if r["umls_name"]:
                print(f"    UMLS says: {r['umls_name']}")
            if r["suggested_cui"]:
                print(f"    Suggested: {r['suggested_cui']} ({r['suggested_name']})")
            print(f"    Action: {r['action']}")
            print()

    # Apply fixes if requested
    if args.apply and actionable:
        print(f"\nApplying {len(actionable)} fixes...")
        data = json.loads(file_path.read_text())
        entry_list = data.get(args.list_key)
        if entry_list is None:
            for key in ["harmful_additives", "ingredients", "additives"]:
                if key in data:
                    entry_list = data[key]
                    break

        applied = 0
        for entry in entry_list:
            eid = entry.get(args.id_field)
            match = next((r for r in actionable if r["id"] == eid), None)
            if not match or not should_apply_cui_fix(
                match,
                allow_mismatch_overwrite=args.apply_mismatches,
            ):
                continue
            if match["status"] == "MISMATCH":
                print(f"  MISMATCH {eid}: {match['current_cui']} → {match['suggested_cui']} "
                      f"('{match['suggested_name']}')")
            entry[args.cui_field] = match["suggested_cui"]
            applied += 1

        file_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        print(f"\nApplied {applied} CUI updates to {file_path.name}")

    return reports


def cmd_lookup_cui(args):
    """Look up a single CUI."""
    client = UMLSClient(
        args.api_key,
        timeout_seconds=args.timeout_seconds,
        failure_limit=args.failure_limit,
        cache_path=Path(args.cache_file) if args.cache_file else None,
        cache_ttl_seconds=args.cache_ttl_seconds,
    )
    info = client.lookup_cui(args.cui)
    if info:
        print(f"CUI: {info['cui']}")
        print(f"Name: {info['name']}")
        print(f"Semantic Types: {', '.join(info['semantic_types'])}")
        print(f"Atom Count: {info['atom_count']}")
        print(f"Status: {info['status']}")
    else:
        print(f"CUI {args.cui} not found in UMLS.")


def cmd_search(args):
    """Search UMLS by substance name."""
    client = UMLSClient(
        args.api_key,
        timeout_seconds=args.timeout_seconds,
        failure_limit=args.failure_limit,
        cache_path=Path(args.cache_file) if args.cache_file else None,
        cache_ttl_seconds=args.cache_ttl_seconds,
    )
    results = client.search(args.search, max_results=10)
    if results:
        print(f"Top {len(results)} results for '{args.search}':\n")
        for i, r in enumerate(results, 1):
            types = ", ".join(r["semantic_types"]) if isinstance(r["semantic_types"], list) else str(r["semantic_types"])
            print(f"  {i}. {r['cui']} — {r['name']}")
            print(f"     Source: {r['source']} | Types: {types}")
            print()
    else:
        print(f"No results for '{args.search}'.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="UMLS CUI Verification & Lookup for PharmaGuide data files",
        epilog=VERIFY_CUI_HELP_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--api-key", default=DEFAULT_API_KEY,
                        help="UMLS API key (or set UMLS_API_KEY env var)")
    parser.add_argument("--file", default=str(DEFAULT_FILE),
                        help=f"JSON data file to verify (default: {DEFAULT_FILE.name})")
    parser.add_argument("--list-key", default="harmful_additives",
                        help="JSON key containing the entry list (default: harmful_additives)")
    parser.add_argument("--id-field", default="id",
                        help="Field name for entry ID (default: id)")
    parser.add_argument("--cui-field", default="cui",
                        help="Field name for CUI (default: cui)")
    parser.add_argument("--apply", action="store_true",
                        help="Apply suggested CUI fixes to the file")
    parser.add_argument("--apply-mismatches", action="store_true",
                        help="Allow --apply to overwrite existing mismatched CUIs when an exact replacement is found")
    parser.add_argument("--cui", help="Look up a single CUI")
    parser.add_argument("--search", help="Search UMLS by substance name")
    parser.add_argument("--timeout-seconds", type=float, default=5.0,
                        help="Per-request timeout for UMLS API calls")
    parser.add_argument("--failure-limit", type=int, default=2,
                        help="Open the transport circuit after this many consecutive request failures")
    parser.add_argument("--cache-file", default=str(Path(__file__).parent / ".cache" / "umls_api_cache.json"),
                        help="JSON cache file for successful UMLS responses")
    parser.add_argument("--cache-ttl-seconds", type=int, default=DEFAULT_CACHE_TTL_SECONDS,
                        help="TTL for cached UMLS API responses")

    args = parser.parse_args()

    if args.cui:
        cmd_lookup_cui(args)
    elif args.search:
        cmd_search(args)
    else:
        cmd_verify(args)


if __name__ == "__main__":
    main()
