"""Regression test: Batch 27 — iron + calcium completion.

Per IQM audit 2026-04-25 Step 4 Batch 27: 11 forms across 2 parents
(iron + calcium). Five PK-rich findings:

1. FERRIC IRON CLASS (Fe3+) — Hallberg 1989 (PMID:2507689): Fe3+
   requires reduction to Fe2+ before DMT1 uptake. Class F ~5-10%.

2. FERRIC CITRATE (Auryxia) — FDA-approved CKD anemia drug. Yokoyama
   2014 (PMID:24408120) phase 3, Van Buren/Lewis 2015 (PMID:25958079)
   52-wk phase 3. Atypical distal-colon absorption (PMID:32514572).

3. IRON PICOLINATE = FERROUS SULFATE — Sabatier 2020 (PMID:31187261):
   stable-isotope RCT, RBV 0.99 (5.2% vs 5.3%). Picolinate premium
   UNSUPPORTED. **DR PHAM C13 downgrade flag** for bio_score=12.

4. CORAL CALCIUM = CaCO3 (~95% composition; class-extension Heaney
   2001 PMID:11444420). No direct coral PK study exists.

5. CALCIUM AMINO ACID CHELATE = bisglycinate-class (PK uncertainty
   band; no robust stable-isotope study).

GHOST PMIDS / CITATIONS CAUGHT (3):
  • "Hashmi 1990 picolinate iron"  — 0 PubMed hits (confirms prior catch)
  • "Heaney 2002 coral calcium"    — 0 PubMed hits, fabricated
  • "Heaney 2003 calcium bisglycinate" — 0 PubMed hits, suspect
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
B27_BANDS = [
    # iron
    ('iron', 'ferric iron',                        0.05, 0.10, 'Hallberg 1989 Fe3+'),
    ('iron', 'iron oxide',                         0.00, 0.05, 'E172 food coloring'),
    ('iron', 'iron (unspecified)',                 0.05, 0.30, 'iron class baseline'),
    ('iron', 'ferric citrate',                     0.05, 0.15, 'Yokoyama 2014 Auryxia'),
    ('iron', 'ferric sulfate',                     0.05, 0.10, 'Fe3+ class'),
    ('iron', 'iron picolinate',                    0.10, 0.20, 'Sabatier 2020 = FeSO4'),
    # calcium
    ('calcium', 'coral calcium',                   0.20, 0.30, 'Heaney 2001 CaCO3 class'),
    ('calcium', 'calcium oxide',                   0.00, 0.10, 'CaO strong base'),
    ('calcium', 'calcium analogs (non-functional)', 0.00, 0.05, 'non-functional'),
    ('calcium', 'calcium (unspecified)',           0.20, 0.42, 'Ca class baseline'),
    ('calcium', 'calcium amino acid chelate',      0.30, 0.40, 'bisglycinate class'),
]


@pytest.mark.parametrize('pid,fname,vmin,vmax,basis', B27_BANDS)
def test_b27_value_in_band(iqm, pid, fname, vmin, vmax, basis):
    """Each form's struct.value must sit in evidence band."""
    form = iqm[pid]['forms'].get(fname)
    assert form is not None, f'{pid}::{fname} missing'
    val = (form.get('absorption_structured') or {}).get('value')
    assert val is not None, f'{pid}::{fname} struct.value should be populated'
    assert vmin <= val <= vmax, (
        f'{pid}::{fname}: struct.value={val} outside band [{vmin}, {vmax}]. '
        f'Basis: {basis}'
    )


def test_iron_picolinate_equals_ferrous_sulfate(iqm):
    """Iron picolinate must be class-equivalent (within 0.05) to ferrous
    sulfate per Sabatier 2020 (PMID:31187261) — RBV 0.99 stable-isotope.
    """
    forms = iqm['iron']['forms']
    pic = (forms['iron picolinate'].get('absorption_structured') or {}).get('value')
    feso4 = (forms['ferrous sulfate'].get('absorption_structured') or {}).get('value')
    assert pic is not None and feso4 is not None
    assert abs(pic - feso4) <= 0.05, (
        f'iron picolinate ({pic}) must be class-equivalent to ferrous '
        f'sulfate ({feso4}) within 0.05 — Sabatier 2020 stable-isotope '
        f'RCT showed RBV 0.99 (PMID:31187261). Picolinate premium '
        f'UNSUPPORTED.'
    )


def test_iron_picolinate_below_bisglycinate(iqm):
    """Iron picolinate must rank BELOW iron bisglycinate — picolinate is
    NOT a premium chelate per Sabatier 2020 (PMID:31187261).
    """
    forms = iqm['iron']['forms']
    pic = (forms['iron picolinate'].get('absorption_structured') or {}).get('value')
    bisg = (forms['iron bisglycinate'].get('absorption_structured') or {}).get('value')
    assert pic is not None and bisg is not None
    assert pic < bisg, (
        f'iron picolinate ({pic}) should rank below iron bisglycinate '
        f'({bisg}) — picolinate matches FeSO4, NOT bisglycinate '
        f'(PMID:31187261).'
    )


def test_ferric_below_ferrous(iqm):
    """All ferric (Fe3+) forms must rank below all ferrous (Fe2+) forms
    per Hallberg 1989 (PMID:2507689) reduction-required mechanism.
    """
    forms = iqm['iron']['forms']
    ferric_forms = ['ferric iron', 'ferric sulfate', 'ferric citrate']
    ferrous_forms = ['ferrous fumarate', 'ferrous gluconate', 'ferrous sulfate',
                     'ferrous ascorbate']
    for fname_ferric in ferric_forms:
        v_ferric = (forms[fname_ferric].get('absorption_structured') or {}).get('value')
        for fname_ferrous in ferrous_forms:
            v_ferrous = (forms[fname_ferrous].get('absorption_structured') or {}).get('value')
            if v_ferric is None or v_ferrous is None:
                continue
            assert v_ferric <= v_ferrous, (
                f'{fname_ferric} ({v_ferric}) must rank ≤ {fname_ferrous} '
                f'({v_ferrous}) — Fe3+ requires reduction (PMID:2507689).'
            )


def test_coral_calcium_class_equivalent_to_caco3(iqm):
    """Coral calcium must be class-equivalent (within 0.10) to calcium
    carbonate per Heaney 2001 (PMID:11444420) — coral is ~95% CaCO3.
    """
    forms = iqm['calcium']['forms']
    coral = (forms['coral calcium'].get('absorption_structured') or {}).get('value')
    caco3 = (forms['calcium carbonate'].get('absorption_structured') or {}).get('value')
    assert coral is not None and caco3 is not None
    assert abs(coral - caco3) <= 0.10, (
        f'coral calcium ({coral}) must be class-equivalent to CaCO3 '
        f'({caco3}) within 0.10 — coral is ~95% CaCO3 + trace minerals '
        f'(class-extension from PMID:11444420; no direct coral PK).'
    )


def test_calcium_aa_chelate_equivalent_to_bisglycinate(iqm):
    """Calcium amino acid chelate must be class-equivalent to bisglycinate
    (within 0.10) — same chelation chemistry, no separate PK.
    """
    forms = iqm['calcium']['forms']
    aa = (forms['calcium amino acid chelate'].get('absorption_structured') or {}).get('value')
    bisg = (forms['calcium bis-glycinate'].get('absorption_structured') or {}).get('value')
    assert aa is not None and bisg is not None
    assert abs(aa - bisg) <= 0.10, (
        f'calcium amino acid chelate ({aa}) must be class-equivalent to '
        f'bis-glycinate ({bisg}) within 0.10.'
    )


def test_no_phantom_hashmi_iron_picolinate(iqm):
    """The non-existent "Hashmi 1990 iron picolinate" must not appear as
    live citation. 0 PubMed hits confirmed in B27.
    """
    form = iqm['iron']['forms']['iron picolinate']
    text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
    text += ' ' + ((form.get('absorption_structured') or {}).get('notes') or '')
    if 'Hashmi' in text and '1990' in text:
        assert any(neg in text.lower() for neg in
                   ('ghost', 'does not exist', '0 pubmed', 'fabricated',
                    'not found', 'confirms')), (
            f'iron picolinate cites "Hashmi 1990" without ghost-trap '
            f'qualification. 0 PubMed hits confirmed.'
        )


def test_no_phantom_heaney_2002_coral(iqm):
    """The non-existent "Heaney 2002 coral calcium" must not appear as
    live citation. 0 PubMed hits confirmed in B27.
    """
    form = iqm['calcium']['forms']['coral calcium']
    text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
    text += ' ' + ((form.get('absorption_structured') or {}).get('notes') or '')
    if 'Heaney' in text and '2002' in text:
        assert any(neg in text.lower() for neg in
                   ('ghost', 'does not exist', '0 pubmed', 'fabricated',
                    'do not cite')), (
            f'coral calcium cites "Heaney 2002" without ghost-trap '
            f'qualification. 0 PubMed hits — fabricated citation.'
        )


def test_class_authority_pmids_introduced_b27(iqm):
    """Verified class-authority PMIDs must each appear in IQM notes."""
    expected_pmids = {
        'PMID:2507689':  'Hallberg 1989 Fe3+',
        'PMID:24408120': 'Yokoyama 2014 Auryxia',
        'PMID:31187261': 'Sabatier 2020 picolinate',
        'PMID:11444420': 'Heaney 2001 CaCO3',
    }
    full_text = ''
    for pid in ('iron', 'calcium'):
        for form in iqm[pid]['forms'].values():
            full_text += (form.get('notes') or '') + ' '
            full_text += (form.get('absorption') or '') + ' '
            full_text += ((form.get('absorption_structured') or {}).get('notes') or '') + ' '
    missing = [pmid for pmid in expected_pmids if pmid not in full_text]
    assert not missing, (
        f'Verified class-authority PMIDs missing: {missing}'
    )


def test_iron_parent_fully_populated(iqm):
    """Iron parent should now have ZERO null forms after B27."""
    forms = iqm['iron']['forms']
    null_forms = [
        fn for fn, f in forms.items()
        if (f.get('absorption_structured') or {}).get('value') is None
    ]
    assert not null_forms, (
        f'iron should have ZERO null forms after B27; still null: {null_forms}'
    )


def test_calcium_parent_fully_populated(iqm):
    """Calcium parent should now have ZERO null forms after B27."""
    forms = iqm['calcium']['forms']
    null_forms = [
        fn for fn, f in forms.items()
        if (f.get('absorption_structured') or {}).get('value') is None
    ]
    assert not null_forms, (
        f'calcium should have ZERO null forms after B27; still null: {null_forms}'
    )
