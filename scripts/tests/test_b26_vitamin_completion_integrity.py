"""Regression test: Batch 26 — vitamin coverage completion.

Per IQM audit 2026-04-25 Step 4 Batch 26: 43 forms across 12 vitamin
parents. Mostly mechanical class-application for non-functional analog/
degraded/oxidized forms (~30) plus PK-rich biotin family (7/7 was null!)
and DHA/pyridoxine HCl/cis-MK-7 (PMID-anchored).

Four key findings:

1. BIOTIN PARENT (B7) — first-ever struct.value population. Zempleni
   1999 (PMID:10075337): ~100% F at pharmacologic oral doses; SMVT
   saturable (Said 2009 PMID:19056639). Yeast biotin = d-biotin.
   Biocytin requires biotinidase cleavage.

2. DHA (DEHYDROASCORBIC ACID) DIFFERENT TRANSPORTER — Rivas/Vera 2008
   (PMID:19391462): DHA → GLUT1/3/4 (NOT SVCT1/2 used by ascorbate).
   Wilson 2002 (PMID:12220624) review.

3. PYRIDOXINE HCl ~95% F — Bor 2003 (PMID:12507972): 100-fold PL rise
   at 40 mg/d. Pyridoxine glutamate class-equivalent post-dissociation.

4. CIS-MK-7 BIOLOGICALLY INACTIVE — Lal 2022 (PMID:35864383): "only
   the all-trans form is biologically active."

GHOST PMIDS / CLAIMS CAUGHT (6):
  • Mock & Malik 1992 biotin — could not verify, use Zempleni 1999
  • Vera 1993 DHA — should be Rivas/Vera 2008 PMID:19391462
  • Wilson 2005 DHA — actually Wilson 2002 PMID:12220624
  • Hansen 2001 pyridoxine — actually Hansen 1996 PMID:8857512
  • Bender 1992 B6 — actually Bender 1999 PMID:10341670
  • Schurgers 2007 cis-MK-7 — claim mismatch; tested all-trans only.
    Use Lal 2022 PMID:35864383 for cis-inactive claim.
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


# (parent, form, vmin, vmax, basis)
B26_BANDS_PK = [
    # PK-anchored (PMID-cited)
    ('vitamin_b6_pyridoxine', 'pyridoxine hydrochloride',     0.85, 0.95, 'Bor 2003'),
    ('vitamin_b6_pyridoxine', 'pyridoxine glutamate',         0.75, 0.90, 'class-equiv HCl'),
    ('vitamin_b7_biotin', 'd-biotin',                         0.85, 1.00, 'Zempleni 1999'),
    ('vitamin_b7_biotin', 'biotin from yeast',                0.80, 0.95, 'class-equiv d-biotin'),
    ('vitamin_b7_biotin', 'protein_bound_biotin',             0.70, 0.90, 'biotinidase cleavage'),
    ('vitamin_b7_biotin', 'dl-biotin (racemic)',              0.40, 0.55, 'L-isomer inactive'),
    ('vitamin_b7_biotin', 'vitamin b7 (unspecified)',         0.50, 0.70, 'biotin class baseline'),
    ('vitamin_c', 'dehydroascorbic acid',                     0.50, 0.80, 'Rivas/Vera 2008 GLUT'),
    ('vitamin_c', 'niacinamide ascorbate',                    0.70, 0.85, 'ascorbate class'),
    ('vitamin_k', 'vitamin K2 (cis form)',                    0.00, 0.10, 'Lal 2022 cis-inactive'),
]

B26_BANDS_MECHANICAL = [
    # Mechanical class-application (analogs, degraded, unspecified)
    ('vitamin_b1_thiamine', 'thiamine oxide',                 0.05, 0.20, 'oxidized partial'),
    ('vitamin_b1_thiamine', 'thiamine analog',                0.00, 0.05, 'non-functional'),
    ('vitamin_b1_thiamine', 'thiamine with thiaminase',       0.00, 0.02, 'thiaminase destroys'),
    ('vitamin_b1_thiamine', 'vitamin b1 (unspecified)',       0.40, 0.70, 'B1 saturable baseline'),
    ('vitamin_b2_riboflavin', 'riboflavin analog',            0.00, 0.05, 'non-functional'),
    ('vitamin_b2_riboflavin', 'light-degraded riboflavin',    0.00, 0.10, 'photodegradation'),
    ('vitamin_b2_riboflavin', 'vitamin b2 (unspecified)',     0.40, 0.65, 'B2 saturable baseline'),
    ('vitamin_b3_niacin', 'niacin analog',                    0.00, 0.05, 'non-functional'),
    ('vitamin_b3_niacin', 'heat-degraded niacin',             0.05, 0.20, 'partial heat degradation'),
    ('vitamin_b3_niacin', 'vitamin b3 (unspecified)',         0.40, 0.70, 'B3 baseline'),
    ('vitamin_b5_pantothenic', 'pantothenic_analog',          0.00, 0.05, 'non-functional'),
    ('vitamin_b5_pantothenic', 'vitamin b5 (unspecified)',    0.40, 0.65, 'B5 SMVT baseline'),
    ('vitamin_b6_pyridoxine', 'pyridoxine_oxide',             0.05, 0.20, 'oxidized partial'),
    ('vitamin_b6_pyridoxine', 'pyridoxine_analog',            0.00, 0.05, 'non-functional'),
    ('vitamin_b6_pyridoxine', 'vitamin b6 (unspecified)',     0.60, 0.85, 'B6 class baseline'),
    ('vitamin_b7_biotin', 'biotin_analog',                    0.00, 0.05, 'non-functional'),
    ('vitamin_b7_biotin', 'biotin degraded by avidin',        0.00, 0.02, 'avidin Kd ~10^-15'),
    ('vitamin_b9_folate', 'folate_analog',                    0.00, 0.05, 'non-functional'),
    ('vitamin_b9_folate', 'heat_degraded_folate',             0.00, 0.10, 'folate heat-labile'),
    ('vitamin_b9_folate', 'vitamin b9 (unspecified)',         0.30, 0.70, 'folate matrix-dep'),
    ('vitamin_a', 'vitamin a (unspecified)',                  0.50, 0.85, 'retinol class'),
    ('vitamin_c', 'vitamin C analogs (non-functional)',       0.00, 0.05, 'non-functional'),
    ('vitamin_c', 'vitamin c (unspecified)',                  0.50, 0.80, 'Levine 2001 sigmoidal'),
    ('vitamin_d', 'vitamin D analogs (non-functional)',       0.00, 0.05, 'non-functional'),
    ('vitamin_d', 'oxidized vitamin D',                       0.00, 0.10, 'degraded'),
    ('vitamin_d', 'vitamin d (unspecified)',                  0.40, 0.70, 'D3 fat-meal-dep'),
    ('vitamin_e', 'vitamin E analogs (non-functional)',       0.00, 0.05, 'non-functional'),
    ('vitamin_e', 'oxidized vitamin E',                       0.00, 0.10, 'chromanol oxidized'),
    ('vitamin_e', 'vitamin e (unspecified)',                  0.20, 0.50, 'tocopherol variable'),
    ('vitamin_k', 'menadione (K3)',                           0.00, 0.05, 'FDA-banned'),
    ('vitamin_k', 'vitamin K analogs (non-functional)',       0.00, 0.05, 'non-functional'),
    ('vitamin_k', 'oxidized vitamin K',                       0.00, 0.05, 'degraded'),
    ('vitamin_k', 'vitamin k (unspecified)',                  0.10, 0.80, 'K varies 10-80%'),
]


@pytest.mark.parametrize('pid,fname,vmin,vmax,basis', B26_BANDS_PK)
def test_b26_pk_anchored_in_band(iqm, pid, fname, vmin, vmax, basis):
    """PK-anchored forms must sit in evidence band."""
    form = iqm[pid]['forms'].get(fname)
    assert form is not None, f'{pid}::{fname} missing'
    val = (form.get('absorption_structured') or {}).get('value')
    assert val is not None, f'{pid}::{fname} struct.value should be populated'
    assert vmin <= val <= vmax, (
        f'{pid}::{fname}: struct.value={val} outside band [{vmin}, {vmax}]. '
        f'Basis: {basis}'
    )


@pytest.mark.parametrize('pid,fname,vmin,vmax,basis', B26_BANDS_MECHANICAL)
def test_b26_mechanical_in_band(iqm, pid, fname, vmin, vmax, basis):
    """Mechanical class-application forms must sit in expected band."""
    form = iqm[pid]['forms'].get(fname)
    assert form is not None, f'{pid}::{fname} missing'
    val = (form.get('absorption_structured') or {}).get('value')
    assert val is not None, f'{pid}::{fname} struct.value should be populated'
    assert vmin <= val <= vmax, (
        f'{pid}::{fname}: struct.value={val} outside band [{vmin}, {vmax}]. '
        f'Basis: {basis}'
    )


def test_biotin_parent_fully_populated(iqm):
    """B7 parent should now have ZERO null forms — first-ever full
    population per Zempleni 1999 (PMID:10075337) anchor.
    """
    forms = iqm['vitamin_b7_biotin']['forms']
    null_forms = [
        fn for fn, f in forms.items()
        if (f.get('absorption_structured') or {}).get('value') is None
    ]
    assert not null_forms, (
        f'vitamin_b7_biotin should have ZERO null forms after B26; '
        f'still null: {null_forms}'
    )


def test_biotin_zempleni_pmid_anchored(iqm):
    """d-biotin notes must reference Zempleni 1999 PMID:10075337."""
    form = iqm['vitamin_b7_biotin']['forms']['d-biotin']
    text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
    assert '10075337' in text, (
        f'd-biotin must cite Zempleni 1999 PMID:10075337. Text: {text[:300]}'
    )


def test_dl_biotin_half_of_d_biotin(iqm):
    """Racemic dl-biotin should be ~50% of d-biotin per L-isomer
    biological inactivity.
    """
    forms = iqm['vitamin_b7_biotin']['forms']
    d = (forms['d-biotin'].get('absorption_structured') or {}).get('value')
    racemic = (forms['dl-biotin (racemic)'].get('absorption_structured') or {}).get('value')
    assert d is not None and racemic is not None
    ratio = racemic / d
    assert 0.40 <= ratio <= 0.65, (
        f'racemic/d-biotin ratio = {ratio:.2f} should be ~0.50 '
        f'(L-isomer biologically inactive)'
    )


def test_dha_different_transporter_documented(iqm):
    """Dehydroascorbic acid notes must document GLUT vs SVCT distinction
    per Rivas/Vera 2008 (PMID:19391462).
    """
    form = iqm['vitamin_c']['forms']['dehydroascorbic acid']
    text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
    text_lower = text.lower()
    flag_phrases = ('glut1', 'glut3', 'glut4', 'glut family', 'glut transporters',
                    '19391462', 'rivas', 'vera 2008', 'differs from ascorbate',
                    'differs from svct')
    assert any(p in text_lower for p in flag_phrases), (
        f'DHA must document GLUT vs SVCT distinction (PMID:19391462). '
        f'Text: {text[:400]}'
    )


def test_cis_mk7_inactive_documented(iqm):
    """Vitamin K2 (cis form) notes must document biological inactivity
    per Lal 2022 (PMID:35864383).
    """
    form = iqm['vitamin_k']['forms']['vitamin K2 (cis form)']
    text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
    text_lower = text.lower()
    flag_phrases = ('all-trans', 'cis isomer', 'biologically inactive',
                    'biologically active', '35864383', 'lal 2022', 'all trans')
    assert any(p in text_lower for p in flag_phrases), (
        f'cis-MK-7 must document biological inactivity per Lal 2022 '
        f'(PMID:35864383). Text: {text[:300]}'
    )


def test_pyridoxine_hcl_pmid_anchored(iqm):
    """Pyridoxine HCl notes must cite Bor 2003 (PMID:12507972) or
    Bosy-Westphal 2001 (PMID:11786647).
    """
    form = iqm['vitamin_b6_pyridoxine']['forms']['pyridoxine hydrochloride']
    text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
    has_pmid = '12507972' in text or '11786647' in text
    assert has_pmid, (
        f'pyridoxine HCl must cite Bor 2003 (PMID:12507972) or '
        f'Bosy-Westphal 2001 (PMID:11786647). Text: {text[:400]}'
    )


def test_no_phantom_mock_malik_1992(iqm):
    """The unverified "Mock & Malik 1992" biotin citation must not appear
    as a live citation. Use Zempleni 1999 (PMID:10075337) instead.
    """
    forms = iqm['vitamin_b7_biotin']['forms']
    for fname, form in forms.items():
        text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
        if 'Mock' in text and 'Malik' in text and '1992' in text:
            assert any(neg in text.lower() for neg in
                       ('could not verify', 'ghost', 'unverified', 'wrong year',
                        'use zempleni')), (
                f'B7::{fname} cites unverified "Mock & Malik 1992" — '
                f'use Zempleni 1999 PMID:10075337 instead.'
            )


def test_class_authority_pmids_introduced_b26(iqm):
    """Verified class-authority PMIDs must each appear in IQM notes."""
    expected_pmids = {
        'PMID:10075337': 'Zempleni 1999 biotin',
        'PMID:19056639': 'Said 2009 SMVT',
        'PMID:19391462': 'Rivas/Vera 2008 DHA GLUT',
        'PMID:12220624': 'Wilson 2002 DHA',
        'PMID:12507972': 'Bor 2003 pyridoxine HCl',
        'PMID:35864383': 'Lal 2022 cis-MK-7',
    }
    full_text = ''
    for pid in ('vitamin_b6_pyridoxine', 'vitamin_b7_biotin', 'vitamin_c',
                'vitamin_k'):
        for form in iqm[pid]['forms'].values():
            full_text += (form.get('notes') or '') + ' '
            full_text += (form.get('absorption') or '') + ' '
    missing = [pmid for pmid in expected_pmids if pmid not in full_text]
    assert not missing, (
        f'Verified class-authority PMIDs missing: {missing}'
    )


def test_non_functional_forms_quality_poor(iqm):
    """All non-functional analog forms (struct.value=0.0) must have
    quality='poor' (the lowest valid enum band).
    """
    non_functional_forms = [
        ('vitamin_b1_thiamine', 'thiamine analog'),
        ('vitamin_b1_thiamine', 'thiamine with thiaminase'),
        ('vitamin_b2_riboflavin', 'riboflavin analog'),
        ('vitamin_b3_niacin', 'niacin analog'),
        ('vitamin_b5_pantothenic', 'pantothenic_analog'),
        ('vitamin_b6_pyridoxine', 'pyridoxine_analog'),
        ('vitamin_b7_biotin', 'biotin_analog'),
        ('vitamin_b7_biotin', 'biotin degraded by avidin'),
        ('vitamin_b9_folate', 'folate_analog'),
        ('vitamin_c', 'vitamin C analogs (non-functional)'),
        ('vitamin_d', 'vitamin D analogs (non-functional)'),
        ('vitamin_e', 'vitamin E analogs (non-functional)'),
        ('vitamin_k', 'menadione (K3)'),
        ('vitamin_k', 'vitamin K analogs (non-functional)'),
        ('vitamin_k', 'oxidized vitamin K'),
    ]
    for pid, fname in non_functional_forms:
        form = iqm[pid]['forms'].get(fname)
        if form is None:
            continue
        struct = form.get('absorption_structured') or {}
        v = struct.get('value')
        q = struct.get('quality')
        assert v is not None and v <= 0.05, (
            f'{pid}::{fname} should have value ≤0.05; got {v}'
        )
        assert q == 'poor', (
            f'{pid}::{fname} value={v} quality={q} — non-functional forms '
            f'with value <0.05 should have quality="poor" (lowest enum band)'
        )
