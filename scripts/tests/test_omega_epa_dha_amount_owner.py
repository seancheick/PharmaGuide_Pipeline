"""EPA+DHA per serving has one owner (scoring_input_contract.epa_dha_amounts_per_serving), and
the label facts it reads are one serving column and never a carrier oil.

Real DSLD records (tests/fixtures/omega_amount_*_raw.json):

- 224615: the Total Omega-3 block (EPA 586, DHA 456 per 2 softgels) is printed
  again per 1 softgel. The columns used to add to 1,563 mg; the label serving
  is 1,042 mg.
- 206295: the fish-oil block is printed per 2 mL, 1 mL and 0.25 mL (age bands);
  it used to add to 325 mg DHA; the canonical 2 mL column is 200 mg.
- 35718: EPA and DHA under krill oil and under fish oil are two sources in one
  serving, so they still add (884 mg).
- 77225: "life'sDHA Oil 600 mg" is the algal source oil nested under DHA 200 mg;
  a reviewed label correction keeps its mass out of EPA+DHA (was 800 mg).
"""
import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / 'fixtures'
EXPECTED_PER_SERVING = {'224615': 1042.0, '206295': 200.0, '35718': 884.0, '77225': 200.0}


def _pipeline(pid):
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    raw = json.loads((FIXTURES / f'omega_amount_{pid}_raw.json').read_text())
    enriched, _ = SupplementEnricherV3().enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))
    return enriched


@pytest.mark.parametrize('pid', sorted(EXPECTED_PER_SERVING))
def test_epa_dha_per_serving_on_real_labels(pid):
    from scoring_input_contract import epa_dha_amounts_per_serving
    from scoring_v4.modules.omega_formulation import _epa_dha_and_oil_mass_mg
    enriched = _pipeline(pid)
    epa, dha, combined = epa_dha_amounts_per_serving(enriched)
    assert max(epa + dha, combined) == EXPECTED_PER_SERVING[pid]
    assert _epa_dha_and_oil_mass_mg(enriched)['epa_dha_mg'] == EXPECTED_PER_SERVING[pid]


def test_repeated_block_keeps_every_column_as_a_variant():
    enriched = _pipeline('206295')
    dha = [r for r in enriched['activeIngredients'] if r.get('canonical_id') == 'dha']
    assert len(dha) == 1
    variants = dha[0]['raw_taxonomy']['quantityVariants']
    assert [(v['quantity'], v['serving_size_quantity']) for v in variants] == [(200, 2), (100, 1), (25, 0.25)]
    assert [v.get('selected_for_analysis') for v in variants] == [True, None, None]


def _column(order, size, qty, children=()):
    return {'name': 'Total Omega-3 Fatty Acids', 'category': 'fatty acid', 'ingredientGroup': 'Omega-3',
            'ingredientId': 1, 'uniiCode': None, 'forms': [], 'alternateNames': [],
            'quantity': [{'servingSizeOrder': order, 'servingSizeQuantity': size,
                          'servingSizeUnit': 'Softgel(s)', 'quantity': qty, 'unit': 'mg'}],
            'nestedRows': [dict(child, quantity=[{'servingSizeOrder': order, 'servingSizeQuantity': size,
                                                   'servingSizeUnit': 'Softgel(s)', 'quantity': amount, 'unit': 'mg'}])
                           for child, amount in children]}


EPA = {'name': 'EPA', 'category': 'fatty acid', 'ingredientGroup': 'EPA', 'ingredientId': 2, 'uniiCode': None,
       'forms': [], 'alternateNames': [], 'nestedRows': []}
DHA = dict(EPA, name='DHA', ingredientGroup='DHA', ingredientId=3)


def test_matching_blocks_in_different_columns_merge_node_by_node():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    rows = [_column(1, 2, 1000, [(EPA, 600), (DHA, 400)]), _column(1, 1, 500, [(EPA, 300), (DHA, 200)])]
    merged = EnhancedDSLDNormalizer._merge_alternate_serving_rows(rows)
    assert len(merged) == 1
    assert [q['quantity'] for q in merged[0]['quantity']] == [1000, 500]
    assert [[q['quantity'] for q in child['quantity']] for child in merged[0]['nestedRows']] == [[600, 300], [400, 200]]


def test_blocks_that_differ_or_share_a_column_stay_separate():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    merge = EnhancedDSLDNormalizer._merge_alternate_serving_rows
    # Different children: two different panels, not one panel twice.
    assert len(merge([_column(1, 2, 1000, [(EPA, 600)]), _column(1, 1, 500, [(DHA, 200)])])) == 2
    # Same column: two sources in one serving add; they are not alternatives.
    assert len(merge([_column(1, 2, 1000, [(EPA, 600)]), _column(1, 2, 500, [(EPA, 300)])])) == 2


def test_omega_pillars_read_the_public_owner_only():
    """Dose, Evidence and Formulation read the contract's public provider; no
    omega pillar imports another pillar's private helpers or re-derives trust."""
    import re
    modules = Path(__file__).resolve().parents[1] / 'scoring_v4' / 'modules'
    for name in ('omega_dose', 'omega_evidence', 'omega_formulation'):
        text = (modules / f'{name}.py').read_text()
        assert 'epa_dha_amounts_per_serving' in text
        assert not re.search(r'from scoring_v4\.modules\.omega_\w+ import \(?\s*_', text), name
        assert '_trustworthy_epa_dha_row' not in text and 'EPA_DHA_SOURCE_RE' not in text, name
