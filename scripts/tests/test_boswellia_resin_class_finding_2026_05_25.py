"""Regression test: boswellia resin powder Class Finding alignment.

Companion to test_boswellia_standardized_class_finding_2026_05_25.py.

Background
----------
Batch 16 (5.0.18, 2026-04-25) audit established the boswellia Class Finding:
"NO human absolute oral F study exists for any boswellic acid form." The
research subagent recommended 5 downgrades pending Dr Pham clinical signoff:

  - 5-loxin:                      14 -> 9   (signed off as 14 -> 7)
  - boswellia aflapin:            14 -> 9   (signed off as 14 -> 7)
  - boswellia standardized extract:12 -> 8   (extended 2026-05-25 to 12 -> 7)
  - boswellia resin powder:        8 -> 5   (NEVER signed off)
  - boswellia (unspecified):       6 -> 4   (settled at 7)

Dr Pham's audit doc (Section C3 "Crominex pattern") only enumerated branded
forms — resin powder was never reviewed. As a result resin retained
bio_score=8 while branded forms dropped to 7, producing an inversion:

  resin:      bio_score=8, absorption_structured.value=0.03  <- LOWEST abs
  branded:    bio_score=7, absorption_structured.value=0.05  <- HIGHEST abs
  standardized: bio_score=7, absorption_structured.value=0.04

Lower measured absorption scoring HIGHER violates the absorption-monotonicity
rule applied to the other 4 forms and contradicts the Class Finding ("no
form has human PK premium").

This 2026-05-25 follow-up extends the standardized-extract fix to resin:
bio_score 8 -> 7. Resin's notes already cite the Class Finding (added at
Batch 16). The fix is purely the bio_score (and recomputed score field).

The original Batch 16 rec (8 -> 5) was more aggressive than needed; 8 -> 7
removes the inversion and brings resin to the Class Finding floor without
overcorrecting. A future Dr Pham re-review may revisit, but the inversion
must not stand.

Blast radius: 1 product in the corpus.

This test enforces:
  • resin bio_score = 7 (Class Finding floor)
  • resin score = 10 (= 7 + 3 natural bonus per score-field invariant)
  • Notes still cite the Batch 16 Class Finding
  • resin bio_score <= branded floor (no inversion)
  • No boswellia form scores higher than any other form with strictly
    higher absorption_structured.value (full monotonicity).
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


@pytest.fixture(scope='module')
def boswellia_forms(iqm):
    return iqm['boswellia']['forms']


def test_resin_powder_bio_score_aligned_to_class_finding(boswellia_forms):
    """Resin powder must equal Class Finding floor (bio_score = 7) matching
    branded/standardized forms. Same no-human-PK Class Finding applies.
    """
    form = boswellia_forms.get('boswellia resin powder')
    assert form is not None, 'boswellia resin powder missing from IQM'
    bio = form.get('bio_score')
    assert bio == 7, (
        f'boswellia resin powder bio_score={bio}, expected 7 per '
        f'2026-05-25 Class Finding extension (originally 8 — inverted '
        f'above branded forms which dropped to 7 at Dr Pham C3 signoff).'
    )


def test_resin_powder_final_score_recomputed(boswellia_forms):
    """score = bio_score + 3 (natural bonus). 7 + 3 = 10. Old score=11
    (8 + 3) must be recomputed when bio_score drops.
    """
    form = boswellia_forms['boswellia resin powder']
    bio = form['bio_score']
    score = form.get('score')
    assert score == bio + 3, (
        f'boswellia resin powder score={score}, expected {bio + 3} '
        f'(bio_score + 3 natural bonus). Was the score field forgotten '
        f'after the bio_score change?'
    )


def test_resin_powder_documents_class_finding(boswellia_forms):
    """Notes must continue to cite Batch 16 Class Finding markers (already
    present per 2026-04-25 audit); the 2026-05-25 fix is bio_score-only
    and must not erase the existing rationale.
    """
    form = boswellia_forms['boswellia resin powder']
    notes = form.get('notes', '')
    required_markers = [
        'Batch 16',
        'CLASS FINDING',
        'NO human absolute oral F study',
        'PMID:15643550',  # Sterk 2004
    ]
    missing = [m for m in required_markers if m not in notes]
    assert not missing, (
        f'boswellia resin powder notes missing required Class Finding '
        f'markers: {missing}. Notes preview: {notes[:300]!r}'
    )


def test_resin_does_not_exceed_branded_floor(boswellia_forms):
    """Core invariant: resin powder bio_score cannot exceed the branded
    floor (5-loxin and aflapin). Same no-human-PK Class Finding applies
    to all boswellic acid forms — crude resin gets no premium.
    """
    bio = {
        name: form.get('bio_score')
        for name, form in boswellia_forms.items()
    }
    branded_floor = min(bio['5-loxin'], bio['boswellia aflapin'])
    resin = bio['boswellia resin powder']
    assert resin <= branded_floor, (
        f'INVERSION: resin powder bio_score={resin} > branded floor '
        f'={branded_floor} (5-loxin={bio["5-loxin"]}, '
        f'aflapin={bio["boswellia aflapin"]}). Crude resin cannot '
        f'exceed branded forms under the same no-human-PK Class Finding.'
    )


def test_no_boswellia_form_inverts_absorption(boswellia_forms):
    """Full monotonicity: no boswellia form may have bio_score strictly
    greater than another form whose absorption_structured.value is
    strictly higher. Under the Class Finding (no form has human PK),
    measured absorption is the only objective signal for ordering.
    """
    rows = []
    for name, form in boswellia_forms.items():
        bio = form.get('bio_score')
        v = (form.get('absorption_structured') or {}).get('value')
        if bio is None or v is None:
            continue
        rows.append((name, bio, v))

    violations = []
    for i, (n1, b1, v1) in enumerate(rows):
        for n2, b2, v2 in rows[i + 1:]:
            # If form2 has strictly higher absorption but lower bio_score,
            # that's an inversion. Symmetric check.
            if v2 > v1 and b1 > b2:
                violations.append(
                    f'{n1} (bio={b1}, abs={v1}) > {n2} (bio={b2}, abs={v2})'
                )
            if v1 > v2 and b2 > b1:
                violations.append(
                    f'{n2} (bio={b2}, abs={v2}) > {n1} (bio={b1}, abs={v1})'
                )
    assert not violations, (
        'Absorption-vs-bio_score inversions in boswellia.forms — under the '
        'no-human-PK Class Finding, no form may score above another with '
        f'strictly higher measured absorption: {violations}'
    )
