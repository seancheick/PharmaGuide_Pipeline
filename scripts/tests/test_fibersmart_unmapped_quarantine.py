"""FiberSMART is a resistant dextrin (FDA GRN 1045, tapioca), not resistant
starch, and no reviewed canonical is the same substance. DSLD filed the printed
"FiberSmart Resistant Starch" row as a childless blend header, which hid the
unmapped active from mapped coverage and let both products ship scored.

The reviewed product_label_corrections entries keep the printed name and
correct only the structural category, so each product's single unmapped active
fails mapped coverage and the product stays NOT_SCORED (out of the catalog)
until a resistant-dextrin identity is reviewed. Real public DSLD records.
"""
import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / 'fixtures'


@pytest.mark.parametrize('pid', ['233404', '233406'])
def test_fibersmart_row_is_an_unmapped_active_and_the_product_is_quarantined(pid):
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
    assert not iqd.get('canonical_id') and not iqd.get('mapped_identity')
    scored = build_scored_artifact(enriched)
    gate = scored['_v4_completeness_gate']
    assert 'mapped_coverage' in gate['missing_fields'] and gate['is_live_eligible'] is False
    assert scored['verdict'] == 'NOT_SCORED'
