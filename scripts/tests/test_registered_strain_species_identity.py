"""A registered probiotic strain keeps its species parent in the cleaner.

The cleaner's probiotic strain bypass renames a label row to the registry
strain's standard name. Strains without their own IQM form (NCIMB 30242,
CNCM I-3799, CU1, Lp-115 ...) then had no canonical id, so the row was
downgraded to unmapped and the enricher reported an identity conflict. Before
those strains were registered the same rows mapped to their species. The
row's structured DSLD ingredientGroup supplies that species parent.
"""

import logging
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
logging.disable(logging.CRITICAL)

import enhanced_normalizer as _enorm  # noqa: E402


@pytest.fixture(scope="module")
def normalizer():
    return _enorm.EnhancedDSLDNormalizer()


def _row(name, group, category="bacteria", qty=0, unit="NP"):
    return {
        "order": 1,
        "name": name,
        "category": category,
        "ingredientGroup": group,
        "quantity": [{"servingSizeOrder": 1, "servingSizeQuantity": 1, "operator": "=",
                      "quantity": qty, "unit": unit, "servingSizeUnit": "Capsule(s)"}],
        "nestedRows": [],
        "alternateNames": [],
        "forms": [],
    }


def _process(normalizer, row):
    out = normalizer._process_single_ingredient_enhanced(row, True)
    return out[0] if isinstance(out, list) and out else out


@pytest.mark.parametrize(
    "row, canonical",
    [
        (_row("Lactobacillus reuteri NCIMB 30242", "Lactobacillus reuteri"), "lactobacillus_reuteri"),
        (_row("Saccharomyces boulardii CNCM I-3799", "Saccharomyces boulardii ",
              category="non-nutrient/non-botanical", qty=250, unit="mg"), "saccharomyces_boulardii"),
        (_row("Bacillus subtilis CU1", "Bacillus Subtilis"), "bacillus_subtilis"),
        (_row("Lactobacillus plantarum Lp-115", "Lactobacillus plantarum"), "lactobacillus_plantarum"),
    ],
)
def test_registered_strain_without_iqm_form_maps_to_its_species(normalizer, row, canonical) -> None:
    out = _process(normalizer, row)
    assert out["canonical_id"] == canonical
    assert out["canonical_source_db"] == "ingredient_quality_map"


def test_species_parent_must_match_the_strain_name(normalizer) -> None:
    out = _process(normalizer, _row("Lactobacillus reuteri NCIMB 30242", "Lactobacillus rhamnosus"))
    assert out["canonical_id"] is None


def test_strain_gets_the_species_an_unregistered_name_in_its_group_gets(normalizer) -> None:
    """Parity with the cleaner's existing ingredientGroup fallback, which an
    unregistered name reaches and the strain bypass skipped."""
    strain = _process(normalizer, _row("Lactobacillus reuteri NCIMB 30242", "Lactobacillus reuteri"))
    unregistered = _process(normalizer, _row("Zzqx Proprietary Culture 7", "Lactobacillus reuteri"))
    assert strain["canonical_id"] == unregistered["canonical_id"] == "lactobacillus_reuteri"


@pytest.mark.parametrize("name", ["Lactobacillus reuteri NCIMB 302420", "Lactobacillus plantarum Lp-1150"])
def test_cleaner_does_not_shorten_an_unregistered_strain_code(normalizer, name):
    assert normalizer._match_probiotic_strain(normalizer.matcher.preprocess_text(name)) is None
