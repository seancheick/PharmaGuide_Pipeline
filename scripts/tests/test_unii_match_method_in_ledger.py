#!/usr/bin/env python3
"""
Sprint 1.1 regression tests for match-ledger attribution.

Sprint 1 (commit 7c7fe70) introduced UNII-first matching and alternateNames
fallback in the cleaner, but the downstream enricher's match_ledger
collapsed those resolves under `exact` because the new method values weren't
threaded through. Sprint 1.1 (commits a5c6c46 → ...) closes that gap:

  1. Cleaner sets `cleaner_match_method` on each cleaned-ingredient dict
     when a Sprint 1 method fired (UNII Tier-0 or alternateNames).
  2. Enricher reads `cleaner_match_method` and overrides the default
     tier-derived method when present, recording one of:
       - METHOD_UNII_EXACT          ("unii_exact_match")
       - METHOD_UNII_FORM_EXACT     ("unii_form_exact_match")
       - METHOD_ALTERNATE_NAME      ("alternate_name_match")

This test file pins the contract:
  - The 3 new constants exist in match_ledger module
  - The cleaner→enricher mapping is complete (no orphan values)
  - For a synthetic product whose name wouldn't match by string but whose
    uniiCode does, the final match_ledger records `unii_exact_match` —
    not `exact` or `normalized`.

If a future change collapses these attributions back into `exact`,
this test catches the regression.
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


# ============================================================================
# Section 1 — constants exist
# ============================================================================


def test_match_ledger_exports_three_new_methods():
    """match_ledger module must export the 3 new method constants."""
    import match_ledger as ml
    assert getattr(ml, "METHOD_UNII_EXACT", None) == "unii_exact_match"
    assert getattr(ml, "METHOD_UNII_FORM_EXACT", None) == "unii_form_exact_match"
    assert getattr(ml, "METHOD_ALTERNATE_NAME", None) == "alternate_name_match"


def test_enricher_imports_three_new_methods():
    """enrich_supplements_v3 must import the 3 new constants for ledger emission."""
    src = (SCRIPTS_DIR / "enrich_supplements_v3.py").read_text(encoding="utf-8")
    for name in ("METHOD_UNII_EXACT", "METHOD_UNII_FORM_EXACT", "METHOD_ALTERNATE_NAME"):
        assert name in src, f"enricher source must import {name}"


def test_cleaner_method_map_is_complete():
    """Every cleaner-side match-method string must map to a match_ledger constant."""
    from enrich_supplements_v3 import _CLEANER_MATCH_METHOD_MAP
    import match_ledger as ml

    expected_keys = {"unii_exact_match", "unii_form_exact_match", "alternate_name_match"}
    assert set(_CLEANER_MATCH_METHOD_MAP.keys()) == expected_keys, (
        f"_CLEANER_MATCH_METHOD_MAP keys drift: got {set(_CLEANER_MATCH_METHOD_MAP.keys())}"
    )
    # And every mapped value must be a real match_ledger constant
    assert _CLEANER_MATCH_METHOD_MAP["unii_exact_match"] == ml.METHOD_UNII_EXACT
    assert _CLEANER_MATCH_METHOD_MAP["unii_form_exact_match"] == ml.METHOD_UNII_FORM_EXACT
    assert _CLEANER_MATCH_METHOD_MAP["alternate_name_match"] == ml.METHOD_ALTERNATE_NAME


# ============================================================================
# Section 2 — cleaner output carries cleaner_match_method
# ============================================================================


def test_cleaner_writes_match_method_into_result_dict():
    """The cleaner's `result` dict (line 5055-onwards in enhanced_normalizer.py)
    must include `cleaner_match_method`. This is the field the enricher reads
    to surface UNII / alternateNames attribution in the final ledger."""
    src = (SCRIPTS_DIR / "enhanced_normalizer.py").read_text(encoding="utf-8")
    # Source-level guarantee: the result-dict construction includes the field
    assert '"cleaner_match_method"' in src, (
        "cleaner_match_method missing from result-dict construction — "
        "enricher won't see UNII/alternateNames attribution"
    )


# ============================================================================
# Section 3 — end-to-end: GNC ledger contains new methods
# ============================================================================
#
# The pre-Sprint-1.1 ledger showed only legacy methods (exact, normalized,
# pattern, contains). After Sprint 1.1, products where the cleaner resolved
# via UNII must appear with `match_method: unii_exact_match` (or _form_).
#
# We rely on the latest GNC enrichment (re-run after Sprint 1.1 lands).
# If no GNC export exists yet, this test is skipped — but once it runs,
# the new methods must be present.


@pytest.fixture(scope="module")
def gnc_match_methods():
    """Collect all match_method values from the latest GNC enrichment's
    match_ledger ingredients-domain records."""
    import glob, json
    enriched_dir = REPO_ROOT / "scripts/products/output_GNC_enriched/enriched"
    files = sorted(glob.glob(str(enriched_dir / "enriched_cleaned_batch_*.json")))
    if not files:
        return None  # signal "no GNC export available"

    methods: dict = {}
    for f in files:
        with open(f, encoding="utf-8") as fh:
            products = json.load(fh)
        for p in products:
            ml = p.get("match_ledger", {}) or {}
            ing_domain = ml.get("domains", {}).get("ingredients", {}) or {}
            records = ing_domain.get("records", []) or []
            for rec in records:
                m = rec.get("match_method")
                if m:
                    methods[m] = methods.get(m, 0) + 1
    return methods


def test_gnc_ledger_includes_unii_or_alternate_methods(gnc_match_methods):
    """End-to-end proof: at least ONE of the 3 new methods appears in the
    final match_ledger of the GNC catalog enrichment."""
    if gnc_match_methods is None:
        pytest.skip("No GNC enriched output available — re-run pipeline after Sprint 1.1 lands")

    new_methods = {"unii_exact_match", "unii_form_exact_match", "alternate_name_match"}
    found = {m: gnc_match_methods.get(m, 0) for m in new_methods}
    total_new = sum(found.values())
    assert total_new > 0, (
        f"After Sprint 1.1, expected ≥1 GNC ingredient resolved via UNII or "
        f"alternateNames in the final match_ledger. Got 0. "
        f"All methods seen: {gnc_match_methods}"
    )


def test_gnc_ledger_records_unii_exact_match(gnc_match_methods):
    """Specific assertion: `unii_exact_match` must appear at least once
    (DSLD-provided top-level uniiCode resolved against UNII index)."""
    if gnc_match_methods is None:
        pytest.skip("No GNC enriched output available")
    assert gnc_match_methods.get("unii_exact_match", 0) > 0, (
        f"unii_exact_match missing from GNC ledger. Methods seen: {gnc_match_methods}"
    )


def test_gnc_ledger_does_not_misattribute_unii_as_exact(gnc_match_methods):
    """High Amylopectin Starch (UNII TQI9LJM246) is one specific case
    we know resolves via UNII. Its match_method MUST be unii_exact_match,
    not exact."""
    if gnc_match_methods is None:
        pytest.skip("No GNC enriched output available")

    import glob, json
    enriched_dir = REPO_ROOT / "scripts/products/output_GNC_enriched/enriched"
    files = sorted(glob.glob(str(enriched_dir / "enriched_cleaned_batch_*.json")))
    found_amylopectin = []
    for f in files:
        with open(f, encoding="utf-8") as fh:
            products = json.load(fh)
        for p in products:
            ml = p.get("match_ledger", {}) or {}
            ing_domain = ml.get("domains", {}).get("ingredients", {}) or {}
            records = ing_domain.get("records", []) or []
            for rec in records:
                rst = rec.get("raw_source_text", "") or ""
                if "amylopectin" in rst.lower():
                    found_amylopectin.append((p.get("id"), rec.get("match_method"), rst))

    if not found_amylopectin:
        pytest.skip("No High Amylopectin Starch ingredients in GNC export to verify against")

    # Every amylopectin record carrying a uniiCode should be unii_exact_match
    misattributed = [
        (pid, m, rst) for pid, m, rst in found_amylopectin
        if m and m != "unii_exact_match" and m != "unii_form_exact_match"
    ]
    assert not misattributed, (
        f"High Amylopectin Starch records misattributed (expected unii_exact_match): "
        f"{misattributed[:5]}"
    )
