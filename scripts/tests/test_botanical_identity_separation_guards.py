"""Anti-regression guards for botanical-identity separations.

These lock CURRENT-CORRECT behavior verified 2026-06-22: none of these plain
botanical labels currently collapse onto an isolated marker or a neighbouring
plant's IQM identity. Each assertion guards against a *specific* documented
mis-mapping risk, NOT against the label being recognized at all — so adding a
legitimate identity-only botanical entry later (e.g. ``Plantago major`` for
plantain) keeps these green; only a marker/neighbor collapse turns them red.

Risks guarded (from the unmapped-actives review):
  - Plantain leaf/whole-herb  must NOT become IQM ``aucubin`` (isolated marker).
  - Passion fruit             must NOT become ``passionflower`` or ``vitexin``.
  - Perilla aerial part       must NOT become ``perilla_oil``.
  - Black rice                must NOT become ``anthocyanins``.
Plus a promotion guard: a plant-part label alone (without the cleaner's
``active_misfiled_in_inactive`` flag) must not be promoted into scoring.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from enhanced_normalizer import EnhancedDSLDNormalizer
from enrich_supplements_v3 import SupplementEnricherV3


@pytest.fixture(scope="module")
def normalizer():
    return EnhancedDSLDNormalizer()


@pytest.fixture(scope="module")
def enricher():
    return SupplementEnricherV3()


@pytest.mark.parametrize(
    "label,forbidden",
    [
        ("Plantain leaf extract", "aucubin"),
        ("Plantain Whole Herb Extract", "aucubin"),
        ("Passion Fruit Extract", "passionflower"),
        ("Passion Fruit Extract", "vitexin"),
        ("Passion Fruit Extract", "isovitexin"),
        # label carries no "oil"; any collapse onto a perilla *oil* form introduces it
        ("Perilla Aerial Part Extract", "oil"),
        ("Perilla aerial part", "oil"),
        ("Black Rice extract", "anthocyanin"),
        ("Black Rice Extract", "anthocyanin"),
    ],
)
def test_botanical_label_does_not_collapse_to_marker_or_neighbor(normalizer, label, forbidden):
    standard_name, _mapped, _ = normalizer._enhanced_ingredient_mapping(label, [])
    assert forbidden not in str(standard_name).lower(), (
        f"{label!r} resolved to {standard_name!r} which contains forbidden "
        f"identity token {forbidden!r}"
    )


def test_plant_part_text_alone_does_not_promote_to_scorable(enricher):
    """Rule D product-type rescue requires the cleaner to have flagged the row as
    an active misfiled into inactives. A bare plant-part label (no such flag)
    must never be promoted into scoring on the strength of the word 'leaf' alone.
    """
    quality_map = enricher.databases["ingredient_quality_map"]
    botanicals_db = enricher.databases["standardized_botanicals"]
    ingredient = {"name": "Plantain leaf extract", "quantity": 100, "unit": "mg"}
    assert (
        enricher._should_promote_to_scorable(ingredient, quality_map, botanicals_db, 0)
        is None
    )


def _perilla_source_product(label, *, oil=False):
    return {
        'id': 'perilla-identity-control', 'fullName': label, 'brandName': 'Source control',
        'physicalState': {'langualCodeDescription': 'Capsule'},
        'servingSizes': [{'order': 1, 'minQuantity': 1, 'maxQuantity': 1, 'unit': 'Capsule(s)'}],
        'ingredientRows': [{
            'name': label, 'ingredientGroup': 'Perilla Oil' if oil else 'perilla',
            'category': 'fat' if oil else 'botanical', 'forms': [], 'nestedRows': [],
            'quantity': [{'servingSizeOrder': 1, 'servingSizeQuantity': 1,
                          'quantity': 150, 'unit': 'mg', 'operator': '=',
                          'servingSizeUnit': 'Capsule(s)'}],
        }],
    }


@pytest.mark.parametrize('label', [
    'Benegut Perilla extract',
    'Benegut Perilla (Perilla frutescens) extract',
    'Benegut® perilla extract',
])
def test_verified_benegut_is_leaf_not_seed_oil_through_clean_and_enrich(normalizer, enricher, label):
    clean = normalizer.normalize_product(_perilla_source_product(label))
    assert clean['activeIngredients'][0]['canonical_id'] == 'perilla_leaf'
    enriched, _ = enricher.enrich_product(clean)
    row = enriched['ingredient_quality_data']['ingredients'][0]
    assert row['canonical_id'] == 'perilla_leaf'
    assert row.get('form_id') != 'perilla seed oil'
    assert row.get('bio_score') is None
    assert (row['raw_source_text'], row['raw_source_path'], row['quantity'], row['unit']) == (
        label, 'ingredientRows[0]', 150.0, 'mg')


@pytest.mark.parametrize('label', [
    'Perilla extract', 'Perilla (Perilla frutescens) extract',
    'Perilla frutescens', 'Perilla',
    'Perilla Seed Extract', 'Perilla frutescens seed extract',
])
def test_unspecified_or_seed_extract_is_not_relabelled_leaf_or_oil(normalizer, enricher, label):
    clean = normalizer.normalize_product(_perilla_source_product(label))
    assert clean['activeIngredients'][0].get('canonical_id') not in {'perilla_leaf', 'perilla_oil'}
    enriched, _ = enricher.enrich_product(clean)
    rows = enriched['ingredient_quality_data']['ingredients']
    assert rows
    assert all(row.get('canonical_id') not in {'perilla_leaf', 'perilla_oil'} for row in rows)
    assert all(row.get('form_id') != 'perilla seed oil' for row in rows)
    assert (rows[0]['raw_source_text'], rows[0]['raw_source_path'],
            rows[0]['quantity'], rows[0]['unit']) == (label, 'ingredientRows[0]', 150.0, 'mg')


@pytest.mark.parametrize('label', ['Perilla oil', 'Perilla frutescens seed oil', 'Perilla frutescens oil', 'Egoma oil'])
def test_explicit_perilla_oil_retains_its_oil_identity(normalizer, enricher, label):
    clean = normalizer.normalize_product(_perilla_source_product(label, oil=True))
    assert clean['activeIngredients'][0]['canonical_id'] == 'perilla_oil'
    enriched, _ = enricher.enrich_product(clean)
    row = enriched['ingredient_quality_data']['ingredients'][0]
    assert (row['canonical_id'], row['form_id'], row['bio_score']) == (
        'perilla_oil', 'perilla seed oil', 10.0)


@pytest.mark.parametrize('label', [
    'Perilla', 'Perilla extract', 'Perilla (Perilla frutescens) extract',
    'Perilla frutescens', 'Perilla Seed Extract', 'Perilla frutescens seed extract',
    'Perilla Aerial Part Extract', 'Perilla frutescens aerial part extract',
])
def test_generic_perilla_retains_identity_without_leaf_oil_or_grade(normalizer, enricher, label):
    clean = normalizer.normalize_product(_perilla_source_product(label))
    assert clean['activeIngredients'][0]['canonical_id'] == 'perilla_unspecified'
    enriched, _ = enricher.enrich_product(clean)
    row = enriched['ingredient_quality_data']['ingredients'][0]
    assert row['canonical_id'] == 'perilla_unspecified'
    assert row.get('form_id') is None
    assert row.get('bio_score') is None
    assert (row['raw_source_text'], row['quantity'], row['unit']) == (label, 150.0, 'mg')
    record = next(entry for entry in enricher.databases['botanical_ingredients']['botanical_ingredients']
                  if entry['id'] == 'perilla_unspecified')
    assert record['attributes']['bonus_eligible'] is False
    assert not record['external_ids']
    assert not {'bio_score', 'study_contexts', 'evidence_level', 'min_clinical_dose'} & record.keys()


@pytest.mark.parametrize('label', ['Perilla leaf extract', 'Perilla frutescens leaf extract'])
def test_explicit_leaf_material_retains_leaf_identity(normalizer, enricher, label):
    clean = normalizer.normalize_product(_perilla_source_product(label))
    assert clean['activeIngredients'][0]['canonical_id'] == 'perilla_leaf'
    enriched, _ = enricher.enrich_product(clean)
    row = enriched['ingredient_quality_data']['ingredients'][0]
    assert row['canonical_id'] == 'perilla_leaf'
    assert row.get('bio_score') is None
    assert row['plantPart'] == 'leaf'


@pytest.mark.parametrize('label,notes,part,canonical', [
    ('Perilla Seed Extract', 'standardized to contain 3% polyphenols', 'seed', 'perilla_unspecified'),
    ('Perilla Aerial Part Extract', '10:1', 'aerial parts', 'perilla_unspecified'),
    ('Perilla extract', 'PlantPart: leaf Note: 4:1', 'leaf', 'perilla_leaf'),
])
def test_generic_identity_preserves_source_part_notes_and_mass(
    normalizer, enricher, label, notes, part, canonical,
):
    raw = _perilla_source_product(label)
    raw['ingredientRows'][0]['notes'] = notes
    clean = normalizer.normalize_product(raw)
    source = clean['activeIngredients'][0]
    assert source['canonical_id'] == canonical
    assert source['plantPart'] == part
    assert source['notes'] == notes
    enriched, _ = enricher.enrich_product(clean)
    row = enriched['ingredient_quality_data']['ingredients'][0]
    assert (row['canonical_id'], row['plantPart'], row['quantity'], row['unit']) == (
        canonical, part, 150.0, 'mg')
    assert row['raw_source_text'] == label
