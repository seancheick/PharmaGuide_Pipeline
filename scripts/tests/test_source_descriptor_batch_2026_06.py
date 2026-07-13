"""Source-descriptor / branded-additive recognition batch (2026-06 unmapped triage).

Unmapped DSLD labels whose identity is an EXISTING non-scorable excipient/additive
— added the missing label aliases so they recognize (non-scorable; no scoring
over-credit, these are excipients/penalty additives, not actives). Collision check
showed all three targets already existed.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from enrich_supplements_v3 import SupplementEnricherV3


@pytest.fixture(scope="module")
def enricher():
    return SupplementEnricherV3()


@pytest.mark.parametrize(
    "label,source,entry_id",
    [
        ("Millers Bran", "other_ingredients", "OI_WHEAT_BRAN"),                 # miller's bran = wheat bran
        ("Calcium Caseinate and Gelatin", "other_ingredients", "NHA_CALCIUM_CASEINATE"),  # casein/gelatin excipient blend
        ("Litesse Polydextrose", "harmful_additives", "ADD_POLYDEXTROSE"),      # Litesse = branded polydextrose
        ("Litesse Polydextrose Fiber", "harmful_additives", "ADD_POLYDEXTROSE"),
        ("Polyphenolic Flavones", "other_ingredients", "NHA_BERGAMOT_POLYPHENOLIC_FLAVONES_MARKER"),
        ("Glycoside Conjugates", "other_ingredients", "NHA_WITHANOLIDE_GLYCOSIDE_CONJUGATES_MARKER"),
        ("40% MCTs", "other_ingredients", "NHA_MCT_PERCENT_COMPOSITION_DESCRIPTOR"),
        ("Bioactive Ribetril-A", "other_ingredients", "PII_BRAND_COMPLEX_DESCRIPTOR"),
        ("Brain Shield Gastrodin", "other_ingredients", "OI_GASTRODIN"),
        ("Brain Shield", "other_ingredients", "OI_GASTRODIN"),
        ("Alkylglycerols", "other_ingredients", "OI_ALKYLGLYCEROLS"),
        ("MOS Yeast Fraction", "other_ingredients", "OI_MOS_YEAST_FRACTION"),
        ("Acetyl L-Carnitine Arginate Di-HCl", "other_ingredients", "OI_ACETYL_L_CARNITINE_ARGINATE"),
        ("L-Tauro Acetyl-L-Carnitine Taurinate Hydrochloride", "other_ingredients", "OI_ACETYL_L_CARNITINE_TAURINATE"),
    ],
)
def test_source_descriptor_recognized(enricher, label, source, entry_id):
    r = enricher._is_recognized_non_scorable(label, label)
    assert r is not None, f"{label!r} should be recognized (non-scorable); got None"
    assert r.get("recognition_source") == source and r.get("matched_entry_id") == entry_id, (
        f"{label!r} should recognize as {source}/{entry_id}; got {r}"
    )


@pytest.mark.parametrize(
    "label",
    [
        "ArginoCarn Acetyl-L-Carnitine Arginate Dihydrochloride",
        "ArginoCarn Acetyl L-Carnitine Arginate Di-HCl",
        "Acetyl L-Carnitine Arginate Dihydrochloride",
    ],
)
def test_unverified_alcar_salts_do_not_inherit_alcar_form_score(enricher, label):
    iqm = enricher.databases["ingredient_quality_map"]
    match = enricher._match_quality_map(label, label, iqm)
    assert match is None or match.get("canonical_id") != "l_carnitine"
    recognized = enricher._is_recognized_non_scorable(label, label)
    assert recognized is not None
    assert recognized.get("matched_entry_id") == "OI_ACETYL_L_CARNITINE_ARGINATE"


def test_declared_alcar_hcl_still_uses_reviewed_alcar_form(enricher):
    iqm = enricher.databases["ingredient_quality_map"]
    match = enricher._match_quality_map("Acetyl L-Carnitine HCl", "Acetyl L-Carnitine HCl", iqm)
    assert match is not None and match.get("canonical_id") == "l_carnitine"
