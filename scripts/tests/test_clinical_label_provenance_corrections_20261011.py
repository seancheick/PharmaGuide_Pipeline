import json
from pathlib import Path

DATA=Path(__file__).resolve().parents[1]/'data/curated_overrides/product_label_corrections.json'


def test_current_label_provenance_does_not_claim_a_nonexistent_printed_unit():
    rows=json.loads(DATA.read_text())['corrections']
    assert 'retinyl acetate' in rows['261915']['evidence']
    assert "PDF prints 675 mcg" in rows['299069']['evidence']
    for key in ['31063','801']:
        assert 'prints 75 mg' in rows[key]['evidence']
        assert 'independent' in rows[key]['evidence']
    for key in ['223563','223572']:
        assert 'prints 900 RAE mg' in rows[key]['evidence']
        assert 'three-glyph' not in rows[key]['evidence']
        assert 'inference' in rows[key]['evidence']


import copy
import pytest
from enhanced_normalizer import EnhancedDSLDNormalizer


@pytest.fixture(scope="module")
def normalizer():
    return EnhancedDSLDNormalizer()


@pytest.mark.parametrize("product_id,name,value,unit", [
    ("31063", "Molybdenum", 75, "mg"),
    ("801", "Molybdenum", 75, "mg"),
    ("223563", "Vitamin A", 900, "mg RAE"),
    ("223572", "Vitamin A", 900, "mg RAE"),
    ("223563", "Vitamin D3", 100, "mg"),
    ("223572", "Vitamin D3", 50, "mg"),
])
def test_reviewed_unit_conflict_preserves_printed_source(normalizer, product_id, name, value, unit):
    rows = [{"name": name, "quantity": [{"quantity": value, "unit": unit}]}]
    corrected = normalizer._apply_label_corrections(copy.deepcopy(rows), product_id)[0]
    assert corrected["quantity"] == rows[0]["quantity"]
    assert corrected["_label_scoring_disposition"] == "unresolved_unit"
    # A changed manufacturer row is not automatically held under an old receipt.
    changed = [{"name": name, "quantity": [{"quantity": value + 1, "unit": unit}]}]
    assert normalizer._apply_label_corrections(copy.deepcopy(changed), product_id) == changed
    assert normalizer._apply_label_corrections(copy.deepcopy(rows), "999999") == rows
