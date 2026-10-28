"""Creatine MagnaPower (Albion/Balchem magnesium creatine chelate) composition.

The chelate supplies magnesium as well as creatine. Sources (receipt:
scripts/audits/creatine_magnapower_20261028/research.md):
  * Albion/Balchem product data sheet 03465, rev. 22-AUG-2024: magnesium
    not less than 8.0 % (guaranteed analysis); typical 9,033 mg magnesium and
    50 g creatine per 100 g as-is (lot averages).
  * U.S. Patent 6,114,379 (Albion), which the label 220208 cites for the
    chelate: preferred 1:1 creatine-to-magnesium molar ratio.

The composition is recorded in the form's notes only. A label's magnesium
total is not partitioned automatically: the supplemental share remains a
review lead, not a pipeline calculation.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
IQM_PATH = ROOT / 'data' / 'ingredient_quality_map.json'
FIXTURE = Path(__file__).parent / 'fixtures' / 'creatine_magnapower_220208_raw.json'


@pytest.fixture(scope='module')
def chelate_form():
    iqm = json.loads(IQM_PATH.read_text())
    return iqm['creatine_monohydrate']['forms']['creatine magnesium chelate']


def test_notes_record_manufacturer_magnesium_specification(chelate_form):
    notes = chelate_form['notes']
    for fact in ('product data sheet 03465', '22 Aug 2024', 'not less than 8.0%',
                 '9,033 mg magnesium', '50 g creatine', 'U.S. Patent 6,114,379',
                 '1:1 creatine-to-magnesium molar ratio'):
        assert fact in notes, fact
    # The existing absorption limit stays recorded; the run-together typo is gone.
    assert 'did not administer this chelate' in notes
    assert 'measure99%absolute' not in notes


def test_notes_keep_magnesium_amount_a_label_fact(chelate_form):
    notes = chelate_form['notes']
    assert 'not partitioned automatically' in notes
    assert chelate_form['absorption_structured']['value'] is None


@pytest.fixture(scope='module')
def rebuilt_mass_xp():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    logging.disable(logging.INFO)
    raw = json.loads(FIXTURE.read_text())
    enriched, _ = SupplementEnricherV3().enrich_product(
        EnhancedDSLDNormalizer().normalize_product(raw))
    return enriched['ingredient_quality_data']['ingredients']


def test_label_magnesium_total_is_not_partitioned(rebuilt_mass_xp):
    rows = {row['name']: row for row in rebuilt_mass_xp}
    magnesium = rows['Magnesium']
    assert (magnesium['canonical_id'], magnesium['quantity'], magnesium['unit']) == (
        'magnesium', 540.0, 'mg')
    chelate = rows['Creatine MagnaPower']
    assert (chelate['canonical_id'], chelate['matched_form']) == (
        'creatine_monohydrate', 'creatine magnesium chelate')
    assert (chelate['quantity'], chelate['unit']) == (2.5, 'Gram(s)')
    assert [row['name'] for row in rebuilt_mass_xp if row.get('canonical_id') == 'magnesium'] == [
        'Magnesium']
