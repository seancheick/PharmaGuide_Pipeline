"""A form the label does not disclose has one owner:
scoring_reference_resolver.unknown_form_quality, consumed by the enricher's
parent fallback, its unmatched form shares, and the scoring contract's
blend-anchor rows.

- An authored unspecified IQM form wins, chosen deterministically.
- Otherwise max(0, lowest eligible named bio_score - 1), identity-neutral:
  no form_id, so no named form's notes, absorption, evidence or consumer copy
  can attach. HMB, L-leucine, Acacia catechu and chlorophyll have no
  unspecified form; an undisclosed form of them once became HMB-Ca, "L-leucine
  powder", "wood and bark extract" and "natural chlorophyll".
"""
import json
import logging
from pathlib import Path

import pytest

from scoring_reference_resolver import unknown_form_quality

IQM = json.loads((Path(__file__).resolve().parents[1] / 'data' / 'ingredient_quality_map.json').read_text())

# parent -> (lowest named bio_score, the named form the fallback used to invent)
DERIVED = {
    'hmb': (13, 'hmb calcium salt (hmb-ca)'),
    'l_leucine': (14, 'l-leucine powder'),
    'acacia_catechu': (9, 'acacia catechu wood and bark extract'),
    'chlorophyll': (3, 'natural chlorophyll'),
}


@pytest.fixture(scope='module')
def enricher():
    from enrich_supplements_v3 import SupplementEnricherV3
    logging.disable(logging.INFO)
    return SupplementEnricherV3()


@pytest.mark.parametrize('parent', sorted(DERIVED))
def test_without_an_authored_unspecified_form_the_unknown_is_lowest_minus_one(parent):
    lowest, _ = DERIVED[parent]
    assert min(f['bio_score'] for f in IQM[parent]['forms'].values()) == lowest
    unknown = unknown_form_quality(IQM[parent])
    assert unknown == {'form_id': None, 'form': None, 'bio_score': lowest - 1.0,
                       'basis': 'derived_lowest_named_minus_one'}


def test_an_authored_unspecified_form_wins():
    unknown = unknown_form_quality(IQM['calcium'])
    assert (unknown['form_id'], unknown['bio_score'], unknown['basis']) == (
        'calcium (unspecified)', 6.0, 'authored_unspecified')


def test_generic_vitamin_d_never_becomes_d2_by_form_order():
    parent = IQM['vitamin_d']
    shuffled = {**parent, 'forms': dict(reversed(list(parent['forms'].items())))}
    assert unknown_form_quality(parent)['form_id'] == unknown_form_quality(shuffled)['form_id'] \
        == 'vitamin d (unspecified)'


def test_the_derived_value_never_goes_below_zero():
    parent = {'forms': {'x': {'bio_score': 0}}}
    assert unknown_form_quality(parent)['bio_score'] == 0.0


def test_a_source_preparation_is_not_an_eligible_named_form():
    parent = {'forms': {'plain': {'bio_score': 8},
                        'from shellfish': {'bio_score': 2, 'alias_identity_scope': 'source_preparation'}}}
    assert unknown_form_quality(parent)['bio_score'] == 7.0


@pytest.mark.parametrize('parent', sorted(DERIVED))
@pytest.mark.parametrize('label', ['Zqx Blend', 'Zqx Powder'])
def test_the_enricher_fallback_names_no_form(enricher, parent, label):
    lowest, invented = DERIVED[parent]
    match = enricher._match_quality_map(label, label, enricher.databases['ingredient_quality_map'],
                                        _form_extraction_attempt=True, preferred_parent=parent,
                                        cleaner_canonical_id=parent)
    assert match['match_tier'] == 'cleaner_canonical_parent'
    assert match['form_id'] is None and match['fallback_form_name'] is None
    assert match['form_name'] == 'unspecified' != invented
    assert (match['notes'], match['absorption']) == (None, None)
    assert match['bio_score'] == lowest - 1.0


@pytest.mark.parametrize('parent', sorted(DERIVED))
def test_the_scoring_contract_fallback_names_no_form(parent):
    from scoring_input_contract import _form_quality_from_iqm
    lowest, _ = DERIVED[parent]
    quality = _form_quality_from_iqm(parent, {'name': 'Zqx Blend'})
    assert 'matched_form' not in quality
    assert quality['bio_score'] == lowest - 1.0


def test_the_scoring_contract_uses_the_authored_unspecified_form():
    # The lowest named digestive-enzyme form is "oxidized enzymes" (2).
    from scoring_input_contract import _form_quality_from_iqm
    quality = _form_quality_from_iqm('digestive_enzymes', {'name': 'Zqx Blend'})
    assert (quality['matched_form'], quality['bio_score']) == ('digestive enzymes (unspecified)', 5.0)


@pytest.mark.parametrize('parent', sorted(DERIVED))
def test_the_export_attaches_no_form_copy_to_a_derived_unknown(parent):
    from build_final_db import _derive_form_evidence, _derive_form_note
    lowest, _ = DERIVED[parent]
    row = {'canonical_id': parent, 'matched_form': 'unspecified', 'matched_forms': [],
           'bio_score': lowest - 1.0}
    iqm_index = {k: v for k, v in IQM.items() if k != '_metadata'}
    assert _derive_form_note(row, iqm_index) == (None, None)
    assert _derive_form_evidence(row, iqm_index) is None


def test_a_disclosed_form_is_read_not_replaced_by_a_default(enricher):
    # 318107 "L-Tyrosine (as N-Acetyl-L-Tyrosine)", UNII DA8G610ZO5 (GSRS:
    # Acetyl L-tyrosine). The hyphenated token missed the NALT form; the old
    # fallback then named D-tyrosine (2), and without it the bare name read as
    # L-tyrosine powder (14). NALT is 8.
    from enhanced_normalizer import EnhancedDSLDNormalizer
    raw = json.loads((Path(__file__).parent / 'fixtures' / 'form_association_318107_raw.json').read_text())
    enriched, _ = enricher.enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))
    row = next(r for r in enriched['ingredient_quality_data']['ingredients'] if r.get('name') == 'L-Tyrosine')
    assert [m['form_key'] for m in row['matched_forms']] == ['n-acetyl l-tyrosine']
    assert row['bio_score'] == 8.0


@pytest.mark.parametrize('token, parent, form', [('N-Acetyl-L-Tyrosine', 'l_tyrosine', 'n-acetyl l-tyrosine'),
                                                 ('N-Acetyl-L-Cysteine', 'nac', 'nac powder')])
def test_hyphenated_acetyl_forms_resolve_by_alias(enricher, token, parent, form):
    match = enricher._match_quality_map(token, token, enricher.databases['ingredient_quality_map'],
                                        _form_extraction_attempt=True, preferred_parent=parent,
                                        cleaner_canonical_id=parent)
    assert (match['form_id'], match['match_tier']) == (form, 'exact')
