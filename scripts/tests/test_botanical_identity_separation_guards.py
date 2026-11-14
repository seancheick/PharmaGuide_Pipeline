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


@pytest.mark.parametrize('label', ['Valerenic Acid', 'Valerenic Acids', 'Valerenic Acid Extract', 'Valerenic Acid 0.8%'])
@pytest.mark.parametrize('group', ['Valerenic Acid', 'Valerian'])
@pytest.mark.parametrize('unii', ['', '34NDB285PM'])
def test_isolated_valerenic_acid_does_not_become_whole_root(normalizer, label, group, unii):
    raw = _perilla_source_product(label)
    raw['ingredientRows'][0].update(ingredientGroup=group, uniiCode=unii)
    clean = normalizer.normalize_product(raw)
    row = clean['activeIngredients'][0]
    assert row.get('canonical_id') != 'valerian'
    assert row['quantity'] == 150


@pytest.mark.parametrize('canonical', [None, 'valerian'])
@pytest.mark.parametrize('label', ['Valerenic Acid', 'Valerenic Acids', 'Valerenic Acid Extract', 'Valerenic Acid 0.8%'])
def test_enrich_does_not_resurrect_root_for_isolated_constituent(enricher, canonical, label):
    match = enricher._match_quality_map(
        label, label, enricher.databases['ingredient_quality_map'],
        cleaner_canonical_id=canonical,
    )
    assert match is None or match['canonical_id'] != 'valerian'


def test_valerian_root_keeps_identity_with_constituent_note(normalizer, enricher):
    raw = _perilla_source_product('Valerian Root Extract')
    raw['ingredientRows'][0].update(ingredientGroup='Valerian', notes='valerenic acid')
    clean = normalizer.normalize_product(raw)
    assert clean['activeIngredients'][0]['canonical_id'] == 'valerian'
    match = enricher._match_quality_map(
        'Valerian Root Extract', 'Valerian', enricher.databases['ingredient_quality_map'],
        cleaner_canonical_id='valerian', row_notes='valerenic acid',
    )
    assert match is not None and match['canonical_id'] == 'valerian'


def test_enrich_stale_root_identity_preserves_unresolved_chemical_amount(normalizer, enricher):
    clean = normalizer.normalize_product(_perilla_source_product('Valerenic Acid'))
    clean['activeIngredients'][0].update(
        canonical_id='valerian', canonical_source_db='ingredient_quality_map',
    )
    enriched, _ = enricher.enrich_product(clean)
    row = enriched['ingredient_quality_data']['ingredients'][0]
    assert row.get('canonical_id') != 'valerian'
    assert row['scoreable_identity'] is False
    assert row['quantity'] == 150


def test_substring_material_exclusion_still_reads_notes(enricher):
    from copy import deepcopy

    quality_map = deepcopy(enricher.databases['ingredient_quality_map'])
    quality_map['valerian']['match_rules']['negative_match_terms'] = ['leaf material']
    match = enricher._match_quality_map(
        'Valerian Root Extract', 'Valerian', quality_map,
        cleaner_canonical_id='valerian', row_notes='actually leaf material',
    )
    assert match is None


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


@pytest.mark.parametrize("index", range(5))
def test_perilla_exact_label_has_limited_evidence_and_no_benchmark(normalizer, enricher, index):
    import json
    from pathlib import Path

    from assessment_readiness import _resolved_evidence_assessment, EVIDENCE_EVALUATED_LIMITED_OR_NEGATIVE
    from evidence_resolver import resolve_evidence_for_row
    from scoring_v4.modules.botanical_profile import _botanical_benchmark
    from scoring_input_contract import get_evidence_subject_rows

    labels = json.loads((Path(__file__).parent / "fixtures/perilla_exact_source_labels.json").read_text())
    clean = normalizer.normalize_product(labels[index])
    product, _ = enricher.enrich_product(clean)
    row, = get_evidence_subject_rows(product)
    assert row["canonical_id"] == "perilla_unspecified"
    assert (row["quantity"], row["unit"]) == (450.0 if index < 4 else 150.0, "mg")
    assert _botanical_benchmark(row, product=product) == "absent"
    resolution = resolve_evidence_for_row(row, product)
    assert resolution.points_eligible is False
    assert resolution.reason_code == "clinical_form_mismatch"
    assert _resolved_evidence_assessment(resolution)[0] == EVIDENCE_EVALUATED_LIMITED_OR_NEGATIVE

    assert resolution.owner_facts["literature_evidence"]["pmids"] == ["24885816"]


@pytest.mark.parametrize("name", ["Perilla leaf extract", "Perilla seed oil", "Perilla extract"])
def test_perilla_exact_review_does_not_transfer_to_other_labels(normalizer, enricher, name):
    from dose_assessment import _dose_source_preparation_matches
    from evidence_resolver import _load_literature_evidence, resolve_evidence_for_row

    product, _ = enricher.enrich_product(normalizer.normalize_product(
        _perilla_source_product(name, oil=name.endswith("oil"))))
    row = product["ingredient_quality_data"]["ingredients"][0]
    record = _load_literature_evidence()["perilla_unspecified"]
    assert not _dose_source_preparation_matches(product, row, record)
    resolution = resolve_evidence_for_row(row, product)
    if row["canonical_id"] == "perilla_unspecified":
        assert resolution.blocking_reasons
        assert resolution.points_eligible is False
        assert resolution.owner_facts.get("literature_evidence", {}).get("pmids") != ["24885816"]


def test_perilla_review_uses_counted_registry_and_verified_per_use_reference():
    import json

    from data_batch import recount
    from dose_assessment import verified_reference_citations
    from evidence_resolver import _LITERATURE_EVIDENCE_PATH

    registry = json.loads(_LITERATURE_EVIDENCE_PATH.read_text())
    assert not recount(_LITERATURE_EVIDENCE_PATH.name, registry)
    record = next(row for row in registry["literature_evidence_records"]
                  if row["canonical_id"] == "perilla_unspecified")
    assert record["reference_semantics"]["exposure_basis"] == "per_use"
    assert record["reference_semantics"]["curve"] == "completed_no_benchmark_neutral"
    assert verified_reference_citations(record)


@pytest.mark.parametrize("placement", ["name", "forms", "notes"])
def test_opposita_yam_does_not_inherit_villosa_identity(normalizer, enricher, placement):
    raw = _perilla_source_product("Wild Yam")
    source = raw["ingredientRows"][0]
    source.update(ingredientGroup="Wild Yam", uniiCode="IWY3IWX2G8")
    species = "wild yam (dioscorea opposita) rhizome standardised extract"
    source[placement] = [{"name": species}] if placement == "forms" else species
    clean = normalizer.normalize_product(raw)
    assert clean["activeIngredients"][0].get("canonical_id") not in {"wild_yam", "wild_yam_root"}
    enriched, _ = enricher.enrich_product(clean)
    row = enriched["ingredient_quality_data"]["ingredients"][0]
    assert row.get("canonical_id") not in {"wild_yam", "wild_yam_root"}
    assert row["scoreable_identity"] is False
    assert row["quantity"] == 150


@pytest.mark.parametrize("label", ["Wild Yam", "Wild Yam (Dioscorea villosa) root extract"])
def test_villosa_yam_identity_control(normalizer, enricher, label):
    raw = _perilla_source_product(label)
    raw["ingredientRows"][0].update(ingredientGroup="Wild Yam", uniiCode="IWY3IWX2G8")
    clean = normalizer.normalize_product(raw)
    assert clean["activeIngredients"][0]["canonical_id"] == "wild_yam"
    enriched, _ = enricher.enrich_product(clean)
    assert enriched["ingredient_quality_data"]["ingredients"][0]["canonical_id"] == "wild_yam"


@pytest.mark.parametrize("label", ["Valerian Root", "Valerian Root Extract"])
def test_botanical_species_veto_preserves_marker_standardization(normalizer, label):
    raw = _perilla_source_product(label)
    raw["ingredientRows"][0].update(ingredientGroup="Valerian", forms=[{
        "name": "Valerenic Acid", "prefix": "standardized to", "percent": 0.8,
        "category": "non-nutrient/non-botanical",
    }])
    clean = normalizer.normalize_product(raw)
    assert clean["activeIngredients"][0]["canonical_id"] == "valerian"
