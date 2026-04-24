"""Regression test: choline form citations + absorption string semantics.

Per IQM audit 2026-04-24 Step 4 Batch 4: "Stoll 2021" was a misattribution
the audit could not locate in PubMed. The actual paper documenting equivalent
plasma choline AUC across alpha-GPC, bitartrate, chloride, and egg-PC is:

  Böckmann KA et al. "Differential metabolism of choline supplements in
  adult volunteers." Eur J Nutr 61(1):219-230 (2022, epub Jul 2021).
  PMID:34287673.

Additionally, the prior absorption strings described "% choline by weight"
(elemental yield per gram of salt) — a DOSING concern, not an absorption
claim. This test enforces that the absorption field no longer mixes
weight-fraction language with PK evidence.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

IQM_PATH = Path(__file__).parent.parent / 'data' / 'ingredient_quality_map.json'

CHOLINE_FORMS = (
    'alpha-GPC',
    'CDP-choline (citicoline)',
    'phosphatidylcholine',
    'choline bitartrate',
    'choline citrate',
    'choline chloride',
)


@pytest.fixture(scope='module')
def iqm():
    with IQM_PATH.open() as f:
        return json.load(f)


def test_no_live_stoll_2021_citation(iqm):
    """No LIVE citation to "Stoll 2021" should remain — that was a
    misattribution. The historical "Stoll 2021" string may appear inside
    the audit trail (quoted, e.g., `"Stoll 2021" was a misattribution`)
    but must not appear as a live citation (unquoted, e.g., `(Stoll 2021)`
    or `per Stoll 2021`).
    """
    # Live citation patterns: parenthesized cite, "per Author Year", etc.,
    # with Stoll not immediately preceded by a quote character.
    live_pattern = re.compile(r'(?<![\"\u201C])Stoll\s*20\d\d(?![\"\u201D])')
    forms = iqm.get('choline', {}).get('forms', {})
    violations = []
    for fname, form in forms.items():
        for field in ('notes', 'absorption'):
            text = form.get(field) or ''
            if live_pattern.search(text):
                # Pull a 40-char window around the match for the error msg
                m = live_pattern.search(text)
                start = max(0, m.start() - 20)
                end = min(len(text), m.end() + 20)
                violations.append((fname, field, text[start:end]))
    assert not violations, (
        f'Live "Stoll 2021" citation still present (actual paper is '
        f'Böckmann 2021 PMID:34287673): {violations}'
    )


@pytest.mark.parametrize('form_name', CHOLINE_FORMS)
def test_choline_absorption_not_weight_fraction(iqm, form_name):
    """absorption field should describe PK, not "% choline by weight"."""
    form = iqm.get('choline', {}).get('forms', {}).get(form_name)
    assert form is not None, f'choline::{form_name} missing'
    s = form.get('absorption') or ''
    assert 'by weight' not in s.lower(), (
        f'choline::{form_name}: absorption string describes weight fraction '
        f'rather than absorption PK. Move that to notes. String: {s!r}'
    )


def test_bockmann_2021_cited_somewhere_in_choline(iqm):
    """The Böckmann 2021 PMID should appear in at least some choline notes."""
    forms = iqm.get('choline', {}).get('forms', {})
    hits = 0
    for form in forms.values():
        notes = form.get('notes') or ''
        if 'PMID:34287673' in notes or 'Böckmann 2021' in notes or 'Böckmann' in notes:
            hits += 1
    assert hits >= 3, (
        f'Böckmann 2021 (PMID:34287673) should be cited in ≥3 choline forms '
        f'(the 4-form crossover is the primary evidence). Found in {hits}.'
    )


def test_choline_struct_values_in_evidence_range(iqm):
    """All free-choline-releasing salts should cluster around 0.85-0.95 per
    Böckmann 2021; PC 0.75-0.90; CDP-choline ≥0.90 per Dinsdale 1983.
    """
    expected = {
        'alpha-GPC':                  (0.80, 0.95),
        'CDP-choline (citicoline)':   (0.90, 0.99),
        'phosphatidylcholine':        (0.75, 0.90),
        'choline bitartrate':         (0.80, 0.95),
        'choline citrate':            (0.80, 0.95),
        'choline chloride':           (0.80, 0.95),
    }
    forms = iqm['choline']['forms']
    violations = []
    for fname, (low, high) in expected.items():
        form = forms.get(fname, {})
        val = (form.get('absorption_structured') or {}).get('value')
        if val is None:
            continue
        if not (low <= val <= high):
            violations.append((fname, val, (low, high)))
    assert not violations, (
        f'choline struct.value out of evidence-supported range: {violations}'
    )
