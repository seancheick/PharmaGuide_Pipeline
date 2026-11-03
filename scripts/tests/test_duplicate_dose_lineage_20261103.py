"""One physical amount is one exposure; a repeated printing never lowers a real one.

Every label named here was read. A row is relabelled only with proof from the label
structure; matching names, amounts or label keys alone are never proof. Rows stay in
the source ledger and keep their printed amounts, and exposure counts each physical
amount once.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from build_final_db import _stamp_dose_contract, build_detail_blob
from enhanced_normalizer import EnhancedDSLDNormalizer
from enrich_supplements_v3 import SupplementEnricherV3
from score_supplements_v4 import score_product_v4
from scoring_v4.dose_safety import _declared_daily_caffeine

FIXTURES = Path(__file__).parent / "fixtures"
NOT_AN_EXPOSURE = {"form_component", "ul_scoped_component"}


@pytest.fixture(scope="module")
def enricher():
    return SupplementEnricherV3()


@pytest.fixture(scope="module")
def enriched(enricher):
    cache = {}

    def load(dsld_id):
        if dsld_id not in cache:
            raw = json.loads((FIXTURES / f"dose_lineage_{dsld_id}_raw.json").read_text())
            cache[dsld_id], _ = enricher.enrich_product(
                EnhancedDSLDNormalizer().normalize_product(raw)
            )
        return cache[dsld_id]

    return load


def _rows(product, name=None):
    rows = product["rda_ul_data"]["analyzed_ingredients"]
    return [r for r in rows if name is None or r.get("ingredient") == name]


def _by_path(product):
    return {r["raw_source_path"]: r for r in _rows(product)}


def _exposure(row):
    return (row.get("safety_exposure") or {}).get("per_day")


def _distinct_total(product, names):
    return sum(
        _exposure(r) or 0
        for r in _rows(product)
        if r.get("ingredient") in names and r.get("dose_role") not in NOT_AN_EXPOSURE
    )


# Printed once as the nutrient, printed again inside the blend that supplies it.
@pytest.mark.parametrize(
    "dsld_id,name,top,child,amount",
    [
        ("271087", "Vitamin C", "ingredientRows[0]", "ingredientRows[1].nestedRows[0]", 500.0),
        ("62816", "Chromium", "ingredientRows[1]", None, 100.0),
        ("231826", "Chromium", "ingredientRows[1]", "ingredientRows[3].nestedRows[3].nestedRows[1]", 100.0),
    ],
)
def test_a_blend_restating_the_top_row_is_one_exposure(enriched, dsld_id, name, top, child, amount):
    product = enriched(dsld_id)
    rows = _rows(product, name)
    assert len(rows) == 2
    kept = _by_path(product)[top]
    repeated = next(r for r in rows if r["raw_source_path"] != top)
    if child:
        assert repeated["raw_source_path"] == child
    assert kept["dose_role"] == "declared_total"
    assert repeated["dose_role"] == "form_component"
    assert _distinct_total(product, {name}) == pytest.approx(_exposure(kept))
    assert kept["quantity"] == repeated["quantity"] == amount


# Folate (DFE) printed with its folic acid: the second row is the same dose in other
# units, and it keeps its own upper-limit check.
@pytest.mark.parametrize(
    "dsld_id,folate,folic",
    [("252902", 200.0, 120.0), ("243163", 400.0, 240.0), ("277384", 510.0, 300.0)],
)
def test_folic_acid_printed_beside_its_dfe_total_is_one_exposure(enriched, dsld_id, folate, folic):
    product = enriched(dsld_id)
    total = next(r for r in _rows(product, "Folate") if r["quantity"] == folate)
    component = next(r for r in _rows(product, "Folic Acid") if r["quantity"] == folic)
    assert total["dose_role"] == "declared_total"
    assert component["dose_role"] == "ul_scoped_component"


# "Vitamin K activity from:" prints a total, then what it is made of.
@pytest.mark.parametrize(
    "dsld_id,total,children",
    [("62812", 2200.0, [1000.0, 1000.0, 200.0]), ("59075", 1100.0, [1000.0, 100.0])],
)
def test_children_that_sum_to_their_printed_parent_are_one_exposure(enriched, dsld_id, total, children):
    product = enriched(dsld_id)
    parent = next(r for r in _rows(product, "Vitamin K") if r["quantity"] == total)
    nested = [
        r for r in _rows(product)
        if r["raw_source_path"].startswith(parent["raw_source_path"] + ".nestedRows[")
    ]
    assert sorted(r["quantity"] for r in nested) == sorted(children)
    assert parent["dose_role"] == "declared_total"
    assert {r["dose_role"] for r in nested} == {"form_component"}


# The compound's mass is the same nutrient the label already prints as elemental.
@pytest.mark.parametrize(
    "dsld_id,elemental,compound",
    [("317118", "Magnesium", "Magnesium Hydroxide"), ("253515", "Choline", "Choline L-Bitartrate")],
)
def test_a_compound_mass_reconciled_to_its_elemental_row_is_one_exposure(enriched, dsld_id, elemental, compound):
    product = enriched(dsld_id)
    [kept] = _rows(product, elemental)
    [mass] = _rows(product, compound)
    assert kept["dose_role"] == "declared_total"
    assert mass["dose_role"] == "form_component"


@pytest.mark.parametrize(
    "dsld_id",
    [
        pytest.param("62820", id="magnesium-85-15"),
        pytest.param("231335", id="b6-90-p5p-20"),
        pytest.param("336846", id="thiamin-two-forms-same-amount"),
        pytest.param("31038", id="olive-two-extracts-same-amount"),
        pytest.param("273843", id="k-120-mk7-50"),
        pytest.param("49236", id="k-children-with-no-exported-parent"),
        pytest.param("329778", id="selenium-printed-twice-with-no-proof"),
    ],
)
def test_real_additive_rows_stay_summed(enriched, dsld_id):
    """Each of these labels prints separate physical amounts. Vitamin E mixtures, on
    49236, are bounded by the declared row and have their own test."""
    assert not [
        (r["ingredient"], r["quantity"], r["dose_role"])
        for r in _rows(enriched(dsld_id))
        if r.get("dose_role") == "form_component" and r.get("canonical_id") != "vitamin_e"
    ]


def test_a_mixture_printed_beside_vitamin_e_bounds_it_and_is_not_counted_again(enriched):
    """210808: Vitamin E 45 IU + Gamma-E 360 mg. The mixture's alpha share is not printed,
    so its mass can only raise the declared row's high figure."""
    rows = [r for r in _rows(enriched("210808")) if r.get("canonical_id") == "vitamin_e"]
    by_name = {r["ingredient"]: r for r in rows}
    assert by_name["Gamma-E Mixed Tocopherols"]["dose_role"] == "form_component"
    declared = by_name["Vitamin E"]
    assert declared["dose_role"] == "declared_total"
    exposure = declared["safety_exposure"]
    assert exposure["low_per_day"] == pytest.approx(exposure["per_day"])
    assert exposure["high_per_day"] == pytest.approx(exposure["per_day"] + 360 * declared["servings_per_day_max"])


def test_magnesium_85_and_15_still_total_100(enriched):
    product = enriched("62820")
    assert sorted(r["quantity"] for r in _rows(product, "Magnesium")) == [15.0, 85.0]
    assert _distinct_total(product, {"Magnesium"}) == pytest.approx(100.0)


def test_equal_rows_with_no_structural_link_stay_summed(enriched):
    """336846 prints Vitamin B-1 twice at 10 mg: benfotiamine and thiamin mononitrate."""
    rows = [r for r in _rows(enriched("336846")) if r["quantity"] == 10.0 and "hiamin" in str(r)]
    assert len(rows) == 2
    assert {r["dose_role"] for r in rows} == {"declared_total"}


# Alternate columns are not an exposure question. A reviewed serving basis merges them at
# the existing owner: the adult column is chosen, the other stays as a printed variant.
# The app profiles start at age 14, so a child column can't apply to any user today.
@pytest.mark.parametrize(
    "dsld_id,name,selected,printed",
    [
        ("246435", "Iron", 9.0, 4.5),
        ("246435", "Vitamin D", 10.0, 5.0),
        ("217227", "Vitamin D", 20.0, 10.0),
        ("221132", "Vitamin D", 26.0, 13.0),
        ("221132", "Calcium", 520.0, 260.0),
        ("221165", "Vitamin D", 26.0, 13.0),
        ("221165", "Calcium", 540.0, 270.0),
        ("206322", "Colostrum", 1500.0, 1500.0),
    ],
)
def test_alternate_columns_keep_one_applicable_amount(enriched, dsld_id, name, selected, printed):
    product = enriched(dsld_id)
    rows = _rows(product, name)
    assert [r["quantity"] for r in rows] == [selected]
    blob = build_detail_blob(product, score_product_v4(product))
    [display] = [
        r for r in blob["display_ingredients"]
        if r.get("raw_source_path") == rows[0]["raw_source_path"]
    ]
    printed_text = " ".join(
        str(variant.get("exact_dose_text")) for variant in display.get("serving_variants") or []
    )
    assert f"{printed:g} " in printed_text and f"{selected:g} " in printed_text


@pytest.mark.parametrize("dsld_id", ["271087", "231826", "252902", "62812", "59075", "317118", "253515"])
def test_a_kept_total_never_falls_below_a_relabelled_row(enriched, dsld_id):
    """A printed total and its conversion agree only to label rounding (253515: 240 mg
    choline printed, 246.8 mg from 600 mg of the bitartrate), hence the margin."""
    product = enriched(dsld_id)
    relabelled = [r for r in _rows(product) if r.get("dose_role") in NOT_AN_EXPOSURE]
    assert relabelled, "the fix must relabel a row on this label"
    for row in relabelled:
        [owner] = [
            r for r in _rows(product)
            if r is not row
            and r.get("dose_role") == "declared_total"
            and r.get("source_label_key") == row.get("parent_label_key")
        ]
        # A vitamin E mixture's mass is bounded by the owner's high figure, not its exact one.
        kept = owner["safety_exposure"].get("high_per_day", _exposure(owner) or 0)
        assert kept >= (_exposure(row) or 0) * 0.95


@pytest.mark.parametrize("dsld_id", ["271087", "62812", "317118"])
def test_the_printed_rows_survive_for_explanation(enriched, dsld_id):
    product = enriched(dsld_id)
    blob = build_detail_blob(product, score_product_v4(product))
    ledger = {r.get("raw_source_path") for r in blob["label_source_rows"]}
    assert {r["raw_source_path"] for r in _rows(product)} <= ledger


@pytest.mark.parametrize(
    "dsld_id,path",
    [
        ("271087", "ingredientRows[1].nestedRows[0]"),
        ("231826", "ingredientRows[3].nestedRows[3].nestedRows[1]"),
        ("62812", "ingredientRows[2].nestedRows[0]"),
        ("317118", "ingredientRows[4]"),
    ],
)
def test_the_blob_ingredient_row_carries_the_role_the_app_honors(enriched, dsld_id, path):
    """The export drops a form_component row from analyzed_ingredients, so the row left
    in `ingredients` needs the role. Without it, the app's threshold reader counts the row
    again: real run gave 231826 chromium 300 mcg and 317118 magnesium 1803 mg."""
    product = enriched(dsld_id)
    blob = build_detail_blob(product, score_product_v4(product))
    [row] = [r for r in blob["ingredients"] if r.get("raw_source_path") == path]
    assert row.get("dose_role") == "form_component"
    assert path not in {
        r.get("raw_source_path") for r in blob["rda_ul_data"]["analyzed_ingredients"]
    }


def test_a_duplicate_can_cross_the_vitamin_c_upper_limit(enriched):
    """271087 + 182730 as a stack, adult UL 2000 mg. Printed: 500 + 500 and 1125 mg.

    The second 500 is the same vitamin C (label: "as ascorbic acid from Polyphenol-C
    Blend"; the blend "containing 500 mg vitamin C"), so the real total is 1625 mg.
    The app sums what the export hands it. Before the fix that is 2125 mg, over the limit.
    """
    upper_limit = 2000.0
    total = sum(
        _exposure(row) or 0
        for dsld_id in ("271087", "182730")
        for row in _rows(enriched(dsld_id), "Vitamin C")
        if row.get("dose_role") not in NOT_AN_EXPOSURE
    )
    assert total == pytest.approx(1625.0)
    assert total < upper_limit


def _collect(enricher, rows):
    return enricher._collect_rda_ul_data(
        {"activeIngredients": rows, "inactiveIngredients": []},
        min_servings_per_day=1,
        max_servings_per_day=1,
    )["analyzed_ingredients"]


def test_a_compound_below_its_nutrient_stays_its_own_row(enricher):
    """A source mass can't be smaller than what it supplies, so 50 mg isn't the 100 mg."""
    rows = _collect(enricher, [
        {"name": "Magnesium", "canonical_id": "magnesium", "quantity": 100, "unit": "mg",
         "dailyValue": 24, "raw_source_path": "ingredientRows[0]"},
        {"name": "Magnesium Oxide", "canonical_id": "magnesium", "quantity": 50, "unit": "mg",
         "raw_source_path": "ingredientRows[1]"},
    ])
    assert {r["ingredient"]: r["dose_role"] for r in rows} == {
        "Magnesium": "declared_total", "Magnesium Oxide": "declared_total"}


def test_a_conversion_that_disagrees_with_its_nutrient_stays_its_own_row(enricher):
    """5 g of magnesium hydroxide is 2 g of magnesium, not the 100 mg printed beside it."""
    rows = _collect(enricher, [
        {"name": "Magnesium", "canonical_id": "magnesium", "quantity": 100, "unit": "mg",
         "dailyValue": 24, "raw_source_path": "ingredientRows[0]"},
        {"name": "Magnesium Hydroxide", "canonical_id": "magnesium", "quantity": 5, "unit": "g",
         "raw_source_path": "ingredientRows[1]"},
    ])
    assert {r["ingredient"]: r["dose_role"] for r in rows}["Magnesium Hydroxide"] == "declared_total"


def test_a_compound_under_another_blend_stays_its_own_row(enricher):
    """246189: Choline 20 mg (as bitartrate) and Alpha-GPC 25 mg in a separate complex."""
    rows = _collect(enricher, [
        {"name": "Choline", "canonical_id": "choline", "quantity": 20, "unit": "mg",
         "dailyValue": 4, "raw_source_path": "ingredientRows[13]"},
        {"name": "CognitivePro Complex", "quantity": 100, "unit": "mg",
         "raw_source_path": "ingredientRows[26]"},
        {"name": "Alpha-GPC", "canonical_id": "choline", "quantity": 25, "unit": "mg",
         "raw_source_path": "ingredientRows[26].nestedRows[2]",
         "isNestedIngredient": True, "parentBlend": "CognitivePro Complex"},
    ])
    assert {r["ingredient"]: r["dose_role"] for r in rows}["Alpha-GPC"] == "declared_total"


def test_a_nested_bare_row_cannot_own_the_total_above_it(enricher):
    rows = _collect(enricher, [
        {"name": "Vitamin K", "canonical_id": "vitamin_k1", "quantity": 500, "unit": "mcg",
         "dailyValue": 400, "raw_source_path": "ingredientRows[0]"},
        {"name": "Vitamin K1", "canonical_id": "vitamin_k1", "quantity": 100, "unit": "mcg",
         "raw_source_path": "ingredientRows[0].nestedRows[0]",
         "isNestedIngredient": True, "parentBlend": "Vitamin K"},
    ])
    total = next(r for r in rows if r["ingredient"] == "Vitamin K")
    assert total.get("skip_ul_reason") != "compound_duplicate_row"


def test_folic_acid_on_the_next_row_needs_the_labels_own_conversion(enricher):
    """Equal converted amounts on distant rows prove nothing."""
    rows = _collect(enricher, [
        {"name": "Folate", "canonical_id": "vitamin_b9_folate", "quantity": 400, "unit": "mcg DFE",
         "dailyValue": 100, "raw_source_path": "ingredientRows[0]"},
        {"name": "Biotin", "canonical_id": "vitamin_b7_biotin", "quantity": 30, "unit": "mcg",
         "dailyValue": 100, "raw_source_path": "ingredientRows[1]"},
        {"name": "Folic Acid", "canonical_id": "vitamin_b9_folate", "quantity": 240, "unit": "mcg",
         "raw_source_path": "ingredientRows[2]", "forms": [{"name": "folic acid"}]},
    ])
    assert {r["ingredient"]: r["dose_role"] for r in rows}["Folic Acid"] == "declared_total"


@pytest.mark.parametrize(
    "serving",
    [
        {},
        {"min_servings_per_day": None, "max_servings_per_day": 2},
        {"min_servings_per_day": 0, "max_servings_per_day": 2},
    ],
)
def test_a_row_outside_the_dose_loop_gets_no_guessed_daily_figure(serving):
    row = {"raw_source_path": "ingredientRows[0]", "normalized_amount": 160.0, "normalized_unit": "mg"}
    _stamp_dose_contract([row], [], serving)
    assert not {"dose_role", "per_day_min", "per_day_max", "converted_unit"} & set(row)


def test_a_row_outside_the_dose_loop_takes_its_daily_figure_from_servings():
    """212783: saw palmetto 160 mg, label two a day, no analyzed row."""
    row = {"raw_source_path": "ingredientRows[0]", "normalized_amount": 160.0, "normalized_unit": "mg"}
    _stamp_dose_contract([row], [], {"min_servings_per_day": 1, "max_servings_per_day": 2})
    assert row["dose_role"] == "declared_total"
    assert (row["per_day_min"], row["per_day_max"], row["converted_unit"]) == (160.0, 320.0, "mg")


def test_daily_figures_ship_together_or_not_at_all():
    row = {"raw_source_path": "ingredientRows[0]"}
    _stamp_dose_contract(
        [row],
        [{"raw_source_path": "ingredientRows[0]", "dose_role": "form_component",
          "per_day_max": 5.0, "converted_unit": "mg", "skip_ul_check": True}],
        {"min_servings_per_day": 1, "max_servings_per_day": 1},
    )
    assert row == {"raw_source_path": "ingredientRows[0]", "dose_role": "form_component"}


def _caffeine_decisions(product):
    """{target: {(status, daily mg)}} across every row the caffeine rule fired on."""
    decisions = {}
    for alert in product["interaction_profile"]["ingredient_alerts"]:
        if alert["rule_id"] != "RULE_INGREDIENT_CAFFEINE":
            continue
        for hit in alert["condition_hits"]:
            decision = hit.get("dose_decision") or {}
            status = decision.get("evaluation_status")
            if status and hit["condition_id"] in {"pregnancy", "hypertension", "ttc"}:
                evaluation = decision.get("dose_evaluation") or {}
                decisions.setdefault(hit["condition_id"], set()).add(
                    (status, evaluation.get("converted_amount"))
                )
    return decisions


@pytest.mark.parametrize(
    "dsld_id,daily_mg",
    [
        pytest.param("312701", 202.0, id="three-botanicals-print-202"),
        pytest.param("316791", 200.0, id="anhydrous-plus-coffee-print-200"),
        pytest.param("82369", 195.0, id="green-tea-plus-caffeine-three-a-day"),
        pytest.param("27350", 400.0, id="four-tablets-a-day-print-400"),
        pytest.param("298076", 100.0, id="complex-prints-50-two-a-day"),
        pytest.param("319907", 300.0, id="blend-header-300-over-250-and-50"),
        pytest.param("274620", 300.0, id="anhydrous-plus-coffea-print-300"),
        pytest.param("253281", 600.0, id="single-row-control"),
    ],
)
def test_each_target_is_judged_once_on_the_distinct_caffeine(enriched, dsld_id, daily_mg):
    """Comparators are not asserted at exactly 200: the rule owner may move them."""
    decisions = _caffeine_decisions(enriched(dsld_id))
    assert set(decisions) == {"pregnancy", "hypertension", "ttc"}
    for target, seen in decisions.items():
        assert {amount for _, amount in seen} == {daily_mg}, target


def test_a_label_summing_past_the_line_now_crosses_it(enriched):
    decisions = _caffeine_decisions(enriched("312701"))
    assert decisions["pregnancy"] == {("above_threshold", 202.0)}
    assert decisions["hypertension"] == {("below_threshold", 202.0)}


def test_correcting_the_serving_basis_keeps_the_pregnancy_alert(enriched):
    """27350: per-row 200 and 40 alone would lose it once the multiplier is right."""
    decisions = _caffeine_decisions(enriched("27350"))
    assert decisions["pregnancy"] == {("above_threshold", 400.0)}
    assert decisions["hypertension"] == {("below_threshold", 400.0)}
    assert _declared_daily_caffeine(enriched("27350"))["confirmed_mg_day_max"] == 400.0


def test_a_complex_mass_is_not_caffeine(enriched):
    """298076: PURENERGY 116 mg prints pterostilbene 66 and caffeine 50 under it."""
    caffeine = _declared_daily_caffeine(enriched("298076"))
    assert (caffeine["total_mg_day_min"], caffeine["total_mg_day_max"]) == (50.0, 100.0)
    decisions = _caffeine_decisions(enriched("298076"))
    assert decisions["pregnancy"] == {("below_threshold", 100.0)}


def test_a_compound_mass_with_no_printed_caffeine_cannot_establish_a_crossing(enriched):
    """249741: 180 mg anhydrous is proven; Infinergy 30 mg is compound mass."""
    decisions = _caffeine_decisions(enriched("249741"))
    assert {status for status, _ in decisions["pregnancy"]} == {"form_unknown"}
    assert {status for status, _ in decisions["ttc"]} == {"form_unknown"}
    assert decisions["hypertension"] == {("below_threshold", 180.0)}


@pytest.mark.parametrize("dsld_id", ["27808", "28993"])
def test_a_held_label_keeps_its_alerts_and_leaves_hypertension_unresolved(enriched, dsld_id):
    """Printed total and printed components disagree, and the reviewed entry forbids
    reconciling them. Every reading crosses pregnancy; only some cross hypertension."""
    decisions = _caffeine_decisions(enriched(dsld_id))
    assert decisions["pregnancy"] == {("above_threshold", 300.0)}
    assert decisions["ttc"] == {("above_threshold", 300.0)}
    assert {status for status, _ in decisions["hypertension"]} == {"form_unknown"}
    assert _declared_daily_caffeine(enriched(dsld_id))["unknown_rows"] > 0


def test_guarana_keeps_its_own_rule_and_amount(enriched):
    alerts = [
        alert for alert in enriched("312701")["interaction_profile"]["ingredient_alerts"]
        if alert["rule_id"] == "RULE_IQM_GUARANA"
    ]
    assert alerts
    hypertension = [h for a in alerts for h in a["condition_hits"] if h["condition_id"] == "hypertension"]
    assert {h["dose_decision"]["evaluation_status"] for h in hypertension} == {"amount_unknown"}


def test_the_export_shows_one_caffeine_decision_per_target(enriched):
    product = enriched("312701")
    blob = build_detail_blob(product, score_product_v4(product))
    amounts = [
        (w.get("dose_decision") or {}).get("evaluated_daily_amount")
        for w in blob["warnings"]
        if w.get("ingredient_canonical_id") == "caffeine"
    ]
    # Pregnancy, hypertension and trying to conceive; the rest carry no dose decision.
    assert [amount for amount in amounts if amount is not None] == [202.0, 202.0, 202.0]


def _caffeine_row(**fields):
    return {"canonical_id": "caffeine", "unit": "mg", "unit_normalized": "mg", **fields}


def test_a_row_with_no_amount_is_not_part_of_the_sum_and_stays_unknown(enricher):
    known = _caffeine_row(name="Caffeine", quantity=150.0, raw_source_path="ingredientRows[0]")
    silent = _caffeine_row(name="Guarana Caffeine", quantity=0.0, unit="NP", unit_normalized="NP",
                           raw_source_path="ingredientRows[1]")
    dose = enricher._distinct_caffeine_dose({}, [known, silent])
    assert dose["quantity"] == 150.0 and dose.get("quantity_upper") is None
    assert id(known) in dose["rows"] and id(silent) not in dose["rows"]


def test_an_upper_qualified_amount_only_bounds_the_total(enricher):
    below = _caffeine_row(name="Caffeine", quantity=100.0, quantity_operator="<",
                          raw_source_path="ingredientRows[0]")
    exact = _caffeine_row(name="Caffeine", quantity=150.0, raw_source_path="ingredientRows[1]")
    dose = enricher._distinct_caffeine_dose({}, [below, exact])
    assert (dose["quantity"], dose["quantity_upper"]) == (150.0, 250.0)


def test_a_lower_qualified_amount_leaves_no_upper_figure(enricher):
    over = _caffeine_row(name="Caffeine", quantity=100.0, quantity_operator=">",
                         raw_source_path="ingredientRows[0]")
    dose = enricher._distinct_caffeine_dose({}, [over])
    assert dose["quantity"] == 100.0 and dose["quantity_upper"] == float("inf")


def test_no_caffeine_rows_means_no_total(enricher):
    assert enricher._distinct_caffeine_dose({}, [{"canonical_id": "magnesium", "quantity": 100.0, "unit": "mg"}]) is None


@pytest.mark.parametrize(
    "dsld_id,low,high",
    [
        pytest.param("64845", 80.0, 176.3, id="alpha-minimums-exceed-the-declaration"),
        pytest.param("64848", 60.3, 138.3, id="declaration-exceeds-the-alpha-minimum"),
        pytest.param("62796", 66.196, 127.826, id="one-a-day-two-mixtures"),
        pytest.param("63428", 84.26, 180.106, id="iu-declaration-two-mixtures"),
        pytest.param("49236", 30.52, 73.23, id="one-mixture-minimum-just-over"),
        pytest.param("60404", 30.52, 73.23, id="same-softgel-in-a-packet"),
        pytest.param("307739", 26.0, 776.0, id="complex-prints-no-alpha"),
    ],
)
def test_the_declared_row_carries_the_alpha_range_at_max_servings(enriched, dsld_id, low, high):
    product = enriched(dsld_id)
    [declared] = [r for r in _rows(product, "Vitamin E")]
    exposure = declared["safety_exposure"]
    assert exposure["low_per_day"] == pytest.approx(low)
    assert exposure["high_per_day"] == pytest.approx(high)
    assert exposure["unit"] == "mg"


@pytest.mark.parametrize(
    "dsld_id,per_day",
    [("64845", 60.3), ("62796", 66.196), ("307739", 26.0)],
)
def test_the_exact_declared_figure_stays_for_existing_readers(enriched, dsld_id, per_day):
    [declared] = _rows(enriched(dsld_id), "Vitamin E")
    assert declared["safety_exposure"]["per_day"] == pytest.approx(per_day)


@pytest.mark.parametrize("dsld_id", ["64845", "62796", "63428", "49236", "307739"])
def test_only_the_declared_row_is_read_as_vitamin_e(enriched, dsld_id):
    """Gamma, delta and printed alpha rows stay in the ledger; none is a second exposure."""
    product = enriched(dsld_id)
    blob = build_detail_blob(product, score_product_v4(product))
    readable = [
        row["name"] for row in blob["ingredients"]
        if row.get("canonical_id") == "vitamin_e"
        and row.get("dose_role") not in NOT_AN_EXPOSURE
        and row.get("per_day_max") is not None
    ]
    assert readable == ["Vitamin E"]
    assert [r["ingredient"] for r in blob["rda_ul_data"]["analyzed_ingredients"]
            if r.get("canonical_id") == "vitamin_e"] == ["Vitamin E"]


def test_the_range_reaches_the_export(enriched):
    product = enriched("64845")
    blob = build_detail_blob(product, score_product_v4(product))
    [row] = [r for r in blob["ingredients"] if r.get("name") == "Vitamin E"]
    assert row["safety_exposure"]["low_per_day"] == pytest.approx(80.0)
    [analyzed] = [r for r in blob["rda_ul_data"]["analyzed_ingredients"] if r["ingredient"] == "Vitamin E"]
    assert analyzed["safety_exposure"]["high_per_day"] == pytest.approx(176.3)


def test_an_exact_vitamin_e_row_has_no_range(enricher):
    rows = [{"name": "Vitamin E", "standardName": "Vitamin E", "canonical_id": "vitamin_e",
             "quantity": 100.0, "unit": "mg", "forms": [{"name": "d-alpha tocopherol"}],
             "raw_source_path": "ingredientRows[0]", "dailyValue": 667.0}]
    [row] = _collect(enricher, rows)
    assert "low_per_day" not in row["safety_exposure"]


def test_a_printed_range_does_not_survive_a_changed_row():
    """A manufacturer revision must not inherit an old printed range."""
    normalizer = EnhancedDSLDNormalizer()
    normalizer._label_corrections_by_dsld_id = {
        "1": {
            "raw_ingredient_text": "Alpha-Tocopherol",
            "printed_alpha_tocopherol_ranges": {"ingredientRows[0]": {"low": 27, "high": 39}},
        }
    }
    same = [{"name": "Alpha-Tocopherol", "raw_source_path": "ingredientRows[0]",
             "quantity": [{"quantity": 39, "unit": "mg"}]}]
    changed = [{"name": "Alpha-Tocopherol", "raw_source_path": "ingredientRows[0]",
                "quantity": [{"quantity": 41, "unit": "mg"}]}]
    assert normalizer._apply_label_corrections(same, "1")[0]["printed_alpha_range_mg"] == {"low": 27, "high": 39}
    assert "printed_alpha_range_mg" not in normalizer._apply_label_corrections(changed, "1")[0]


def _vitamin_e_decision(product):
    alerts = [a for a in product["interaction_profile"]["ingredient_alerts"]
              if a["rule_id"] == "RULE_IQM_VITAMIN_E_PREGNANCY_EXCESS"]
    return {
        (hit["dose_decision"].get("evaluation_status"),
         (hit["dose_decision"].get("dose_evaluation") or {}).get("converted_amount"))
        for alert in alerts for hit in alert["condition_hits"]
        if hit["condition_id"] == "pregnancy" and hit.get("dose_decision")
    }


@pytest.mark.parametrize("dsld_id,low", [("64845", 80.0), ("62796", 66.196), ("307739", 26.0)])
def test_the_pregnancy_rule_reads_the_same_range_and_rules_out_excess(enriched, dsld_id, low):
    [(status, amount)] = _vitamin_e_decision(enriched(dsld_id))
    assert status == "below_threshold"
    assert amount == pytest.approx(low)


def test_a_range_straddling_the_limit_is_not_within_it(enricher):
    decision = enricher._evaluate_dose_thresholds_for_target(
        thresholds=[{"scope": "condition", "target_id": "pregnancy", "basis": "per_day",
                     "comparator": ">", "value": 1000, "unit": "mg",
                     "severity_if_met": "avoid", "severity_if_not_met": "monitor"}],
        target_type="condition",
        target_id="pregnancy",
        ingredient={"name": "Vitamin E", "standard_name": "Vitamin E", "quantity": 400.0,
                    "quantity_upper": 1200.0, "unit": "mg"},
        servings_per_day_max=1.0,
        base_severity="monitor",
    )[1]
    assert decision["evaluation_status"] == "form_unknown"


def test_a_low_above_the_limit_establishes_the_excess(enricher):
    decision = enricher._evaluate_dose_thresholds_for_target(
        thresholds=[{"scope": "condition", "target_id": "pregnancy", "basis": "per_day",
                     "comparator": ">", "value": 1000, "unit": "mg",
                     "severity_if_met": "avoid", "severity_if_not_met": "monitor"}],
        target_type="condition",
        target_id="pregnancy",
        ingredient={"name": "Vitamin E", "standard_name": "Vitamin E", "quantity": 1100.0,
                    "quantity_upper": 1500.0, "unit": "mg"},
        servings_per_day_max=1.0,
        base_severity="monitor",
    )[1]
    assert decision["evaluation_status"] == "above_threshold"
