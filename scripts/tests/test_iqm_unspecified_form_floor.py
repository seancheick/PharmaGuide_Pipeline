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

# Probiotic species-only exemptions (2026-06-06).
#
# The generic peer-min rule is correct for most supplement forms, but it is
# wrong for probiotics because named strains are not merely "specific forms" of
# an honest-middle parent. They carry strain-specific clinical identity that v4
# scores separately in the probiotic module. A species-only row should not be
# forced up to the named-strain peer minimum.
_PROBIOTIC_SPECIES_ONLY_PEER_MIN_EXEMPTIONS = {
    'lactobacillus_casei',
    'saccharomyces_boulardii',
    'streptococcus_salivarius',
    'lactobacillus_reuteri',
    'bacillus_coagulans',
    'bacillus_subtilis',
    'lactobacillus_paracasei',
    'lactobacillus_gasseri',
    'bifidobacterium_breve',
    'bacillus_clausii',
}

# Undisclosed oil/fatty-acid forms deliberately sit below disclosed lower-quality
# forms and are locked in test_iqm_report_mechanical_fixes.py. This older
# peer-min contract predates that convention.
_UNDISCLOSED_OIL_PEER_MIN_EXEMPTIONS = {
    'dha',
    'epa',
    'fish_oil',
    'ceramides',
    'hemp_seed_oil',
}

# Standardization-marker peer-min exemptions (2026-05-25).
#
# The peer-min policy (Batch 5 recalibration, 2026-04-29) assumes the
# higher-scoring peer form is "the cheapest specific form a label could
# plausibly contain" — a cheap-plausible baseline. That assumption holds
# for generic-extract peers but BREAKS when the higher peer is a
# *standardization-marker* form (saponin, aescin, hederacoside C, ginkgolide,
# etc.) carrying a clinical premium that the unspecified form intentionally
# does not — because no marker is guaranteed in unspecified material.
#
# Raising the unspecified score to match a marker-locked peer would erase
# a clinically meaningful distinction. The right answer is exemption + a
# lock on the intended spread (see test_standardization_marker_spread_locked
# below) — NOT scoring inflation in the IQM data.
#
# Each exemption MUST be paired with an entry in
# _STANDARDIZATION_MARKER_LOCKED_SPREAD so the gap cannot silently drift.
_STANDARDIZATION_MARKER_PEER_MIN_EXEMPTIONS = {
    'english_ivy',           # hederacoside C marker (Hedera helix saponin)
    'horse_chestnut_seed',   # aescin marker (Aesculus hippocastanum triterpene)
    'lutein',                # disclosed FloraGLO/Lutemax/free-lutein form
}

# Locked spread for standardization-marker exemptions. (unspec_score,
# standardized_score) pairs the intended gap so any future score change
# requires updating both the exemption and this lock together.
_STANDARDIZATION_MARKER_LOCKED_SPREAD = {
    'english_ivy': {
        'unspec_form':       'english ivy leaf extract (unspecified)',
        'unspec_bio':        8,
        'unspec_score':      11,
        'marker_form':       'english ivy standardized (hederacoside C marker)',
        'marker_bio':        10,
        'marker_score':      13,
    },
    'horse_chestnut_seed': {
        'unspec_form':       'horse chestnut seed (unspecified)',
        'unspec_bio':        8,
        'unspec_score':      11,
        'marker_form':       'horse chestnut standardized (aescin marker)',
        'marker_bio':        10,
        'marker_score':      13,
    },
    'lutein': {
        'unspec_form':       'lutein (unspecified)',
        'unspec_bio':        8,
        'unspec_score':      8,
        'marker_form':       'free lutein (floraglo / lutemax, marigold)',
        'marker_bio':        10,
        'marker_score':      13,
    },
}

_LOCAL_MATRIX_UNSPECIFIED_PEER_MIN_EXEMPTIONS = {
    'lions_mane',
    'reishi',
    'cordyceps',
    'chaga',
    'shiitake',
    'maitake',
    'turkey_tail',
    'button_mushroom',
    'auricularia',
    'manuka_honey',
}

_LOCAL_MATRIX_UNSPECIFIED_LOCKED_SPREAD = {
    'lions_mane': ("lion's mane (unspecified)", 5, 5, 9),
    'reishi': ('reishi (unspecified)', 5, 5, 9),
    'cordyceps': ('cordyceps (unspecified)', 5, 5, 8),
    'chaga': ('chaga (unspecified)', 5, 5, 9),
    'shiitake': ('shiitake (unspecified)', 5, 5, 9),
    'maitake': ('maitake (unspecified)', 5, 5, 9),
    'turkey_tail': ('turkey tail (unspecified)', 5, 5, 9),
    'button_mushroom': ('button mushroom (unspecified)', 5, 5, 8),
    'auricularia': ('auricularia (unspecified)', 5, 5, 9),
    'manuka_honey': ('manuka honey (unspecified)', 8, 8, 9),
}


# Audit-locked "(unspecified)" peer-min exemptions (2026-06-16).
#
# The Batch-5 peer-min floor (2026-04-29, above) is a *generic* recalibration:
# it assumes an unspecified form should never sit below the cheapest plausible
# disclosed peer. A later wave of *specific* clinical audits deliberately locked
# several unspecified forms BELOW their peer-min, because the parent's real
# worst-case form is genuinely lower-quality than the generic floor assumes
# (intact ATP is not orally bioavailable; an unknown-matrix carotenoid sits
# below any disclosed source; marker/species-free botanicals sit below their
# standardized extracts; generic "prebiotics"/"choline" sit below disclosed
# FOS-GOS / citrate forms).
#
# Specific audit locks win over the generic floor. Each parent below is pinned
# to its exact locked score by the cited audit suite AND re-pinned in
# test_audit_locked_unspecified_scores_pinned, so the value cannot drift in
# either direction without explicit review against the owning audit.
_AUDIT_LOCKED_UNSPECIFIED_PEER_MIN_EXEMPTIONS = {
    'astaxanthin':         10,  # minerals_actives_06b: unknown matrix < disclosed source
    'atp':                  6,  # botanicals_actives_06c: intact ATP < disodium salt
    'phosphatidylcholine': 11,  # botanicals_actives_06c: undisclosed < soy-PC
    'stinging_nettle':      9,  # botanicals_actives_06c: < root 11 / leaf 10
    'pygeum':               8,  # botanicals_actives_06c: < bark extract 11
    'prebiotics':           9,  # probiotics_phospholipids_06f: < disclosed FOS/GOS/HMO/XOS
    'choline':              8,  # probiotics_phospholipids_06f / b33: < citrate/bitartrate 10
    'rhodiola':             8,  # botanicals_06o: < rosavin-standardized extract
    'ginkgo':               8,  # botanicals_06o: < EGb 24% flavone-glycoside extract
}


def test_no_unspec_form_scores_below_peer_min(iqm):
    """Every '(unspecified)' form must score ≥ parent's peer min,
    EXCEPT for clinician-locked overrides (Dr Pham probiotic sign-off) and
    standardization-marker exemptions (see exemption set above)."""
    violations = []
    for parent_key, v in iqm.items():
        if parent_key.startswith('_') or not isinstance(v, dict):
            continue
        if parent_key in _DR_PHAM_PEER_MIN_EXEMPTIONS:
            continue
        if parent_key in _PROBIOTIC_SPECIES_ONLY_PEER_MIN_EXEMPTIONS:
            continue
        if parent_key in _UNDISCLOSED_OIL_PEER_MIN_EXEMPTIONS:
            continue
        if parent_key in _STANDARDIZATION_MARKER_PEER_MIN_EXEMPTIONS:
            continue
        if parent_key in _LOCAL_MATRIX_UNSPECIFIED_PEER_MIN_EXEMPTIONS:
            continue
        if parent_key in _AUDIT_LOCKED_UNSPECIFIED_PEER_MIN_EXEMPTIONS:
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


def test_audit_locked_unspecified_scores_pinned(iqm):
    """Pin the exact score of every audit-locked unspecified form that is
    exempted from the peer-min floor.

    These forms are deliberately BELOW peer-min (see
    _AUDIT_LOCKED_UNSPECIFIED_PEER_MIN_EXEMPTIONS). The exemption alone would
    let the score drift silently in either direction — including a well-meant
    "raise it to satisfy the floor" edit that would undo the clinical audit.
    This test re-pins each form to its exact audit-locked value, forcing any
    change to be reconciled with the owning test_iqm_*_audit_2026_06* suite
    rather than this generic floor test.
    """
    mismatches = []
    for parent_key, locked_score in _AUDIT_LOCKED_UNSPECIFIED_PEER_MIN_EXEMPTIONS.items():
        forms = iqm.get(parent_key, {}).get('forms', {})
        unspec = {k: f for k, f in forms.items()
                  if isinstance(f, dict) and 'unspecified' in k.lower()}
        if not unspec:
            mismatches.append(f'{parent_key}: no unspecified form found')
            continue
        fk, ff = next(iter(unspec.items()))
        s = ff.get('score')
        if s != locked_score:
            mismatches.append(
                f'{parent_key}/{fk}: score={s}, expected audit-locked {locked_score}'
            )
    assert not mismatches, (
        'Audit-locked unspecified scores drifted. Specific audit locks win over '
        'the generic peer-min floor — if a value here changed, reconcile with the '
        'owning test_iqm_*_audit_2026_06* suite, not this floor test:\n  '
        + '\n  '.join(mismatches)
    )


def test_recalibrated_high_impact_entries(iqm):
    """Spot-check the highest-impact recalibrations from the audit."""
    expected = {
        # parent: minimum acceptable unspec score (peer-min from audit)
        'maca': 12,
        'ashwagandha': 7,
        # rhodiola/pygeum/atp/phosphatidylserine were lowered to their later
        # audit-locked unspecified scores (botanicals_06o / botanicals_actives_06c /
        # the phospholipid audit). The generic peer-min spot-check must not
        # demand more than the specific audit lock allows. See
        # _AUDIT_LOCKED_UNSPECIFIED_PEER_MIN_EXEMPTIONS and
        # test_audit_locked_unspecified_scores_pinned.
        'rhodiola': 8,
        'pygeum': 8,
        'atp': 6,
        'resveratrol': 11,
        'phosphatidylserine': 10,
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


def test_standardization_marker_spread_locked(iqm):
    """Lock the intended (unspec, standardized-marker) spread for parents
    exempted from peer-min. Required to prevent silent drift — any future
    score change to one side without the other will fail this test, forcing
    explicit review of the standardization premium.

    The exemption set and this lock must be kept in sync: every entry in
    _STANDARDIZATION_MARKER_PEER_MIN_EXEMPTIONS must have a matching entry
    here.
    """
    # Sync invariant first — fail loudly if a parent is exempted but not locked.
    unlocked = (
        _STANDARDIZATION_MARKER_PEER_MIN_EXEMPTIONS
        - _STANDARDIZATION_MARKER_LOCKED_SPREAD.keys()
    )
    assert not unlocked, (
        f'Standardization-marker parents exempted from peer-min but not '
        f'locked in _STANDARDIZATION_MARKER_LOCKED_SPREAD: {unlocked}. '
        f'Every exemption must pair with an intended-spread lock.'
    )

    mismatches = []
    for parent_key, spec in _STANDARDIZATION_MARKER_LOCKED_SPREAD.items():
        forms = iqm.get(parent_key, {}).get('forms', {})
        if not forms:
            mismatches.append(f'{parent_key}: missing from IQM')
            continue
        for side in ('unspec', 'marker'):
            form_key = spec[f'{side}_form']
            form = forms.get(form_key)
            if not isinstance(form, dict):
                mismatches.append(f'{parent_key}/{form_key}: missing form')
                continue
            bio = form.get('bio_score')
            score = form.get('score')
            exp_bio = spec[f'{side}_bio']
            exp_score = spec[f'{side}_score']
            if bio != exp_bio or score != exp_score:
                mismatches.append(
                    f'{parent_key}/{form_key}: bio={bio}/score={score} '
                    f'(expected bio={exp_bio}/score={exp_score})'
                )
    assert not mismatches, (
        'Standardization-marker spread drifted from locked values. Either '
        'the IQM was edited without updating _STANDARDIZATION_MARKER_LOCKED_'
        'SPREAD, or the lock needs deliberate revision after clinical '
        'review:\n  ' + '\n  '.join(mismatches)
    )


def test_local_matrix_mushroom_unspecified_spread_locked(iqm):
    """Mushroom/fungal actives are local/matrix ingredients.

    Their form-quality signal is fruiting body / extract / standardization
    disclosure, not systemic absorption alone. An unspecified mushroom row
    must therefore sit below the lowest disclosed form and must not receive a
    natural-source bonus.
    """
    unlocked = (
        _LOCAL_MATRIX_UNSPECIFIED_PEER_MIN_EXEMPTIONS
        - _LOCAL_MATRIX_UNSPECIFIED_LOCKED_SPREAD.keys()
    )
    assert not unlocked, (
        f'Local/matrix parents exempted from peer-min but not spread-locked: {unlocked}'
    )

    mismatches = []
    for parent_key, (unspec_form, exp_bio, exp_score, exp_lowest_disclosed) in (
        _LOCAL_MATRIX_UNSPECIFIED_LOCKED_SPREAD.items()
    ):
        forms = iqm.get(parent_key, {}).get('forms', {})
        unspec = forms.get(unspec_form)
        if not isinstance(unspec, dict):
            mismatches.append(f'{parent_key}/{unspec_form}: missing form')
            continue

        disclosed_bios = [
            form.get('bio_score')
            for form_name, form in forms.items()
            if form_name != unspec_form
            and isinstance(form, dict)
            and isinstance(form.get('bio_score'), (int, float))
        ]
        lowest_disclosed = min(disclosed_bios) if disclosed_bios else None

        if unspec.get('bio_score') != exp_bio or unspec.get('score') != exp_score:
            mismatches.append(
                f'{parent_key}/{unspec_form}: bio={unspec.get("bio_score")}/'
                f'score={unspec.get("score")} expected bio={exp_bio}/score={exp_score}'
            )
        if unspec.get('natural') is not False:
            mismatches.append(f'{parent_key}/{unspec_form}: natural must be false')
        if lowest_disclosed != exp_lowest_disclosed:
            mismatches.append(
                f'{parent_key}: lowest disclosed bio={lowest_disclosed}, '
                f'expected {exp_lowest_disclosed}'
            )
        if isinstance(lowest_disclosed, (int, float)) and unspec.get('bio_score') >= lowest_disclosed:
            mismatches.append(
                f'{parent_key}/{unspec_form}: unspecified bio={unspec.get("bio_score")} '
                f'must be below lowest disclosed bio={lowest_disclosed}'
            )

    assert not mismatches, (
        'Local/matrix mushroom unspecified spread drifted from locked values:\n  '
        + '\n  '.join(mismatches)
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
