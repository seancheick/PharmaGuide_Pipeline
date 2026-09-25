"""A row's form shares hold only forms of that row's own parent
(enrich_supplements_v3._match_multi_form).

Real DSLD labels (tests/fixtures/form_association_*_raw.json):

- 15823: Magnesium lists "Cranberry powder" beside its carbonate and hydroxide.
  The cranberry token was read as magnesium citrate (bio 14) because the
  parent fallback followed the word "powder"; the row scored 7.7.
- 47815: Vitamin C lists "Acerola Extract", the botanical source, as a sixth
  form; its share was scored as an unknown 5.0.
- 12012: Thiamine lists "Vitamin B1", the nutrient's own name, as a form.
- 176044: Leucine lists the whey proteins it comes from as forms.
- Controls: 47815 Magnesium and 17118 Calcium name real salts the IQM does not
  carry (arginate, ascorbate, D-pantothenate); those stay in the shares.
"""
import json
import logging
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / 'fixtures'


@pytest.fixture(scope='module')
def enricher():
    from enrich_supplements_v3 import SupplementEnricherV3
    logging.disable(logging.INFO)
    return SupplementEnricherV3()


def _row(enricher, pid, name):
    from enhanced_normalizer import EnhancedDSLDNormalizer
    raw = json.loads((FIXTURES / f'form_association_{pid}_raw.json').read_text())
    enriched, _ = enricher.enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))
    return next(r for r in enriched['ingredient_quality_data']['ingredients'] if r.get('name') == name)


def _forms(row):
    return sorted((m['raw_form_text'], m['form_key']) for m in row.get('matched_forms') or [])


def test_a_botanical_listed_under_a_mineral_is_not_a_form_of_it(enricher):
    row = _row(enricher, '15823', 'Magnesium')
    assert _forms(row) == [('Magnesium Carbonate', 'magnesium carbonate'),
                           ('Magnesium Hydroxide', 'magnesium hydroxide')]
    assert row['bio_score'] == 4.5


def test_a_botanical_source_does_not_dilute_the_named_forms(enricher):
    row = _row(enricher, '47815', 'Vitamin C')
    assert 'Acerola Extract' not in {m['raw_form_text'] for m in row['matched_forms']}
    assert row['bio_score'] == 11.4


def test_the_nutrients_own_name_is_not_a_second_form(enricher):
    assert _row(enricher, '12012', 'Thiamine')['bio_score'] == 10.0


def test_source_proteins_are_not_forms_of_an_amino_acid(enricher):
    row = _row(enricher, '176044', 'Leucine')
    assert [text for text, _ in _forms(row)] == ['L-Leucine']
    assert row['bio_score'] == 14.0


@pytest.mark.parametrize('pid, name, expected', [('47815', 'Magnesium', 8.2), ('17118', 'Calcium', 6.3)])
def test_named_salts_the_iqm_lacks_still_count(enricher, pid, name, expected):
    assert _row(enricher, pid, name)['bio_score'] == expected


def test_parent_fallback_never_scores_above_the_unspecified_form(enricher):
    iqm = enricher.databases['ingredient_quality_map']
    match = enricher._match_quality_map('Cranberry powder', 'Cranberry powder', iqm,
                                        _form_extraction_attempt=True, preferred_parent='magnesium',
                                        cleaner_canonical_id='magnesium')
    assert match['form_id'] == 'magnesium (unspecified)'
    assert match['bio_score'] == iqm['magnesium']['forms']['magnesium (unspecified)']['bio_score']
