"""Real products that read mapped_coverage 0.0 because of how the label is encoded.

Each case is a label whose identity we do know. The gate stays as it is: the
identity has to reach it through the existing owner.
"""
import copy
import json
import logging
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def run():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    from score_supplements_v4 import score_product_v4

    logging.disable(logging.INFO)
    normalizer, enricher = EnhancedDSLDNormalizer(), SupplementEnricherV3()
    cache = {}

    def _run(pid):
        if pid not in cache:
            raw = json.loads((FIXTURES / f"low_coverage_{pid}_raw.json").read_text())
            enriched, _ = enricher.enrich_product(normalizer.normalize_product(copy.deepcopy(raw)))
            cache[pid] = (enriched, score_product_v4(enriched))
        return cache[pid]

    return _run


def _anchors(enriched):
    from scoring_input_contract import get_scoring_ingredients

    rows = get_scoring_ingredients(enriched, strict=True).rows
    return rows, [r for r in rows if r.get("evidence_type") == "blend_anchor_mass"]


# DSLD lists these members as forms of a dosed blend row. The cleaner flattens
# the forms and drops the header, so the blend mass had no row to stand on,
# while the same label written with nestedRows (74457) keeps its anchor.
@pytest.mark.parametrize(
    "pid,anchor,mass",
    [
        ("855", "oregano", 60),
        ("12300", "blessed_thistle", 860),
        ("19598", "celadrin", 1200),
        ("271115", "fenugreek", 1000),  # both are in the title; label order picks
    ],
)
def test_form_encoded_blend_keeps_its_blend_level_anchor(run, pid, anchor, mass):
    enriched, scored = run(pid)
    rows, anchors = _anchors(enriched)
    assert [(a["canonical_id"], a["dose_value"], a["dose_unit"]) for a in anchors] == [(anchor, mass, "mg")]
    assert anchors[0]["evidence_scope"] == "blend_level"
    assert anchors[0]["raw_source_path"].startswith("ingredientRows[")
    assert ".forms[" not in anchors[0]["raw_source_path"]
    assert scored["v4_breakdown"]["completeness_gate"]["mapped_coverage"] >= 0.3
    # A member's amount is not printed: the blend mass never becomes its dose.
    for row in enriched["ingredient_quality_data"]["ingredients"]:
        if ".forms[" in str(row.get("raw_source_path")):
            assert not row.get("quantity")


def test_nested_row_twin_is_the_same_rule(run):
    _, anchors = _anchors(run("74457")[0])
    assert [(a["canonical_id"], a["dose_value"]) for a in anchors] == [("oregano", 60)]


def test_blend_total_by_volume_stays_without_an_anchor(run):
    # 1 mL has no mass; the anchor owner requires one.
    enriched, scored = run("315586")
    assert _anchors(enriched)[1] == []
    assert scored["v4_breakdown"]["completeness_gate"]["mapped_coverage"] == 0.0


def test_oyster_whole_extract_is_the_oyster_extract_identity(run):
    enriched, scored = run("330192")
    row = next(r for r in enriched["ingredient_quality_data"]["ingredients"]
               if r.get("name") == "Oyster Whole Extract")
    assert row["canonical_id"] == "PII_OYSTER_EXTRACT"
    assert scored["v4_breakdown"]["completeness_gate"]["mapped_coverage"] >= 0.3


def test_oyster_shell_extract_stays_a_different_unresolved_material(run):
    # The alias names whole extract only. 330191 printed Whole under an API
    # "Shell"; these three stay held until their own printed labels are read.
    enriched, scored = run("294580")
    assert not any(r.get("canonical_id") == "PII_OYSTER_EXTRACT"
                   for r in enriched["ingredient_quality_data"]["ingredients"])
    assert scored["v4_breakdown"]["completeness_gate"]["mapped_coverage"] == 0.0


def _rows_named(enriched, name):
    return [r for r in enriched["ingredient_quality_data"]["ingredients"] if r.get("name") == name]


def test_omega_total_over_an_undosed_oil_row_owns_the_dose(run):
    # "Total Omega-3 300 mg" over an undosed Fish Oil row that itemizes DHA and
    # EPA is the nestedRows twin of 75188, where the same itemizing is in forms.
    enriched, scored = run("260262")
    [total] = _rows_named(enriched, "Total Omega-3 Fatty Acids")
    assert (total["canonical_id"], total["quantity"], total["unit"]) == ("fish_oil", 300, "mg")
    assert total.get("skip_reason") is None
    assert scored["v4_breakdown"]["completeness_gate"]["mapped_coverage"] >= 0.3
    # The children stay display rows; nothing borrows the total's mass.
    for name in ("Fish Oil", "Docosahexaenoic Acid", "Eicosapentaenoic Acid"):
        assert all(r.get("skip_reason") and not r.get("quantity") for r in _rows_named(enriched, name))


def test_label_with_a_dosed_oil_row_keeps_the_oil_as_the_owner(run):
    enriched, _ = run("253580")
    [oil] = _rows_named(enriched, "Fish Oil")
    assert oil["quantity"] == 1 and oil.get("skip_reason") is None
    assert not _rows_named(enriched, "Total Omega-3 Fatty Acids")


def test_oil_wrapper_row_still_reads_the_total_as_epa_plus_dha(run):
    from scoring_input_contract import _child_disclosed_epa_dha_owner

    enriched, _ = run("260262")
    rows = enriched["activeIngredients"]
    total = next(r for r in rows if r["name"] == "Total Omega-3 Fatty Acids")
    assert _child_disclosed_epa_dha_owner(total, rows) == "epa_dha"
    # Any other omega-3 beneath the oil means the total is not only EPA and DHA.
    other = next(r for r in rows if r["name"] == "Docosahexaenoic Acid")
    assert _child_disclosed_epa_dha_owner(
        total, [r for r in rows if r is not other] + [{**other, "name": "ALA", "canonical_id": "ala"}],
    ) is None
