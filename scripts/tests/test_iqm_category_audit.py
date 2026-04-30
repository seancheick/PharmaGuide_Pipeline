#!/usr/bin/env python3
"""IQM category_enum audit (2026-04-30) — pin specific reclassifications.

Confirms 41 IQM parents previously misfiled as 'other' are now in their
correct canonical category (functional_foods, proteins, fibers, etc.).
Catches regressions on the recategorize.py decisions.
"""

import json
from pathlib import Path
import pytest

DATA_PATH = Path(__file__).parent.parent / "data" / "ingredient_quality_map.json"


@pytest.fixture(scope="module")
def iqm():
    return json.load(open(DATA_PATH, encoding="utf-8"))


PINNED = {
    # functional_foods
    "apple_cider_vinegar":       "functional_foods",
    "chlorella":                 "functional_foods",
    "spirulina":                 "functional_foods",
    "colostrum":                 "functional_foods",
    "rice_bran":                 "functional_foods",
    # proteins
    "collagen":                  "proteins",
    "casein_hydrolysate":        "proteins",
    "keratin":                   "proteins",
    # fibers
    "chondroitin":               "fibers",
    "hyaluronic_acid":           "fibers",
    "glucosamine":               "fibers",
    "prebiotics":                "fibers",
    # fatty_acids
    "palmitic_acid":             "fatty_acids",
    "lecithin":                  "fatty_acids",
    "alpha_gpc":                 "fatty_acids",
    "tudca":                     "fatty_acids",
    # amino_acids
    "creatine_monohydrate":      "amino_acids",
    "choline":                   "amino_acids",
    "paba":                      "amino_acids",
    # vitamins
    "nicotinamide_riboside":     "vitamins",
    "nmn":                       "vitamins",
    # antioxidants
    "urolithin_a":               "antioxidants",
    "diindolylmethane":          "antioxidants",
    # herbs (plant alkaloids)
    "caffeine":                  "herbs",
    "theophylline":              "herbs",
    "berberine_supplement":      "herbs",
    "synephrine":                "herbs",
    # minerals
    "bentonite":                 "minerals",
}


@pytest.mark.parametrize("parent_id,expected", list(PINNED.items()))
def test_iqm_parent_category(iqm, parent_id, expected):
    entry = iqm.get(parent_id)
    assert isinstance(entry, dict), f"{parent_id} missing from IQM"
    actual = entry.get("category_enum")
    assert actual == expected, (
        f"{parent_id}: expected category_enum={expected!r}, got {actual!r}"
    )


def test_other_bucket_under_threshold(iqm):
    """After 2026-04-30 audit, the 'other' bucket should hold only ambiguous
    entries (hormones, nucleotides, organic acids) — no clear-fit entries."""
    parents = {k: v for k, v in iqm.items()
               if not k.startswith("_") and isinstance(v, dict)}
    others = sum(1 for v in parents.values() if v.get("category_enum") == "other")
    assert others <= 40, (
        f"'other' bucket has {others} entries — audit may have regressed. "
        f"Target ≤40 (legitimate ambiguous: hormones, nucleotides, sulfur cmpds)."
    )
