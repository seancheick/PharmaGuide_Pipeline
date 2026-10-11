import json
from pathlib import Path
DATA=Path(__file__).resolve().parents[1]/'data'


def test_known_manufacturer_events_are_not_described_as_absent():
    rows={r['id']:r for r in json.loads((DATA/'top_manufacturers_data.json').read_text())['top_manufacturers']}
    expected={'MANUF_NATURE_MADE':'2016','MANUF_NORDIC_NATURALS':'2024','MANUF_GARDEN_OF_LIFE':'2016','MANUF_ORGAIN':'2023','MANUF_DOUBLE_WOOD':'2020','MANUF_METAGENICS':'2013','MANUF_ORTHO_MOLECULAR':'2023'}
    for key,year in expected.items():
        text=' '.join(rows[key]['evidence'])
        assert year in text
        assert not any(p in text.lower() for p in ['no recalls','zero warning letters','no history of fda','no significant recalls','no regulatory penalties or recalls','no fda warning letters or recalls'])


def test_seed_founders_and_adviser_roles_are_distinct():
    rows=json.loads((DATA/'top_manufacturers_data.json').read_text())['top_manufacturers']
    row=next(r for r in rows if r['id']=='MANUF_SEED_HEALTH')
    text=' '.join(row['evidence'])
    assert 'Ara Katz' in text and 'Raja Dhir' in text
    assert 'Founded by Dr. Gregor Reid' not in text


def test_negative_deduction_explanation_uses_addition_and_current_owner():
    data=json.loads((DATA/'manufacture_deduction_expl.json').read_text())
    assert '100 + ' in data['calculation_rules']['step_8']
    assert 'generic_manufacturer.py' in data['total_deduction_cap_graduated']['applies_at']
    assert 'ephedra mislabeled as ma huang' not in json.dumps(data['violation_categories'])
