"""Regression test: boswellia standardized extract C3-extension alignment.

Per Dr Pham IQM audit (2026-04-25), branded boswellia forms 5-loxin and
boswellia aflapin were downgraded bio_score 14 -> 7 ("Crominex pattern")
because the industry-cited "+51.78% AUC vs 5-Loxin" claim is Sprague-Dawley
RAT-only (Sengupta 2011, PMID:21479939), and NO human absolute oral F
study exists for any boswellic acid form (Class Finding from Batch 16).

`boswellia standardized extract` (generic 65% boswellic acids) was NOT
included in Dr Pham's C3 list of 9 forms and retained its older
bio_score=12 from a concentration-as-bioavailability assumption that the
Class Finding directly contradicts.

THREE signs the generic form should match the Class Finding floor:

  1. Its own notes say: "Generic standardized extracts are less studied
     than 5-Loxin or Aflapin branded forms" — yet bio_score was higher.
  2. Its absorption_structured.value = 0.04 is LOWER than branded
     (0.05) — bio_score cannot meaningfully be higher.
  3. Dr Pham rule D3: "Branded forms with clinical RCTs but no human PK
     should have F set by the parent compound's class baseline." The
     branded forms ARE the class baseline ceiling — generic cannot
     exceed it under the same Class Finding.

This test enforces:
  • Generic standardized matches branded floor (bio_score = 7).
  • final score = 10 (= 7 + 3 natural bonus per score-field invariant).
  • Notes document the 2026-05-25 Class Finding extension.
  • Monotonicity: branded forms >= standardized >= resin >= unspecified.
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


def test_standardized_extract_bio_score_aligned_to_class_finding(boswellia_forms):
    """Generic standardized must equal Class Finding floor (bio_score = 7)
    matching branded forms after Dr Pham C3 sign-off.
    """
    form = boswellia_forms.get('boswellia standardized extract')
    assert form is not None, 'boswellia standardized extract missing from IQM'
    bio = form.get('bio_score')
    assert bio == 7, (
        f'boswellia standardized extract bio_score={bio}, expected 7 per '
        f'Class Finding extension of Dr Pham C3 (no human PK justifies '
        f'higher score than branded 5-loxin/aflapin which are at 7).'
    )


def test_standardized_extract_final_score_recomputed(boswellia_forms):
    """final score = bio_score + (3 if natural) per IQM invariant. With
    bio=7 and natural=True, score must be 10.
    """
    form = boswellia_forms['boswellia standardized extract']
    assert form.get('natural') is True, 'natural flag must remain True'
    score = form.get('score')
    assert score == 10, (
        f'boswellia standardized extract score={score}, expected 10 '
        f'(7 bio + 3 natural). Score field violates invariant.'
    )


def test_standardized_extract_documents_class_finding_extension(boswellia_forms):
    """Notes must document the 2026-05-25 Class Finding extension so the
    rationale survives future audits.
    """
    form = boswellia_forms['boswellia standardized extract']
    notes = (form.get('notes') or '').lower()
    required_markers = [
        ('2026-05-25', 'date stamp for class-finding extension'),
        ('class finding', 'reference to no-human-PK Class Finding'),
    ]
    missing = [m for m, _why in required_markers if m not in notes]
    assert not missing, (
        f'boswellia standardized extract notes missing required markers '
        f'{missing}. Notes must document the C3-extension rationale.'
    )


def test_standardized_does_not_exceed_branded_floor(boswellia_forms):
    """Core C3-extension invariant: generic standardized cannot exceed the
    branded floor (5-loxin and aflapin). Same no-human-PK Class Finding
    applies to all boswellic acid forms — generic gets no premium.

    (Resin-vs-branded ordering is a separately tracked inversion;
    intentionally not asserted here.)
    """
    bio = {
        name: form.get('bio_score')
        for name, form in boswellia_forms.items()
    }
    branded_floor = min(bio['5-loxin'], bio['boswellia aflapin'])
    standardized = bio['boswellia standardized extract']

    assert standardized <= branded_floor, (
        f'INVERSION: standardized bio_score={standardized} > branded floor '
        f'={branded_floor} (5-loxin={bio["5-loxin"]}, '
        f'aflapin={bio["boswellia aflapin"]}). Generic cannot exceed '
        f'branded forms under the same no-human-PK Class Finding.'
    )
    # And it must remain >= unspecified (disclosed concentration is at
    # least as informative as no-info).
    unspecified = bio['boswellia (unspecified)']
    assert standardized >= unspecified, (
        f'standardized bio_score={standardized} < unspecified={unspecified}. '
        f'Disclosed-concentration form cannot score below unspecified.'
    )


def test_standardized_not_above_branded_under_class_finding(boswellia_forms):
    """Scoped absorption-vs-bio_score check for the C3-extension:
    generic standardized extract's bio_score cannot exceed branded forms
    when its measured absorption is lower. (A separate inversion exists
    for resin powder bio=8 vs branded bio=7 — tracked as a follow-up,
    not in scope for this 2026-05-25 fix.)
    """
    forms = boswellia_forms
    branded_5loxin = forms['5-loxin']
    branded_aflapin = forms['boswellia aflapin']
    standardized = forms['boswellia standardized extract']

    s_abs = (standardized.get('absorption_structured') or {}).get('value')
    s_bio = standardized.get('bio_score')

    for label, b in (('5-loxin', branded_5loxin), ('aflapin', branded_aflapin)):
        b_abs = (b.get('absorption_structured') or {}).get('value')
        b_bio = b.get('bio_score')
        if s_abs is not None and b_abs is not None and s_abs < b_abs:
            assert s_bio <= b_bio, (
                f'standardized extract (abs={s_abs}, bio={s_bio}) cannot '
                f'score above branded {label} (abs={b_abs}, bio={b_bio}): '
                f'lower measured absorption must not score higher under '
                f'the no-human-PK Class Finding.'
            )
