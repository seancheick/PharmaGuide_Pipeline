"""Regression test: Batch 29 — omega_3 minor n-3 / SPM precursors.

UPDATED 2026-04-25 (post-Batch 38 architectural merge per Dr Pham D8.1):

Original B29 tests validated the architectural-duplicate state (omega_3 +
epa_dha vs fish_oil). That state has been RESOLVED by Batch 38:
  • 5 fish-oil-class forms migrated from omega_3 → fish_oil
  • algal DHA migrated to algae_oil
  • flaxseed (ALA) migrated to flaxseed
  • epa_dha parent DELETED (1 form merged into fish_oil)

omega_3 is now the focused parent for "Minor Omega-3 Fatty Acids & SPM
Precursors" — only minor n-3 fatty acids and oxidized SPM precursors remain.

This test now validates:
  1. omega_3 retains only minor + SPM forms (5 total)
  2. epa_dha parent deleted
  3. SPM precursors class-consistent
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

IQM_PATH = Path(__file__).parent.parent / 'data' / 'ingredient_quality_map.json'


@pytest.fixture(scope='module')
def iqm():
    with IQM_PATH.open() as f:
        return json.load(f)


# Forms that should REMAIN in omega_3 after architectural merge
B29_REMAINING = [
    ('omega_3', 'eicosatetraenoic acid (ETA, 20:4n-3)',             0.80, 0.90, 'minor n-3 TG'),
    ('omega_3', 'eicosatrienoic acid (20:3n-3)',                    0.80, 0.90, 'minor n-3 TG'),
    ('omega_3', '14-hydroxy-docosahexaenoic acid (14-HDHA)',        0.30, 0.50, 'SPM precursor'),
    ('omega_3', '17-hydroxy-docosahexaenoic acid (17-HDHA)',        0.30, 0.50, 'SPM precursor'),
    ('omega_3', '18-hydroxy-eicosapentaenoic acid (18-HEPE)',       0.30, 0.50, 'SPM precursor'),
]


@pytest.mark.parametrize('pid,fname,vmin,vmax,basis', B29_REMAINING)
def test_b29_remaining_forms_in_band(iqm, pid, fname, vmin, vmax, basis):
    """Each remaining minor/SPM form must sit in evidence band."""
    form = iqm[pid]['forms'].get(fname)
    assert form is not None, f'{pid}::{fname} missing'
    val = (form.get('absorption_structured') or {}).get('value')
    assert val is not None, f'{pid}::{fname} struct.value should be populated'
    assert vmin <= val <= vmax, (
        f'{pid}::{fname}: struct.value={val} outside band [{vmin}, {vmax}]. '
        f'Basis: {basis}'
    )


def test_b38_architectural_merge_complete(iqm):
    """Batch 38 architectural merge must be complete:
    1. epa_dha parent deleted
    2. omega_3 has only 5 forms (minor + SPM)
    3. fish_oil has the migrated forms
    """
    # epa_dha deleted
    assert 'epa_dha' not in iqm, 'epa_dha parent should be deleted post-merge'

    # omega_3 only contains minor + SPM forms
    omega3 = iqm['omega_3']
    forms = omega3.get('forms', {})
    assert len(forms) == 5, (
        f'omega_3 should have 5 forms post-merge (minor n-3 + 3 SPM); '
        f'has {len(forms)}: {list(forms.keys())}'
    )
    expected = {
        'eicosatetraenoic acid (ETA, 20:4n-3)',
        'eicosatrienoic acid (20:3n-3)',
        '14-hydroxy-docosahexaenoic acid (14-HDHA)',
        '17-hydroxy-docosahexaenoic acid (17-HDHA)',
        '18-hydroxy-eicosapentaenoic acid (18-HEPE)',
    }
    assert set(forms.keys()) == expected, (
        f'omega_3 forms do not match expected set. Got: {set(forms.keys())}'
    )

    # omega_3 description updated
    desc = omega3.get('description', '')
    assert 'minor' in desc.lower() or 'spm' in desc.lower(), (
        f'omega_3 description should reflect minor/SPM scope: "{desc[:200]}"'
    )

    # fish_oil should have at least the original 7 + emulsified (8)
    fish_oil_forms = iqm['fish_oil'].get('forms', {})
    assert 'emulsified' in fish_oil_forms, (
        'fish_oil should have new "emulsified" form post-merge'
    )


def test_spm_precursors_class_consistent(iqm):
    """All 3 SPM precursors must have same value (class-equivalent)."""
    forms = iqm['omega_3']['forms']
    spm_values = [
        (forms['14-hydroxy-docosahexaenoic acid (14-HDHA)']
            .get('absorption_structured') or {}).get('value'),
        (forms['17-hydroxy-docosahexaenoic acid (17-HDHA)']
            .get('absorption_structured') or {}).get('value'),
        (forms['18-hydroxy-eicosapentaenoic acid (18-HEPE)']
            .get('absorption_structured') or {}).get('value'),
    ]
    assert all(v is not None for v in spm_values)
    assert max(spm_values) - min(spm_values) <= 0.05, (
        f'SPM precursors must be class-consistent within 0.05. Values: {spm_values}'
    )


def test_aliases_migrated_to_fish_oil(iqm):
    """Aliases from migrated omega_3 forms must now appear in fish_oil forms."""
    fish_oil_forms = iqm['fish_oil']['forms']

    # rTG migration: fish_oil::triglyceride (rTG) form should have additional aliases
    rtg_form = fish_oil_forms.get('triglyceride (rTG) form')
    assert rtg_form is not None
    rtg_aliases = rtg_form.get('aliases', [])
    # Should have grown from original 3 to ~12 with omega_3 merge
    assert len(rtg_aliases) >= 8, (
        f'fish_oil::triglyceride (rTG) form aliases should have grown via merge; '
        f'has {len(rtg_aliases)}: {rtg_aliases[:5]}'
    )

    # epa_dha migration: fish_oil::fish oil (unspecified) should have epa_dha aliases
    unspec_form = fish_oil_forms.get('fish oil (unspecified)')
    assert unspec_form is not None
    unspec_aliases = unspec_form.get('aliases', [])
    assert len(unspec_aliases) >= 50, (
        f'fish_oil::fish oil (unspecified) aliases should be ≥50 post-merge; '
        f'has {len(unspec_aliases)}.'
    )
