"""Regression test: Batch 30 — Bucket B mechanical class-application.

28 forms across 14 parents. Mostly mechanical class-application from
established frameworks (no new PMID research):

1. ALGAE OIL (TG omega-3 class B9; architectural duplicate D8.1)
2. ASHWAGANDHA (Crominex pattern B21; liposomal-thin)
3. MUSHROOM CLASS (B1 framework; chitin shell barrier)
4. PROBIOTIC STRAIN (B18 framework; live-organism)
5. NAD PRECURSORS (architectural overlap NR/NMN — D8.2 pending)
6. RNA/DNA digestion barrier (similar to SOD protein-digestion B24)
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


B30_BANDS = [
    # algae_oil
    ('algae_oil', 'algae oil (dha)',                                0.80, 0.90, 'TG omega-3 B9'),
    ('algae_oil', 'algae oil (unspecified)',                        0.78, 0.88, 'algae class'),
    # ashwagandha (unspecified populated; liposomal stays null)
    ('ashwagandha', 'ashwagandha (unspecified)',                    0.15, 0.30, 'withanolide B21'),
    # mushroom class
    ('auricularia', 'auricularia fruiting body extract',            0.05, 0.15, 'mushroom B1'),
    ('auricularia', 'auricularia (unspecified)',                    0.03, 0.12, 'mushroom class'),
    ('button_mushroom', 'button mushroom fruiting body extract',    0.05, 0.15, 'mushroom B1'),
    ('button_mushroom', 'button mushroom (unspecified)',            0.03, 0.12, 'mushroom class'),
    ('royal_sun_blazei', 'agaricus blazei fruiting body extract',   0.05, 0.15, 'mushroom B1'),
    ('royal_sun_blazei', 'royal sun blazei (unspecified)',          0.03, 0.12, 'mushroom class'),
    # probiotic
    ('bifidobacterium_longum', 'bifidobacterium longum infantis ni313', 0.05, 0.20, 'probiotic B18'),
    ('bifidobacterium_longum', 'bifidobacterium longum infantis bi-26', 0.05, 0.20, 'probiotic B18'),
    ('kefir_culture', 'kefir culture (fermented)',                  0.05, 0.20, 'live organism B18'),
    ('kefir_culture', 'kefir (unspecified)',                        0.03, 0.15, 'live organism B18'),
    # coconut_water
    ('coconut_water', 'coconut water powder',                       0.80, 0.95, 'electrolyte solution'),
    ('coconut_water', 'coconut water (unspecified)',                0.80, 0.95, 'electrolyte solution'),
    # dicalcium phosphate
    ('dicalcium_phosphate', 'dicalcium phosphate dihydrate',        0.20, 0.30, 'Ca phosphate B27'),
    ('dicalcium_phosphate', 'di-calcium phosphate (unspecified)',   0.20, 0.30, 'Ca phosphate'),
    # sarsaparilla
    ('sarsaparilla', 'sarsaparilla root extract',                   0.10, 0.25, 'saponin class-poor'),
    ('sarsaparilla', 'sarsaparilla (unspecified)',                  0.05, 0.20, 'saponin class'),
    # zinc
    ('zinc', 'zinc oxide',                                          0.25, 0.35, 'Wapnir 1985 ZnO'),
    ('zinc', 'zinc (unspecified)',                                  0.30, 0.65, 'Zn class baseline'),
    # nad
    ('nad_precursors', 'oxidized nad+ precursor',                   0.00, 0.05, 'oxidative degradation'),
    ('nad_precursors', 'nad+ precursors (unspecified)',             0.30, 0.70, 'NR/NMN class'),
    # rna_dna
    ('rna_dna', 'nucleic acid complex',                             0.00, 0.10, 'NA digestion barrier'),
    ('rna_dna', 'rna/dna (nucleic acids) (unspecified)',            0.00, 0.10, 'NA digestion barrier'),
    # chasteberry
    ('chasteberry', 'chasteberry powder',                           0.05, 0.15, 'vitex class'),
    ('chasteberry', 'chasteberry (unspecified)',                    0.05, 0.15, 'vitex class'),
]

B30_NULL_FORMS = [
    ('ashwagandha', 'liposomal ashwagandha', 'liposomal-thin pattern'),
]


@pytest.mark.parametrize('pid,fname,vmin,vmax,basis', B30_BANDS)
def test_b30_value_in_band(iqm, pid, fname, vmin, vmax, basis):
    """Each form's struct.value must sit in evidence band."""
    form = iqm[pid]['forms'].get(fname)
    assert form is not None, f'{pid}::{fname} missing'
    val = (form.get('absorption_structured') or {}).get('value')
    assert val is not None, f'{pid}::{fname} struct.value should be populated'
    assert vmin <= val <= vmax, (
        f'{pid}::{fname}: struct.value={val} outside band [{vmin}, {vmax}]. '
        f'Basis: {basis}'
    )


@pytest.mark.parametrize('pid,fname,reason', B30_NULL_FORMS)
def test_b30_null_form(iqm, pid, fname, reason):
    """Each null form must have struct.value=null."""
    form = iqm[pid]['forms'].get(fname)
    assert form is not None, f'{pid}::{fname} missing'
    val = (form.get('absorption_structured') or {}).get('value')
    assert val is None, f'{pid}::{fname} should be null — {reason}'


def test_zinc_oxide_below_zinc_citrate(iqm):
    """ZnO must rank below soluble Zn salts (Wapnir 1985 baseline)."""
    forms = iqm['zinc']['forms']
    zno = (forms['zinc oxide'].get('absorption_structured') or {}).get('value')
    citrate = (forms.get('zinc citrate', {}).get('absorption_structured') or {}).get('value')
    if citrate is not None:
        assert zno < citrate, (
            f'zinc oxide ({zno}) should rank below zinc citrate ({citrate}) — '
            f'lower solubility per Wapnir 1985.'
        )


def test_nucleic_acid_digestion_barrier_documented(iqm):
    """RNA/DNA forms must document the digestion-barrier framework."""
    forms = iqm['rna_dna']['forms']
    for fname, form in forms.items():
        text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
        text_lower = text.lower()
        flag_phrases = ('digestion barrier', 'digested', 'nucleotide', 'nuclease',
                        'does not survive', 'not survive')
        assert any(p in text_lower for p in flag_phrases), (
            f'rna_dna::{fname} must document NA digestion barrier. Text: {text[:300]}'
        )


def test_algae_oil_matches_omega3_TG_class(iqm):
    """algae_oil DHA must match TG omega-3 class baseline (B9)."""
    val = (iqm['algae_oil']['forms']['algae oil (dha)']
           .get('absorption_structured') or {}).get('value')
    fish_natural_tg = (iqm['fish_oil']['forms']['natural triglyceride']
                       .get('absorption_structured') or {}).get('value')
    assert val is not None and fish_natural_tg is not None
    assert abs(val - fish_natural_tg) <= 0.05, (
        f'algae_oil DHA ({val}) must match fish_oil natural TG ({fish_natural_tg}) '
        f'within 0.05 — TG omega-3 class.'
    )
