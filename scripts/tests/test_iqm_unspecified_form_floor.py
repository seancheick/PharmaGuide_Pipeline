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
    """Return min bio_score across forms whose key does NOT contain 'unspecified'."""
    scores = []
    for fk, ff in forms.items():
        if not isinstance(ff, dict):
            continue
        if 'unspecified' in fk.lower():
            continue
        s = ff.get('bio_score')
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

# Every disclosed BCAA form is a premium ratio / instantized / peptide form
# (14-15). The ratio-unspecified generic form (renamed from "(standard)" on
# 2026-09-25, value unchanged at the curated 10) is not required to sit
# within one of them. Pinned in test_audit_locked_unspecified_scores_pinned.
_PREMIUM_ONLY_PEER_EXEMPTIONS = {
    'branched_chain_amino_acids',
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
    'vanadium':             4,  # minerals/B25: hazardous trace mineral — unknown-form floor (UMLS poison flag, GI tox >1.8 mg/day, ~5% F) kept below the disclosed sodium-vanadate class floor (7); conservative-by-design, and the safety-correct direction
    'vitamin_k2':           6,  # subtype undisclosed: cannot inherit MK-4, MK-7, cis-isomer, or source-specific properties
    'branched_chain_amino_acids': 10,  # ratio-unspecified generic BCAA; see _PREMIUM_ONLY_PEER_EXEMPTIONS
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
        if parent_key in _PREMIUM_ONLY_PEER_EXEMPTIONS:
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
            s = ff.get('bio_score')
            # The 2026-08-13 evidence contract caps unsupported unspecified
            # forms at bio_score 11. On bio_score (IQM 5.6.0, natural bonus
            # retired) the agreed rule is "unspecified = lowest valid named
            # form - 1", so an unspecified form may sit exactly one below
            # peer-min (curcumin: 5 vs 6), never further.
            evidence_ceiling = 11
            required_floor = min(peer_min - 1, evidence_ceiling)
            if isinstance(s, (int, float)) and s < required_floor:
                violations.append((parent_key, fk, s, required_floor))

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
        s = ff.get('bio_score')
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
    """Spot-check the highest-impact unspecified forms against the unknown-form
    owner (scoring_reference_resolver): the value is lowest eligible named
    bio_score - 1, or a documented override. The Batch-5 minimums these once
    pinned (maca 11, psyllium 11, holy basil 11) came from the 2026-08-13
    legacy restore and rewarded nondisclosure; they are superseded."""
    from scoring_reference_resolver import authored_unknown_form, unknown_floor, unknown_floor_override
    expected = {
        # parent: (value, 'floor' | 'override')
        'maca': (8, 'floor'),          # maca root powder 9 - 1
        'psyllium': (8, 'floor'),      # psyllium seed 9 - 1
        'holy_basil': (9, 'floor'),    # holy basil extract 10 - 1
        'rosemary': (9, 'floor'),      # rosemary essential oil 10 - 1
        'immunoglobulin': (10, 'floor'),
        'rhodiola': (8, 'override'),   # batch-13 audit lock
        'phosphatidylserine': (10, 'override'),
        'magnesium': (5, 'override'),  # clinician mineral table
    }
    for parent, (value, basis) in expected.items():
        name, form = authored_unknown_form(iqm[parent])
        assert form['bio_score'] == value, (parent, name, form['bio_score'])
        if basis == 'override':
            assert unknown_floor_override(form), parent
        else:
            assert not unknown_floor_override(form) and unknown_floor(iqm[parent])[0] == value, parent


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
            exp_bio = spec[f'{side}_bio']
            if bio != exp_bio:
                mismatches.append(f'{parent_key}/{form_key}: bio={bio} (expected bio={exp_bio})')
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

        if unspec.get('bio_score') != exp_bio:
            mismatches.append(f'{parent_key}/{unspec_form}: bio={unspec.get("bio_score")} expected bio={exp_bio}')
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
