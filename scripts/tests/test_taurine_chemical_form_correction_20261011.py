"""A chemistry-specific powder is distinct from generated nondisclosure."""
import json
from pathlib import Path
from scoring_reference_resolver import unknown_form_quality

def test_free_taurine_anchor_and_liposomal_control_are_not_generic_nondisclosure():
    parent=json.loads((Path(__file__).parents[1]/'data/ingredient_quality_map.json').read_text())['taurine']
    assert parent['forms']['free taurine']['bio_score']==11
    assert parent['forms']['liposomal taurine']['bio_score']==11
    assert {'pure taurine','taurine powder','l-taurine'} <= set(parent['forms']['free taurine']['aliases'])
    unknown=unknown_form_quality(parent)
    assert unknown['bio_score']==10
    assert unknown['form_id'] is None and unknown['form'] is None


def test_oral_plasma_kinetics_does_not_establish_absolute_taurine_fraction():
    parent=json.loads((Path(__file__).parents[1]/'data/ingredient_quality_map.json').read_text())['taurine']
    row=parent['forms']['free taurine']
    assert row['absorption_structured']['value'] is None
    assert '95' not in row['absorption']
    assert 'near-complete' not in row['notes']
    assert row['bio_score']==11
