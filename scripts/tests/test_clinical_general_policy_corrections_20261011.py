import json
from pathlib import Path
DATA=Path(__file__).resolve().parents[1]/'data'


def test_selected_adulteration_database_is_not_market_prevalence():
    rows={r['id']:r for r in json.loads((DATA/'proprietary_blends.json').read_text())['proprietary_blend_concerns']}
    assert '317' in rows['BLEND_WEIGHT_LOSS']['notes']
    assert '776 adulterated weight loss' not in rows['BLEND_WEIGHT_LOSS']['notes']
    assert 'highest contamination risk' not in rows['BLEND_TESTOSTERONE']['notes']


def test_lgg_copy_does_not_claim_a_universal_dose():
    rows={r['id']:r for r in json.loads((DATA/'proprietary_blends.json').read_text())['proprietary_blend_concerns']}
    assert 'requires ≥10B CFU' not in rows['BLEND_PROBIOTIC']['notes']


def test_metabolaid_final_blend_marker_scope_matches_studied_material():
    rows={r['id']:r for r in json.loads((DATA/'proprietary_blends.json').read_text())['proprietary_blend_concerns']}
    assert '3.5%' in rows['BLEND_METABOLAID']['notes']
    assert '15%' in rows['BLEND_METABOLAID']['notes']
    assert '≥25%' not in rows['BLEND_METABOLAID']['notes']
