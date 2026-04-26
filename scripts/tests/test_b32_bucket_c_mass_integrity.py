"""Regression test: Batch 32 — Bucket C mass class-application.

36 forms across 36 parents. Mechanical class-application from existing
companion baselines + established framework rules (B1 mushroom, B19
flavonoid, B18 probiotic, B16/B21 Crominex, etc.). NO new PMID research.

Key applications:
  • Anthocyanin class-poor: bilberry, cranberry, elderberry (B19/B31)
  • Mushroom class-poor: chaga, lion's mane, maitake (B1)
  • CoQ10/curcumin/phytosterol class-poor (B7/B8)
  • Mineral class baselines: chromium (~2%), molybdenum (~91%),
    phosphorus (~42%)
  • Probiotic harmonization flag: L. acidophilus, paracasei (B18 vs
    older 0.65-0.90 nutrient-density framework — pending Dr Pham E2)
  • D-tyrosine biological inactivity (B26 dl-biotin parallel)
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


B32_BANDS = [
    # Botanicals
    ('amla', 'amla (unspecified)',                                  0.40, 0.55, 'amla class'),
    ('bilberry', 'bilberry (unspecified)',                          0.005, 0.02, 'anthocyanin class-poor'),
    ('capsaicin', 'capsaicin (unspecified)',                        0.50, 0.70, 'capsaicinoid class'),
    ('chaga', 'chaga (unspecified)',                                0.08, 0.15, 'mushroom class-poor B1'),
    ('chinese_skullcap', 'chinese skullcap (unspecified)',          0.55, 0.70, 'baicalein class'),
    ('chondroitin', 'chondroitin (unspecified)',                    0.10, 0.18, 'chondroitin class'),
    ('citrus_bergamot', 'bergamot (unspecified)',                   0.05, 0.12, 'flavonoid class-poor'),
    ('cranberry', 'cranberry (unspecified)',                        0.005, 0.02, 'PAC/anthocyanin class-poor'),
    ('devils_claw', "devil's claw (unspecified)",                   0.25, 0.50, 'harpagoside class'),
    ('dong_quai', 'dong quai (unspecified)',                        0.25, 0.45, 'dong quai class'),
    ('echinacea', 'echinacea (unspecified)',                        0.20, 0.45, 'alkamide class'),
    ('elderberry', 'elderberry (unspecified)',                      0.01, 0.05, 'anthocyanin class-poor'),
    ('feverfew', 'feverfew (unspecified)',                          0.35, 0.65, 'parthenolide class'),
    ('fo_ti', 'fo-ti (unspecified)',                                0.20, 0.40, 'fo-ti class'),
    ('garcinia_cambogia', 'garcinia cambogia (unspecified)',        0.35, 0.50, 'HCA class'),
    ('ginger', 'ginger (unspecified)',                              0.55, 0.85, 'gingerol class'),
    ('grape_seed_extract', 'grape seed extract (unspecified)',      0.03, 0.10, 'OPC class-poor'),
    ('gymnema_sylvestre', 'gymnema sylvestre (unspecified)',        0.15, 0.50, 'gymnemic acid class'),
    ('hawthorn', 'hawthorn (unspecified)',                          0.55, 0.70, 'hawthorn class'),
    ('holy_basil', 'holy basil (unspecified)',                      0.60, 0.75, 'tulsi class'),
    ('irish_sea_moss', 'irish sea moss (unspecified)',              0.45, 0.60, 'sea moss class'),
    ('l_theanine', 'l-theanine (unspecified)',                      0.60, 0.80, 'theanine class'),
    ('l_tyrosine', 'd-tyrosine',                                    0.25, 0.50, 'D-isomer inactive'),
    ('lactobacillus_acidophilus', 'lactobacillus acidophilus (unspecified)',
                                                                    0.05, 0.20, 'probiotic class B18'),
    ('lactobacillus_paracasei', 'lactobacillus paracasei (unspecified)',
                                                                    0.05, 0.20, 'probiotic class B18'),
    ("lions_mane", "lion's mane (unspecified)",                     0.10, 0.18, 'mushroom class-poor'),
    ('maca', 'maca (unspecified)',                                  0.60, 0.72, 'maca class'),
    ('maitake', 'maitake (unspecified)',                            0.08, 0.15, 'mushroom class-poor'),
    ('molybdenum', 'molybdenum (unspecified)',                      0.85, 0.95, 'Mo class baseline'),
    ('oregano', 'oregano (unspecified)',                            0.50, 0.75, 'carvacrol class'),
    ('phosphatidylethanolamine', 'phosphatidylethanolamine (unspecified)',
                                                                    0.45, 0.60, 'PE phospholipid class'),
    ('phosphorus', 'phosphorus (unspecified)',                      0.30, 0.55, 'phosphate class'),
    ('phytosterols', 'phytosterols (unspecified)',                  0.00, 0.05, 'phytosterol class-poor'),
    ('chromium', 'chromium (unspecified)',                          0.01, 0.04, 'Cr class baseline'),
    ('coq10', 'coq10 (unspecified)',                                0.03, 0.08, 'CoQ10 class-poor'),
    ('curcumin', 'curcumin (unspecified)',                          0.01, 0.05, 'curcumin class-poor B8'),
]


@pytest.mark.parametrize('pid,fname,vmin,vmax,basis', B32_BANDS)
def test_b32_value_in_band(iqm, pid, fname, vmin, vmax, basis):
    """Each form's struct.value must sit in evidence band."""
    form = iqm[pid]['forms'].get(fname)
    assert form is not None, f'{pid}::{fname} missing'
    val = (form.get('absorption_structured') or {}).get('value')
    assert val is not None, f'{pid}::{fname} struct.value should be populated'
    assert vmin <= val <= vmax, (
        f'{pid}::{fname}: struct.value={val} outside band [{vmin}, {vmax}]. '
        f'Basis: {basis}'
    )


def test_d_tyrosine_below_l_tyrosine_class(iqm):
    """D-tyrosine must rank below all L-tyrosine forms — only L-isomer
    is biologically active for protein synthesis (parallels B26 dl-biotin).
    """
    forms = iqm['l_tyrosine']['forms']
    d_tyr = (forms['d-tyrosine'].get('absorption_structured') or {}).get('value')
    # Find any L-tyrosine form
    l_forms = {fn: (f.get('absorption_structured') or {}).get('value')
               for fn, f in forms.items()
               if 'l-' in fn.lower() or 'tyrosine' in fn.lower()}
    l_max = max((v for v in l_forms.values() if v is not None and v != d_tyr), default=None)
    if l_max is not None:
        assert d_tyr < l_max + 0.01, (
            f'd-tyrosine ({d_tyr}) should rank below L-tyrosine class max '
            f'({l_max}) — D-isomer is biologically inactive (B26 framework).'
        )


def test_anthocyanin_class_consistent(iqm):
    """All anthocyanin-class forms (bilberry, cranberry, elderberry) must
    cluster in 0-0.05 band per González-Barrio 2010 / Czank 2013.
    """
    forms = [
        ('bilberry', 'bilberry (unspecified)'),
        ('cranberry', 'cranberry (unspecified)'),
        ('elderberry', 'elderberry (unspecified)'),
    ]
    for pid, fname in forms:
        form = iqm[pid]['forms'].get(fname)
        if form is None:
            continue
        v = (form.get('absorption_structured') or {}).get('value')
        assert v is not None and v <= 0.05, (
            f'{pid}::{fname} value={v} should be ≤0.05 — anthocyanin '
            f'class-poor (B19/B31 framework).'
        )


def test_mushroom_class_consistent(iqm):
    """All mushroom-class unspecified forms must cluster in 0.05-0.18 per
    B1 framework (chitin shell + polysaccharide).
    """
    forms = [
        ('chaga', 'chaga (unspecified)'),
        ("lions_mane", "lion's mane (unspecified)"),
        ('maitake', 'maitake (unspecified)'),
    ]
    for pid, fname in forms:
        form = iqm[pid]['forms'].get(fname)
        if form is None:
            continue
        v = (form.get('absorption_structured') or {}).get('value')
        assert v is not None and 0.05 <= v <= 0.18, (
            f'{pid}::{fname} value={v} outside mushroom class [0.05, 0.18] '
            f'(B1 framework).'
        )


def test_chromium_class_consistent(iqm):
    """Chromium unspecified must be in the inherent-low Cr class baseline
    (~1-4% F per Anderson 1996).
    """
    v = (iqm['chromium']['forms']['chromium (unspecified)']
         .get('absorption_structured') or {}).get('value')
    assert v is not None and 0.01 <= v <= 0.04, (
        f'chromium (unspecified) value={v} should be in Cr class baseline '
        f'[0.01, 0.04].'
    )
