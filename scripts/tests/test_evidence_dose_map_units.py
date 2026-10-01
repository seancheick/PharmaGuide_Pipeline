"""Identity-keyed Evidence doses compare amounts in the record's unit.

``generic_evidence._dose_map`` keys each label amount by the identities a row
names; ``_converted_product_dose`` reads that key for records without a source
row (recovered collagen, aggregate BCAA) and gates them on ``min_clinical_dose``.
A raw number is not comparable across units: 300 mg is less than 2.5 g. The
largest matching amount must be chosen after conversion, the same policy the
source-row path already applies.
"""
from __future__ import annotations

import copy
import json
import logging
from pathlib import Path

import pytest

from scoring_v4.modules.generic_evidence import (
    _RECOVERED_COLLAGEN_PEPTIDES_MATCH,
    _converted_product_dose,
    _dose_map,
)
from tests.test_v4_generic_evidence_p133 import _ingredient, _product


FIXTURES = Path(__file__).parent / "fixtures"


def _evidence_for_raw(raw: dict) -> dict:
    """Clean -> Enrich -> the public artifact's Evidence dimension."""
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    from scoring_v4.scored_artifact import build_scored_artifact

    logging.disable(logging.INFO)
    enriched = SupplementEnricherV3().enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))[0]
    return build_scored_artifact(enriched)["_v4_module_breakdown"]["dimensions"]["evidence"]


def _collagen_label(repeat_at: int | None = None) -> dict:
    """DSLD 329893: 2.5 g hydrolyzed fish collagen, the recovered record's exact
    2,500 mg minimum. ``repeat_at`` repeats that ingredient at 300 mg."""
    raw = json.loads((FIXTURES / "dose_map_units_collagen_329893_raw.json").read_text())
    if repeat_at is not None:
        rows = raw["ingredientRows"]
        repeat = copy.deepcopy(rows[2])
        repeat["quantity"] = [dict(repeat["quantity"][0], quantity=300, unit="mg")]
        rows.insert(repeat_at, repeat)
        for order, row in enumerate(rows, start=1):
            row["order"] = order
    return raw


@pytest.mark.parametrize("repeat_at", [None, 2, 3], ids=["label", "small_row_first", "small_row_last"])
def test_a_smaller_mg_row_never_hides_the_gram_dose_from_the_studied_minimum(repeat_at):
    evidence = _evidence_for_raw(_collagen_label(repeat_at))
    metadata = evidence["metadata"]

    assert metadata["recovered_matches"] == ["RECOVERED_COLLAGEN_PEPTIDES_V1"]
    assert "SUB_CLINICAL_DOSE_DETECTED" not in metadata["flags"]
    assert metadata["sub_clinical_canonicals"] == []
    assert metadata["primary_evidence_floor_canonical"] == "collagen"


def _collagen_dose(*rows) -> float | None:
    product = _product(ingredients=list(rows), matches=[])
    return _converted_product_dose(dict(_RECOVERED_COLLAGEN_PEPTIDES_MATCH), _dose_map(product))[0]


def _collagen_row(name, quantity, unit):
    return _ingredient(name=name, standard_name="Collagen", canonical_id="collagen", quantity=quantity, unit=unit)


@pytest.mark.parametrize("reverse", [False, True])
def test_identity_dose_is_the_largest_amount_after_mass_conversion(reverse):
    rows = [_collagen_row("Bovine Hide Collagen", 10, "g"), _collagen_row("Hydrolyzed Collagen Peptides", 300, "mg")]

    assert _collagen_dose(*(rows[::-1] if reverse else rows)) == pytest.approx(10000)


@pytest.mark.parametrize("reverse", [False, True])
def test_a_larger_number_in_another_dimension_never_displaces_the_mass_amount(reverse):
    # 50,000 of a unit the converter cannot read as mass is not "more" than 5 g.
    rows = [_collagen_row("Collagen", 5, "Gram(s)"), _collagen_row("Collagen", 50000, "IU")]

    assert _collagen_dose(*(rows[::-1] if reverse else rows)) == pytest.approx(5000)


def test_an_identity_with_no_convertible_amount_stays_unresolved():
    assert _collagen_dose(_collagen_row("Collagen", 50000, "IU")) is None


def test_aggregate_components_read_their_largest_converted_amount():
    record = {
        "id": "INGR_BRANCHED_CHAIN_AMINO_ACIDS",
        "ingredient": "Branched Chain Amino Acids",
        "aggregate_canonical_ids": ["l_leucine", "l_isoleucine", "l_valine"],
        "min_clinical_dose": 5000,
        "dose_unit": "mg",
    }
    product = _product(ingredients=[
        _ingredient(name="L-Leucine", canonical_id="l_leucine", quantity=3, unit="Gram(s)"),
        _ingredient(name="L-Leucine", canonical_id="l_leucine", quantity=500, unit="mg"),
        _ingredient(name="L-Isoleucine", canonical_id="l_isoleucine", quantity=1500, unit="mg"),
        _ingredient(name="L-Valine", canonical_id="l_valine", quantity=1500, unit="mg"),
    ], matches=[])

    assert _converted_product_dose(record, _dose_map(product))[0] == pytest.approx(6000)
