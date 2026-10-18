"""Sports Dose retains reviewed regimens without inventing general dose curves.

Alpha-GPC, ATP, betaine, taurine and BCAA assessments are completed neutral;
caffeine uses the approved contribution policy. Lost amounts remain incomplete,
while genuine label hiding takes the shared neutral independently of opacity.
"""

from __future__ import annotations

import os
import pytest
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scoring_v4.modules.sports_dose import score_dose


def _row(canonical_id: str, quantity, unit: str, *, name: str | None = None) -> dict:
    return {
        "name": name or canonical_id.replace("_", " ").title(),
        "standard_name": name or canonical_id.replace("_", " ").title(),
        "canonical_id": canonical_id,
        "quantity": quantity,
        "unit": unit,
        "mapped": True,
        "mapped_identity": True,
        "scoreable_identity": True,
        "score_eligible_by_cleaner": True,
        "role_classification": "active_scorable",
        "cleaner_row_role": "active_scorable",
        "dose_class": "therapeutic_mass",
        "source_section": "activeIngredients",
        "raw_source_path": f"activeIngredients[{canonical_id}]",
    }


def _product(*rows: dict, name: str = "Pre-Workout Elite", primary_type: str = "pre_workout") -> dict:
    return {
        "servingSizes": [{"quantity": 1, "unit": "scoop", "minDailyServings": 1, "maxDailyServings": 1}],
        "fullName": name,
        "product_name": name,
        "primary_type": primary_type,
        "supplement_taxonomy": {"primary_type": primary_type},
        "ingredient_quality_data": {"ingredients_scorable": list(rows)},
    }


def _primary(product) -> tuple:
    res = score_dose(product)
    return res["components"]["sports_primary_active_dose"], res["metadata"]["dose_basis"]


# --- alpha-GPC (moderate) ---------------------------------------------------

def test_alpha_gpc_600mg_completed_neutral() -> None:
    product = _product(_row("alpha_gpc", 600, "mg"))
    assert _primary(product) == (11.4, "alpha_gpc_completed_no_general_benchmark")
    payload = score_dose(product)
    # V4.1 Step 4: no single-active completion bonus; the primary is the assessment.
    assert "sports_focused_single_completion" not in payload["components"]
    assert payload["score"] == 11.4


def test_alpha_gpc_300mg_completed_neutral() -> None:
    assert _primary(_product(_row("alpha_gpc", 300, "mg"))) == (11.4, "alpha_gpc_completed_no_general_benchmark")


# --- ATP: evidence certainty never caps Dose (Dose V4.1 section 2.2) --------

def test_atp_studied_regimen_is_not_a_general_curve() -> None:
    assert _primary(_product(_row("adenosine_triphosphate", 450, "mg"))) == (11.4, "atp_completed_no_general_benchmark")
    assert _primary(_product(_row("adenosine_triphosphate", 200, "mg"))) == (11.4, "atp_completed_no_general_benchmark")


# --- caffeine (strong) ------------------------------------------------------

def test_caffeine_200mg_full_credit() -> None:
    assert _primary(_product(_row("caffeine", 200, "mg"))) == (20.0, "caffeine_contribution_policy")


# --- betaine: certainty is Evidence's (Dose V4.1 section 2.2) ---------------

def test_betaine_2500mg_completed_neutral() -> None:
    assert _primary(_product(_row("betaine", 2500, "mg"))) == (11.4, "betaine_completed_no_general_benchmark")


# --- taurine: flat dose-response plateau at 1 g; certainty is Evidence's ----

def test_taurine_1500mg_completed_neutral() -> None:
    assert _primary(_product(_row("taurine", 1500, "mg"))) == (11.4, "taurine_completed_no_general_benchmark")


# --- BCAA aggregate (recovery aid -> capped) --------------------------------

def test_bcaa_aggregate_7g_completed_neutral() -> None:
    assert _primary(
        _product(_row("branched_chain_amino_acids", 7000, "mg"), primary_type="amino_acid")
    ) == (11.4, "bcaa_completed_no_general_benchmark")


# --- disclosed-dose-only: opaque actives earn nothing -----------------------

def test_undisclosed_alpha_gpc_earns_no_dose_credit() -> None:
    primary, _basis = _primary(_product(_row("alpha_gpc", 0, "NP")))
    assert primary == 0.0


# --- off-list dominant active: generic dose proxy instead of crater ---------

def test_declared_offlist_active_keeps_one_equal_purpose_vote() -> None:
    # The named carnitine and BCAA purposes each retain their completed-neutral
    # assessment; neither a coverage floor nor the strongest purpose overrides it.
    res = score_dose(
        _product(
            _row("l_carnitine", 1, "Gram(s)"),
            _row("branched_chain_amino_acids", 250, "mg"),
            name="Carnitine 1000 + BCAA",
            primary_type="amino_acid",
        )
    )
    assert res["score"] == 11.4
    assert res["metadata"]["dose_aggregation"] == "co_primary_average"
    assert {row["ingredient"] for row in res["metadata"]["dose_contributions"]} == {"l_carnitine", "bcaa"}


def test_a_single_active_title_mass_is_still_an_offlist_primary() -> None:
    # A row-level active whose mass comes from the product title is also typed
    # blend_anchor_mass by the contract, but it is one disclosed active, not a
    # blend total: its declared purpose keeps one equal vote.
    carnitine = dict(
        _row("l_carnitine", 1, "Gram(s)"),
        evidence_type="blend_anchor_mass",
        evidence_scope="row_level",
        reason="single_active_title_embedded_mass",
    )
    res = score_dose(
        _product(
            carnitine,
            _row("branched_chain_amino_acids", 250, "mg"),
            name="Carnitine 1000 + BCAA",
            primary_type="amino_acid",
        )
    )
    assert res["metadata"]["dose_aggregation"] == "co_primary_average"
    assert {row["ingredient"] for row in res["metadata"]["dose_contributions"]} == {"l_carnitine", "bcaa"}


@pytest.mark.parametrize("heading", ["Wheybolic Complex", "Recovery Complex"])
def test_structural_blend_heading_is_not_a_separate_sports_purpose(heading):
    from scoring_v4.scored_artifact import build_scored_artifact

    parent = dict(_row(heading.lower().replace(" ", "_"), 22.4, "g", name=heading),
                  is_parent_total=True)
    product = _product(parent, _row("creatine_monohydrate", 5, "g"),
                       _row("branched_chain_amino_acids", 7, "g"),
                       name=f"{heading} Creatine BCAA")
    artifact = build_scored_artifact(product)
    dose = artifact["_v4_module_breakdown"]["dimensions"]["dose"]
    assert dose["score"] == 15.7  # two actual preparations, not a third vote for their container
    assert {entry["ingredient"] for entry in dose["metadata"]["dose_contributions"]} == {"creatine", "bcaa"}
    assert dose["metadata"].get("assessment_status") != "incomplete"


def test_an_actual_offlist_purpose_with_lost_amount_still_holds_sports_dose():
    from scoring_v4.scored_artifact import build_scored_artifact

    product = _product(_row("l_carnitine", None, "mg"),
                       _row("branched_chain_amino_acids", 7, "g"),
                       name="Carnitine BCAA")
    dose = build_scored_artifact(product)["_v4_module_breakdown"]["dimensions"]["dose"]
    assert dose["score"] is None
    assert dose["metadata"]["reason_code"] == "unresolved_source_quantity"


def test_onlist_underdosed_active_is_not_rescued_by_proxy() -> None:
    # An under-target creatine (1 g, on-list) keeps proportional contribution; the
    # off-list proxy floor must NOT rescue it, because creatine has a sports band.
    res = score_dose(_product(_row("creatine_monohydrate", 1, "Gram(s)"), primary_type="general_supplement"))
    assert res["components"]["sports_primary_active_dose"] == pytest.approx(20 / 3, abs=.0001)
    assert res["metadata"]["dose_basis"] == "creatine_contribution_policy"


# --- real Thorne Pre-Workout Elite shape: best disclosed primary wins -------

def test_thorne_preworkout_alpha_gpc_atp_takes_alpha_gpc_primary() -> None:
    # The two reviewed sports preparations both contribute completed neutral.
    primary, basis = _primary(
        _product(_row("alpha_gpc", 600, "mg"), _row("adenosine_triphosphate", 450, "mg"))
    )
    assert primary == 11.4
    assert basis == "alpha_gpc_completed_no_general_benchmark"


@pytest.mark.parametrize("lent,quantity,expected", [(False,7000,11.4), (True,7000,11.4), (False,None,0)])
def test_bcaa_preparation_assessment_owns_aggregate_not_individual_mass(lent, quantity, expected):
    from scoring_v4.modules.generic_helpers import has_usable_individual_dose
    from scoring_v4.modules.sports_helpers import sports_dosed_rows
    row = dict(_row("branched_chain_amino_acids", quantity, "mg"),
               evidence_type="blend_anchor_mass", evidence_scope="blend_level",
               scoring_input_kind="product_level_evidence")
    if lent:
        row["reason"] = "identity_bearing_blend_header_mass_from_nested_child"
    product = _product(row, primary_type="amino_acid")
    assert not has_usable_individual_dose(row)
    assert not sports_dosed_rows(product)
    assert _primary(product)[0] == expected
    if lent:
        # The 7g blend total is not the child's amount. Positive source-owned
        # hiding takes the shared neutral without inventing individual mass.
        payload = score_dose(product)
        assert payload["metadata"]["dose_basis"] == "hidden_amount_neutral"
        assert payload["metadata"]["dose_contributions"][0].get("amount_per_serving") is None


def test_bcaa_header_does_not_duplicate_individually_disclosed_members():
    row = dict(_row("branched_chain_amino_acids", 7000, "mg"),
               evidence_type="blend_anchor_mass", evidence_scope="blend_level",
               scoring_input_kind="product_level_evidence")
    product = _product(row, _row("l_leucine",3500,"mg"), _row("l_isoleucine",1750,"mg"),
                       _row("l_valine",1750,"mg"), primary_type="amino_acid")
    payload = score_dose(product)
    assert payload["components"]["sports_primary_active_dose"] == 11.4
    assert "sports_focused_single_completion" not in payload["components"]


@pytest.mark.parametrize("pid", ["306183", "307773"])
def test_raw_disclosed_bcaa_preparation_has_completed_neutral(pid):
    import json
    from pathlib import Path
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    from scoring_v4.scored_artifact import build_scored_artifact
    raw = json.loads((Path(__file__).parent / "fixtures" / f"dose_bcaa_{pid}_raw.json").read_text())
    enriched, errors = SupplementEnricherV3().enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))
    assert not errors
    result = build_scored_artifact(enriched)
    dose = result["_v4_module_breakdown"]["dimensions"]["dose"]
    assert result["quality_score_status"] == "scored"
    assert dose["components"]["sports_primary_active_dose"] == 11.4
    assert dose["metadata"]["dose_basis"] == "bcaa_completed_no_general_benchmark"
