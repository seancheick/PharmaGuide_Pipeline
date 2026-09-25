"""B12 delivery wording must not claim an unmeasured mucosal absorption premium."""
import json
from pathlib import Path
import pytest

@pytest.mark.parametrize('name', ['methylcobalamin sublingual', 'cyanocobalamin sublingual'])
def test_sublingual_b12_has_no_invented_fraction_or_if_bypass(name):
    iqm=json.loads((Path(__file__).parents[1]/'data/ingredient_quality_map.json').read_text())
    form=iqm['vitamin_b12_cobalamin']['forms'][name]
    absorption=form['absorption_structured']
    assert absorption.get('value') is None
    assert absorption.get('range_low') is None
    assert absorption.get('range_high') is None
    assert absorption['quality']=='unknown'
    text=(form['absorption']+' '+form['notes']).lower()
    for obsolete in ['10-40%', 'bypasses if', 'partial first-pass bypass', 'delivery to improve absorption', 'modest premium']:
        assert obsolete not in text
    assert '14616423' in text
    assert 'no significant difference' in text
