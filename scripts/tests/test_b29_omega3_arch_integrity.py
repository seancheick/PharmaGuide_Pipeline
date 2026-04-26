"""Regression test: Batch 29 — omega_3 / epa_dha architectural duplicates.

Per IQM audit 2026-04-25 Step 4 Batch 29: 12 forms across 2 parents
(omega_3 + epa_dha — both architectural duplicates of fish_oil).

Class-equivalence applied from fish_oil baselines:
  • rTG/natural TG/EE/unspecified — direct match to fish_oil
  • emulsified — modest premium over plain TG
  • algal DHA — class-equiv to algae_oil parent
  • ETA / 20:3n-3 — minor n-3 fatty acids; TG class
  • 14-HDHA / 17-HDHA / 18-HEPE — SPM precursors; class-distinct
    framework with conservative range pending dedicated audit

ARCHITECTURAL CONSOLIDATION PROPOSAL flagged for Dr Pham — see review
doc Section D8 for cross-file migration plan (omega_3/epa_dha referenced
in synergy_cluster, interaction_rules, CAERS, percentile_categories).
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


B29_BANDS = [
    # omega_3 fish-oil-class duplicates
    ('omega_3', 'omega-3 triglyceride (rTG)',                       0.85, 0.95, 'fish_oil rTG class'),
    ('omega_3', 'omega-3 natural triglyceride',                     0.80, 0.90, 'fish_oil TG class'),
    ('omega_3', 'omega-3 ethyl ester (EE)',                         0.65, 0.75, 'fish_oil EE class'),
    ('omega_3', 'omega-3 (unspecified)',                            0.70, 0.85, 'fish_oil unspec'),
    ('omega_3', 'omega-3 emulsified',                               0.85, 0.95, 'emulsified premium'),
    # omega_3 non-fish-oil forms
    ('omega_3', 'algal omega-3 DHA',                                0.80, 0.90, 'algae_oil class'),
    ('omega_3', 'eicosatetraenoic acid (ETA, 20:4n-3)',             0.80, 0.90, 'minor n-3 TG'),
    ('omega_3', 'eicosatrienoic acid (20:3n-3)',                    0.80, 0.90, 'minor n-3 TG'),
    # SPM precursors — class-distinct
    ('omega_3', '14-hydroxy-docosahexaenoic acid (14-HDHA)',        0.30, 0.50, 'SPM precursor'),
    ('omega_3', '17-hydroxy-docosahexaenoic acid (17-HDHA)',        0.30, 0.50, 'SPM precursor'),
    ('omega_3', '18-hydroxy-eicosapentaenoic acid (18-HEPE)',       0.30, 0.50, 'SPM precursor'),
    # epa_dha
    ('epa_dha', 'epa dha (standard)',                               0.70, 0.85, 'class-equiv fish_oil unspec'),
]


@pytest.mark.parametrize('pid,fname,vmin,vmax,basis', B29_BANDS)
def test_b29_value_in_band(iqm, pid, fname, vmin, vmax, basis):
    """Each form's struct.value must sit in evidence band."""
    form = iqm[pid]['forms'].get(fname)
    assert form is not None, f'{pid}::{fname} missing'
    val = (form.get('absorption_structured') or {}).get('value')
    assert val is not None, f'{pid}::{fname} struct.value should be populated'
    assert vmin <= val <= vmax, (
        f'{pid}::{fname}: struct.value={val} outside band [{vmin}, {vmax}]. '
        f'Basis: {basis}'
    )


def test_omega3_rTG_matches_fish_oil_rTG(iqm):
    """omega-3 rTG must equal fish_oil rTG (within 0.05) — class-equivalence."""
    omega3_rtg = (iqm['omega_3']['forms']['omega-3 triglyceride (rTG)']
                  .get('absorption_structured') or {}).get('value')
    fish_rtg = (iqm['fish_oil']['forms']['triglyceride (rTG) form']
                .get('absorption_structured') or {}).get('value')
    assert omega3_rtg is not None and fish_rtg is not None
    assert abs(omega3_rtg - fish_rtg) <= 0.05, (
        f'omega_3 rTG ({omega3_rtg}) must match fish_oil rTG ({fish_rtg}) '
        f'within 0.05 — architectural duplicate.'
    )


def test_omega3_EE_matches_fish_oil_EE(iqm):
    """omega-3 EE must equal fish_oil EE (within 0.05)."""
    omega3_ee = (iqm['omega_3']['forms']['omega-3 ethyl ester (EE)']
                 .get('absorption_structured') or {}).get('value')
    fish_ee = (iqm['fish_oil']['forms']['ethyl ester']
               .get('absorption_structured') or {}).get('value')
    assert omega3_ee is not None and fish_ee is not None
    assert abs(omega3_ee - fish_ee) <= 0.05, (
        f'omega_3 EE ({omega3_ee}) must match fish_oil EE ({fish_ee}) '
        f'within 0.05.'
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


def test_omega3_architectural_duplicate_documented(iqm):
    """omega_3 forms must reference the architectural-duplicate flag for
    Dr Pham review.
    """
    forms = iqm['omega_3']['forms']
    populated_forms = [
        (fn, f) for fn, f in forms.items()
        if (f.get('absorption_structured') or {}).get('value') is not None
        and 'B29 audit' in (f.get('notes') or '')
    ]
    # At least one populated form should reference architectural-duplicate
    found = False
    for fn, form in populated_forms:
        text = (form.get('notes') or '') + ' '
        text += ((form.get('absorption_structured') or {}).get('notes') or '')
        if any(p in text.lower() for p in ('architectural', 'duplicate', 'dr pham')):
            found = True
            break
    assert found, (
        'omega_3 parent should reference architectural-duplicate flag in '
        'at least one B29-audited form notes.'
    )
