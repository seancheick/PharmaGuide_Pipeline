#!/usr/bin/env python3
"""
IQM "(unspecified)" form scoring contract (Batch 5 recalibration, 2026-04-29).

Bug discovered 2026-04-29: 151 IQM parents had an "(unspecified)" form
scoring 5-9 points below their peer forms (median 9-point gap). Examples:
- reishi (unspecified)        score=5  vs peer min=12  →  +7 unfair penalty
- ashwagandha (unspecified)   score=5  vs peer min=7   →  +2 unfair penalty
- pygeum (unspecified)        score=5  vs peer min=14  →  +9 unfair penalty
- atp (unspecified)           score=5  vs peer min=14  →  +9 unfair penalty

Symptom: 1,966 SAFE products scored below 50 just because their label
said "Reishi 500mg" without specifying "(red reishi extract 1:10)".

Policy decision (2026-04-29): the "(unspecified)" form must NEVER score
below the parent's peer-form minimum. The realistic worst-case bioavail-
ability/quality is the cheapest specific form a label could plausibly
contain, NOT a 5-point punitive default. Severe under-scoring of the
honest middle of the market is worse than mild over-scoring of a few
genuinely under-formulated unspec products.
"""

import json
import os

import pytest


@pytest.fixture(scope="module")
def iqm():
    return json.load(open(os.path.join(
        os.path.dirname(__file__), "..", "data", "ingredient_quality_map.json"
    )))


def _peer_min_score(forms):
    """Return min score across forms whose key does NOT contain 'unspecified'."""
    scores = []
    for fk, ff in forms.items():
        if not isinstance(ff, dict):
            continue
        if 'unspecified' in fk.lower():
            continue
        s = ff.get('score')
        if isinstance(s, (int, float)):
            scores.append(s)
    return min(scores) if scores else None


# Clinician (Dr Pham) explicitly signed off on bio_scores below peer-min for
# these probiotic strains. Override of the peer-min policy is intentional —
# enforced by test_b35_dr_pham_signoff_integrity. The peer-min contract
# defers to the clinician override here.
_DR_PHAM_PEER_MIN_EXEMPTIONS = {
    'lactobacillus_plantarum',
    'bifidobacterium_lactis',
    'lactobacillus_rhamnosus',
}


def test_no_unspec_form_scores_below_peer_min(iqm):
    """Every '(unspecified)' form must score ≥ parent's peer min,
    EXCEPT for clinician-locked overrides (Dr Pham probiotic sign-off)."""
    violations = []
    for parent_key, v in iqm.items():
        if parent_key.startswith('_') or not isinstance(v, dict):
            continue
        if parent_key in _DR_PHAM_PEER_MIN_EXEMPTIONS:
            continue
        forms = v.get('forms', {})
        if not isinstance(forms, dict):
            continue
        peer_min = _peer_min_score(forms)
        if peer_min is None:
            continue
        for fk, ff in forms.items():
            if not isinstance(ff, dict) or 'unspecified' not in fk.lower():
                continue
            s = ff.get('score')
            if isinstance(s, (int, float)) and s < peer_min:
                violations.append((parent_key, fk, s, peer_min))

    assert not violations, (
        f"Found {len(violations)} '(unspecified)' forms below peer-min "
        f"(unfair under-scoring of honest-middle products):\n"
        + "\n".join(
            f"  {p}/{f}: score={s} but peer_min={pm} (gap={pm-s})"
            for p, f, s, pm in violations[:15]
        )
    )


def test_recalibrated_high_impact_entries(iqm):
    """Spot-check the highest-impact recalibrations from the audit."""
    expected = {
        # parent: minimum acceptable unspec score (peer-min from audit)
        'reishi': 12,
        'maca': 12,
        'ashwagandha': 7,
        'rhodiola': 10,
        'pygeum': 14,
        'atp': 14,
        'resveratrol': 11,
        'phosphatidylserine': 12,
        'collagen': 10,
        'psyllium': 12,
        'holy_basil': 13,
        'sulforaphane': 10,
    }
    for parent, min_score in expected.items():
        if parent not in iqm:
            continue
        forms = iqm[parent].get('forms', {})
        unspec_forms = {k: v for k, v in forms.items()
                        if isinstance(v, dict) and 'unspecified' in k.lower()}
        if not unspec_forms:
            continue
        unspec = next(iter(unspec_forms.values()))
        s = unspec.get('score')
        assert isinstance(s, (int, float)) and s >= min_score, (
            f"{parent} unspec must score ≥{min_score} (peer-min); got {s}"
        )


def test_schema_formula_still_holds_after_recalibration(iqm):
    """Recalibration must preserve schema rule:
    score = bio_score + (3 if natural else 0)."""
    mismatches = []
    for parent_key, v in iqm.items():
        if parent_key.startswith('_') or not isinstance(v, dict):
            continue
        for form_key, form in v.get('forms', {}).items():
            if not isinstance(form, dict):
                continue
            bio = form.get('bio_score')
            score = form.get('score')
            natural = bool(form.get('natural', False))
            if isinstance(bio, (int, float)) and isinstance(score, (int, float)):
                expected = bio + (3 if natural else 0)
                if score != expected:
                    mismatches.append((parent_key, form_key, bio, natural, score, expected))
    assert not mismatches, (
        f"Recalibration broke schema formula in {len(mismatches)} forms:\n"
        + "\n".join(
            f"  {p}/{f}: bio={b}, natural={n}, score={s}, expected={e}"
            for p, f, b, n, s, e in mismatches[:10]
        )
    )
