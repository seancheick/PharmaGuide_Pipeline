"""Regression test: Batch 22 — small molecules + AAs + prebiotics + BHB.

Per IQM audit 2026-04-25 Step 4 Batch 22: 10 forms across 8 parents.
Four major findings:

1. PREBIOTICS CATEGORY ERROR (3rd confirmation after manuka Batch 18 +
   organ extracts Batch 20). Inulin + larch AG not systemically absorbed;
   colonic fermentation to SCFAs.

2. BHB SALTS ≠ CREATINE SALTS PATTERN. Stubbs 2017 (PMID:29163194):
   salts deliver ~50% inactive L-βHB; ester delivers pure D-βHB.

3. BCAA peptides confirm Silk pattern (Batch 20) — kinetic faster but
   extent same ~90%.

4. D-CHIRO-INOSITOL = MYO-INOSITOL class-equivalent (Lepore 2021).

Verified PMIDs:
  PMID:6966118  Magnussen 1980 — 5-HTP F 69.2%
  PMID:29163194 Stubbs 2017 — BHB ester vs salt
  PMID:11258045 Rigalli 2001 — NaF PK
  PMID:15877886 Roberfroid 2005 — inulin non-digestible
  PMID:28165863 Holscher 2017 — DEFINITIVE prebiotic category-error
  PMID:18727553 Rutherfurd 2008 — methionine bioavailability
  PMID:34202683 Lepore 2021 — inositol class-equivalence

Ghost references caught:
  • Stubbs PMID:28261556 (actually Korean diet paper) → use PMID:29163194
  • DPA PMID:29618497 (actually SCFA letter)
  • "Crittenden 2007 inulin" — NOT FOUND
  • "Larrosa 2010 inulin" — NOT FOUND
  • TUDCA human oral F — NO robust PMID exists
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

IQM_PATH = Path(__file__).parent.parent / 'data' / 'ingredient_quality_map.json'


@pytest.fixture(scope='module')
def iqm():
    with IQM_PATH.open() as f:
        return json.load(f)


# (parent, form, vmin, vmax, basis)
B22_BANDS_VALUED = [
    ('5_htp', '5-htp (unspecified)',                                    0.47, 0.84,  'Magnussen 1980'),
    ('tudca', 'tudca (standard)',                                       0.30, 0.50,  'mechanistic inference'),
    ('inositol', 'd-chiro-inositol',                                    0.70, 0.95,  'class-equiv to myo'),
    ('d_beta_hydroxybutyrate_bhb', 'd beta hydroxybutyrate bhb (standard)', 0.80, 0.90,  'Stubbs 2017 salt-form'),
    ('methionine', 'l-methionine',                                       0.90, 1.00,  'B0AT1/PepT1 class'),
    ('branched_chain_amino_acids', 'branched chain amino acids (standard)', 0.85, 0.95,  'BCAA class'),
    ('docosapentaenoic_acid_dpa', 'docosapentaenoic acid dpa (standard)', 0.75, 0.90,  'omega-3 TG class'),
    ('fluoride', 'fluoride (standard)',                                  0.80, 0.95,  'Rigalli 2001 NaF'),
]

B22_NULL_FORMS = [
    # Prebiotics — CATEGORY ERROR
    ('larch_arabinogalactan', 'larch arabinogalactan powder'),
    ('inulin', 'inulin (unspecified)'),
]


@pytest.mark.parametrize('pid,fname,vmin,vmax,basis', B22_BANDS_VALUED)
def test_b22_value_in_band(iqm, pid, fname, vmin, vmax, basis):
    """Each form's struct.value must sit in evidence band."""
    form = iqm[pid]['forms'].get(fname)
    assert form is not None, f'{pid}::{fname} missing'
    val = (form.get('absorption_structured') or {}).get('value')
    assert val is not None, f'{pid}::{fname} struct.value should be populated'
    assert vmin <= val <= vmax, (
        f'{pid}::{fname}: struct.value={val} outside band [{vmin}, {vmax}]. '
        f'Basis: {basis}'
    )


@pytest.mark.parametrize('pid,fname', B22_NULL_FORMS)
def test_b22_prebiotic_category_error_null(iqm, pid, fname):
    """Prebiotic forms must have struct.value=null per category-error finding —
    non-digestible polysaccharides; activity via colonic fermentation to SCFAs.
    """
    form = iqm[pid]['forms'].get(fname)
    assert form is not None, f'{pid}::{fname} missing'
    val = (form.get('absorption_structured') or {}).get('value')
    assert val is None, (
        f'{pid}::{fname} value={val} must be null — non-digestible '
        f'polysaccharide per Holscher 2017 (PMID:28165863) and Roberfroid '
        f'2005 (PMID:15877886). Activity via colonic fermentation to SCFAs, '
        f'not classical absorption (3rd category-error after manuka + '
        f'organ extracts).'
    )


def test_prebiotic_category_error_documented(iqm):
    """Prebiotic notes must document fermentation/SCFA mechanism."""
    forms = [
        ('larch_arabinogalactan', 'larch arabinogalactan powder'),
        ('inulin', 'inulin (unspecified)'),
    ]
    for pid, fname in forms:
        form = iqm[pid]['forms'][fname]
        text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
        text += ' ' + ((form.get('absorption_structured') or {}).get('notes') or '')
        text_lower = text.lower()
        flag_phrases = ('fermentation', 'scfa', 'short-chain fatty', 'category error',
                        'non-digestible', 'not systemically absorbed', 'colonic')
        assert any(p in text_lower for p in flag_phrases), (
            f'{pid}::{fname} must document prebiotic fermentation mechanism. '
            f'Text: {text[:300]}'
        )


def test_bhb_salts_vs_creatine_distinction_qualified(iqm):
    """BHB salt form notes must distinguish from creatine salts pattern —
    salts deliver ~50% inactive L-isomer per Stubbs 2017 (PMID:29163194).
    """
    form = iqm['d_beta_hydroxybutyrate_bhb']['forms']['d beta hydroxybutyrate bhb (standard)']
    text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
    text += ' ' + ((form.get('absorption_structured') or {}).get('notes') or '')
    text_lower = text.lower()
    # Must reference inactive isomer or Stubbs/Cmax difference
    flag_phrases = ('inactive l-isomer', 'l-βhb', 'l-bhb', 'l-isomer',
                    'inactive enantiomer', '50% inactive', 'not class-equivalent',
                    'stubbs 2017', '29163194')
    assert any(p in text_lower for p in flag_phrases), (
        f'BHB notes must distinguish salt-form ~50% inactive L-isomer per '
        f'Stubbs 2017 (PMID:29163194). Text: {text[:300]}'
    )


def test_d_chiro_class_equivalent_to_myo(iqm):
    """D-chiro-inositol must be class-equivalent (within 0.10) to myo-inositol
    per Lepore 2021 (PMID:34202683) — same SMIT2/passive transport.
    """
    forms = iqm['inositol']['forms']
    myo = (forms['myo-inositol'].get('absorption_structured') or {}).get('value')
    d_chiro = (forms['d-chiro-inositol'].get('absorption_structured') or {}).get('value')
    assert myo is not None and d_chiro is not None
    assert abs(myo - d_chiro) <= 0.10, (
        f'd-chiro-inositol ({d_chiro}) should be class-equivalent to myo-'
        f'inositol ({myo}) within 0.10 per Lepore 2021 (PMID:34202683)'
    )


def test_5_htp_unspec_matches_extract_band(iqm):
    """5-HTP unspecified should match the published Magnussen 1980 (PMID:6966118)
    band — extract form already at 0.70.
    """
    forms = iqm['5_htp']['forms']
    extract = (forms['5-htp extract'].get('absorption_structured') or {}).get('value')
    unspec = (forms['5-htp (unspecified)'].get('absorption_structured') or {}).get('value')
    assert extract is not None and unspec is not None
    # Both should be in 0.47-0.84 band per Magnussen
    for v in (extract, unspec):
        assert 0.47 <= v <= 0.84, (
            f'5-HTP value {v} should be in Magnussen 1980 band [0.47, 0.84]'
        )


def test_tudca_no_human_pk_qualified(iqm):
    """TUDCA notes must qualify the absence of robust human oral F PMID."""
    form = iqm['tudca']['forms']['tudca (standard)']
    text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
    text += ' ' + ((form.get('absorption_structured') or {}).get('notes') or '')
    text_lower = text.lower()
    flag_phrases = ('no verified human', 'mechanistic inference', 'no human pk',
                    'not robustly published', 'no robust')
    assert any(p in text_lower for p in flag_phrases), (
        f'TUDCA must qualify absence of human PK. Text: {text[:300]}'
    )


def test_no_phantom_stubbs_28261556(iqm):
    """Wrong "Stubbs 2017 PMID:28261556" must not appear as live citation —
    that's actually a Korean diet/cognition paper. Correct: PMID:29163194.
    """
    form = iqm['d_beta_hydroxybutyrate_bhb']['forms']['d beta hydroxybutyrate bhb (standard)']
    text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
    text += ' ' + ((form.get('absorption_structured') or {}).get('notes') or '')
    if 'PMID:28261556' in text:
        assert 'wrong' in text.lower() or 'misattribut' in text.lower() or 'ghost' in text.lower(), (
            f'BHB notes still cite PMID:28261556 as live citation '
            f'(Korean diet paper). Use PMID:29163194 (Stubbs 2017).'
        )


def test_class_authority_pmids_introduced(iqm):
    """Verified class-authority PMIDs must each appear in IQM notes."""
    expected_pmids = {
        'PMID:6966118':  'Magnussen 1980 5-HTP',
        'PMID:29163194': 'Stubbs 2017 BHB',
        'PMID:28165863': 'Holscher 2017 prebiotic',
        'PMID:15877886': 'Roberfroid 2005 inulin',
    }
    full_text = ''
    for pid in ('5_htp', 'd_beta_hydroxybutyrate_bhb', 'larch_arabinogalactan',
                'inulin', 'tudca', 'inositol', 'methionine'):
        for form in iqm[pid]['forms'].values():
            full_text += (form.get('notes') or '') + ' '
            full_text += (form.get('absorption') or '') + ' '
            full_text += ((form.get('absorption_structured') or {}).get('notes') or '') + ' '
    missing = [pmid for pmid in expected_pmids if pmid not in full_text]
    assert not missing, (
        f'Verified class-authority PMIDs missing: {missing}'
    )


def test_third_category_error_pattern(iqm):
    """Three category-error forms now established: manuka (Batch 18), organ
    extracts (Batch 20), prebiotics (Batch 22). All should have struct.value
    null and category-error documentation.
    """
    category_error_forms = [
        ('manuka_honey', 'umf 15+ / mgo 514+'),
        ('organ_extracts', 'grass-fed desiccated'),
        ('inulin', 'inulin (unspecified)'),
        ('larch_arabinogalactan', 'larch arabinogalactan powder'),
    ]
    for pid, fname in category_error_forms:
        form = iqm[pid]['forms'].get(fname)
        if form is None:
            continue
        v = (form.get('absorption_structured') or {}).get('value')
        assert v is None, (
            f'{pid}::{fname} value={v} should be null per category-error '
            f'(framework does not apply: local-action, composite food, or '
            f'fermented substrate)'
        )
