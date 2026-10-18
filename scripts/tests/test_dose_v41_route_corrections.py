"""Confirmed route audit defects: group votes, hidden amounts and daily betaine."""
import pytest

from test_v4_sports_dose_p171 import _product, _row
from test_v4_botanical_profile import _botanical_product, _botanical_ingredient
from scoring_v4.modules.sports_dose import score_dose
from scoring_v4.modules.sports_helpers import EAA_CANONICALS
from scoring_v4.scored_artifact import build_scored_artifact


def _dose(product):
    return build_scored_artifact(product)["quality_pillars_v4"]["dose"]["score"]


def test_bcaa_aggregate_is_one_coprimary_vote():
    product = _product(_row("creatine_monohydrate", 5, "Gram(s)"),
                       _row("branched_chain_amino_acids", 1, "Gram(s)"),
                       name="Creatine + BCAA", primary_type="pre_workout")
    assert _dose(product) == 11.8  # (20 + aggregate 4/22*20) / 2
    contributions = score_dose(product)["metadata"]["dose_contributions"]
    assert [c["ingredient"] for c in contributions] == ["creatine", "bcaa"]


def test_split_bcaa_gets_one_group_vote_not_three_amino_acid_votes():
    product = _product(_row("creatine_monohydrate", 5, "Gram(s)"),
                       _row("l_leucine", 1, "Gram(s)"),
                       _row("l_isoleucine", .5, "Gram(s)"),
                       _row("l_valine", .5, "Gram(s)"),
                       name="Creatine + BCAA", primary_type="pre_workout")
    assert _dose(product) == 14.5  # (20 + group (8 + composition 2)/22*20) / 2
    contributions = score_dose(product)["metadata"]["dose_contributions"]
    assert [c["ingredient"] for c in contributions] == ["creatine", "bcaa"]
    assert contributions[1]["amount_per_serving"] == 2.0


def test_complete_eaa_aggregate_is_one_vote_and_does_not_add_a_bcaa_vote():
    eaa = {**_row("essential_amino_acids", 5, "Gram(s)"),
           "scoring_input_kind": "product_level_evidence", "evidence_type": "sports_primary_dose",
           "verified_child_canonicals": sorted(EAA_CANONICALS)}
    product = _product(_row("creatine_monohydrate", 5, "Gram(s)"), eaa,
                       name="Creatine + Essential Amino Acids", primary_type="pre_workout")
    assert _dose(product) == 17.3  # (20 + EAA group (14 + composition 2)/22*20) / 2
    contributions = score_dose(product)["metadata"]["dose_contributions"]
    assert [c["ingredient"] for c in contributions] == ["creatine", "eaa"]
    assert contributions[1]["amount_per_serving"] == 5.0


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("identity", ["bcaa", "eaa"])
def test_group_leading_average_equals_its_standalone_assessment_in_either_order(identity, reverse):
    creatine = _row("creatine_monohydrate", 1, "Gram(s)")
    if identity == "bcaa":
        amino_rows = [_row("l_leucine", 2.5, "Gram(s)"),
                      _row("l_isoleucine", 1.25, "Gram(s)"), _row("l_valine", 1.25, "Gram(s)")]
        title = "Creatine + BCAA"
    else:
        amino_rows = [{**_row("essential_amino_acids", 8, "Gram(s)"),
                      "scoring_input_kind": "product_level_evidence", "evidence_type": "sports_primary_dose",
                      "verified_child_canonicals": sorted(EAA_CANONICALS)}]
        title = "Creatine + Essential Amino Acids"
    rows = [creatine, *amino_rows]
    if reverse:
        rows.reverse()
    group_score = _dose(_product(*amino_rows, name=title, primary_type="pre_workout"))
    creatine_score = _dose(_product(creatine, name="Creatine", primary_type="pre_workout"))
    product = _product(*rows, name=title, primary_type="pre_workout")
    assert group_score == 20 and creatine_score == 8
    assert _dose(product) == (group_score + creatine_score) / 2 == 14
    assert score_dose(product)["components"]["sports_ratio_or_completeness"] == 0
    standalone = score_dose(_product(*amino_rows, name=title, primary_type="pre_workout"))
    # The preparation's contribution includes its composition assessment;
    # a receipt must not lose those points or add them globally after averaging.
    assert standalone["metadata"]["dose_contributions"][0]["credit_raw"] == standalone["score"] == 22


@pytest.mark.parametrize("hidden,expected", [(True, 15.7), (False, 10.0)])
def test_only_positive_label_hiding_gets_a_neutral_coprimary_vote(hidden, expected):
    missing = {**_row("beta_alanine", 1, "Gram(s)"), "quantity": None, "unit": ""}
    if hidden:
        missing["isNestedIngredient"] = True
    product = _product(_row("creatine_monohydrate", 5, "Gram(s)"), missing,
                       name="Creatine + Beta-Alanine", primary_type="pre_workout")
    assert _dose(product) == pytest.approx(expected)
    contribution = score_dose(product)["metadata"]["dose_contributions"][1]
    assert (contribution["assessment"] == "hidden_amount_neutral") is hidden
    assert contribution.get("amount_per_serving") is None


def test_unresolved_disclosed_sports_amount_is_not_hidden_neutral():
    unread = {**_row("beta_alanine", 4, "Gram(s)"), "quantity_operator": "ambiguous",
              "isNestedIngredient": True}
    product = _product(_row("creatine_monohydrate", 5, "Gram(s)"), unread,
                       name="Creatine + Beta-Alanine", primary_type="pre_workout")
    assert build_scored_artifact(product)["quality_score_status"] == "not_scored"
    assert all(c["assessment"] != "hidden_amount_neutral"
               for c in score_dose(product)["metadata"]["dose_contributions"])


@pytest.mark.parametrize("minimum,maximum,expected", [(2, 2, 20), (1, 2, 10), (2, 4, 20)])
def test_betaine_daily_target_uses_the_minimum_directed_exposure(minimum, maximum, expected):
    product = _product(_row("betaine", 1.25, "Gram(s)"), name="Betaine", primary_type="pre_workout")
    product["servingSizes"][0].update(minDailyServings=minimum, maxDailyServings=maximum)
    assert _dose(product) == expected
    contribution = score_dose(product)["metadata"]["dose_contributions"][0]
    assert contribution["amount_per_serving"] == 1.25
    assert contribution["amount_at_minimum"] == 1.25 * minimum
    assert contribution["amount_at_maximum"] == 1.25 * maximum
    assert contribution["amount_unit"] == "g"
    assert contribution["reference_value"] == 2.5
    assert contribution["pct_of_reference"] == 50 * minimum


def test_per_use_atp_target_is_not_multiplied_by_daily_directions():
    # PMID 34957398 used a single acute dose; its 400mg comparison is per use.
    product = _product(_row("atp", 200, "mg"), name="ATP", primary_type="pre_workout")
    product["servingSizes"][0].update(minDailyServings=2, maxDailyServings=2)
    assert _dose(product) == 10.0


@pytest.mark.parametrize("quantity,hidden,expected", [(None, False, 0), (None, True, 11.4), (300, False, 11.4)])
def test_no_botanical_benchmark_does_not_hide_missing_capture(quantity, hidden, expected):
    row = _botanical_ingredient(name="Elderflower", standard_name="Elderflower",
                               canonical_id="elderflower", quantity=quantity, unit="mg")
    if hidden:
        row["isNestedIngredient"] = True
    assert _dose(_botanical_product(row)) == expected


def test_sports_contributions_record_each_serving_and_directed_daily_amount():
    product = _product(_row("creatine_monohydrate", 5, "Gram(s)"),
                       _row("beta_alanine", 1, "Gram(s)"),
                       name="Creatine + Beta-Alanine", primary_type="pre_workout")
    product["servingSizes"][0].update(minDailyServings=1, maxDailyServings=2)
    contributions = score_dose(product)["metadata"]["dose_contributions"]
    assert [(c["ingredient"], c["amount_per_serving"], c["amount_at_minimum"],
             c["amount_at_maximum"], c["amount_unit"]) for c in contributions] == [
                 ("creatine", 5, 5, 10, "g"), ("beta_alanine", 1, 1, 2, "g")]


def test_offlist_sports_proxy_receipt_keeps_the_selected_assessment():
    product = _product(_row("l_carnitine", 1, "Gram(s)"),
                       _row("branched_chain_amino_acids", 250, "mg"),
                       name="Carnitine 1000 + BCAA", primary_type="pre_workout")
    artifact = build_scored_artifact(product)
    dose = artifact["quality_pillars_v4"]["dose"]
    receipt = dose["explanation"]["dose_receipt"]
    assert dose["score"] == 11.4
    assert receipt["reconciles"] is True
    assert receipt["aggregation"] == "declared_purpose_equal_weight"
    assert {c["ingredient"] for c in receipt["contributions"]} == {"l_carnitine", "branched_chain_amino_acids"}
    assert all(c["assessment"] == "no_benchmark_neutral" for c in receipt["contributions"])
