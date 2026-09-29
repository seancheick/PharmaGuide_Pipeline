"""Phase-2 verified mineral forms and vanadium parent-scoped sources."""

import json
from pathlib import Path


IQM = json.loads(
    (Path(__file__).parents[1] / "data" / "ingredient_quality_map.json").read_text()
)


def test_verified_mineral_salts_are_named_without_an_absorption_premium():
    expected = {
        "calcium": {
            "calcium acetate": 3,
            "calcium sulfate": 3,
            "calcium chloride": 3,
            "calcium glycerophosphate": 3,
        },
        "magnesium": {"magnesium glycerophosphate": 2},
        "potassium": {"potassium iodate": 7},
        "silicon": {
            "sodium metasilicate": 8,
            "magnesium trisilicate": 8,
            "calcium silicate (as silicon source)": 8,
        },
        "silica": {"sodium metasilicate (as silica source)": 8},
    }
    for parent_id, forms in expected.items():
        for form_id, score in forms.items():
            form = IQM[parent_id]["forms"][form_id]
            assert form["bio_score"] == score
            assert "PubChem CID" in form["notes"]


def test_vanadium_nutrient_parent_reads_sources_without_stealing_compound_identity():
    expected = {
        "vanadyl sulfate (as vanadium source)": "vanadyl sulfate",
        "bis(maltolato)oxovanadium (as vanadium source)": "BMOV",
        "bis(picolinato)oxovanadium (as vanadium source)": "BPOV",
        "vanadium amino acid chelate": "vanadium amino acid chelate",
        "vanadium aspartate (as vanadium source)": "vanadium aspartate",
        "vanadium citrate (as vanadium source)": "vanadium citrate",
    }
    forms = IQM["vanadium"]["forms"]
    for form_id, printed in expected.items():
        assert forms[form_id]["bio_score"] == 7
        assert printed in forms[form_id]["source_form_aliases"]

    assert IQM["vanadyl_sulfate"]["external_ids"]["unii"] == "6DU9Y533FA"
    assert IQM["vanadium"]["external_ids"]["unii"] == "00J9J9XKDE"
