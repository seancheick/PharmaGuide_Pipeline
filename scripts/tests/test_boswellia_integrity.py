"""Regression test: boswellia forms PK + Aflapin rat-only conflation.

Per IQM audit 2026-04-25 Step 4 Batch 16: 5 boswellia forms populated.
Research subagent USED WebFetch on PubMed eutils. Three major findings:

1. AFLAPIN "+51.78% AUC vs 5-Loxin" IS RAT-ONLY — Sengupta 2011
   (PMID:21479939, Mol Cell Biochem) is Sprague-Dawley rats only.
   Same rat-vs-human conflation pattern as Mg threonate (Batch 15),
   tocotrienol (Batch 13).
2. CLINICAL EFFICACY ≠ BIOAVAILABILITY — Sengupta 2008/2010 + Vishal
   2011 measure WOMAC OA outcomes, not plasma PK.
3. NO HUMAN ABSOLUTE F STUDY EXISTS for any boswellic acid form.
   Class F inferred ~1-7% from lipophilicity.

Verified PMIDs:
  PMID:15643550  Sterk 2004 — human food-effect PK (no IV reference)
  PMID:18667054  Sengupta 2008 — 5-Loxin OA RCT (clinical)
  PMID:21060724  Sengupta 2010 — 5-Loxin vs Aflapin (clinical)
  PMID:21479939  Sengupta 2011 — RAT PK + in-vitro
  PMID:22022214  Vishal 2011 — Aflapin OA RCT (clinical)

Misattributions caught BEFORE introduction:
  • "Sterk 2004 PMID:15047492" — wrong (cytokine paper)
  • "Vishal 2011 PMID:21235550" — wrong (transgenic fish paper)
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


# (form, vmin, vmax, basis)
BOSWELLIA_BANDS = [
    ('5-loxin',                          0.02, 0.10, 'class-poor F; clinical only'),
    ('boswellia aflapin',                0.02, 0.10, 'rat PK only; class-poor F'),
    ('boswellia standardized extract',   0.01, 0.08, 'food-dependent; Sterk 2004'),
    ('boswellia resin powder',           0.01, 0.05, 'crude resin; lower BAs'),
    ('boswellia (unspecified)',          0.01, 0.07, 'class-poor F'),
]


@pytest.mark.parametrize('fname,vmin,vmax,basis', BOSWELLIA_BANDS)
def test_boswellia_value_in_band(iqm, fname, vmin, vmax, basis):
    """Each boswellia form's struct.value must sit in evidence band (1-10%)
    per class-poor lipophilic absorption.
    """
    form = iqm['boswellia']['forms'].get(fname)
    assert form is not None, f'boswellia::{fname} missing'
    val = (form.get('absorption_structured') or {}).get('value')
    assert val is not None, f'boswellia::{fname} struct.value should be populated'
    assert vmin <= val <= vmax, (
        f'boswellia::{fname}: struct.value={val} outside band [{vmin}, {vmax}]. '
        f'Basis: {basis}'
    )


def test_boswellia_class_poor_F(iqm):
    """All boswellia forms must have struct.value ≤ 0.10 — boswellic acids
    are class-poor lipophilic with inferred F ~1-7%. No form has human PK
    evidence to support higher F.
    """
    forms = iqm['boswellia']['forms']
    violations = []
    for fname, form in forms.items():
        v = (form.get('absorption_structured') or {}).get('value')
        if v is None:
            continue
        if v > 0.10:
            violations.append((fname, v))
    assert not violations, (
        f'Boswellia forms with struct.value > 0.10 violate class-poor F '
        f'evidence (no human absolute F study exists): {violations}'
    )


def test_aflapin_rat_only_qualified(iqm):
    """Aflapin notes must qualify the "+51.78%" claim as RAT-ONLY per
    Sengupta 2011 (PMID:21479939). Cannot be presented as human-validated.
    """
    form = iqm['boswellia']['forms']['boswellia aflapin']
    text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
    text_lower = text.lower()
    if any(p in text_lower for p in ('51.78', '51 percent', '+51')):
        assert 'rat' in text_lower or 'sprague' in text_lower, (
            f'Aflapin "+51.78%" claim must be qualified as RAT-ONLY per '
            f'Sengupta 2011 (PMID:21479939). Text: {text[:400]}'
        )


def test_no_phantom_sterk_pmid_15047492(iqm):
    """The wrong "Sterk 2004 PMID:15047492" must not appear as live citation.
    Correct PMID is 15643550.
    """
    form = iqm['boswellia']['forms']['boswellia standardized extract']
    text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
    if 'PMID:15047492' in text:
        assert 'wrong' in text.lower() or 'misattribut' in text.lower(), (
            f'Sterk 2004 wrong PMID:15047492 (cytokine paper) cited without '
            f'qualification. Correct is PMID:15643550'
        )


def test_no_phantom_vishal_pmid_21235550(iqm):
    """The wrong "Vishal 2011 PMID:21235550" must not appear as live citation.
    Correct PMID is 22022214.
    """
    form = iqm['boswellia']['forms']['boswellia aflapin']
    text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
    if 'PMID:21235550' in text:
        assert 'wrong' in text.lower() or 'misattribut' in text.lower(), (
            f'Vishal 2011 wrong PMID:21235550 (transgenic fish paper) '
            f'cited without qualification. Correct is PMID:22022214'
        )


def test_class_authority_pmids_introduced(iqm):
    """Verified class-authority PMIDs must each appear in IQM boswellia notes."""
    expected_pmids = {
        'PMID:15643550': 'Sterk 2004 (food effect)',
        'PMID:18667054': 'Sengupta 2008 (5-Loxin clinical)',
        'PMID:21479939': 'Sengupta 2011 (RAT)',
    }
    full_text = ''
    for form in iqm['boswellia']['forms'].values():
        full_text += (form.get('notes') or '') + ' '
        full_text += (form.get('absorption') or '') + ' '
    missing = [pmid for pmid in expected_pmids if pmid not in full_text]
    assert not missing, (
        f'Verified class-authority PMIDs missing from boswellia notes: {missing}'
    )


def test_5loxin_clinical_not_pk_qualified(iqm):
    """5-Loxin notes must qualify Sengupta 2008 (PMID:18667054) as CLINICAL
    OA outcome, not bioavailability/PK evidence.
    """
    form = iqm['boswellia']['forms']['5-loxin']
    text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
    if 'PMID:18667054' in text or 'Sengupta 2008' in text:
        text_lower = text.lower()
        # Must indicate clinical outcome (WOMAC, OA, RCT) not PK
        assert any(m in text_lower for m in ('clinical', 'womac', 'oa rct', 'rct', 'outcome', 'no pk')), (
            f'5-Loxin citing Sengupta 2008 must qualify as CLINICAL outcome. '
            f'Text: {text[:300]}'
        )
