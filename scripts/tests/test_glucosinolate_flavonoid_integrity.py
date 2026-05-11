"""Regression test: glucosinolate/sulforaphane/flavonoid PK evidence locks.

Per IQM audit 2026-04-24 Step 4 Batch 5: these 6 forms across 3 parents
were already well-audited from prior quarterly cycles. This test locks in
the evidence-backed state to prevent future regressions toward inflated
absorption values.

Evidence basis (verified in prior audits):
  • PMC:3076202   Egner 2011 — sulforaphane urinary metabolite recovery PK
  • PMID:15640486 Manach 2005 — flavonoid subclass bioavailability review
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

IQM_PATH = Path(__file__).parent.parent / 'data' / 'ingredient_quality_map.json'

# (parent, form, value_min, value_max, basis)
EVIDENCE_LOCKS = [
    # Flavonoids: anthocyanin baseline ~0.1, subclass-variable up to 0.43
    ('flavonoids',     'flavonoids (unspecified)',     0.05, 0.20,
     'PMID:15640486 — flavonoid subclass-variable; 0.1 reflects anthocyanin baseline'),
    # Glucosinolates: variable; 0.1 represents glucoraphanin-conversion baseline
    ('glucosinolates', 'glucosinolates (unspecified)', 0.05, 0.20,
     'PMC:3076202 — glucoraphanin → sulforaphane ~5% without myrosinase'),
    # Sulforaphane forms: hierarchy stabilized > +myrosinase ≈ sprout > glucoraphanin alone
    ('sulforaphane',   'stabilized sulforaphane',      0.55, 0.85,
     'PMC:3076202 — pre-formed sulforaphane ~70% urinary metabolite recovery'),
    # NOTE: 'broccoli sprout extract' removed by identity_bioactivity_split
    # Phase 2 — broccoli sprout is now a source-botanical canonical
    # (broccoli_sprout), not a sulforaphane IQM form. Sulforaphane Section C
    # credit requires explicit standardization per
    # scripts/data/botanical_marker_contributions.json.
    ('sulforaphane',   'glucoraphanin',                0.01, 0.10,
     'PMC:3076202 — mean ~5% conversion without exogenous myrosinase'),
    ('sulforaphane',   'glucoraphanin + myrosinase',   0.20, 0.45,
     'Exogenous mustard/moringa myrosinase ~20-40% conversion'),
]


@pytest.fixture(scope='module')
def iqm():
    with IQM_PATH.open() as f:
        return json.load(f)


@pytest.mark.parametrize('pid,fname,vmin,vmax,basis', EVIDENCE_LOCKS)
def test_struct_value_in_evidence_band(iqm, pid, fname, vmin, vmax, basis):
    """absorption_structured.value must stay in the evidence-supported band."""
    form = iqm.get(pid, {}).get('forms', {}).get(fname)
    assert form is not None, f'{pid}::{fname} missing from IQM'
    val = (form.get('absorption_structured') or {}).get('value')
    if val is None:
        return
    assert vmin <= val <= vmax, (
        f'{pid}::{fname}: struct.value={val} outside evidence band '
        f'[{vmin}, {vmax}]. Basis: {basis}'
    )


def test_sulforaphane_hierarchy_preserved(iqm):
    """Sulforaphane form ranking by absorption MUST stay in evidence order:
    stabilized > +myrosinase > glucoraphanin alone.

    Note: identity_bioactivity_split Phase 2 removed 'broccoli sprout extract'
    from sulforaphane IQM forms (relocated to broccoli_sprout source botanical).
    The remaining IQM forms still preserve the active-ingredient hierarchy.
    Broccoli sprout's Section C credit pathway lives in
    scripts/data/botanical_marker_contributions.json under standardization gating.
    """
    f = iqm['sulforaphane']['forms']
    def v(name):
        return (f[name].get('absorption_structured') or {}).get('value')

    stabilized   = v('stabilized sulforaphane')
    plus_myro    = v('glucoraphanin + myrosinase')
    glucoraphanin = v('glucoraphanin')

    assert stabilized > plus_myro, (
        f'stabilized sulforaphane ({stabilized}) must absorb more than '
        f'glucoraphanin + exogenous myrosinase ({plus_myro})'
    )
    assert plus_myro > glucoraphanin, (
        f'glucoraphanin + myrosinase ({plus_myro}) must absorb more than '
        f'glucoraphanin alone ({glucoraphanin}); exogenous enzyme overcomes '
        f'absent gut myrosinase activity'
    )


def test_pmid_citations_present(iqm):
    """Key PMIDs must remain cited in the relevant forms' notes."""
    sulforaphane_forms = iqm['sulforaphane']['forms']
    egner_count = sum(
        1 for form in sulforaphane_forms.values()
        if 'PMC3076202' in (form.get('notes') or '') or 'PMC:3076202' in (form.get('notes') or '')
        or 'Egner 2011' in (form.get('notes') or '')
    )
    assert egner_count >= 2, (
        f'Egner 2011 (PMC3076202) must remain cited in ≥2 sulforaphane forms; '
        f'found {egner_count}. This is the primary human PK evidence.'
    )

    flavonoids_unspec = iqm['flavonoids']['forms']['flavonoids (unspecified)']
    notes = flavonoids_unspec.get('notes', '') or ''
    abs_str = flavonoids_unspec.get('absorption', '') or ''
    assert 'PMID:15640486' in (notes + abs_str) or 'PMID 15640486' in (notes + abs_str), (
        'PMID:15640486 (Manach 2005) must remain cited on flavonoids '
        '(unspecified) form'
    )


def test_no_inflated_sulforaphane_glucoraphanin_value(iqm):
    """Glucoraphanin alone (no myrosinase) MUST NOT have struct.value > 0.10
    — this is the most-cited error pattern for sulforaphane products.
    """
    form = iqm['sulforaphane']['forms']['glucoraphanin']
    val = (form.get('absorption_structured') or {}).get('value')
    if val is None:
        return
    assert val <= 0.10, (
        f'sulforaphane::glucoraphanin (no myrosinase) struct.value={val} '
        f'exceeds 0.10 evidence cap. PMC:3076202 (Egner 2011) shows mean '
        f'~5% conversion without exogenous myrosinase. Without an enzyme '
        f'source, oral glucoraphanin yields very little sulforaphane.'
    )
