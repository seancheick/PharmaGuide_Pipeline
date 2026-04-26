"""Regression test: Batch 33 — Bucket C continuation (25 forms, 25 parents).

Mechanical class-application from companion baselines + prior batch
frameworks. NO new PMID research.

Key applications:
  • Mushroom class-poor (B1): shiitake, turkey tail
  • Reishi triterpene class (higher than mushroom B1 due to lipid-
    soluble actives — ganoderic acids)
  • Bioflavonoid class-poor (B19): quercetin, pine bark extract
  • Resveratrol class (rapid glucuronidation): 0.30
  • Pomegranate ellagitannin → urolithin metabolite class
  • Mineral class baselines: copper ~40%, potassium ~85%
  • Choline class ~90%, TMG ~85%
  • Probiotic harmonization (B18 vs older nutrient-density framework):
    streptococcus_salivarius
  • Probiotics (unspecified) — set null with framework-mismatch flag
    (mixed live-organism + fermented-substrate companions)
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


B33_BANDS = [
    ('chlorella', 'chlorella (unspecified)',                        0.10, 0.50, 'cell wall class'),
    ('choline', 'choline (unspecified)',                            0.82, 0.97, 'choline class'),
    ('copper', 'copper (unspecified)',                              0.20, 0.65, 'Cu class baseline'),
    ('garlic', 'garlic (unspecified)',                              0.10, 0.55, 'garlic prep-dep'),
    ('ginkgo', 'ginkgo (unspecified)',                              0.25, 0.65, 'ginkgo class'),
    ('ginseng', 'ginseng (unspecified)',                            0.00, 0.30, 'ginsenoside class'),
    ('glutathione', 'glutathione (unspecified)',                    0.10, 0.25, 'GSH class-poor'),
    ('phosphatidylserine', 'phosphatidylserine (unspecified)',      0.35, 0.70, 'PS class'),
    ('pine_bark_extract', 'pine bark extract (unspecified)',        0.02, 0.06, 'OPC class-poor'),
    ('pomegranate', 'pomegranate (unspecified)',                    0.35, 0.50, 'urolithin class'),
    ('potassium', 'potassium (unspecified)',                        0.78, 0.92, 'K class'),
    ('pqq', 'pqq (pyrroloquinoline quinone) (unspecified)',         0.30, 0.65, 'PQQ class'),
    ('quercetin', 'quercetin (unspecified)',                        0.02, 0.10, 'quercetin class-poor'),
    ('reishi', 'reishi (unspecified)',                              0.65, 0.85, 'reishi triterpene'),
    ('resveratrol', 'resveratrol (unspecified)',                    0.25, 0.45, 'resveratrol class'),
    ('rhodiola', 'rhodiola (unspecified)',                          0.28, 0.38, 'rosavin class'),
    ('rosemary', 'rosemary (unspecified)',                          0.50, 0.70, 'rosmarinic class'),
    ('saw_palmetto', 'saw palmetto (unspecified)',                  0.30, 0.75, 'lipid extract class'),
    ('shiitake', 'shiitake (unspecified)',                          0.10, 0.15, 'mushroom class-poor B1'),
    ('stinging_nettle', 'stinging nettle (unspecified)',            0.55, 0.70, 'nettle class'),
    ('streptococcus_salivarius', 'streptococcus salivarius (unspecified)',
                                                                    0.60, 0.80, 'probiotic harmonization'),
    ('sulforaphane', 'sulforaphane (unspecified)',                  0.10, 0.55, 'myrosinase-dep class'),
    ('tmg_betaine', 'tmg (trimethylglycine) (unspecified)',         0.75, 0.95, 'TMG class'),
    ('turkey_tail', 'turkey tail (unspecified)',                    0.10, 0.13, 'mushroom class-poor B1'),
]

B33_NULL_FORMS = [
    ('probiotics', 'probiotics (unspecified)',                      'framework-mismatch'),
]


@pytest.mark.parametrize('pid,fname,vmin,vmax,basis', B33_BANDS)
def test_b33_value_in_band(iqm, pid, fname, vmin, vmax, basis):
    """Each populated form must sit in evidence band."""
    form = iqm[pid]['forms'].get(fname)
    assert form is not None, f'{pid}::{fname} missing'
    val = (form.get('absorption_structured') or {}).get('value')
    assert val is not None, f'{pid}::{fname} struct.value should be populated'
    assert vmin <= val <= vmax, (
        f'{pid}::{fname}: struct.value={val} outside band [{vmin}, {vmax}]. '
        f'Basis: {basis}'
    )


@pytest.mark.parametrize('pid,fname,reason', B33_NULL_FORMS)
def test_b33_null_form(iqm, pid, fname, reason):
    """Each null form must have struct.value=null."""
    form = iqm[pid]['forms'].get(fname)
    assert form is not None, f'{pid}::{fname} missing'
    val = (form.get('absorption_structured') or {}).get('value')
    assert val is None, f'{pid}::{fname} should be null — {reason}'


def test_mushroom_class_consistent_b33(iqm):
    """All mushroom-class forms (shiitake, turkey tail) must cluster in
    0.05-0.15 band per B1 framework.
    """
    forms = [
        ('shiitake', 'shiitake (unspecified)'),
        ('turkey_tail', 'turkey tail (unspecified)'),
    ]
    for pid, fname in forms:
        form = iqm[pid]['forms'].get(fname)
        if form is None:
            continue
        v = (form.get('absorption_structured') or {}).get('value')
        assert v is not None and 0.05 <= v <= 0.15, (
            f'{pid}::{fname} value={v} outside mushroom class [0.05, 0.15] '
            f'(B1 framework).'
        )


def test_probiotics_unspecified_framework_mismatch_documented(iqm):
    """probiotics (unspecified) must have null + framework-mismatch flag."""
    form = iqm['probiotics']['forms']['probiotics (unspecified)']
    val = (form.get('absorption_structured') or {}).get('value')
    assert val is None, 'probiotics (unspecified) should be null'
    text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
    text_lower = text.lower()
    flag_phrases = ('framework_mismatch', 'framework mismatch', 'pending',
                    'harmonization', 'mixed', 'b18', 'b22', 'category-error')
    assert any(p in text_lower for p in flag_phrases), (
        f'probiotics (unspecified) must document framework-mismatch + '
        f'pending Dr Pham. Text: {text[:300]}'
    )
