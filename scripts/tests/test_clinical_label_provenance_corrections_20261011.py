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
