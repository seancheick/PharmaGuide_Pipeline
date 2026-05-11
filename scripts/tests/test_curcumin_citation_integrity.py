"""Regression test: curcumin enhanced forms PK + citation integrity.

Per IQM audit 2026-04-25 Step 4 Batch 8: curcumin cluster had three concurrent
issues: 7 of 11 forms had null struct.value despite high bio_scores; multiple
citation misattributions (the Stoll 2021 / Lopez-Lluch 2019 pattern recurring);
and fold-change-vs-absolute-F confusion. Research subagent verified PMIDs and
established that Kroon 2025 is the authoritative class-reappraisal reference.

Verified PMIDs:
  PMID:40487425  Kroon 2025 iScience — class authority
  PMID:24402825  Schiborr 2014 — NovaSol 185× total AUC (n=23)
  PMID:28204880  Purpura 2018 — γ-CD CW8 39× (NOT 136×, NOT Schiborr)
  PMID:21413691  Cuomo 2011 — Meriva 29× total
  PMID:21532153  Sasaki 2011 — Theracurmin 27× total
  PMID:20046768  Antony 2008 — BCM-95 6.93× pilot
  PMID:29974228  Briskey 2019 — HydroCurc 2.5× total

Misattributions caught + corrected:
  • "Verhoeven 2025" doesn't exist — actual is Kroon 2025
  • CurcuWIN had 3 errors: Schiborr→Purpura, 136×→39×, wrong product
  • NovaSol PMID :28204880 → :24402825
  • HydroCurc "no PK study" misclaim → Briskey 2019
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

IQM_PATH = Path(__file__).parent.parent / 'data' / 'ingredient_quality_map.json'

# (form_name, vmin, vmax, basis_pmid)
CURCUMIN_EVIDENCE_BANDS = [
    ('longvida curcumin',                   0.005, 0.025, 'PMID:40487425 Kroon 2025 — no improvement vs unformulated'),
    ('novasol curcumin',                    0.02,  0.07,  'PMID:24402825 Schiborr 2014 + PMID:40487425 Kroon 2025'),
    ('hydrocurc',                           0.02,  0.07,  'PMID:29974228 Briskey 2019 — ~2.5× total'),
    ('curcuwin',                            0.02,  0.06,  'PMID:28204880 Purpura 2018 — 39× CW8'),
    ('meriva curcumin',                     0.03,  0.08,  'PMID:21413691 Cuomo 2011 — 29× total, phase-2 only'),
    ('theracurmin',                         0.02,  0.07,  'PMID:21532153 Sasaki 2011 — 27× total'),
    ('bcm-95 curcumin',                     0.01,  0.05,  'PMID:20046768 Antony 2008 — 6.93× pilot'),
    ('curcumin c3 complex with bioperine',  0.01,  0.05,  'PMID:40487425 Kroon 2025 — piperine debunked'),
    ('curcumin c3 complex',                 0.005, 0.04,  'class baseline ~1-3% absolute F'),
    # NOTE: 'turmeric powder (unstandardized)' removed by identity_bioactivity_split
    # Phase 2 — turmeric is no longer a curcumin IQM form (relocated to source
    # botanical 'turmeric'). Raw turmeric on labels now resolves to botanical
    # canonical; curcumin Section C credit requires 95%+ standardization
    # declaration per botanical_marker_contributions.json policy.
]


@pytest.fixture(scope='module')
def iqm():
    with IQM_PATH.open() as f:
        return json.load(f)


@pytest.mark.parametrize('fname,vmin,vmax,basis', CURCUMIN_EVIDENCE_BANDS)
def test_curcumin_value_in_evidence_band(iqm, fname, vmin, vmax, basis):
    """Each curcumin form's struct.value must sit in evidence-supported band."""
    form = iqm.get('curcumin', {}).get('forms', {}).get(fname)
    assert form is not None, f'curcumin::{fname} missing'
    val = (form.get('absorption_structured') or {}).get('value')
    assert val is not None, (
        f'curcumin::{fname} struct.value should be populated (per Batch 8)'
    )
    assert vmin <= val <= vmax, (
        f'curcumin::{fname}: struct.value={val} outside band [{vmin}, {vmax}]. '
        f'Basis: {basis}'
    )


def test_no_phantom_verhoeven_2025_citation(iqm):
    """The "Verhoeven 2025" first-author surname must not appear as a live
    citation — the actual paper is Kroon 2025 (PMID:40487425). Allowed
    only inside audit-trail (quoted) references.
    """
    live = re.compile(r'(?<![\"“])Verhoeven\s*2025(?![\"”])', re.IGNORECASE)
    forms = iqm.get('curcumin', {}).get('forms', {})
    violations = []
    for fname, form in forms.items():
        for field in ('notes', 'absorption'):
            text = form.get(field) or ''
            for m in live.finditer(text):
                start = max(0, m.start() - 1)
                end = min(len(text), m.end() + 1)
                window = text[start:end]
                if '"' in window or '“' in window or '”' in window:
                    continue
                violations.append((fname, field, text[max(0, m.start()-15):m.end()+15]))
        struct_notes = (form.get('absorption_structured') or {}).get('notes') or ''
        for m in live.finditer(struct_notes):
            start = max(0, m.start() - 1)
            end = min(len(struct_notes), m.end() + 1)
            window = struct_notes[start:end]
            if '"' in window or '“' in window or '”' in window:
                continue
            violations.append((fname, 'struct.notes', struct_notes[max(0, m.start()-15):m.end()+15]))
    assert not violations, (
        f'Live "Verhoeven 2025" citation still present (actual paper is Kroon '
        f'2025 PMID:40487425): {violations}'
    )


def test_curcuwin_no_live_136x_claim(iqm):
    """CurcuWIN must not LIVE-claim 136× attribution. The audit-trail
    note may legitimately reference the historical "NOT 136×" or "wrong
    fold: 136× → 39×" phrasing — those are quoted/qualified references,
    not live citations. Live claims fail; audit-trail references pass.
    """
    form = iqm['curcumin']['forms']['curcuwin']
    bad_pattern = re.compile(r'13[56]\s*[xX×]', re.IGNORECASE)
    # Negators that mark a "NOT a live claim" context
    negation_window = re.compile(
        r'(?:not|wrong\s*fold|→\s*39|NOT\s*136|"|“|”)',
        re.IGNORECASE,
    )
    violations = []

    def _check(text, field):
        for m in bad_pattern.finditer(text):
            # Look at 60 chars before the match for negation
            start = max(0, m.start() - 60)
            end = min(len(text), m.end() + 5)
            window = text[start:end]
            if negation_window.search(window):
                continue  # historical reference inside audit-trail
            violations.append((field, text[max(0, m.start()-20):m.end()+20]))

    for field in ('notes', 'absorption'):
        _check(form.get(field) or '', field)
    _check((form.get('absorption_structured') or {}).get('notes') or '', 'struct.notes')

    assert not violations, (
        f'CurcuWIN still LIVE-claims 136× absorption — that figure is '
        f'unverified in PubMed. Purpura 2018 (PMID:28204880) reports 39×: {violations}'
    )


def test_kroon_2025_cited_for_critical_reappraisals(iqm):
    """Kroon 2025 (PMID:40487425) is the class authority and must appear in
    forms it informs: longvida, novasol, c3+bioperine.
    """
    forms = iqm['curcumin']['forms']
    must_cite = ['longvida curcumin', 'novasol curcumin', 'curcumin c3 complex with bioperine']
    for fname in must_cite:
        form = forms.get(fname, {})
        text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
        assert ('PMID:40487425' in text or 'Kroon 2025' in text), (
            f'curcumin::{fname} should cite Kroon 2025 (PMID:40487425) as '
            f'class-authority critical reappraisal of curcumin enhanced forms'
        )


def test_meriva_top_evidence_ranking(iqm):
    """Meriva should rank highest among standardized enhanced forms (35+ RCTs,
    Cuomo 2011 paper has the strongest methodology among the group).
    """
    forms = iqm['curcumin']['forms']
    def v(name):
        return (forms[name].get('absorption_structured') or {}).get('value') or 0
    meriva = v('meriva curcumin')
    # Meriva should at least match or exceed novasol/curcuwin/theracurmin/bcm-95/hydrocurc
    competitors = ['novasol curcumin', 'curcuwin', 'theracurmin', 'bcm-95 curcumin', 'hydrocurc']
    for comp in competitors:
        assert meriva >= v(comp), (
            f'Meriva ({meriva}) should not score lower than {comp} ({v(comp)}) — '
            f'Meriva has strongest evidence base (35+ RCTs, Cuomo 2011 robust methodology)'
        )


def test_longvida_appropriately_low(iqm):
    """Longvida value must be class-low (≤0.025) per Kroon 2025 finding that
    AUC is not different from unformulated curcumin.
    """
    val = (iqm['curcumin']['forms']['longvida curcumin']
           .get('absorption_structured') or {}).get('value')
    assert val is not None and val <= 0.025, (
        f'Longvida value should be ≤0.025 per Kroon 2025 (PMID:40487425) finding '
        f'that AUC is not different from unformulated curcumin. Current: {val}'
    )


def test_novasol_pmid_attribution_correct(iqm):
    """NovaSol must cite Schiborr 2014 with the correct PMID (24402825),
    NOT 28204880 (which is Purpura 2018, a different paper on γ-CD CW8).
    """
    form = iqm['curcumin']['forms']['novasol curcumin']
    text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
    # If Schiborr is cited, the PMID must be 24402825
    if 'Schiborr' in text:
        # Look for incorrect PMID linkage
        assert 'PMID:28204880' not in text or 'Purpura' in text, (
            f'NovaSol cites Schiborr but with wrong PMID — Schiborr 2014 is '
            f'PMID:24402825 (Mol Nutr Food Res), not 28204880 (which is '
            f'Purpura 2018 on CurcuWIN-area material)'
        )
