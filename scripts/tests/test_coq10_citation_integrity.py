"""Regression test: CoQ10 form bioavailability + citation integrity.

Per IQM audit 2026-04-25 Step 4 Batch 7: CoQ10 forms had multiple citation
misattributions and 5 of 6 forms had null struct.value despite high
bio_scores. Research subagent verified PMIDs and corrected attributions.

Verified PMIDs:
  PMID:32380795  Mantle & Dybring 2020 — class authority review
  PMID:16551570  Bhagavan & Chopra 2006 — class baseline
  PMID:30153575  Lopez-Lluch 2019 — RELATIVE AUC ranking only (NOT absolute F)
  PMID:16919858  Hosoe 2007 — Kaneka CoQH-CF PK
  PMID:17482886  Bhagavan & Chopra 2007 — solubilized > non-solubilized

Misattribution caught + corrected:
  • "Lopez-Lluch 2019" cited for 1.3%, 3%, 2-4×, 2.3× absolute/fold figures
    that are NOT in PMID:30153575. Reattributed to Mantle 2020 + Bhagavan 2006.
  • "Langsjoen 2014 1.7× higher plasma in older adults" doesn't match any
    verified PMID. Closest PMID:19096107 was NYHA IV CHF, wrong population.

Test guards both data integrity and citation discipline.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

IQM_PATH = Path(__file__).parent.parent / 'data' / 'ingredient_quality_map.json'

# (form_name, vmin, vmax, basis_pmid)
COQ10_EVIDENCE_BANDS = [
    ('ubiquinol crystal-free',         0.04, 0.10, 'PMID:16919858 Hosoe 2007 Kaneka CoQH-CF — class-leading AUC'),
    ('ubiquinol',                       0.03, 0.08, 'PMID:32380795 Mantle 2020 — modest gain over ubiquinone'),
    ('ubiquinone crystal-dispersed',    0.03, 0.07, 'PMID:30153575 Lopez-Lluch 2019 — top-2 by AUC ranking'),
    ('ubiquinone softgel',              0.02, 0.05, 'PMID:30153575 Lopez-Lluch 2019 — oil-softgel ranked top'),
    ('ubiquinone standard',             0.015, 0.04, 'PMID:16551570 Bhagavan 2006 — slow & limited'),
    ('ubiquinone powder/capsule',       0.005, 0.025, 'PMID:32380795 Mantle 2020 — ~75% lower than dispersed'),
]


@pytest.fixture(scope='module')
def iqm():
    with IQM_PATH.open() as f:
        return json.load(f)


@pytest.mark.parametrize('fname,vmin,vmax,basis', COQ10_EVIDENCE_BANDS)
def test_coq10_value_in_evidence_band(iqm, fname, vmin, vmax, basis):
    """Each CoQ10 form's struct.value must sit in evidence-supported band."""
    form = iqm.get('coq10', {}).get('forms', {}).get(fname)
    assert form is not None, f'coq10::{fname} missing'
    val = (form.get('absorption_structured') or {}).get('value')
    assert val is not None, (
        f'coq10::{fname} struct.value should be populated (per Batch 7)'
    )
    assert vmin <= val <= vmax, (
        f'coq10::{fname}: struct.value={val} outside band [{vmin}, {vmax}]. '
        f'Basis: {basis}'
    )


def test_coq10_form_ranking_consistent(iqm):
    """CoQ10 form ranking by struct.value must match clinical evidence:
    ubiquinol crystal-free > ubiquinol ≈ crystal-dispersed > softgel > standard > powder.
    """
    forms = iqm['coq10']['forms']
    def v(name):
        return (forms[name].get('absorption_structured') or {}).get('value')

    # Tier 1 (highest): ubiquinol crystal-free
    assert v('ubiquinol crystal-free') >= v('ubiquinol')
    assert v('ubiquinol crystal-free') >= v('ubiquinone crystal-dispersed')
    # Tier 2: ubiquinol ≈ crystal-dispersed
    assert v('ubiquinol') >= v('ubiquinone softgel')
    assert v('ubiquinone crystal-dispersed') >= v('ubiquinone softgel')
    # Tier 3: softgel > standard
    assert v('ubiquinone softgel') >= v('ubiquinone standard')
    # Tier 4: standard > powder
    assert v('ubiquinone standard') >= v('ubiquinone powder/capsule')


def test_no_lopez_lluch_misattribution_for_absolute_numbers(iqm):
    """Lopez-Lluch 2019 (PMID:30153575) must NOT be cited as the source for
    specific absolute % numbers (1.3%, 3%) or specific fold-changes
    (2-4×, 2.3×) — those are not in that paper's abstract.

    Acceptable: citing it for "relative AUC ranking" or "AUC superiority"
    without claiming specific absolute %/fold figures.
    """
    forms = iqm.get('coq10', {}).get('forms', {})
    # Patterns that combine a specific number with the Lopez-Lluch attribution
    bad_patterns = [
        re.compile(r'~?\s*1\.3\s*%[^.]*Lopez[- ]?Lluch', re.IGNORECASE),
        re.compile(r'~?\s*3\s*%[^.]*Lopez[- ]?Lluch', re.IGNORECASE),
        re.compile(r'~?\s*2\s*-\s*4\s*x[^.]*Lopez[- ]?Lluch', re.IGNORECASE),
        re.compile(r'~?\s*2\.3\s*x[^.]*Lopez[- ]?Lluch', re.IGNORECASE),
    ]
    violations = []
    for fname, form in forms.items():
        for field in ('notes', 'absorption'):
            text = form.get(field) or ''
            for pat in bad_patterns:
                if pat.search(text):
                    m = pat.search(text)
                    violations.append((fname, field, m.group()))
        # Also check absorption_structured.notes
        struct_notes = (form.get('absorption_structured') or {}).get('notes') or ''
        for pat in bad_patterns:
            if pat.search(struct_notes):
                m = pat.search(struct_notes)
                violations.append((fname, 'struct.notes', m.group()))
    assert not violations, (
        f'Lopez-Lluch 2019 (PMID:30153575) misattributed for specific absolute '
        f'%/fold numbers (which are not in that paper). Reattribute to Mantle '
        f'2020 / Bhagavan 2006 for class baselines: {violations}'
    )


def test_no_phantom_langsjoen_2014_claim(iqm):
    """The "Langsjoen 2014 1.7× higher in older adults" claim must not appear
    as a live citation — no verified PMID matches that population/effect.
    Allowed only inside the audit-trail (quoted, e.g., describing the
    misattribution itself).
    """
    live = re.compile(r'Langsjoen\s*2014', re.IGNORECASE)
    forms = iqm['coq10']['forms']
    violations = []
    for fname, form in forms.items():
        for field in ('notes', 'absorption'):
            text = form.get(field) or ''
            for m in live.finditer(text):
                # Allow if surrounded by quote marker (audit-trail reference)
                start = max(0, m.start() - 1)
                end = min(len(text), m.end() + 1)
                window = text[start:end]
                if '"' in window or '“' in window or '”' in window:
                    continue
                violations.append((fname, field, text[max(0, m.start()-15):m.end()+15]))
    assert not violations, (
        f'Live "Langsjoen 2014" citation still present (claim is not '
        f'PMID-verified — closest is PMID:19096107 in NYHA IV CHF, wrong '
        f'population): {violations}'
    )


def test_class_authority_pmids_cited(iqm):
    """Mantle 2020 (PMID:32380795) AND Bhagavan 2006 (PMID:16551570) — the
    two class-authority references — must each appear in ≥2 CoQ10 forms.
    """
    forms = iqm['coq10']['forms']
    counts = {'PMID:32380795': 0, 'PMID:16551570': 0}
    for form in forms.values():
        text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
        for pmid in counts:
            if pmid in text:
                counts[pmid] += 1
    for pmid, n in counts.items():
        assert n >= 2, (
            f'Class authority {pmid} should be cited in ≥2 CoQ10 forms; '
            f'currently in {n}'
        )
