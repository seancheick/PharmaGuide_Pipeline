"""Gold proprietary-blend / missing-data benchmark (roadmap 1.10): raw labels through Clean and Enrich."""

import copy
import json
from pathlib import Path

import pytest

from enhanced_normalizer import EnhancedDSLDNormalizer
from enrich_supplements_v3 import SupplementEnricherV3

DOC = json.loads((Path(__file__).resolve().parent / "fixtures" / "blend_disclosure_gold_cases.json").read_text())
CASES = DOC["cases"]
MERGE_DUPLICATES = {"74832", "243975", "59514"}


@pytest.fixture(scope="module")
def enriched_by_id():
    normalizer, enricher = EnhancedDSLDNormalizer(), SupplementEnricherV3()
    out = {}
    for case in CASES:
        cleaned = normalizer.normalize_product(copy.deepcopy(case["raw_label"]))
        out[case["dsld_id"]], _ = enricher.enrich_product(cleaned)
    return out


def _records(enriched, case):
    return [b for b in enriched["proprietary_blends"] if case["blend"].lower() in (b.get("name") or "").lower()]


def test_fixture_is_well_formed():
    assert DOC["_metadata"]["case_count"] == len(CASES)
    assert len({c["id"] for c in CASES}) == len(CASES)


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_blend_reaches_enrich_with_its_tier(enriched_by_id, case):
    assert case["expect"] in {b["disclosure_level"] for b in _records(enriched_by_id[case["dsld_id"]], case)}


def _invariant_param(case):
    marks = [pytest.mark.xfail(strict=True, reason=DOC["_metadata"]["known_defect"])] \
        if case["dsld_id"] in MERGE_DUPLICATES else []
    return pytest.param(case, id=case["id"], marks=marks)


@pytest.mark.parametrize("case", [_invariant_param(c) for c in CASES])
def test_no_record_claims_full_without_quantified_components(enriched_by_id, case):
    for blend in _records(enriched_by_id[case["dsld_id"]], case):
        if blend["disclosure_level"] == "full":
            children = blend.get("child_ingredients") or []
            assert children and all(c.get("amount") for c in children), blend


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_unquantified_member_is_never_a_dose(enriched_by_id, case):
    enriched = enriched_by_id[case["dsld_id"]]
    hidden = {c["name"] for b in _records(enriched, case) for c in b.get("child_ingredients") or [] if not c.get("amount")}
    for row in enriched["ingredient_quality_data"]["ingredients"]:
        if row.get("name") in hidden:
            assert row.get("has_dose") is False, row["name"]
