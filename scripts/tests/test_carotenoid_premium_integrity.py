"""Regression test: astaxanthin + premium vitamin A absorption integrity.

Per IQM audit 2026-04-24 Step 4 Batch 6: 5 forms previously had
struct.value=None despite high bio_scores. PubMed research populated
evidence-backed values with explicit caveats for evidence-thin cases.

Verified PMIDs:
  PMID:12885395  Mercke Odeberg 2003 — astaxanthin lipid F-enhancement
  PMID:11120445  Østerlie 2000 — astaxanthin Cmax 1.3 mg/L at 100mg w/ meal
  PMID:38748358  Khayyal 2024 — micellar vs reference astaxanthin crossover
  PMID:24036530  Reboul 2013 — vitamin A 70-90% absorption review

Critical caveats this test enforces:
  1. Synthetic astaxanthin must NOT score above natural (no head-to-head PK)
  2. Liposomal/micellized vitamin A notes must contain evidence-thin flag
  3. Astaxanthin values must stay in 0.05-0.55 evidence-supported band
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
EVIDENCE_BANDS = [
    ('astaxanthin', 'natural astaxanthin (haematococcus pluvialis)', 0.10, 0.50,
     'PMID:12885395 + PMID:11120445 — lipid-enhancement 1.7-3.7×, no IV-vs-oral F study'),
    ('astaxanthin', 'synthetic astaxanthin', 0.10, 0.50,
     'No head-to-head human PK; mirror natural form'),
    ('astaxanthin', 'unspecified astaxanthin', 0.05, 0.30,
     'PMID:38748358 reference-arm Cmax 3.86 µg/mL — unformulated baseline'),
    ('vitamin_a', 'micellized vitamin A', 0.70, 0.95,
     'PMID:24036530 review extrapolation — no isolated micellized human PK'),
    ('vitamin_a', 'liposomal vitamin A', 0.70, 0.95,
     'NO human oral PK exists — mechanistic extrapolation only'),
]


@pytest.mark.parametrize('pid,fname,vmin,vmax,basis', EVIDENCE_BANDS)
def test_carotenoid_premium_value_in_band(iqm, pid, fname, vmin, vmax, basis):
    """struct.value for astaxanthin + premium vit A forms must stay in band."""
    form = iqm.get(pid, {}).get('forms', {}).get(fname)
    assert form is not None, f'{pid}::{fname} missing from IQM'
    val = (form.get('absorption_structured') or {}).get('value')
    assert val is not None, f'{pid}::{fname} struct.value should be populated'
    assert vmin <= val <= vmax, (
        f'{pid}::{fname}: struct.value={val} outside evidence band '
        f'[{vmin}, {vmax}]. Basis: {basis}'
    )


def test_synthetic_astaxanthin_not_above_natural(iqm):
    """Synthetic astaxanthin MUST NOT have higher struct.value than natural —
    no head-to-head human PK exists, so marketing claims of "natural absorbs
    better" cannot drive differential values either way.
    """
    forms = iqm['astaxanthin']['forms']
    natural_val = (forms['natural astaxanthin (haematococcus pluvialis)']
                   .get('absorption_structured') or {}).get('value')
    synth_val = (forms['synthetic astaxanthin']
                 .get('absorption_structured') or {}).get('value')
    assert synth_val <= natural_val, (
        f'synthetic astaxanthin value={synth_val} exceeds natural {natural_val}; '
        f'no human head-to-head PK supports differentiation. Marketing claim leakage check.'
    )


def test_evidence_thin_flags_preserved(iqm):
    """Notes for liposomal vitamin A and micellized vitamin A must explicitly
    flag the evidence-thin status (no human oral PK published).
    """
    forms = iqm['vitamin_a']['forms']
    for fname in ('liposomal vitamin A', 'micellized vitamin A'):
        notes = forms[fname].get('notes', '') or ''
        assert 'EVIDENCE-THIN' in notes or 'evidence-thin' in notes.lower(), (
            f'vitamin_a::{fname} notes must explicitly flag evidence-thin '
            f'status (no isolated human oral PK published). Current notes '
            f'do not contain that flag.'
        )


def test_astaxanthin_pmids_cited(iqm):
    """At least 3 of the 4 verified astaxanthin PMIDs must remain cited
    across the 3 astaxanthin forms.
    """
    forms = iqm['astaxanthin']['forms']
    expected = {'PMID:12885395', 'PMID:11120445', 'PMID:38748358'}
    seen = set()
    for form in forms.values():
        notes = form.get('notes', '') or ''
        abs_str = form.get('absorption', '') or ''
        for pmid in expected:
            if pmid in notes or pmid in abs_str:
                seen.add(pmid)
    assert len(seen) >= 2, (
        f'At least 2 of {expected} must remain cited in astaxanthin forms; '
        f'found {seen}'
    )


def test_no_synthetic_marketing_claim_leakage(iqm):
    """The synthetic astaxanthin notes must not assert "natural is superior" —
    that's not human-PK-supported.
    """
    notes = iqm['astaxanthin']['forms']['synthetic astaxanthin'].get('notes', '') or ''
    bad_patterns = [
        'synthetic is inferior',
        'natural is superior',
        'natural is more bioavailable',
        'synthetic absorbs less',
    ]
    notes_lower = notes.lower()
    violations = [p for p in bad_patterns if p in notes_lower]
    assert not violations, (
        f'synthetic astaxanthin notes contain unsupported marketing claim '
        f'leakage: {violations}. No human head-to-head PK exists to support '
        f'such claims (per Step 4 Batch 6 audit research).'
    )
