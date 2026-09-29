"""One serving printed at two sizes is one ingredient, not two.

GNC and others print "1 scoop" and "2 scoops" columns. DSLD files them with
the same servingSizeOrder and different servingSizeQuantity, but gives the
second column's rows their own ingredientId, sometimes a respelled form
("DL-Alpha-Tocopheryl" / "Tocopherol" Acetate) and occasionally a node
misplaced from the other column ("Calories from Fat" at the 2-scoop size
nested under the 1-scoop creatine block). The exact-identity merge in
`_merge_alternate_serving_rows` declined those rows, so both columns entered
analysis: 49630 counted every creatine ingredient twice (2.5 g and 5 g blocks),
221108 two Protein rows, 250086 two Vitamin E rows (register Q39a).

Different serving orders (age bands, AM/PM packs) keep the exact rule, and two
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


@pytest.mark.parametrize("pid, name", [
    ("221108", "Protein"),
    ("250086", "Vitamin E"),
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


def test_age_band_columns_keep_the_exact_rule():
    # U-Cubes 241222: servingSizes order 1 (2-3 years) and order 2 (4 years and
    # older) are different servings; this change does not touch them.
    assert {k: v for k, v in _names(_clean("241222")).items() if v > 1} == {
        "Iodine": 2, "Magnesium": 2, "Inositol": 2}


def _row(name, order, size, qty, ingredient_id, children=(), form=None):
    return {
        "name": name, "category": "vitamin", "ingredientGroup": name, "ingredientId": ingredient_id,
        "uniiCode": None, "alternateNames": [],
        "forms": [{"name": form, "ingredientId": ingredient_id + 100}] if form else [],
        "quantity": [{"servingSizeOrder": order, "servingSizeQuantity": size,
                      "servingSizeUnit": "Scoop(s)", "quantity": qty, "unit": "mg"}],
        "nestedRows": list(children),
    }


def test_ids_and_form_spelling_do_not_split_one_serving():
    from enhanced_normalizer import EnhancedDSLDNormalizer

    merge = EnhancedDSLDNormalizer._merge_alternate_serving_rows
    rows = [_row("Vitamin E", 1, 4, 30, 1, form="DL-Alpha-Tocopheryl Acetate"),
            _row("Vitamin E", 1, 2, 15, 2, form="DL-Alpha-Tocopherol Acetate")]
    merged = merge(rows)
    assert len(merged) == 1
    assert [q["quantity"] for q in merged[0]["quantity"]] == [30, 15]
    assert merged[0]["forms"][0]["name"] == "DL-Alpha-Tocopheryl Acetate"


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
