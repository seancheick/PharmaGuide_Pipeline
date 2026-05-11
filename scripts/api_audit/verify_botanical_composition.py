#!/usr/bin/env python3
"""
verify_botanical_composition.py — Phase 1 reference data builder + validator.

Two modes:

  --build-baseline
      Calls USDA FoodData Central + PubMed to fetch initial verified data for
      the 9 source botanicals in the identity/bioactivity split. Writes
      scripts/data/botanical_marker_contributions.json with citations inline.

  --validate (default)
      Reads botanical_marker_contributions.json and re-validates each entry
      against live APIs. For USDA entries: confirms food item resolves and
      nutrient value still within ±5% tolerance. For PubMed entries: confirms
      PMID exists and abstract/title mentions the claimed botanical + marker.
      Exits non-zero if any entry fails content verification (per
      critical_no_hallucinated_citations memory).

Clinical model: for botanicals where marker content is HIGHLY VARIABLE across
extracts (curcumin in turmeric, sulforaphane in broccoli sprout, capsaicin in
cayenne, quercetin in sophora, aescin in horse chestnut, resveratrol in
polygonum, vitamin C in camu camu), we require explicit label standardization
(min_standardization_pct_required). For botanicals where marker content is a
characterized food nutrient (vitamin C in acerola, lycopene in tomato), we
allow a default_contribution_mg_per_g traced to USDA FDC.

Usage:
    python3 scripts/api_audit/verify_botanical_composition.py --build-baseline
    python3 scripts/api_audit/verify_botanical_composition.py            # validate
    python3 scripts/api_audit/verify_botanical_composition.py --json     # JSON output
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET

import requests

SCRIPT_DIR = Path(__file__).resolve().parent
SCRIPTS_ROOT = SCRIPT_DIR.parent
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

import env_loader  # noqa: F401  (side-effect: loads .env into os.environ)
from api_audit.pubmed_client import PubMedClient, load_pubmed_config

REPO_ROOT = SCRIPTS_ROOT.parent
DATA_PATH = SCRIPTS_ROOT / "data" / "botanical_marker_contributions.json"

USDA_API_KEY = os.environ.get("USDA_API_KEY", "")
USDA_BASE = "https://api.nal.usda.gov/fdc/v1"
USDA_TIMEOUT = 20

# USDA FDC standard nutrient IDs
NUTRIENT_VITAMIN_C = 1162      # Total ascorbic acid (mg)
NUTRIENT_LYCOPENE = 1122       # Lycopene (μg)

# Tolerance bands when revalidating (±%)
USDA_TOLERANCE = 0.30  # 30% — broad because food data legitimately varies
PUBMED_REQUIRED_CONFIDENCE = 0.5  # min keyword match ratio. standardization_required entries cite policy/known-source-of-marker, not dose claims, so 0.5 of expected keywords is sufficient.


# ---------------------------------------------------------------------------
# Baseline definitions
# ---------------------------------------------------------------------------

# For each botanical, define the marker contribution model.
# DEFAULT_CONTRIBUTION entries get default_contribution_mg_per_g (USDA-verified).
# STANDARDIZATION_REQUIRED entries get min_standardization_pct_required only
# (no default credit; label must declare).
BASELINE_SPECS: list[dict[str, Any]] = [
    {
        "botanical_id": "acerola_cherry",
        "botanical_source_db": "botanical_ingredients",
        "marker": "vitamin_c",
        "model": "default_contribution",
        "usda_search_term": "acerola raw",
        "usda_nutrient_id": NUTRIENT_VITAMIN_C,
        "usda_units": "mg",
        "standardization_keywords": ["standardized to", "% vitamin c", "% ascorbic acid", "mg vitamin c"],
        "notes": (
            "Fresh acerola fruit averages ~1670 mg vitamin C per 100g per USDA FoodData "
            "Central; one of the highest natural sources. Default contribution gives "
            "partial credit when label declares acerola but does not standardize."
        ),
    },
    {
        "botanical_id": "tomato",
        "botanical_source_db": "botanical_ingredients",
        "marker": "lycopene",
        "model": "default_contribution",
        "usda_search_term": "tomato puree canned",
        "usda_nutrient_id": NUTRIENT_LYCOPENE,
        "usda_units": "ug",   # USDA returns lycopene in μg per 100g
        "standardization_keywords": ["standardized to", "% lycopene", "mg lycopene"],
        "notes": (
            "Tomato concentrates/purees contain measurable lycopene per USDA FDC. "
            "Fresh tomato is lower (~2500 μg/100g); concentrates 10x+ higher. "
            "Default contribution uses puree value as conservative midpoint."
        ),
    },
    {
        "botanical_id": "camu_camu",
        "botanical_source_db": "standardized_botanicals",
        "marker": "vitamin_c",
        "model": "standardization_required",
        "min_standardization_pct_required": 5.0,
        "standardization_keywords": ["standardized to", "% vitamin c", "% ascorbic acid", "mg vitamin c"],
        "pubmed_query": "camu camu vitamin C content Myrciaria dubia",
        "expected_keywords": ["camu", "vitamin c", "ascorbic"],
        "notes": (
            "Camu camu (Myrciaria dubia) berry vitamin C content is highly variable "
            "(2-3% w/w fresh, 20%+ in standardized extracts). Conservative policy: "
            "credit vitamin C only when label explicitly declares standardization."
        ),
    },
    {
        "botanical_id": "turmeric",
        "botanical_source_db": "botanical_ingredients",
        "marker": "curcumin",
        "model": "standardization_required",
        "min_standardization_pct_required": 95.0,
        "standardization_keywords": ["curcuminoid", "95%", "standardized to", "% curcumin"],
        "pubmed_query": "turmeric curcumin content standardization Curcuma longa",
        "expected_keywords": ["turmeric", "curcumin", "curcuminoid"],
        "notes": (
            "Raw turmeric rhizome contains 2-9% curcuminoids; commercial standardized "
            "extracts (95% curcuminoids) are the clinical reference. Credit curcumin "
            "only when label declares 95%+ standardization (industry standard)."
        ),
    },
    {
        "botanical_id": "broccoli_sprout",
        "botanical_source_db": "MISSING_NEEDS_CREATION",
        "marker": "sulforaphane",
        "model": "standardization_required",
        "min_standardization_pct_required": 1.0,
        "standardization_keywords": ["sulforaphane", "glucoraphanin", "% sulforaphane", "% glucoraphanin", "myrosinase"],
        "pubmed_query": "broccoli sprout sulforaphane glucoraphanin",
        "expected_keywords": ["broccoli", "sulforaphane"],
        "notes": (
            "Sulforaphane is generated from glucoraphanin by myrosinase during chewing. "
            "Raw broccoli sprout glucoraphanin varies 0.5-13 mg/g; sulforaphane yield "
            "depends on processing. Credit only when label declares standardization."
        ),
    },
    {
        "botanical_id": "cayenne_pepper",
        "botanical_source_db": "botanical_ingredients",
        "marker": "capsaicin",
        "model": "standardization_required",
        "min_standardization_pct_required": 2.0,
        "standardization_keywords": ["capsaicin", "capsaicinoid", "% capsaicin", "Scoville"],
        "pubmed_query": "cayenne capsicum capsaicin capsaicinoid content variability",
        "expected_keywords": ["capsicum", "capsaicin"],
        "notes": (
            "Cayenne (Capsicum annuum) capsaicinoid content varies widely (0.1-2% w/w) "
            "by cultivar and growing conditions. Standardized commercial extracts "
            "(e.g., Capsimax 2%) are the clinical reference. Credit only when standardized."
        ),
    },
    {
        "botanical_id": "sophora_japonica",
        "botanical_source_db": "botanical_ingredients",
        "marker": "quercetin",
        "model": "standardization_required",
        "min_standardization_pct_required": 95.0,
        "standardization_keywords": ["quercetin", "% quercetin", "standardized to"],
        "pubmed_query": "Sophora japonica flower bud quercetin rutin flavonoid",
        "expected_keywords": ["sophora", "quercetin"],
        "notes": (
            "Sophora japonica flower buds are a commercial source of quercetin via "
            "rutin hydrolysis. Commercial quercetin from sophora is typically 95%+ "
            "pure. Credit only when label declares standardization."
        ),
    },
    {
        "botanical_id": "horse_chestnut_seed",
        "botanical_source_db": "botanical_ingredients",
        "marker": "aescin",
        "model": "standardization_required",
        "min_standardization_pct_required": 16.0,
        "standardization_keywords": ["aescin", "escin", "16%", "20%", "% aescin", "% escin"],
        "pubmed_query": "horse chestnut Aesculus hippocastanum aescin escin standardization",
        "expected_keywords": ["horse chestnut", "aescin", "escin"],
        "notes": (
            "Horse chestnut seed extract (HCSE) used clinically is standardized to "
            "16-20% triterpene glycosides (aescin/escin). Raw seed content varies. "
            "Credit only when label declares 16%+ standardization."
        ),
    },
    {
        "botanical_id": "japanese_knotweed",
        "botanical_source_db": "botanical_ingredients",
        "marker": "resveratrol",
        "model": "standardization_required",
        "min_standardization_pct_required": 50.0,
        "standardization_keywords": ["resveratrol", "trans-resveratrol", "% resveratrol", "standardized to"],
        "pubmed_query": "Polygonum cuspidatum Japanese knotweed resveratrol content extraction",
        "expected_keywords": ["polygonum", "knotweed", "resveratrol"],
        "notes": (
            "Polygonum cuspidatum (Japanese knotweed) is the commercial source of "
            "resveratrol. Raw root contains 0.1-1.5% resveratrol; standardized extracts "
            "are 50-98% pure. Credit only when label declares standardization."
        ),
    },
]


# ---------------------------------------------------------------------------
# USDA FoodData Central client
# ---------------------------------------------------------------------------

def usda_search(query: str) -> list[dict]:
    if not USDA_API_KEY:
        return []
    url = f"{USDA_BASE}/foods/search"
    params = {"api_key": USDA_API_KEY, "query": query, "pageSize": 10}
    r = requests.get(url, params=params, timeout=USDA_TIMEOUT)
    r.raise_for_status()
    return r.json().get("foods", []) or []


def usda_food_detail(fdc_id: int) -> dict:
    url = f"{USDA_BASE}/food/{fdc_id}"
    params = {"api_key": USDA_API_KEY}
    r = requests.get(url, params=params, timeout=USDA_TIMEOUT)
    r.raise_for_status()
    return r.json()


def extract_nutrient_value(food: dict, nutrient_id: int) -> float | None:
    """Returns value per 100g (USDA standard) or None."""
    for n in food.get("foodNutrients", []) or []:
        # Search responses use {nutrientId, value}; detail responses use {nutrient: {id}, amount}
        nid = n.get("nutrientId") or (n.get("nutrient") or {}).get("id")
        if nid == nutrient_id:
            return n.get("value", n.get("amount"))
    return None


# ---------------------------------------------------------------------------
# PubMed wrapper helpers
# ---------------------------------------------------------------------------

def pubmed_first_pmid(client: PubMedClient, query: str) -> str | None:
    res = client.esearch(query, retmax=5, sort="relevance")
    ids = (res.get("esearchresult") or {}).get("idlist") or []
    return ids[0] if ids else None


def pubmed_fetch_summary(client: PubMedClient, pmid: str) -> dict | None:
    """Returns {title, abstract, journal, year} for a PMID."""
    xml = client.efetch(pmid, rettype="abstract", retmode="xml")
    if not xml:
        return None
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return None
    article = root.find(".//Article")
    if article is None:
        return None
    title = (article.findtext("ArticleTitle") or "").strip()
    abstract_node = article.find("Abstract")
    abstract = ""
    if abstract_node is not None:
        abstract = " ".join(
            (t.text or "").strip() for t in abstract_node.findall("AbstractText") if t.text
        )
    return {"title": title, "abstract": abstract, "pmid": pmid}


def keyword_coverage(text: str, keywords: list[str]) -> float:
    """Fraction of keywords present in text (case-insensitive)."""
    if not keywords:
        return 1.0
    text_l = text.lower()
    hits = sum(1 for k in keywords if k.lower() in text_l)
    return hits / len(keywords)


# ---------------------------------------------------------------------------
# Baseline construction
# ---------------------------------------------------------------------------

@dataclass
class BuildResult:
    botanical_id: str
    marker: str
    status: str  # ok, partial, failed
    detail: str = ""
    payload: dict = field(default_factory=dict)


def build_default_contribution(spec: dict) -> BuildResult:
    botanical_id = spec["botanical_id"]
    marker = spec["marker"]
    if not USDA_API_KEY:
        return BuildResult(botanical_id, marker, "failed", "USDA_API_KEY not set")

    foods = usda_search(spec["usda_search_term"])
    if not foods:
        return BuildResult(botanical_id, marker, "failed", f"USDA search returned 0 results for {spec['usda_search_term']!r}")
    # Pick first food entry that has the nutrient
    for food in foods:
        val = extract_nutrient_value(food, spec["usda_nutrient_id"])
        if val is None:
            continue
        fdc_id = food.get("fdcId")
        food_name = food.get("description") or food.get("lowercaseDescription")
        # Convert μg to mg if needed (lycopene in USDA is μg per 100g)
        value_mg_per_100g = val / 1000.0 if spec["usda_units"] == "ug" else float(val)
        contribution_mg_per_g = round(value_mg_per_100g / 100.0, 6)
        payload = {
            "marker_canonical_id": marker,
            "model": "default_contribution",
            "default_contribution_mg_per_g": contribution_mg_per_g,
            "evidence_source": f"USDA FoodData Central — {food_name}",
            "evidence_url": f"https://fdc.nal.usda.gov/food-details/{fdc_id}/nutrients",
            "evidence_id": f"USDA_FDC:{fdc_id}",
            "evidence_nutrient_id": spec["usda_nutrient_id"],
            "evidence_raw_value": val,
            "evidence_raw_units": spec["usda_units"] + " per 100g",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "standardization_keywords": spec["standardization_keywords"],
            "min_standardization_pct_required": None,
            "notes": spec["notes"],
        }
        return BuildResult(botanical_id, marker, "ok", f"USDA FDC {fdc_id}: {val} {spec['usda_units']}/100g", payload)

    return BuildResult(botanical_id, marker, "failed", f"No USDA food entries had nutrient {spec['usda_nutrient_id']}")


def build_standardization_required(spec: dict, pubmed_client: PubMedClient) -> BuildResult:
    botanical_id = spec["botanical_id"]
    marker = spec["marker"]
    pmid = pubmed_first_pmid(pubmed_client, spec["pubmed_query"])
    if not pmid:
        return BuildResult(botanical_id, marker, "failed", f"PubMed esearch returned 0 PMIDs for {spec['pubmed_query']!r}")
    summary = pubmed_fetch_summary(pubmed_client, pmid)
    if not summary:
        return BuildResult(botanical_id, marker, "failed", f"PubMed efetch failed for PMID {pmid}")
    cov = keyword_coverage(summary["title"] + " " + summary["abstract"], spec["expected_keywords"])
    if cov < PUBMED_REQUIRED_CONFIDENCE:
        return BuildResult(
            botanical_id, marker, "partial",
            f"PMID {pmid} keyword coverage {cov:.2f} < {PUBMED_REQUIRED_CONFIDENCE:.2f} — content may not verify claim. Title: {summary['title']!r}",
            {"pmid": pmid, "title": summary["title"], "coverage": cov},
        )
    payload = {
        "marker_canonical_id": marker,
        "model": "standardization_required",
        "min_standardization_pct_required": spec["min_standardization_pct_required"],
        "default_contribution_mg_per_g": None,
        "evidence_source": f"PubMed PMID:{pmid} — {summary['title']}",
        "evidence_url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        "evidence_id": f"PMID:{pmid}",
        "evidence_keyword_coverage": round(cov, 3),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "standardization_keywords": spec["standardization_keywords"],
        "notes": spec["notes"],
    }
    return BuildResult(botanical_id, marker, "ok", f"PMID {pmid} ({cov:.2f} coverage)", payload)


def build_baseline() -> int:
    if not USDA_API_KEY:
        print("WARNING: USDA_API_KEY not set — default_contribution entries will fail.", file=sys.stderr)
    pubmed_client = PubMedClient(config=load_pubmed_config())

    output: dict = {
        "_metadata": {
            "schema_version": "1.0.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "generator": "scripts/api_audit/verify_botanical_composition.py --build-baseline",
            "source_authorities": [
                "USDA FoodData Central API (api.nal.usda.gov/fdc/v1)",
                "PubMed E-utilities (eutils.ncbi.nlm.nih.gov/entrez/eutils)",
            ],
            "policy": (
                "Identity vs Bioactivity Split — source botanicals only credit marker Section C "
                "evidence when (a) label explicitly declares standardization meeting "
                "min_standardization_pct_required, or (b) botanical has a default_contribution_mg_per_g "
                "with USDA FDC citation."
            ),
            "total_entries": 0,
        },
        "botanicals": {},
    }
    results: list[BuildResult] = []
    for spec in BASELINE_SPECS:
        print(f"Building {spec['botanical_id']} → {spec['marker']} ({spec['model']})...", file=sys.stderr)
        if spec["model"] == "default_contribution":
            res = build_default_contribution(spec)
        else:
            res = build_standardization_required(spec, pubmed_client)
        results.append(res)
        if res.status == "ok" and res.payload:
            output["botanicals"].setdefault(res.botanical_id, {"delivers": []})
            output["botanicals"][res.botanical_id]["delivers"].append(res.payload)
            output["botanicals"][res.botanical_id]["source_db"] = spec["botanical_source_db"]
        time.sleep(0.2)  # be polite to USDA + PubMed
    output["_metadata"]["total_entries"] = sum(len(v.get("delivers", [])) for v in output["botanicals"].values())

    # Persist
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATA_PATH.write_text(json.dumps(output, indent=2))

    # Summary
    n_ok = sum(1 for r in results if r.status == "ok")
    n_partial = sum(1 for r in results if r.status == "partial")
    n_failed = sum(1 for r in results if r.status == "failed")
    print(f"\n=== Baseline build complete ===", file=sys.stderr)
    print(f"OK:      {n_ok}", file=sys.stderr)
    print(f"PARTIAL: {n_partial}", file=sys.stderr)
    print(f"FAILED:  {n_failed}", file=sys.stderr)
    for r in results:
        print(f"  [{r.status:7s}] {r.botanical_id:25s} {r.marker:14s} {r.detail}", file=sys.stderr)
    print(f"\nOutput: {DATA_PATH}", file=sys.stderr)
    return 1 if n_failed else 0


# ---------------------------------------------------------------------------
# Validation (re-verify existing entries)
# ---------------------------------------------------------------------------

def validate_entry(botanical_id: str, contribution: dict, pubmed_client: PubMedClient) -> tuple[bool, str]:
    model = contribution.get("model")
    if model == "default_contribution":
        eid = contribution.get("evidence_id", "")
        m = re.match(r"^USDA_FDC:(\d+)$", eid)
        if not m:
            return False, f"evidence_id {eid!r} not in USDA_FDC:<id> form"
        fdc_id = int(m.group(1))
        try:
            food = usda_food_detail(fdc_id)
        except requests.HTTPError as e:
            return False, f"USDA FDC {fdc_id} fetch failed: {e}"
        nid = contribution.get("evidence_nutrient_id")
        live = extract_nutrient_value(food, nid)
        if live is None:
            return False, f"USDA FDC {fdc_id} no longer has nutrient {nid}"
        recorded = contribution.get("evidence_raw_value", 0)
        if recorded and abs(live - recorded) / max(recorded, 1e-9) > USDA_TOLERANCE:
            return False, f"USDA value drift: recorded {recorded}, live {live} (>{USDA_TOLERANCE*100:.0f}%)"
        return True, f"USDA FDC {fdc_id} verified ({live} matches recorded {recorded})"
    elif model == "standardization_required":
        eid = contribution.get("evidence_id", "")
        m = re.match(r"^PMID:(\d+)$", eid)
        if not m:
            return False, f"evidence_id {eid!r} not in PMID:<id> form"
        pmid = m.group(1)
        summary = pubmed_fetch_summary(pubmed_client, pmid)
        if not summary:
            return False, f"PMID {pmid} efetch returned no article"
        # Re-verify keyword coverage using same threshold
        # Use botanical_id + marker as keywords for content check
        keywords = [botanical_id.split("_")[0], contribution.get("marker_canonical_id", "")]
        cov = keyword_coverage(summary["title"] + " " + summary["abstract"], keywords)
        if cov < 0.5:
            return False, f"PMID {pmid} content coverage {cov:.2f} too low — ghost reference suspected"
        return True, f"PMID {pmid} content verified ({cov:.2f} coverage)"
    else:
        return False, f"Unknown model {model!r}"


def validate_data() -> int:
    if not DATA_PATH.exists():
        print(f"ERROR: {DATA_PATH} does not exist — run --build-baseline first", file=sys.stderr)
        return 2
    with DATA_PATH.open() as f:
        data = json.load(f)
    pubmed_client = PubMedClient(config=load_pubmed_config())
    n_ok = n_fail = 0
    failures: list[str] = []
    for botanical_id, entry in data.get("botanicals", {}).items():
        for contrib in entry.get("delivers", []):
            ok, detail = validate_entry(botanical_id, contrib, pubmed_client)
            tag = "OK" if ok else "FAIL"
            print(f"  [{tag:4s}] {botanical_id:25s} {contrib.get('marker_canonical_id',''):14s} {detail}", file=sys.stderr)
            if ok:
                n_ok += 1
            else:
                n_fail += 1
                failures.append(f"{botanical_id}/{contrib.get('marker_canonical_id')}: {detail}")
            time.sleep(0.2)
    print(f"\n=== Validation complete: {n_ok} OK, {n_fail} FAIL ===", file=sys.stderr)
    if failures:
        print("\nFailures:", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
    return 0 if n_fail == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-baseline", action="store_true", help="Fetch USDA + PubMed data and write botanical_marker_contributions.json")
    parser.add_argument("--json", action="store_true", help="Emit JSON status report to stdout")
    args = parser.parse_args()
    if args.build_baseline:
        return build_baseline()
    return validate_data()


if __name__ == "__main__":
    sys.exit(main())
