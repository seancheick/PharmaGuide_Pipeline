"""Vitamin/prenatal form ownership (quality_score 1.7.0).

IQM ``bio_score`` is the one form-quality owner for multi/prenatal and
B-complex Formulation. A premium-form count, a preferred-form name table and a
bio_score dose multiplier re-rank that same fact, so they must not add points.
The component math and canaries were presented to the owner before
implementation (docs/superpowers/plans/2026-09-15-probiotic-completeness.md,
"Next bounded implementation: vitamin form ownership").

Every case scores a reviewed archetype fixture through the single production
seam, mutating one source fact at a time.
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from audit_v4_archetype_fixtures import load_fixture_suite  # noqa: E402
from scoring_v4.quality_score import _config  # noqa: E402
from scoring_v4.scored_artifact import build_scored_artifact  # noqa: E402

PRENATAL = "prenatal_multi__ideal"
B_COMPLEX = "b_complex__ideal"
PILLARS = ("formulation", "dose", "evidence", "transparency", "verification", "safety_hygiene")


def _fixture(case_id: str) -> dict:
    return copy.deepcopy(load_fixture_suite().by_id(case_id).product)


def _rows(product: dict) -> list[dict]:
    return product["ingredient_quality_data"]["ingredients_scorable"]


def _set_bio(product: dict, value: float) -> dict:
    for row in _rows(product):
        row["bio_score"] = value
    return product


def _score(product: dict) -> dict:
    return build_scored_artifact(copy.deepcopy(product))


def _dimension(artifact: dict, name: str) -> dict:
    return artifact["_v4_module_breakdown"]["dimensions"][name]


def _pillars(artifact: dict) -> dict[str, float]:
    return {name: artifact["quality_pillars_v4"][name]["score"] for name in PILLARS}


def _rename(product: dict, names: dict[str, str]) -> dict:
    """Replace form wording on the name and matched form; identity stays put."""
    for row in _rows(product):
        if row["canonical_id"] in names:
            row["name"] = names[row["canonical_id"]]
            row["standard_name"] = names[row["canonical_id"]]
            row["matched_form"] = names[row["canonical_id"]].lower()
    return product


# --- multi/prenatal Formulation: panel form quality 12 + disclosure 2 --------


def test_prenatal_formulation_canary_at_equal_iqm_12() -> None:
    artifact = _score(_set_bio(_fixture(PRENATAL), 12))
    formulation = _dimension(artifact, "formulation")

    assert artifact["_v4_module"] == "multi_or_prenatal"
    assert formulation["components"] == {
        "panel_form_quality": 11.12,
        "panel_disclosure_structure": 2.0,
    }
    assert formulation["score"] == 13.12
    assert artifact["quality_pillars_v4"]["formulation"]["components"]["reference"] == 14.0
    assert artifact["quality_pillars_v4"]["formulation"]["score"] == 18.7


def test_prenatal_formulation_reaches_full_pillar_at_iqm_15() -> None:
    artifact = _score(_set_bio(_fixture(PRENATAL), 15))

    assert _dimension(artifact, "formulation")["score"] == 14.0
    assert artifact["quality_pillars_v4"]["formulation"]["score"] == 20.0


def test_prenatal_preferred_form_names_add_no_points_at_equal_iqm() -> None:
    preferred = _set_bio(_fixture(PRENATAL), 12)
    standard = _rename(_set_bio(_fixture(PRENATAL), 12), {
        "vitamin_b9_folate": "Folic Acid",
        "vitamin_b12_cobalamin": "Cyanocobalamin",
        "vitamin_d": "Vitamin D2 Ergocalciferol",
        "vitamin_b2_riboflavin": "Riboflavin",
        "vitamin_b6_pyridoxine": "Pyridoxine HCl",
        "iron": "Iron as Ferrous Sulfate",
        "zinc": "Zinc as Zinc Oxide",
        "magnesium": "Magnesium as Magnesium Oxide",
    })

    assert _dimension(_score(standard), "formulation") == _dimension(_score(preferred), "formulation")


def test_prenatal_panel_size_adds_no_points_at_equal_iqm() -> None:
    full = _set_bio(_fixture(PRENATAL), 15)
    smaller = _set_bio(_fixture(PRENATAL), 15)
    iqd = smaller["ingredient_quality_data"]
    # One row versus eighteen: a count-based credit cannot hide here, because
    # a single form earns nothing extra while the full panel would reach the cap.
    iqd["ingredients_scorable"] = iqd["ingredients_scorable"][:1]
    iqd["total_active"] = 1

    full_artifact, smaller_artifact = _score(full), _score(smaller)

    assert smaller_artifact["_v4_module"] == "multi_or_prenatal"
    assert _dimension(smaller_artifact, "formulation")["score"] == _dimension(full_artifact, "formulation")["score"]


def test_prenatal_payload_has_no_duplicate_form_rankings() -> None:
    formulation = _dimension(_score(_fixture(PRENATAL)), "formulation")

    assert set(formulation["components"]) == {"panel_form_quality", "panel_disclosure_structure"}
    assert "premium_form_count" not in formulation["metadata"]
    assert "key_form_details" not in formulation["metadata"]


def test_prenatal_missing_dose_disclosure_still_loses_formulation_credit() -> None:
    product = _set_bio(_fixture(PRENATAL), 12)
    for row in _rows(product)[:8]:
        row.pop("quantity", None)
        row.pop("unit", None)

    formulation = _dimension(_score(product), "formulation")

    assert formulation["components"]["panel_disclosure_structure"] < 2.0


# --- B-complex Formulation: panel 10 + IQM form 8 + focus 3 + disclosure 2 ---


def test_b_complex_formulation_canary_at_equal_iqm_12() -> None:
    artifact = _score(_set_bio(_fixture(B_COMPLEX), 12))
    formulation = _dimension(artifact, "formulation")

    assert artifact["_v4_module"] == "b_complex"
    assert formulation["components"] == {
        "core_b_panel_coverage": 10.0,
        "b_form_quality": 7.5143,
        "b_complex_focus_purity": 3.0,
        "dose_disclosure": 2.0,
    }
    assert formulation["score"] == 22.5143
    assert artifact["quality_pillars_v4"]["formulation"]["components"]["reference"] == 23.0
    assert artifact["quality_pillars_v4"]["formulation"]["score"] == 19.6


def test_b_complex_formulation_reaches_full_pillar_at_iqm_15() -> None:
    artifact = _score(_set_bio(_fixture(B_COMPLEX), 15))

    assert _dimension(artifact, "formulation")["score"] == 23.0
    assert artifact["quality_pillars_v4"]["formulation"]["score"] == 20.0


def test_b_complex_preferred_form_names_add_no_points_at_equal_iqm() -> None:
    preferred = _set_bio(_fixture(B_COMPLEX), 12)
    standard = _rename(_set_bio(_fixture(B_COMPLEX), 12), {
        "vitamin_b2_riboflavin": "Riboflavin",
        "vitamin_b3_niacin": "Niacin",
        "vitamin_b6_pyridoxine": "Pyridoxine HCl",
        "vitamin_b9_folate": "Folic Acid",
        "vitamin_b12_cobalamin": "Cyanocobalamin",
    })

    assert _dimension(_score(standard), "formulation") == _dimension(_score(preferred), "formulation")


def test_b_complex_unrelated_active_still_changes_focus_by_existing_rule() -> None:
    product = _set_bio(_fixture(B_COMPLEX), 12)
    extra = copy.deepcopy(_rows(product)[0])
    extra.update({"canonical_id": "coenzyme_q10", "name": "Coenzyme Q10", "standard_name": "Coenzyme Q10",
                  "matched_form": None, "quantity": 100, "unit": "mg"})
    _rows(product).append(extra)

    formulation = _dimension(_score(product), "formulation")

    assert formulation["components"]["b_complex_focus_purity"] == 2.0
    assert formulation["score"] == 21.5143


def test_b_complex_missing_dose_disclosure_still_loses_credit() -> None:
    product = _set_bio(_fixture(B_COMPLEX), 12)
    for row in _rows(product)[:4]:
        row.pop("quantity", None)
        row.pop("unit", None)

    formulation = _dimension(_score(product), "formulation")

    assert formulation["components"]["dose_disclosure"] < 2.0
    assert formulation["score"] < _dimension(
        _score(_set_bio(_fixture(B_COMPLEX), 12)), "formulation"
    )["score"]


def test_b_complex_payload_has_no_preferred_form_ranking() -> None:
    formulation = _dimension(_score(_fixture(B_COMPLEX)), "formulation")

    assert "preferred_active_forms" not in formulation["components"]
    assert "preferred_form_hits" not in formulation["metadata"]


# --- canonical config owner --------------------------------------------------


def test_config_references_match_retained_component_ceilings() -> None:
    cfg = _config()
    multi = cfg["formulation_variant_magnitudes"]["multi_prenatal"]

    assert cfg["formulation_subscale"]["archetype_reference"]["prenatal_multi"] == 14.0
    assert multi["cap_formulation"] == multi["cap_panel_form_quality"] + multi["cap_panel_disclosure_structure"] == 14.0
    assert not {"cap_premium_form_diversity", "cap_key_form_support", "premium_form_threshold",
                "premium_points_per_additional"} & set(multi)
    assert dict(cfg["category_magnitudes"]["multi_prenatal"]["dimension_caps"])["formulation"] == 14
    assert cfg["formulation_subscale"]["archetype_reference"]["b_complex"] == 23.0
    assert cfg["category_magnitudes"]["b_complex"]["formulation_cap"] == 23.0
    # Removing an ordinal multiplier that never exceeded 1.0 leaves the dose ceiling alone.
    assert cfg["dose_subscale"]["archetype_reference"]["prenatal_multi"] == 23.0


# --- isolated variants: each mutation moves only its own pillar --------------


def _weak_verification(product: dict) -> dict:
    product["verified_cert_programs"] = []
    product["certification_data"] = {}
    product["has_batch_coa"] = False
    return product


def _underdosed(product: dict) -> dict:
    for row in product["rda_ul_data"]["adequacy_results"]:
        row["pct_rda"] = 20.0
        if row.get("pct_ul") is not None:
            row["pct_ul"] = 5.0
    return product


def _unnecessary_complexity(product: dict) -> dict:
    rows = _rows(product)
    for canonical_id, name in (("ashwagandha", "Ashwagandha Root Extract"), ("coenzyme_q10", "Coenzyme Q10")):
        extra = copy.deepcopy(rows[0])
        extra.update({"canonical_id": canonical_id, "name": name, "standard_name": name,
                      "matched_form": None, "quantity": 100, "unit": "mg"})
        rows.append(extra)
    if "total_active" in product["ingredient_quality_data"]:
        product["ingredient_quality_data"]["total_active"] = len(rows)
    return product


def _incomplete_review(product: dict) -> dict:
    for match in product["evidence_data"]["clinical_matches"]:
        match["effect_direction"] = "unresolved"
    return product


def _moved(base: dict, variant: dict) -> dict[str, tuple[float, float]]:
    before, after = _pillars(base), _pillars(variant)
    return {name: (before[name], after[name]) for name in PILLARS if before[name] != after[name]}


@pytest.mark.parametrize("case_id", [PRENATAL, B_COMPLEX])
def test_excellent_variant_is_scored_with_full_verification_and_safety(case_id: str) -> None:
    artifact = _score(_fixture(case_id))

    assert artifact["quality_score_status"] == "scored"
    assert artifact["quality_pillars_v4"]["verification"]["score"] == 15.0
    assert artifact["quality_pillars_v4"]["safety_hygiene"]["score"] == 10.0


@pytest.mark.parametrize("case_id", [PRENATAL, B_COMPLEX])
def test_weak_verification_variant_moves_only_verification(case_id: str) -> None:
    base = _score(_fixture(case_id))
    moved = _moved(base, _score(_weak_verification(_fixture(case_id))))

    assert set(moved) == {"verification"}
    assert moved["verification"][1] < moved["verification"][0]


@pytest.mark.parametrize("case_id", [PRENATAL, B_COMPLEX])
def test_underdosed_variant_lowers_dose_without_touching_form_quality(case_id: str) -> None:
    base = _score(_fixture(case_id))
    variant = _score(_underdosed(_fixture(case_id)))
    moved = _moved(base, variant)

    assert "dose" in moved and moved["dose"][1] < moved["dose"][0]
    # Evidence may legitimately apply its own dose guards; form quality,
    # disclosure, verification and safety hygiene are not dose facts.
    assert not {"formulation", "transparency", "verification", "safety_hygiene"} & set(moved)
    assert _dimension(variant, "formulation") == _dimension(base, "formulation")


@pytest.mark.parametrize("case_id", [PRENATAL, B_COMPLEX])
def test_unnecessary_complexity_variant_never_adds_formulation_points(case_id: str) -> None:
    base = _score(_fixture(case_id))
    variant = _score(_unnecessary_complexity(_fixture(case_id)))
    before, after = _pillars(base), _pillars(variant)

    assert after["formulation"] <= before["formulation"]
    assert after["verification"] == before["verification"]
    if case_id == B_COMPLEX:
        # Only the focused B-complex adapter has a focus rule; the broad panel
        # adapter is count-neutral at equal form quality.
        assert after["formulation"] < before["formulation"]


@pytest.mark.parametrize("case_id", [PRENATAL, B_COMPLEX])
def test_unrelated_clinical_review_state_does_not_erase_nutrient_authority(case_id: str) -> None:
    base = _score(_fixture(case_id))
    variant = _score(_incomplete_review(_fixture(case_id)))

    assert _pillars(variant)["evidence"] == _pillars(base)["evidence"]
