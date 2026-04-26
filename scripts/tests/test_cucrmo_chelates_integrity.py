"""Regression test: Cu/Cr/Mo chelate forms + ghost-reference findings.

Per IQM audit 2026-04-25 Step 4 Batch 17: 11 forms across copper, chromium,
molybdenum populated. Research subagent USED WebFetch on PubMed eutils.

Four major findings:
  1. Cr chelidamate arginate has ZERO PubMed hits on ANY topic — pure marketing
  2. Crominex 3+ has only Natreon-funded clinical RCTs (PMID:32021349, 30723735),
     no absolute F or PK data
  3. Cu picolinate "Hashmi" PMID is a GHOST REFERENCE (does not exist)
  4. Mo picolinate has no human PK (class F already 88-93% per Turnlund 1995)

Class context:
  • Copper: 12-56% F dose-inverse homeostatic (Turnlund 1989 PMID:2718922)
  • Chromium: 0.5-4% class-poor across all forms
  • Molybdenum: 88-93% across all forms per Turnlund 1995 (PMID:7572711)

Verified PMIDs:
  PMID:7572711   Turnlund 1995 — Mo 88-93%
  PMID:7733035   Turnlund 1995 — Mo depletion/repletion
  PMID:15564651  Anderson 2004 — Cr histidinate vs picolinate
  PMID:10573563  Baker 1999 — Cu oxide
  PMID:2718922   Turnlund 1989 — Cu 12-56%
  PMID:32021349  Natreon Crominex endothelial (clinical, NOT PK)
  PMID:30723735  Natreon Crominex lipid (clinical, NOT PK)
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
CUCRMO_BANDS = [
    # COPPER (class F 30-55%)
    ('copper', 'copper brown rice chelate',  0.30, 0.55, 'class chelate; marketing label'),
    ('copper', 'copper amino acid chelate',  0.30, 0.55, 'generic AAC'),
    ('copper', 'copper picolinate',          0.25, 0.55, 'no human PK; ghost ref'),
    ('copper', 'copper citrate',             0.25, 0.50, 'inorganic salt'),
    # CHROMIUM (class F 0.5-4%)
    ('chromium', 'chromium brown rice chelate',     0.005, 0.04, 'class-poor; marketing'),
    ('chromium', 'crominex 3+ chromium complex',    0.005, 0.04, 'no PK; clinical RCTs only'),
    ('chromium', 'chromium chelidamate arginate',   0.005, 0.04, 'ZERO PubMed presence'),
    # MOLYBDENUM (class F 88-93%)
    ('molybdenum', 'molybdenum brown rice chelate', 0.85, 0.95, 'class F per Turnlund 1995'),
    ('molybdenum', 'molybdenum amino acid chelate', 0.85, 0.95, 'class F per Turnlund 1995'),
    ('molybdenum', 'molybdenum picolinate',         0.85, 0.95, 'no human PK; class F'),
    ('molybdenum', 'molybdenum chloride',           0.85, 0.95, 'inorganic; class F'),
]


@pytest.mark.parametrize('pid,fname,vmin,vmax,basis', CUCRMO_BANDS)
def test_cucrmo_value_in_band(iqm, pid, fname, vmin, vmax, basis):
    """Each Cu/Cr/Mo form's struct.value must sit in evidence band."""
    form = iqm[pid]['forms'].get(fname)
    assert form is not None, f'{pid}::{fname} missing'
    val = (form.get('absorption_structured') or {}).get('value')
    assert val is not None, f'{pid}::{fname} struct.value should be populated'
    assert vmin <= val <= vmax, (
        f'{pid}::{fname}: struct.value={val} outside band [{vmin}, {vmax}]. '
        f'Basis: {basis}'
    )


def test_chromium_class_poor_F(iqm):
    """All chromium forms must have struct.value ≤ 0.05 — chromium is
    class-poor (0.5-4% F regardless of form per Anderson 2004 PMID:15564651).
    """
    forms = iqm['chromium']['forms']
    violations = []
    for fname, form in forms.items():
        v = (form.get('absorption_structured') or {}).get('value')
        if v is None:
            continue
        if v > 0.05:
            violations.append((fname, v))
    assert not violations, (
        f'Chromium forms with struct.value > 0.05 violate class-poor F '
        f'evidence (0.5-4% across all forms): {violations}'
    )


def test_molybdenum_class_high_F(iqm):
    """All molybdenum forms with values must be in 88-93% band per Turnlund
    1995 (PMID:7572711). Mo class is homeostatically regulated near saturation.
    """
    forms = iqm['molybdenum']['forms']
    expected_min = 0.85
    expected_max = 0.95
    violations = []
    for fname, form in forms.items():
        if 'unspecified' in fname.lower():
            continue
        v = (form.get('absorption_structured') or {}).get('value')
        if v is None:
            continue
        if not (expected_min <= v <= expected_max):
            violations.append((fname, v))
    assert not violations, (
        f'Mo forms outside class F band [{expected_min}, {expected_max}] per '
        f'Turnlund 1995 (PMID:7572711): {violations}'
    )


def test_copper_class_homeostatic_F(iqm):
    """Copper forms with values must be in 0.10-0.55 band (class F 12-56%
    per Turnlund 1989 PMID:2718922; oxide near low end, chelates near high).
    """
    forms = iqm['copper']['forms']
    violations = []
    for fname, form in forms.items():
        if 'unspecified' in fname.lower() or 'oxide' in fname.lower():
            continue
        v = (form.get('absorption_structured') or {}).get('value')
        if v is None:
            continue
        if not (0.10 <= v <= 0.90):  # bisglycinate is at 0.825
            violations.append((fname, v))
    assert not violations, (
        f'Cu forms outside class F band: {violations}'
    )


def test_crominex_no_pk_qualified(iqm):
    """Crominex 3+ notes must qualify the absence of PK data — only
    clinical-endpoint RCTs exist (PMID:32021349, 30723735).
    """
    form = iqm['chromium']['forms']['crominex 3+ chromium complex']
    text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
    text_lower = text.lower()
    flag_phrases = ('no pk', 'clinical only', 'clinical rct', 'no absolute f',
                    'no bioavailability', 'no published evidence', 'natreon')
    assert any(p in text_lower for p in flag_phrases), (
        f'Crominex 3+ notes must qualify absence of PK data. Text: {text[:300]}'
    )


def test_chelidamate_arginate_zero_evidence_qualified(iqm):
    """Cr chelidamate arginate notes must flag the zero-PubMed status.
    """
    form = iqm['chromium']['forms']['chromium chelidamate arginate']
    text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
    text_lower = text.lower()
    flag_phrases = ('zero pubmed', '0 pubmed', 'no published',
                    'no evidence', 'marketing-only', 'marketing only')
    assert any(p in text_lower for p in flag_phrases), (
        f'Cr chelidamate arginate notes must flag zero-PubMed status. '
        f'Text: {text[:300]}'
    )


def test_cu_picolinate_ghost_reference_qualified(iqm):
    """Cu picolinate notes must qualify the absence of human PK; the
    "Hashmi" PMID often cited is a ghost reference.
    """
    form = iqm['copper']['forms']['copper picolinate']
    text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
    text_lower = text.lower()
    flag_phrases = ('no human pk', 'ghost', 'extrapolated', 'unsourced',
                    'not found', 'no published')
    assert any(p in text_lower for p in flag_phrases), (
        f'Cu picolinate notes must qualify absence of dedicated human PK. '
        f'Text: {text[:300]}'
    )


def test_class_authority_pmids_introduced(iqm):
    """Verified class-authority PMIDs must each appear in IQM notes."""
    expected_pmids = {
        'PMID:7572711':  'Turnlund 1995 Mo class F',
        'PMID:2718922':  'Turnlund 1989 Cu class F',
        'PMID:32021349': 'Crominex endothelial (clinical only)',
    }
    full_text = ''
    for pid in ('copper', 'chromium', 'molybdenum'):
        for form in iqm[pid]['forms'].values():
            full_text += (form.get('notes') or '') + ' '
            full_text += (form.get('absorption') or '') + ' '
    missing = [pmid for pmid in expected_pmids if pmid not in full_text]
    assert not missing, (
        f'Verified class-authority PMIDs missing from Cu/Cr/Mo notes: {missing}'
    )


def test_brown_rice_chelate_consistency_across_minerals(iqm):
    """Brown rice chelate must be flagged as marketing across Cu/Cr/Mo too
    (consistent with Batch 11 finding for Fe/Mn/Zn/Se/Mg).
    """
    forms = (
        ('copper', 'copper brown rice chelate'),
        ('chromium', 'chromium brown rice chelate'),
        ('molybdenum', 'molybdenum brown rice chelate'),
    )
    for pid, fname in forms:
        form = iqm[pid]['forms'].get(fname)
        assert form is not None, f'{pid}::{fname} missing'
        text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
        text_lower = text.lower()
        flag_phrases = ('marketing', '0 pubmed', 'zero pubmed', 'class-equivalent',
                        'no peer-reviewed', 'marketing-only', 'marketing label')
        assert any(p in text_lower for p in flag_phrases), (
            f'{pid}::{fname} must flag brown-rice-chelate marketing status. '
            f'Text: {text[:200]}'
        )
