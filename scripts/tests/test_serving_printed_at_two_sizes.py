"""One serving printed at two sizes is one ingredient, not two.

GNC and others print "1 scoop" and "2 scoops" columns. DSLD files them with
the same servingSizeOrder and different servingSizeQuantity, but gives the
second column's rows their own ingredientId and occasionally a node
misplaced from the other column ("Calories from Fat" at the 2-scoop size
nested under the 1-scoop creatine block). The exact-identity merge in
`_merge_alternate_serving_rows` declined those rows, so both columns entered
analysis: 49630 counted every creatine ingredient twice (2.5 g and 5 g blocks),
221108 two Protein rows (register Q39a).

Columns for different audiences (serving orders whose DV target groups
differ, 241222 "2-3 years" / "4 years and older") merge the same way; each
audience's amount stays a variant and analysis reads the adult/largest column.
Declared forms must agree (the same normalized form name or the same nonempty
form UNII, or no form on one side): D-alpha and DL-alpha tocopherol are
different declarations. DSLD 250086's "Tocopheryl" / "Tocopherol" Acetate
wording carries the same form UNII, so those two serving columns merge. Serving
orders for one audience (AM/PM packs) or none keep the exact rule, and two
blocks whose own children differ stay two panels.
"""
import collections
import json
import logging
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def _clean(pid):
    from enhanced_normalizer import EnhancedDSLDNormalizer

    logging.disable(logging.INFO)
    raw = json.loads((FIXTURES / f"serving_column_{pid}_raw.json").read_text())
    return EnhancedDSLDNormalizer().normalize_product(raw)["activeIngredients"]


def _names(rows):
    return collections.Counter(r["name"] for r in rows)


def _all_names(rows):
    names = collections.Counter()
    for row in rows:
        names[row["name"]] += 1
        names.update(_all_names(row.get("nestedRows") or []))
    return names


@pytest.mark.parametrize("pid, name", [
    ("221108", "Protein"),
    ("49630", "Advanced Creatine Complex"),
    ("49630", "Creatine Hydrochloride"),
    ("49630", "CoQ-10"),
])
def test_one_serving_at_two_sizes_is_one_row(pid, name):
    assert _names(_clean(pid))[name] == 1


def test_the_merged_row_keeps_both_printed_amounts_and_analyses_one():
    protein = next(r for r in _clean("221108") if r["name"] == "Protein")
    variants = protein["raw_taxonomy"]["quantityVariants"]
    assert sorted((v["quantity"], v["serving_size_quantity"]) for v in variants) == [(20, 33), (40, 66)]
    assert protein["quantity"] == 40.0  # the label's declared 66 g serving


def test_the_merged_row_keeps_its_own_raw_path():
    creatine = [r for r in _clean("49630") if r["name"] == "Creatine Hydrochloride"]
    assert [r["raw_source_path"] for r in creatine] == ["ingredientRows[8].nestedRows[1]"]


def test_audience_columns_are_one_row_analysed_for_the_adult_column():
    # U-Cubes 241222: order 1 is "2-3 years of age" (DV group "Children less
    # than 4 years of age"), order 2 "Children 4 years and older" ("Adults and
    # children 4 or more years of age"). Each audience's amount is kept as a
    # variant; analysis reads the largest serving (serving_frequency
    # .select_canonical_serving), the adult/4+ column the app shows.
    rows = _clean("241222")
    assert not {k: v for k, v in _names(rows).items() if v > 1}
    iodine = next(r for r in rows if r["name"] == "Iodine")
    variants = iodine["raw_taxonomy"]["quantityVariants"]
    assert sorted((v["quantity"], v["serving_size_order"]) for v in variants) == [(30, 1), (60, 2)]
    assert iodine["quantity"] == 60.0


def _audience_row(name, order, size, qty, ingredient_id, group):
    row = _row(name, order, size, qty, ingredient_id)
    row["quantity"][0]["dailyValueTargetGroup"] = [{"name": group}] if group else []
    return row


def test_columns_of_one_audience_or_none_keep_the_exact_rule():
    from enhanced_normalizer import EnhancedDSLDNormalizer

    merge = EnhancedDSLDNormalizer._merge_alternate_serving_rows
    adults = "Adults and children 4 or more years of age"
    # AM / PM packets: two serving orders for the same audience add up.
    assert len(merge([_audience_row("Zinc", 1, 1, 5, 1, adults), _audience_row("Zinc", 2, 1, 10, 2, adults)])) == 2
    # No audience named: not established as alternatives.
    assert len(merge([_audience_row("Zinc", 1, 2, 5, 1, None), _audience_row("Zinc", 2, 4, 10, 2, None)])) == 2
    # Two audiences: one ingredient with two audience amounts.
    kids = "Children less than 4 years of age"
    assert len(merge([_audience_row("Zinc", 1, 2, 5, 1, kids), _audience_row("Zinc", 2, 4, 10, 2, adults)])) == 1


def _row(name, order, size, qty, ingredient_id, children=(), form=None, form_unii=None):
    return {
        "name": name, "category": "vitamin", "ingredientGroup": name, "ingredientId": ingredient_id,
        "uniiCode": None, "alternateNames": [],
        "forms": [{"name": form, "ingredientId": ingredient_id + 100,
                   "uniiCode": form_unii}] if form else [],
        "quantity": [{"servingSizeOrder": order, "servingSizeQuantity": size,
                      "servingSizeUnit": "Scoop(s)", "quantity": qty, "unit": "mg"}],
        "nestedRows": list(children),
    }


def test_ids_do_not_split_one_serving():
    from enhanced_normalizer import EnhancedDSLDNormalizer

    merge = EnhancedDSLDNormalizer._merge_alternate_serving_rows
    rows = [_row("Vitamin E", 1, 4, 30, 1, form="DL-Alpha-Tocopheryl Acetate"),
            _row("Vitamin E", 1, 2, 15, 2, form="dl-alpha-tocopheryl acetate")]
    merged = merge(rows)
    assert len(merged) == 1
    assert [q["quantity"] for q in merged[0]["quantity"]] == [30, 15]


def test_a_form_declared_in_one_column_only_is_kept():
    from enhanced_normalizer import EnhancedDSLDNormalizer

    merged = EnhancedDSLDNormalizer._merge_alternate_serving_rows(
        [_row("Vitamin E", 1, 4, 30, 1), _row("Vitamin E", 1, 2, 15, 2, form="D-Alpha-Tocopherol")])
    assert len(merged) == 1
    assert [f["name"] for f in merged[0]["forms"]] == ["D-Alpha-Tocopherol"]


@pytest.mark.parametrize("first, second", [
    ("D-Alpha-Tocopherol", "DL-Alpha-Tocopherol"),
])
def test_conflicting_form_declarations_are_not_merged(first, second):
    from enhanced_normalizer import EnhancedDSLDNormalizer

    merged = EnhancedDSLDNormalizer._merge_alternate_serving_rows(
        [_row("Vitamin E", 1, 4, 30, 1, form=first), _row("Vitamin E", 1, 2, 15, 2, form=second)])
    assert [[f["name"] for f in r["forms"]] for r in merged] == [[first], [second]]


def test_conflicting_child_forms_keep_the_blocks_apart():
    from enhanced_normalizer import EnhancedDSLDNormalizer

    a = _row("Blend", 1, 2, 500, 1, children=[_row("Vitamin E", 1, 2, 30, 3, form="D-Alpha-Tocopherol")])
    b = _row("Blend", 1, 1, 250, 2, children=[_row("Vitamin E", 1, 1, 15, 4, form="DL-Alpha-Tocopherol")])
    assert len(EnhancedDSLDNormalizer._merge_alternate_serving_rows([a, b])) == 2


def test_matching_form_unii_merges_dsld_wording_variants():
    from enhanced_normalizer import EnhancedDSLDNormalizer

    rows = [
        _row("Vitamin E", 1, 4, 30, 1, form="DL-Alpha-Tocopheryl Acetate", form_unii="WR1WPI7EW8"),
        _row("Vitamin E", 1, 2, 15, 2, form="DL-Alpha-Tocopherol Acetate", form_unii="WR1WPI7EW8"),
    ]
    merged = EnhancedDSLDNormalizer._merge_alternate_serving_rows(rows)
    assert len(merged) == 1
    assert [q["quantity"] for q in merged[0]["quantity"]] == [30, 15]


def test_the_respelled_real_label_is_one_declaration():
    rows = [r for r in _clean("250086") if r["name"] == "Vitamin E"]
    assert len(rows) == 1
    variants = rows[0]["raw_taxonomy"]["quantityVariants"]
    assert sorted((v["quantity"], v["serving_size_quantity"]) for v in variants) == [(15, 2), (30, 4)]


def test_different_orders_or_different_children_stay_separate():
    from enhanced_normalizer import EnhancedDSLDNormalizer

    merge = EnhancedDSLDNormalizer._merge_alternate_serving_rows
    # Different serving orders with different ids: not one serving at two sizes.
    assert len(merge([_row("Zinc", 1, 2, 5, 1), _row("Zinc", 2, 4, 10, 2)])) == 2
    # The same column twice: two sources that add.
    assert len(merge([_row("Zinc", 1, 2, 5, 1), _row("Zinc", 1, 2, 10, 2)])) == 2
    # Own children differ: two panels, even at one serving order.
    a = _row("Blend", 1, 2, 500, 1, children=[_row("Alpha", 1, 2, 300, 3)])
    b = _row("Blend", 1, 1, 250, 2, children=[_row("Beta", 1, 1, 150, 4)])
    assert len(merge([a, b])) == 2


def test_a_node_misplaced_from_the_other_column_does_not_block_the_merge():
    from enhanced_normalizer import EnhancedDSLDNormalizer

    merge = EnhancedDSLDNormalizer._merge_alternate_serving_rows
    stray = _row("Calories from Fat", 1, 2, 10, 9)  # the 2-scoop column's row, filed under the 1-scoop block
    a = _row("Blend", 1, 1, 250, 1, children=[_row("Alpha", 1, 1, 150, 3), stray])
    b = _row("Blend", 1, 2, 500, 2, children=[_row("Alpha", 1, 2, 300, 4)])
    merged = merge([a, b])
    assert len(merged) == 1
    alpha = [c for c in merged[0]["nestedRows"] if c["name"] == "Alpha"]
    assert len(alpha) == 1 and [q["quantity"] for q in alpha[0]["quantity"]] == [150, 300]
    assert any(c["name"] == "Calories from Fat" for c in merged[0]["nestedRows"])


def test_merged_protein_column_still_reads_the_declared_protein():
    """Wheybolic Ripped 228714 prints Protein 40 g (2 scoops) and 20 g (1 scoop).
    Merged, the display row carries both as serving variants instead of one dose
    string; the declared-protein projection must still read it, at the label's
    serving (40 g), not the 1-scoop value the duplicate row used to leak."""
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    from scoring_input_contract import get_scoring_ingredients

    logging.disable(logging.INFO)
    raw = json.loads((FIXTURES / "serving_column_228714_raw.json").read_text())
    enriched, _ = SupplementEnricherV3().enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))
    assert enriched["nutrition_summary"]["protein_g"] == 40.0
    protein = [r for r in get_scoring_ingredients(enriched, strict=True).rows
               if r.get("canonical_id") == "protein" and r.get("evidence_type") == "sports_primary_dose"]
    assert [r.get("quantity") for r in protein] == [40.0]

@pytest.mark.parametrize("pid,name,expected_quantity", [
    ("219982", "Bilberry Fruit Powder", 100.0),
    ("304687", "Melatonin", 1.0),
    ("266727", "Folate", 200.0),
    ("184730", "Probiotic Blend", 0.0),
    ("278251", "Probiotic Blend", 0.0),
    ("287473", "Probiotic Blend", 0.0),
])
def test_audience_note_columns_merge_even_without_row_dv_groups(pid, name, expected_quantity):
    rows = _clean(pid)
    matching = [row for row in rows if row["name"].casefold() == name.casefold()]
    assert len(matching) == 1
    assert matching[0]["quantity"] == expected_quantity
    assert len(matching[0]["raw_taxonomy"]["quantityVariants"]) == 2


def test_misspelled_child_in_alternate_column_merges_by_dsld_identity_group():
    rows = _clean("33341")
    dim = [row for row in rows if "diindol" in row["name"].casefold()]
    assert len(dim) == 1
    assert dim[0]["quantity"] == 2000.0
    assert len(dim[0]["raw_taxonomy"]["quantityVariants"]) == 2


def test_interleaved_wheybolic_columns_do_not_duplicate_formula_rows():
    rows = _clean("220082")
    counts = _names(rows)
    for name in (
        "Wheybolic Complex",
        "Branched-Chain Amino Acids",
        "Velositol Amylopectin Chromium Complex",
        "ProHydrolase Protease Enzyme Blend",
        "Thermo Ripped Matrix",
        "Caffeine Anhydrous",
        "Water Balance Blend",
        "L-Carnitine",
    ):
        assert counts[name] == 1, name


def test_macros_column_variants_merge_despite_dsld_group_drift_and_literal_duplicates():
    rows = _clean("220125")
    top_counts = _names(rows)
    for name in ("Vitamin A", "Zinc", "Copper"):
        assert top_counts[name] == 1, name
    assert _all_names(rows)["Dietary Fats Blend"] == 1


def test_interleaved_nested_and_top_level_variants_keep_one_ingredient():
    rows = _clean("228714")
    assert _all_names(rows)["L-Carnitine"] == 1


def test_literal_same_source_row_is_not_counted_twice():
    from enhanced_normalizer import EnhancedDSLDNormalizer

    row = _row("Zinc", 1, 2, 5, 44)
    assert len(EnhancedDSLDNormalizer._merge_alternate_serving_rows([row, dict(row)])) == 1
