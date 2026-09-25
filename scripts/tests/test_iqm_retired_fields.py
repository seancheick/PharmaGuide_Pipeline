"""IQM `score` and `natural` are retired: IQM owns form quality through
`bio_score` alone, and no second quality value may exist or be read.

- No IQM form carries either field.
- The enricher and scorer run end to end over real labels with IQM forms that
  raise on any access to them.
- Enriched ingredient rows and matched forms, and the ingredients and matched
  forms of a detail blob built from them, carry neither field.
- Formulation reads bio_score only: a row without it has no form rating.

Product and pillar `score` fields are the V4 score and are not affected.
"""
import json
import logging
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).parent / 'fixtures'
RETIRED = ('score', 'natural')
# Labels that score end to end (a held product stops before the scoring
# modules, so it would not exercise their reads).
LABELS = ['form_association_176044_raw.json', 'form_association_318107_raw.json',
          'form_association_214477_raw.json', 'omega_amount_35718_raw.json']


def _iqm():
    return json.loads((SCRIPTS / 'data' / 'ingredient_quality_map.json').read_text())


def _forms(iqm):
    for parent, entry in iqm.items():
        if isinstance(entry, dict) and isinstance(entry.get('forms'), dict):
            for name, form in entry['forms'].items():
                yield parent, name, form


def test_no_iqm_form_carries_a_retired_field():
    offenders = [(p, n, k) for p, n, f in _forms(_iqm()) for k in RETIRED if k in f]
    assert offenders == []


READS = []


class _GuardedForm(dict):
    """Records every read of a retired field. It does not raise: the enricher
    catches broad exceptions, and a raise there would empty the product and
    let this test pass vacuously."""

    def __getitem__(self, key):
        if key in RETIRED:
            READS.append(key)
        return super().__getitem__(key)

    def get(self, key, default=None):
        if key in RETIRED:
            READS.append(key)
        return super().get(key, default)

    def __contains__(self, key):
        if key in RETIRED:
            READS.append(key)
        return super().__contains__(key)


@pytest.fixture(scope='module')
def guarded_enricher():
    from enrich_supplements_v3 import SupplementEnricherV3
    logging.disable(logging.INFO)
    enricher = SupplementEnricherV3()
    for entry in enricher.databases['ingredient_quality_map'].values():
        if isinstance(entry, dict) and isinstance(entry.get('forms'), dict):
            entry['forms'] = {name: _GuardedForm(form) for name, form in entry['forms'].items()}
    enricher._build_performance_indexes()  # indexes must point at the guarded forms
    return enricher


@pytest.mark.parametrize('label', LABELS)
def test_enrichment_and_scoring_never_read_a_retired_field(guarded_enricher, label):
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from score_supplements_v4 import score_product_v4
    raw = json.loads((FIXTURES / label).read_text())
    READS.clear()
    enriched, _ = guarded_enricher.enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))
    result = score_product_v4(enriched)
    rows = enriched['ingredient_quality_data']['ingredients']
    assert rows and any(r.get('matched_forms') for r in rows), 'label produced no matched forms'
    assert result.get('quality_score_v4_100') is not None
    assert READS == []
    for row in rows:
        assert not set(RETIRED) & set(row), row.get('name')
        for match in row.get('matched_forms') or []:
            assert not set(RETIRED) & set(match), row.get('name')


def test_formulation_reads_bio_score_only():
    from scoring_v4.modules.generic_helpers import bio_score_of
    assert bio_score_of({'score': 12}) is None
    assert bio_score_of({'bio_score': 9}) == 9.0


@pytest.mark.parametrize('label', LABELS)
def test_the_exported_detail_blob_carries_no_retired_field(guarded_enricher, label):
    from build_final_db import build_detail_blob
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from score_supplements_v4 import score_product_v4
    raw = json.loads((FIXTURES / label).read_text())
    enriched, _ = guarded_enricher.enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))
    blob = build_detail_blob(enriched, score_product_v4(enriched))
    rows = blob['ingredients']
    assert rows and any(r.get('matched_forms') for r in rows), 'blob exported no matched forms'
    for row in rows:
        assert not set(RETIRED) & set(row), row.get('name')
        for match in row.get('matched_forms') or []:
            assert not set(RETIRED) & set(match), row.get('name')
