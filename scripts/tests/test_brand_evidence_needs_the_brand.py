"""A brand's clinical record reaches a label only when the label names the brand.

`enrich_supplements_v3._brand_mentioned` confirms an alias-only BRAND_ match in the
product text, using the entry's curated `brand_tokens` when present; aliases stay the
discovery surface and may be generic. BioPerine and Zynamite had no brand_tokens, so
a generic alias ("piperine", "mangiferin") confirmed itself, and HMB and OptiFerrin
were ingredient evidence filed as brands: 81 raw labels in the corpus census of
2026-09-29 took a brand's Evidence floor without naming a brand. Receipts:
scripts/audits/rr_correctness_20260928/research.md.
"""
import json
import logging
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
DATA = Path(__file__).resolve().parents[1] / "data"


def _entries():
    rows = json.loads((DATA / "backed_clinical_studies.json").read_text())["backed_clinical_studies"]
    return {e["id"]: e for e in rows}


def test_brands_with_generic_aliases_confirm_on_their_brand_token():
    entries = _entries()
    assert entries["BRAND_BIOPERINE"]["brand_tokens"] == ["bioperine"]
    assert entries["BRAND_ZYNAMITE"]["brand_tokens"] == ["zynamite"]
    assert entries["BRAND_SUNTHEANINE"]["brand_tokens"] == ["suntheanine"]


def test_ingredient_evidence_is_filed_as_ingredient_evidence():
    entries = _entries()
    assert "BRAND_HMB" not in entries and "BRAND_OPTIFERRIN" not in entries
    hmb, lactoferrin = entries["INGR_HMB"], entries["INGR_LACTOFERRIN"]
    assert hmb["evidence_level"] == lactoferrin["evidence_level"] == "ingredient-human"
    assert {"hmb", "calcium hmb"} <= set(hmb["aliases"])
    assert "lactoferrin" in lactoferrin["aliases"]
    assert (lactoferrin["min_clinical_dose"], lactoferrin["dose_unit"]) == (200, "mg")


def _matches(pid):
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3

    logging.disable(logging.INFO)
    raw = json.loads((FIXTURES / f"brand_generic_{pid}_raw.json").read_text())
    enriched, _ = SupplementEnricherV3().enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))
    return {m.get("id") for m in (enriched.get("evidence_data") or {}).get("clinical_matches") or []}


@pytest.mark.parametrize("pid, absent, present", [
    ("176168", "BRAND_BIOPERINE", None),         # piperine, BioPerine not named
    ("233404", "BRAND_ZYNAMITE", None),          # mangiferin, Zynamite not named
    ("18416", "BRAND_HMB", "INGR_HMB"),          # plain HMB
    ("267894", "BRAND_OPTIFERRIN", "INGR_LACTOFERRIN"),  # plain lactoferrin
    ("182824", None, "BRAND_BIOPERINE"),        # "Curcumin 500 with Bioperine"
    ("214982", None, "BRAND_SUNTHEANINE"),      # names Suntheanine
])
def test_real_labels_reach_the_right_record(pid, absent, present):
    matches = _matches(pid)
    if absent:
        assert absent not in matches
    if present:
        assert present in matches
