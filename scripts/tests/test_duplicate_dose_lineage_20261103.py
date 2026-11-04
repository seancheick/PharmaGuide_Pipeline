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

from build_final_db import _stamp_dose_contract, build_detail_blob, compact_dose_decision
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
    [
        ("62812", 2200.0, [1000.0, 1000.0, 200.0]),
        ("59075", 1100.0, [1000.0, 100.0]),
        ("62815", 2200.0, [1000.0, 1000.0, 200.0]),
    ],
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
    assert f"{printed:,g} " in printed_text and f"{selected:,g} " in printed_text


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


@pytest.mark.parametrize("dsld_id", ["27808", "28993"])
def test_an_unresolved_caffeine_check_reaches_the_user(enriched, dsld_id):
    hits = [
        hit
        for alert in enriched(dsld_id)["interaction_profile"]["ingredient_alerts"]
        if alert["subject_ref"]["canonical_id"] == "caffeine"
        for hit in alert["condition_hits"]
        if hit["condition_id"] == "hypertension"
    ]
    assert hits
    assert {hit["dose_decision"]["evaluation_status"] for hit in hits} == {"form_unknown"}
    assert {hit["dose_decision"]["consumer_disposition"] for hit in hits} == {"review"}


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


@pytest.mark.parametrize("name,unit,amount", [
    ("Alpha-Tocopherol", "mg", 41),
    ("Alpha-Tocopherol", "mcg", 39),
    ("Gamma-Tocopherol", "mg", 39),
])
def test_a_printed_range_does_not_survive_a_changed_row(name, unit, amount):
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
    changed = [{"name": name, "raw_source_path": "ingredientRows[0]",
                "quantity": [{"quantity": amount, "unit": unit}]}]
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


# Transcription errors the label settles. Each label was read.
def test_a_calcium_row_mistyped_as_vitamin_c_stops_adding_to_vitamin_c(enriched):
    """263869 prints Calcium 55 mg (as Ester-C Calcium Ascorbate); DSLD calls it Vitamin C."""
    product = enriched("263869")
    assert [r["quantity"] for r in _rows(product) if r.get("canonical_id") == "vitamin_c"] == [500.0]
    [calcium] = [r for r in _rows(product) if r.get("canonical_id") == "calcium"]
    assert calcium["quantity"] == 55.0
    assert _exposure(calcium) == pytest.approx(110.0)


def test_thiamine_printed_in_milligrams_is_not_read_in_micrograms(enriched):
    """328514 prints 125 mg, 10417% of the 1.2 mg Daily Value."""
    [thiamine] = _rows(enriched("328514"), "Thiamine")
    assert (thiamine["quantity"], thiamine["unit"]) == (125.0, "mg")


@pytest.mark.parametrize(
    "dsld_id,name,per_day",
    [
        ("311734", "Caffeine, Natural", 100.0),
        ("2704", "Pantothenic Acid", 15.0),
        ("c4sport", "Caffeine Anhydrous", 200.0),
    ],
)
def test_a_serving_mislabelled_in_dsld_does_not_scale_the_daily_amount(enriched, dsld_id, name, per_day):
    """311734: 1 scoop (21 g) daily, panel rows filed against 22 g. 2704: 2 tablespoons
    (30 mL) daily, filed as 2 capsules per packet beside a second 30 mL serving."""
    [row] = _rows(enriched(dsld_id), name)
    assert row["servings_per_day_max"] == 1.0
    assert _exposure(row) == pytest.approx(per_day)


def test_one_amount_printed_for_two_forms_counts_once(enriched):
    """62825 prints "4 mg meso-zeaxanthin & trans-zeaxanthin"; DSLD gives each 4 mg."""
    rows = [r for r in _rows(enriched("62825")) if r.get("canonical_id") == "zeaxanthin"]
    assert [r["ingredient"] for r in rows] == ["Meso-Zeaxanthin"]
    assert _exposure(rows[0]) == pytest.approx(4.0)
    product = enriched("62825")
    exported = {
        r["name"]: r for r in build_detail_blob(product, score_product_v4(product))["ingredients"]
        if r.get("canonical_id") == "zeaxanthin"
    }
    assert exported["Meso-Zeaxanthin"]["dose_role"] == "declared_total"
    assert exported["Trans-Zeaxanthin"]["dose_role"] == "form_component"
    assert "per_day_max" not in exported["Trans-Zeaxanthin"]


# A printed amount can miss both arrays: no upper limit keeps it out of analyzed_ingredients,
# a strict primary contract keeps it out of ingredients. It still reaches the dose readers.
def _exported(enriched, dsld_id):
    product = enriched(dsld_id)
    return product, build_detail_blob(product, score_product_v4(product))


def test_an_amount_missing_from_both_arrays_reaches_the_dose_readers(enriched):
    _, blob = _exported(enriched, "c4sport")
    [caffeine] = [r for r in blob["ingredients"] if r.get("canonical_id") == "caffeine"]
    assert caffeine["raw_source_path"] == "ingredientRows[14].nestedRows[1]"
    assert caffeine["dose_role"] == "declared_total"
    assert (caffeine["per_day_min"], caffeine["per_day_max"], caffeine["converted_unit"]) == (200.0, 200.0, "mg")
    # Contract fields only: nothing a reader could take for an analysis, a limit or a flag.
    assert set(caffeine) == {
        "name", "canonical_id", "raw_source_path", "dose_role",
        "per_day_min", "per_day_max", "converted_unit",
    }


def test_restoring_a_dose_row_adds_no_label_row(enriched):
    _, blob = _exported(enriched, "c4sport")
    paths = [r.get("raw_source_path") for r in blob["ingredients"]]
    assert len(paths) == len(set(paths))
    assert "ingredientRows[14].nestedRows[1]" in paths
    assert [r.get("raw_source_path") for r in blob["display_ingredients"]].count(
        "ingredientRows[14].nestedRows[1]"
    ) == 1


@pytest.mark.parametrize("dsld_id", ["62825", "64845"])
def test_a_component_never_comes_back_as_a_dose_row(enriched, dsld_id):
    product, blob = _exported(enriched, dsld_id)
    components = {
        r["raw_source_path"] for r in _rows(product) if r.get("dose_role") in NOT_AN_EXPOSURE
    }
    counted = [
        r for r in blob["ingredients"]
        if r.get("raw_source_path") in components and r.get("dose_role") not in NOT_AN_EXPOSURE
    ]
    assert not counted


def test_a_row_represented_by_its_exported_parent_is_not_added():
    from build_final_db import _append_dose_only_rows

    ingredients = [{"raw_source_path": "ingredientRows[0]", "name": "BCAA"}]
    _append_dose_only_rows(
        ingredients,
        [
            {"raw_source_path": "ingredientRows[0].nestedRows[0]", "ingredient": "Leucine",
             "canonical_id": "leucine", "dose_role": "declared_total", "ul_gate_eligible": False,
             "per_day_min": 2.5, "per_day_max": 2.5, "converted_unit": "g"},
        ],
    )
    assert len(ingredients) == 1


def test_a_row_the_analyzed_export_keeps_is_not_added():
    from build_final_db import _append_dose_only_rows

    ingredients = []
    _append_dose_only_rows(
        ingredients,
        [
            {"raw_source_path": "ingredientRows[1]", "ingredient": "Polyphenols",
             "canonical_id": "polyphenols", "dose_role": "declared_total", "ul_gate_eligible": True,
             "per_day_min": 400.0, "per_day_max": 400.0, "converted_unit": "mg"},
        ],
    )
    assert ingredients == []


# Vitamin E rows beside or inside the declared row. Each label named here was read.
@pytest.mark.parametrize(
    "dsld_id,low,high",
    [("63432", 67.0, 87.0), ("232781", 67.0, 87.0), ("29161", 3.35, 5.5)],
)
def test_a_mixture_beside_the_declared_row_raises_only_the_high_figure(enriched, dsld_id, low, high):
    [row] = _rows(enriched(dsld_id), "Vitamin E")
    assert row["safety_exposure"]["low_per_day"] == pytest.approx(low)
    assert row["safety_exposure"]["high_per_day"] == pytest.approx(high)


@pytest.mark.parametrize(
    "dsld_id,low,high",
    [("284266", 1005.0, 1005.0), ("188715", 335.0, 335.0), ("327306", 80.6, 161.2), ("313913", 80.6, 161.2)],
)
def test_forms_printed_inside_the_declared_row_are_part_of_it(enriched, dsld_id, low, high):
    """284266 prints "as d-Alpha Tocopherol from 1,000 mg Mixed Tocopherols", 335 mg, up to 3 a day.
    327306 and 313913 print d-alpha 73.9 and 6.7 under 80.6, with no form on the total, so
    they keep the existing mass bound. The mixture's 98.5 mg adds nothing to either."""
    [row] = _rows(enriched(dsld_id), "Vitamin E")
    exposure = row["safety_exposure"]
    assert exposure.get("low_per_day", exposure["per_day"]) == pytest.approx(low)
    assert exposure.get("high_per_day", exposure["per_day"]) == pytest.approx(high)


@pytest.mark.parametrize("dsld_id,per_day", [("307590", 41.0), ("328834", 13.5)])
def test_a_single_non_alpha_form_does_not_move_the_vitamin_e_figure(enriched, dsld_id, per_day):
    """Whether gamma, delta, beta or tocotrienol mass counts is an open clinical question."""
    [row] = _rows(enriched(dsld_id), "Vitamin E")
    assert row["safety_exposure"]["per_day"] == pytest.approx(per_day)
    assert "high_per_day" not in row["safety_exposure"]


def test_a_vitamin_d_row_in_iu_beside_its_mcg_total_is_not_summed(enriched):
    """242553 prints Vitamin D 20 mcg (as D3 800 IU): one amount in two units."""
    assert _distinct_total(enriched("242553"), {"Vitamin D", "Vitamin D3"}) == pytest.approx(20.0)


def test_a_compound_row_keeps_its_elemental_child_as_owner(enriched):
    """232148 prints CDP-Choline 250 mg and footnotes elemental choline 51.25 mg."""
    rows = _by_path(enriched("232148"))
    assert rows["ingredientRows[0]"]["dose_role"] == "form_component"
    assert _exposure(rows["ingredientRows[0].nestedRows[0]"]) == pytest.approx(51.25)
    assert rows["ingredientRows[0].nestedRows[0]"]["dose_role"] not in NOT_AN_EXPOSURE


# Beta-carotene dose tiers. A stack total can only meet a tier a product's warning carries.
# The 10,000 tier's card is for every viewer, so it has no profile gate; its authored
# risk factors let a stack rule read it.
RISK_FACTORS = ["asbestos_exposure", "current_smoker", "former_smoker"]


def _dose_cards(product, rule_id):
    return [
        w for w in build_detail_blob(product, score_product_v4(product))["warnings"]
        if w.get("source_rule_id") == rule_id and (w.get("profile_gate") or {}).get("gate_type") == "dose"
    ]


def _tiers(product, rule_id, condition="current_smoker"):
    return [
        hit["dose_decision"]["decision_rule"]["threshold"]
        for alert in product["interaction_profile"]["ingredient_alerts"]
        if alert["rule_id"] == rule_id
        for hit in alert["condition_hits"]
        if hit["condition_id"] == condition
    ]


@pytest.mark.parametrize(
    "dsld_id,rule_id",
    [
        ("294483", "RULE_IQM_BETA_CAROTENE_LUNG_CANCER"),
        ("178431", "RULE_IQM_VITAMIN_A_BETA_CAROTENE_LUNG_CANCER"),
    ],
)
def test_the_dose_card_carries_the_higher_tier_to_its_risk_factors(enriched, dsld_id, rule_id):
    """Each label is 7,500 mcg RAE a day: it meets the lower tier and not the higher."""
    product = enriched(dsld_id)
    assert _tiers(product, rule_id) == [7500.0]
    [card] = _dose_cards(product, rule_id)
    assert card["condition_ids"] == RISK_FACTORS
    decision = card["dose_decision"]
    assert decision["decision_rule"]["threshold"] == 10000.0
    assert decision["evaluated_daily_amount"] == pytest.approx(7500.0)
    assert decision["evaluation_status"] == "below_threshold"
    assert decision["consumer_disposition"] == "suppress"
    assert not (card["profile_gate"].get("requires") or {}).get("conditions_any")


def test_a_scoped_rule_reads_the_nested_row_of_its_form(enriched):
    """80495 prints Vitamin A 15000 IU (33% retinyl, 67% beta-carotene), then Beta-Carotene
    5625 mcg. The nested amount is 2,812.5 mcg RAE; the row's even form split would give 2,250."""
    rule_id = "RULE_IQM_VITAMIN_A_BETA_CAROTENE_LUNG_CANCER"
    product = enriched("80495")
    [hit] = [
        h for a in product["interaction_profile"]["ingredient_alerts"] if a["rule_id"] == rule_id
        for h in a["condition_hits"] if h["condition_id"] == "current_smoker"
    ]
    assert compact_dose_decision(hit["dose_decision"])["evaluated_daily_amount"] == pytest.approx(2812.5)


# The two lung-cancer rules measure one exposure, supplemental beta-carotene per day
# (Dr Pham, PHASE3_CLINICAL_POLICY_20260921.md section 5).
LUNG_RULES = ("RULE_IQM_BETA_CAROTENE_LUNG_CANCER", "RULE_IQM_VITAMIN_A_BETA_CAROTENE_LUNG_CANCER")


def _lung_cards(product, condition="current_smoker"):
    return [
        w for w in build_detail_blob(product, score_product_v4(product))["warnings"]
        if w.get("source_rule_id") in LUNG_RULES and condition in (w.get("condition_ids") or [])
    ]


@pytest.mark.parametrize("dsld_id", ["178431", "80495", "294483"])
def test_both_lung_cancer_rules_warn_on_the_beta_carotene_exposure(enriched, dsld_id):
    assert {w["ingredient_canonical_id"] for w in _lung_cards(enriched(dsld_id))} == {"beta_carotene"}


def test_a_preformed_rule_keeps_its_vitamin_a_subject(enriched):
    product = enriched("80495")
    warnings = build_detail_blob(product, score_product_v4(product))["warnings"]
    assert {
        w["ingredient_canonical_id"] for w in warnings
        if w.get("source_rule_id") == "RULE_IQM_VITAMIN_A_PREGNANCY_DOSE"
    } == {"vitamin_a"}


def test_a_product_with_both_rules_carries_one_amount_per_tier(enriched):
    """80495 prints the beta-carotene mass, 5,625 mcg, under its Vitamin A row."""
    cards = _lung_cards(enriched("80495"))
    assert sorted(
        (w["dose_decision"]["decision_rule"]["threshold"], w["dose_decision"]["evaluated_daily_amount"])
        for w in cards
    ) == [(7500.0, 2812.5), (10000.0, 2812.5)]


def test_two_rows_of_one_exposure_keep_the_larger_amount(enriched):
    """228355 prints Vitamin A 4,500 mcg as beta-carotene, then Mixed Carotenoids 172 mcg."""
    assert sorted(w["dose_decision"]["evaluated_daily_amount"] for w in _lung_cards(enriched("228355"))) == [4500.0, 4500.0]


def test_an_unknown_amount_stays_beside_a_known_one(enriched):
    """220806's Beta-Carotene row prints no amount. Its unknown must stay readable."""
    assert {
        (w["dose_decision"]["decision_rule"]["threshold"], w["dose_decision"].get("evaluated_daily_amount"))
        for w in _lung_cards(enriched("220806"))
    } == {(7500.0, 4500.0), (10000.0, 4500.0), (10000.0, None)}


@pytest.mark.parametrize("dsld_id", ["19170", "28483", "16730"])
def test_a_control_with_no_beta_carotene_row_does_not_gain_a_tier(enriched, dsld_id):
    for rule_id in ("RULE_IQM_VITAMIN_A_BETA_CAROTENE_LUNG_CANCER", "RULE_IQM_BETA_CAROTENE_LUNG_CANCER"):
        assert not _tiers(enriched(dsld_id), rule_id)
        assert not _dose_cards(enriched(dsld_id), rule_id)


# The pregnancy rule is scoped to preformed forms: "carotenoids are not handled by this
# threshold rule". A label declaring the preformed share states the amount it judges.
def _pregnancy_decisions(product):
    return {
        hit["condition_id"]: (hit["severity"], compact_dose_decision(hit["dose_decision"]))
        for alert in product["interaction_profile"]["ingredient_alerts"]
        if alert["rule_id"] == "RULE_IQM_VITAMIN_A_PREGNANCY_DOSE"
        for hit in alert["condition_hits"]
        if hit["condition_id"] in {"pregnancy", "ttc"}
    }


@pytest.mark.parametrize(
    "dsld_id,preformed_iu",
    [("80495", 4950.0), ("278001", 5000.0), ("66380", 7525.0), ("200725", 7050.0)],
)
def test_a_declared_preformed_share_is_what_the_pregnancy_rule_reads(enriched, dsld_id, preformed_iu):
    """80495 prints Vitamin A 15000 IU as 33% retinyl acetate, 67% beta-carotene."""
    for severity, decision in _pregnancy_decisions(enriched(dsld_id)).values():
        assert decision["evaluation_status"] == "below_threshold"
        assert decision["consumer_disposition"] == "suppress"
        assert decision["evaluated_daily_amount"] == pytest.approx(preformed_iu, rel=0.01)
        assert severity == "caution"


def test_a_mixed_row_with_no_declared_share_stays_unresolved(enriched):
    for _, decision in _pregnancy_decisions(enriched("16730")).values():
        assert decision["evaluation_status"] == "form_unknown"
        assert decision["consumer_disposition"] == "review"


def test_a_preformed_share_above_the_line_still_blocks(enricher):
    row = {"name": "Vitamin A", "canonical_id": "vitamin_a", "quantity": 25000.0, "unit": "IU"}
    forms = [{"name": "Beta-Carotene"}, {"name": "Retinyl Acetate"}]
    share = enricher._preformed_share_row(row, {"forms": forms, "notes": "as 50% Retinyl Acetate, 50% Beta Carotene"})
    assert share["quantity"] == 12500.0
    assert enricher._preformed_share_row(row, {"forms": forms, "notes": ""}) is None
    assert enricher._preformed_share_row(row, None) is None


# A mixture with no canonical identity and no alpha figure may hold any share of alpha.
# It stays out of the exact figure and still reaches the upper bound (Dr Pham E3).
def test_a_mixture_with_no_identity_still_reaches_the_vitamin_e_high(enriched):
    product = enriched("232315")
    [row] = [
        r for r in _rows(product)
        if r.get("canonical_id") == "vitamin_e" and r.get("dose_role") not in NOT_AN_EXPOSURE
    ]
    exposure = row["safety_exposure"]
    assert exposure["low_per_day"] == pytest.approx(60.3)
    assert exposure["high_per_day"] == pytest.approx(1070.3)
    [(status, _)] = _vitamin_e_decision(product)
    assert status == "form_unknown"


# 400 IU is activity, not a mass its children can be compared to. The rows below it are one
# material with it, not further doses (Dr Pham E3). Dose keeps reading the printed alpha row.
def test_rows_below_a_vitamin_e_total_in_iu_are_one_structure_with_it(enriched):
    product = enriched("2528")
    [(status, amount)] = _vitamin_e_decision(product)
    assert status == "below_threshold"
    assert amount == pytest.approx(268.0)
    assert score_product_v4(product)["quality_pillars_v4"]["dose"]["score"] == 20.0


def test_a_printed_alpha_range_does_not_hide_another_unprinted_mixture(enricher):
    """A revised second mixture has mass but no reviewed alpha allocation."""
    raw = json.loads((FIXTURES / "dose_lineage_64845_raw.json").read_text())
    raw["ingredientRows"][2]["quantity"][0]["quantity"] = 1500
    raw["ingredientRows"][2]["nestedRows"] = []
    product, _ = enricher.enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))
    [declared] = _rows(product, "Vitamin E")
    exposure = declared["safety_exposure"]
    # Two directed daily servings: the unchanged first mixture's printed high is
    # 39 mg, while the second still permits up to its whole 1500 mg mass.
    assert exposure["high_per_day"] == pytest.approx(exposure["per_day"] + (39 + 1500) * 2)
    [(status, _)] = _vitamin_e_decision(product)
    assert status == "form_unknown"


@pytest.mark.parametrize("operator,status", [
    (">", "above_threshold"),
    (">=", "form_unknown"),
    ("=", "below_threshold"),
])
def test_a_strict_caffeine_lower_bound_proves_the_authored_threshold(enricher, operator, status):
    row = _caffeine_row(name="Caffeine", quantity=200.0, quantity_operator=operator,
                        raw_source_path="ingredientRows[0]")
    dose = enricher._distinct_caffeine_dose({}, [row])
    severity, decision = enricher._evaluate_dose_thresholds_for_target(
        [{"scope": "condition", "target_id": "pregnancy", "basis": "per_day",
          "comparator": ">", "value": 200, "unit": "mg",
          "severity_if_met": "avoid", "severity_if_not_met": "monitor",
          "unknown_form_disposition": "review"}],
        "condition", "pregnancy", {**row, **dose}, 1.0, "monitor",
    )
    assert decision["evaluation_status"] == status
    assert severity == ("avoid" if status == "above_threshold" else "monitor")


def test_a_nested_unprinted_mixture_survives_its_siblings_alpha_range(enricher):
    owner = {"name": "Vitamin E", "canonical_id": "vitamin_e", "quantity": 100,
             "unit": "mg", "raw_source_path": "ingredientRows[0]"}
    mixture = {"name": "Mixed Tocopherols", "canonical_id": "vitamin_e", "quantity": 1600,
               "unit": "mg", "raw_source_path": "ingredientRows[1]"}
    alpha = {"name": "Alpha-Tocopherol", "canonical_id": "vitamin_e", "quantity": 39,
             "unit": "mg", "raw_source_path": "ingredientRows[1].nestedRows[0]",
             "printed_alpha_range_mg": {"low": 27, "high": 39}}
    unprinted = {"name": "Mixed Tocopherols", "canonical_id": "vitamin_e", "quantity": 1500,
                 "unit": "mg", "raw_source_path": "ingredientRows[1].nestedRows[1]"}
    row = {"dose_role": "declared_total", "servings_per_day_max": 1,
           "safety_exposure": {"per_day": 100, "unit": "mg"}}
    rows = [owner, mixture, alpha, unprinted]
    enricher._stamp_vitamin_e_ranges([(row, 100, owner["raw_source_path"])], rows,
                                    {id(mixture): owner}, rows)
    assert row["safety_exposure"]["low_per_day"] == 100
    assert row["safety_exposure"]["high_per_day"] == 1639
