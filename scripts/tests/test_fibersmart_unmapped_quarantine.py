"""FiberSMART is a resistant dextrin (FDA GRAS Notice 1045: resistant dextrin
from tapioca, Anderson Global Group, no-questions letter 2022-08-26), not
resistant starch. DSLD filed the printed "FiberSmart Resistant Starch" row as a
childless blend header, which hid it from mapped coverage; the reviewed
product_label_corrections entries keep the printed name and correct only the
structural category.

Until 2026-09-27 no reviewed identity existed and the products stayed
quarantined. IQM fiber now carries a "resistant dextrin" form (Sean,
2026-09-27: add the missing identity), so the row maps to it, never to
resistant starch, and the products score. Real public DSLD records.
"""
import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / 'fixtures'


@pytest.mark.parametrize('pid', ['233404', '233406'])
def test_fibersmart_row_is_resistant_dextrin_and_the_product_scores(pid):
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    from scoring_v4.scored_artifact import build_scored_artifact
    raw = json.loads((FIXTURES / f'fibersmart_{pid}_raw.json').read_text())
    cleaned = EnhancedDSLDNormalizer().normalize_product(raw)
    row = next(r for r in cleaned['activeIngredients'] if r.get('name') == 'FiberSmart Resistant Starch')
    assert row.get('raw_category') == 'fiber' and row.get('ingredientGroup') == 'Resistant Dextrin'
    assert row.get('cleaner_row_role') != 'blend_header_total'
    enriched, _ = SupplementEnricherV3().enrich_product(cleaned)
    iqd = next(r for r in enriched['ingredient_quality_data']['ingredients'] if r.get('name') == 'FiberSmart Resistant Starch')
    # Resolved as dietary fiber (a Supplement Facts fiber line), never as resistant starch.
    assert iqd.get('canonical_id') == 'fiber' and iqd.get('identity_disposition') == 'clean'
    assert 'resistant starch' not in str(iqd.get('form_id') or '')
    scored = build_scored_artifact(enriched)
    assert scored['quality_score_status'] == 'scored'
