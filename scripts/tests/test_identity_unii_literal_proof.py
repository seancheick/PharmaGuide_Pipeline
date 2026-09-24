"""A cleaner IQM identity proven by the label is not repaired to a broader DSLD
ingredient group, even on a row the enricher never re-matched (nested
display-only rows inside a non-therapeutic blend).

The public DSLD raw labels are stored under tests/fixtures, so CI always runs
the full clean -> enrich decision; the same checks rerun against the local
staging copy when it is present.

- 293400 Fiber Fusion Daily: "Oat Bran" carries UNII KQX236OK4U, IQM oat_bran's
  registered UNII, and its literal resolves to oat_bran. The DSLD group
  "Oat Fiber" used to rewrite it to the botanical oat_generic.
- 293280: the same "Oat Bran" row without a UNII keeps oat_bran through the
  reviewed canonical_equivalences relationship oat_generic > oat_bran.
- 306383: "Saccharomyces boulardii" carries the S. cerevisiae UNII (brewers
  yeast's), but its literal names a different identity, so its repair to
  saccharomyces_boulardii stands.
"""
import json
import os
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / 'fixtures'
STAGING = Path(os.environ.get('PG_DSLD_STAGING', '/Users/seancheick/Downloads/PharmaGuide_Datasets/staging/brands'))
CASES = {
    '293400': ('oat_bran_293400_raw.json', 'Oat Bran', 'oat_bran'),
    '293280': ('oat_bran_293280_raw.json', 'Oat Bran', 'oat_bran'),
    '306383': ('boulardii_306383_raw.json', 'Saccharomyces boulardii', 'saccharomyces_boulardii'),
}


def _enriched_row(raw, name):
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    product, _ = SupplementEnricherV3().enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))
    return next(r for r in product['ingredient_quality_data']['ingredients'] if r.get('name') == name)


@pytest.mark.parametrize('pid', sorted(CASES))
def test_label_proven_identity_survives_enrichment(pid):
    fixture, name, expected = CASES[pid]
    row = _enriched_row(json.loads((FIXTURES / fixture).read_text()), name)
    assert row['canonical_id'] == expected


@pytest.mark.parametrize('pid', sorted(CASES))
def test_same_result_on_the_local_staging_label(pid):
    raw = next(iter(sorted(STAGING.glob(f'*/{pid}.json'))), None) if STAGING.is_dir() else None
    if raw is None:
        pytest.skip('local staging label unavailable; the fixture test covers CI')
    _, name, expected = CASES[pid]
    assert _enriched_row(json.loads(raw.read_text()), name)['canonical_id'] == expected


def test_unii_proof_requires_the_parent_registered_unii():
    from enrich_supplements_v3 import SupplementEnricherV3
    qm = {'oat_bran': {'external_ids': {'unii': 'KQX236OK4U'}}, 'oat_generic': {'external_ids': {}}}
    proof = SupplementEnricherV3._row_unii_is_iqm_parent_unii
    assert proof({'uniiCode': 'kqx236ok4u'}, 'oat_bran', qm)
    assert proof({'raw_taxonomy': {'uniiCode': 'KQX236OK4U'}}, 'oat_bran', qm)
    assert not proof({'uniiCode': 'KQX236OK4U'}, 'oat_generic', qm)
    assert not proof({}, 'oat_bran', qm)
    assert not proof({'uniiCode': 'MA9CQJ3F7F'}, 'oat_bran', qm)
