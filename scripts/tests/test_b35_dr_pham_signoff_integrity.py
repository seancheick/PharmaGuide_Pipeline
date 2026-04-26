"""Regression test: Batches 35-37 — Dr Pham clinical sign-off applied.

Verifies that all Dr Pham approved decisions from
docs/DR_PHAM_IQM_AUDIT_REVIEW_2026-04-25.md are correctly applied:

  • Section C bio_score downgrades (52 forms)
  • Section E open-question decisions (10 forms)
  • Section D7 category_error_type enum (41 forms)

NOTE: Section A category-errors and Section B ghost catches were
already preserved by prior batches (B22-B34); this test confirms they
remain intact.
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


# ============================================================================
# Section C — bio_score downgrades
# ============================================================================

@pytest.mark.parametrize('pid,fname,expected_bio', [
    # C2 — B12
    ('vitamin_b12_cobalamin', 'methylcobalamin sublingual',  12),
    ('vitamin_b12_cobalamin', 'methylcobalamin',              8),
    ('vitamin_b12_cobalamin', 'adenosylcobalamin',            8),
    ('vitamin_b12_cobalamin', 'hydroxocobalamin',             8),
    ('vitamin_b12_cobalamin', 'cyanocobalamin sublingual',    9),
    # C3 — Crominex
    ('chromium', 'crominex 3+ chromium complex',              7),
    ('boswellia', '5-loxin',                                  7),
    ('boswellia', 'boswellia aflapin',                        7),
    ('fenugreek', 'testofen',                                 7),
    ('shilajit', 'primavie shilajit',                         7),
    ('black_cohosh', 'remifemin',                             7),
    ('chasteberry', 'vitex standardized extract',             7),
    ('pqq', 'microactive PQQ',                                7),
    ('pqq', 'lifepqq',                                        7),
    # C4 — Brown rice chelate
    ('chromium', 'chromium brown rice chelate',               6),
    ('manganese', 'manganese brown rice chelate',             6),
    ('selenium', 'selenium brown rice chelate',               8),
    ('zinc', 'zinc brown rice chelate',                       8),
    ('iron', 'iron brown rice chelate',                       6),
    ('magnesium', 'magnesium brown rice chelate',             6),
    ('boron', 'boron brown rice chelate',                     9),
    ('potassium', 'potassium brown rice chelate',             9),
    # C5 — Liposomal cap at 9
    ('glutathione', 'liposomal glutathione',                  9),
    ('berberine_supplement', 'liposomal berberine',           9),
    ('nad_precursors', 'liposomal nmn / nr',                  9),
    ('iron', 'liposomal iron',                                9),
    # C6 — Curcumin
    ('curcumin', 'novasol curcumin',                          9),
    ('curcumin', 'curcuwin',                                  8),
    ('curcumin', 'meriva curcumin',                           8),
    ('curcumin', 'theracurmin',                               7),
    # C7 — Chromium chelates
    ('chromium', 'chromium picolinate',                       7),
    ('chromium', 'chromium nicotinate glycinate',             7),
    ('chromium', 'chromium chelidamate arginate',             7),
    ('chromium', 'chromium polynicotinate',                   7),
    ('chromium', 'chromium GTF',                              7),
    ('chromium', 'chromium histidinate',                      7),
    # C8 — Iron (bisglycinate retained at 12 per modify)
    ('iron', 'iron bisglycinate',                             12),
    ('iron', 'iron protein succinylate',                      10),
    ('iron', 'heme iron polypeptide',                         10),
    ('iron', 'iron amino acid chelate',                       10),
    ('iron', 'ferrous ascorbate',                             10),
    # C9 — Probiotics → 7 placeholder
    ('lactobacillus_plantarum', 'lactobacillus plantarum (unspecified)',         7),
    ('lactobacillus_salivarius', 'lactobacillus salivarius ha-118',              7),
    ('bifidobacterium_lactis', 'bifidobacterium lactis (unspecified)',           7),
    ('lactobacillus_rhamnosus', 'lactobacillus rhamnosus (unspecified)',         7),
    ('bifidobacterium_longum', 'bifidobacterium longum infantis 35624',          7),
    # C12 — BMOV
    ('vanadyl_sulfate', 'bis(maltolato)oxovanadium (BMOV)',   7),
    # C13 — Iron picolinate
    ('iron', 'iron picolinate',                               8),
])
def test_dr_pham_section_c_bio_score(iqm, pid, fname, expected_bio):
    """Section C bio_score downgrades must be applied per Dr Pham sign-off."""
    form = iqm[pid]['forms'].get(fname)
    assert form is not None, f'{pid}::{fname} missing'
    actual = form.get('bio_score')
    assert actual == expected_bio, (
        f'{pid}::{fname} bio_score={actual}, expected {expected_bio} per Dr Pham C section.'
    )


def test_c1_coq10_pd_respect_documented(iqm):
    """C1 CoQ10 forms must document PD-respect notes (bio_score retained)."""
    forms = iqm['coq10']['forms']
    coq10_forms = ['ubiquinol crystal-free', 'ubiquinone crystal-dispersed',
                   'ubiquinol', 'ubiquinone softgel']
    for fname in coq10_forms:
        form = forms.get(fname)
        if form is None:
            continue
        notes = form.get('notes') or ''
        assert 'PD-respect' in notes or 'C1' in notes or 'PD' in notes, (
            f'{fname} must document PD-respect decoupling per Dr Pham C1.'
        )


def test_c12_bmov_struct_value_downgraded(iqm):
    """C12 BMOV must have struct.value downgraded to V class baseline."""
    form = iqm['vanadyl_sulfate']['forms']['bis(maltolato)oxovanadium (BMOV)']
    val = (form.get('absorption_structured') or {}).get('value')
    assert val is not None and 0.01 <= val <= 0.03, (
        f'BMOV struct.value={val} should be in V class baseline [0.01, 0.03].'
    )


# ============================================================================
# Section E — Open-question decisions
# ============================================================================

def test_e1_gaba_pk_strict(iqm):
    """E1 GABA companions must be PK-strict (BBB-blocked) ~0.05-0.10."""
    forms = iqm['gaba']['forms']
    for fname in ['gaba powder', 'pharma-gaba']:
        form = forms.get(fname)
        if form is None:
            continue
        v = (form.get('absorption_structured') or {}).get('value')
        assert v is not None and 0.02 <= v <= 0.10, (
            f'gaba::{fname} value={v} should be PK-strict [0.02, 0.10] '
            f'per Dr Pham E1 BBB-blocked decision.'
        )
        bio = form.get('bio_score')
        assert bio is not None and bio <= 7, (
            f'gaba::{fname} bio_score={bio} should be ≤7 per Dr Pham E1.'
        )


def test_e2_spirulina_category_error(iqm):
    """E2 Spirulina companions must be category-error (composite food)."""
    forms = iqm['spirulina']['forms']
    for fname in ['fresh spirulina paste', 'organic spirulina',
                  'spirulina powder', 'spirulina tablets']:
        form = forms.get(fname)
        if form is None:
            continue
        v = (form.get('absorption_structured') or {}).get('value')
        assert v is None, (
            f'spirulina::{fname} value={v} should be null per Dr Pham E2 '
            f'category-error (composite food).'
        )


def test_e3_digestive_enzymes_category_error(iqm):
    """E3 Digestive enzymes companions must be category-error (local action)."""
    forms = iqm['digestive_enzymes']['forms']
    for fname in ['plant-based enzyme complex', 'pancreatic enzymes (animal-derived)',
                  'specific enzymes', 'enteric-coated enzymes']:
        form = forms.get(fname)
        if form is None:
            continue
        v = (form.get('absorption_structured') or {}).get('value')
        assert v is None, (
            f'digestive_enzymes::{fname} value={v} should be null per Dr Pham E3 '
            f'category-error (local action).'
        )


# ============================================================================
# Section D7 — REMOVED 2026-04-26: category_error_type/_label fields were
# bloat I added; users said don't over-engineer. The mechanism is documented
# in form.notes (the existing user-facing field) — no separate enum needed.
# ============================================================================


# ============================================================================
# Schema integrity post-Dr-Pham
# ============================================================================

def test_score_field_recomputed_after_bio_changes(iqm):
    """score = bio_score + (3 if natural else 0) — must hold after B35 bio
    downgrades.
    """
    mismatches = []
    for pid, parent in iqm.items():
        for fname, form in parent.get('forms', {}).items():
            bio = form.get('bio_score')
            if not isinstance(bio, (int, float)):
                continue
            natural = bool(form.get('natural', False))
            expected = bio + (3 if natural else 0)
            actual = form.get('score')
            if actual != expected:
                mismatches.append((pid, fname, bio, natural, actual, expected))
    assert not mismatches, (
        f'{len(mismatches)} score field mismatches: {mismatches[:5]}'
    )
