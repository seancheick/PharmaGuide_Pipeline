"""
Wave 6.Z A2 — curated branded-blend header anchors.

This is deliberately narrower than "score any branded blend."  A branded
blend header becomes anchor-eligible only when an exact alias is present in
scripts/data/branded_blend_anchor_overrides.json with live-verified PubMed
evidence.  Generic proprietary/herbal/superfood blends remain fail-closed.
"""

from __future__ import annotations

from pathlib import Path
import json
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from score_supplements import SupplementScorer  # noqa: E402
from test_not_scored_truthful_diagnostics import (  # noqa: E402
    _make_blend_header_anchor_eligible,
    _rejected_row,
)


ANCHOR_DATA = Path(__file__).parent.parent / "data" / "branded_blend_anchor_overrides.json"
OTHER_INGREDIENTS_DATA = Path(__file__).parent.parent / "data" / "other_ingredients.json"


@pytest.fixture
def scorer():
    return SupplementScorer()


def _make_branded_blend_header(
    *,
    header_name: str,
    header_std_name: str,
    header_canonical_id: str | None,
    header_canonical_source_db: str,
    header_quantity: float = 100.0,
    header_unit: str = "mg",
):
    product = _make_blend_header_anchor_eligible(
        header_name=header_name,
        header_std_name=header_std_name,
        header_canonical_id=header_canonical_id or "",
        header_canonical_source_db=header_canonical_source_db,
        header_quantity=header_quantity,
        header_unit=header_unit,
    )
    product["formulation_data"]["standardized_botanicals"] = []
    return product


def _add_display_only_child(product, *, name: str = "Display Child"):
    row = _rejected_row(
        name=name,
        standard_name=name,
        canonical_id="display_child",
        canonical_source_db="ingredient_quality_map",
        quantity=0.0,
        unit="NP",
        recognized_non_scorable=False,
        skip_reason="nested_under_non_therapeutic_parent",
        score_exclusion_reason="nested_display_only",
        is_blend_header=False,
        blend_total_weight_only=False,
        is_proprietary_blend=True,
    )
    product["ingredient_quality_data"]["ingredients_skipped"].append(row)
    product["ingredient_quality_data"]["total_active"] += 1
    product["ingredient_quality_data"]["skipped_non_scorable_count"] += 1


def _add_proprietary_blend_child_dose(product):
    product["proprietary_blends"] = [
        {
            "name": "Urox Proprietary Blend",
            "disclosure_level": "full",
            "total_weight": 840.0,
            "unit": "mg",
            "child_ingredients": [
                {"name": "Horsetail extract", "amount": 200.0, "unit": "mg"},
            ],
        }
    ]


def test_curated_anchor_data_has_verified_evidence_inventory():
    data = json.loads(ANCHOR_DATA.read_text())
    anchors = {entry["id"]: entry for entry in data["anchors"]}

    assert set(anchors) == {
        "urox",
        "xanthigen",
        "metabolaid",
        "univestin",
        "br_dim_indolplex",
    }
    assert anchors["urox"]["evidence_pmids"] == ["29385990"]
    assert anchors["xanthigen"]["evidence_pmids"] == ["19840063"]
    assert anchors["metabolaid"]["evidence_pmids"] == ["33810049"]
    assert anchors["univestin"]["evidence_pmids"] == ["24611484"]
    assert anchors["br_dim_indolplex"]["evidence_pmids"] == ["22075942", "28560655"]


def test_univestin_note_uses_verified_joint_support_reference():
    data = json.loads(OTHER_INGREDIENTS_DATA.read_text())
    univestin = next(e for e in data["other_ingredients"] if e["id"] == "NHA_UNIVESTIN")
    notes = univestin["notes"]

    assert "PMID 24611484" in notes
    assert "10.1089/jmf.2013.0010" in notes
    assert "10.1186/1472-6882-12-8" not in notes


@pytest.mark.parametrize(
    ("header_name", "std_name", "canonical_id", "source_db"),
    [
        ("Urox Proprietary Blend", "Urox Proprietary Blend", None, "unmapped"),
        ("Xanthigen Proprietary Blend", "Xanthigen Proprietary Blend", None, "unmapped"),
        ("Metabolaid", "Metabolaid (Lemon Verbena-Hibiscus Blend)", "BLEND_METABOLAID", "proprietary_blends"),
        ("Acacia catechu wood & bark extract and Chinese Skullcap root extract", "Univestin", "NHA_UNIVESTIN", "other_ingredients"),
        ("Indolplex Diindolylmethane (BR-DIM) Complex", "Indolplex Diindolylmethane (BR-DIM) Complex", None, "unmapped"),
    ],
)
def test_verified_branded_blend_headers_promote_to_anchor(
    scorer,
    header_name,
    std_name,
    canonical_id,
    source_db,
):
    product = _make_branded_blend_header(
        header_name=header_name,
        header_std_name=std_name,
        header_canonical_id=canonical_id,
        header_canonical_source_db=source_db,
    )
    _add_display_only_child(product)

    result = scorer.score_product(product)

    assert result["verdict"] in {"POOR", "CAUTION"}
    assert result["score_basis"] == "blend_header_anchor"
    assert "SCORED_VIA_BLEND_HEADER_ANCHOR" in result["flags"]
    assert result["not_scorable_reason"] is None
    assert "scored_via_blend_header_anchor_path" in result["strict_scoring_contract"]["findings"]


@pytest.mark.parametrize(
    ("header_name", "std_name", "canonical_id", "source_db"),
    [
        ("Proprietary Blend", "General Proprietary Blends", "BLEND_GENERAL", "proprietary_blends"),
        ("Seditol", "Seditol", "PII_SEDITOL_BRANDED_BLEND", "other_ingredients"),
        ("BioCore Recovery(TM) Enzyme Blend", "BioCore Recovery(TM) Enzyme Blend", None, "unmapped"),
    ],
)
def test_unverified_or_generic_branded_shapes_stay_not_scored(
    scorer,
    header_name,
    std_name,
    canonical_id,
    source_db,
):
    product = _make_branded_blend_header(
        header_name=header_name,
        header_std_name=std_name,
        header_canonical_id=canonical_id,
        header_canonical_source_db=source_db,
    )

    result = scorer.score_product(product)

    assert result["verdict"] == "NOT_SCORED"
    assert "SCORED_VIA_BLEND_HEADER_ANCHOR" not in result["flags"]


def test_curated_anchor_stands_down_when_blend_children_have_usable_doses(scorer):
    product = _make_branded_blend_header(
        header_name="Urox Proprietary Blend",
        header_std_name="Urox Proprietary Blend",
        header_canonical_id=None,
        header_canonical_source_db="unmapped",
        header_quantity=840.0,
        header_unit="mg",
    )
    _add_proprietary_blend_child_dose(product)

    result = scorer.score_product(product)

    assert result["verdict"] == "NOT_SCORED"
    assert "SCORED_VIA_BLEND_HEADER_ANCHOR" not in result["flags"]
