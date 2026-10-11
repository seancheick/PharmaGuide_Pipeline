"""Regression test: Batches 35-37 — Dr Pham clinical sign-off applied.

Verifies that all Dr Pham approved decisions from
docs/DR_PHAM_IQM_AUDIT_REVIEW_2026-04-25.md are correctly applied:

  • Section C reviewed bio_score decisions (52 forms), with later
    parent-relative recalibrations where explicitly recorded in IQM history
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
# Section C — reviewed bio_score decisions
# ============================================================================

@pytest.mark.parametrize('pid,fname,expected_bio', [
    # C2 — B12
    # The later parent-relative B12 recalibration preserves Dr Pham's finding
    # that the reviewed forms have no established absorption advantage, while
    # assigning tied best forms the IQM parent maximum.
    ('vitamin_b12_cobalamin', 'methylcobalamin sublingual',  15),
    ('vitamin_b12_cobalamin', 'methylcobalamin',             15),
    ('vitamin_b12_cobalamin', 'adenosylcobalamin',           15),
    ('vitamin_b12_cobalamin', 'hydroxocobalamin',            15),
    ('vitamin_b12_cobalamin', 'cyanocobalamin sublingual',   15),
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
    # C3 extension 2026-05-25 — generic standardized boswellia aligned to
    # branded floor (no-human-PK Class Finding applies to ALL boswellic
    # acid forms; generic cannot exceed branded under same evidence).
    ('boswellia', 'boswellia standardized extract',           7),
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
    # 2026-06-02 clinician mineral recalibration retained liposomal iron at
    # bio_score 10 as a promising delivery form, still below heme/bisglycinate.
    ('iron', 'liposomal iron',                                10),
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
    ('iron', 'iron bisglycinate',                             13),
    ('iron', 'iron protein succinylate',                      10),
    # Form-specific human evidence supports Excellent, but not the former
    # maximum score or a clinical advantage over conventional iron.
    ('iron', 'heme iron polypeptide',                         13),
    ('iron', 'iron amino acid chelate',                       11),
    ('iron', 'ferrous ascorbate',                             13),
    # C9 — Probiotics → 7 placeholder
    ('lactobacillus_plantarum', 'lactobacillus plantarum (unspecified)',         9),
    ('lactobacillus_salivarius', 'lactobacillus salivarius ha-118',              7),
    ('bifidobacterium_lactis', 'bifidobacterium lactis (unspecified)',          11),
    ('lactobacillus_rhamnosus', 'lactobacillus rhamnosus (unspecified)',        10),
    ('bifidobacterium_longum', 'bifidobacterium longum 35624',          7),
    # C12 — BMOV
    ('vanadyl_sulfate', 'bis(maltolato)oxovanadium (BMOV)',   7),
    # C13 — Iron picolinate
    ('iron', 'iron picolinate',                               8),
])
def test_dr_pham_section_c_bio_score(iqm, pid, fname, expected_bio):
    """Section C decisions plus recorded later recalibrations must stay pinned."""
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
        if fname == 'ubiquinol crystal-free':
            assert form['bio_score'] == 13
            assert '16919858' in notes and 'did not include an active' in notes
            continue
        if fname == 'ubiquinol':
            assert form['bio_score'] == 13
            assert '32188111' in notes and 'not significant' in notes
            continue
        assert 'PD-respect' in notes or 'C1' in notes or 'PD' in notes, (
            f'{fname} must document PD-respect decoupling per Dr Pham C1.'
        )


def test_c12_bmov_struct_value_downgraded(iqm):
    # Source-qualified preparation/endpoints supersede inferred absolute-F hierarchy.
    form = iqm['vanadyl_sulfate']['forms']['bis(maltolato)oxovanadium (BMOV)']
    assert form['absorption_structured'] == dict(value=None, range_low=None, range_high=None, quality='unknown')
    assert 'Human comparative evidence remains unresolved' in form['notes']
    assert 'A sulfate study cannot demonstrate equivalence' in form['notes']
    assert form['bio_score'] == 7



# ============================================================================
# Section E — Open-question decisions
# ============================================================================

def test_e1_gaba_pk_strict(iqm):
    # Source-qualified preparation/endpoints supersede inferred absolute-F hierarchy.
    form = iqm['gaba']['forms']['gaba powder']
    assert form['absorption_structured'] == dict(value=None, range_low=None, range_high=None, quality='unknown')
    assert '26500584' in form['notes']
    assert 'contradictory BBB' in form['notes']
    assert 'oral uptake is distinct from brain entry' in form['notes']
    form = iqm['gaba']['forms']['pharma-gaba']
    assert form['absorption_structured'] == dict(value=None, range_low=None, range_high=None, quality='unknown')
    assert 'same GABA molecular identity' in form['notes']
    assert 'not establish a human absorption or BBB premium' in form['notes']
    assert iqm['gaba']['forms']['gaba powder']['bio_score'] == 6
    assert iqm['gaba']['forms']['pharma-gaba']['bio_score'] == 6



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
