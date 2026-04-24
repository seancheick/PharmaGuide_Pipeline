"""Regression test: adaptogen absorption strings/values must match PK evidence.

Per IQM audit 2026-04-24 Step 4 Batch 3: cordyceps, bacopa, rhodiola, and
ashwagandha adaptogens had absorption values/strings inflated relative to
published PK evidence. Key findings:
  • Cordycepin is NOT orally absorbed — only the ADA-deaminated metabolite
    3'-deoxyinosine reaches circulation (PMID:31673018, Lee 2019).
  • Withaferin A rat absolute oral F = 32.4% (PMID:31062367, Dai 2019); human
    plasma Cmax typically 0.1-49.5 ng/mL with KSM-66 withanolide A Cmax
    only 0.09 ng/mL (PMID:39599622, Speers 2024 review).
  • Salidroside rat absolute F = 32.1% (PMID:18088572, Yu 2008).
  • Rosavin is inactive in Porsolt assay (PMID:18054474, Panossian 2010),
    consistent with very low systemic exposure.

This test guards against regression to marketing-inflation absorption values.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

IQM_PATH = Path(__file__).parent.parent / 'data' / 'ingredient_quality_map.json'

# (parent_id, form_name, max_value, max_pct_in_string)
# Both struct.value and claimed %-in-string are capped by evidence-supported
# ceilings. Shoden and Sensoril get higher caps reflecting glycoside-rich
# human PK evidence (PMID:38144272). Cordycepin forms capped very low because
# parent cordycepin is orally non-absorbable.
EVIDENCE_CAPS = [
    # parent_id,          form_name,                                    val_cap, str_pct_cap, basis_pmid
    ('cordyceps',         'cordyceps militaris',                         0.25,   25, 'PMID:31673018 cordycepin non-absorbable'),
    ('cordyceps',         'cordyceps sinensis mycelium',                 0.20,   25, 'PMID:31673018 cordycepin non-absorbable'),
    ('bacopa',            'bacopa (unspecified)',                        0.25,   25, 'Must not exceed specified extracts (0.18-0.22)'),
    ('rhodiola',          'rhodiola rosea extract (3% rosavins)',        0.50,   50, 'PMID:18088572 salidroside F=32%, rosavin poor'),
    ('rhodiola',          'rhodiola root powder',                        0.45,   50, 'PMID:18088572 salidroside F=32%'),
    ('ashwagandha',       'Shoden ashwagandha extract',                  0.55,   50, 'PMID:38144272 WS-35 proxy; Cmax 49.5 ng/mL'),
    ('ashwagandha',       'standard ashwagandha extract',                0.40,   40, 'PMID:31062367 withaferin A rat F=32%'),
    ('ashwagandha',       'KSM-66 ashwagandha',                          0.35,   40, 'PMID:39599622 withanolide A Cmax 0.09 ng/mL'),
    ('ashwagandha',       'ashwagandha powder',                          0.35,   40, 'Raw powder; content ceiling lower than extracts'),
    ('ashwagandha',       'sensoril ashwagandha',                        0.45,   50, 'PMID:39599622 withanolide review'),
]


@pytest.fixture(scope='module')
def iqm():
    with IQM_PATH.open() as f:
        return json.load(f)


@pytest.mark.parametrize('pid,fname,val_cap,str_pct_cap,basis', EVIDENCE_CAPS)
def test_adaptogen_struct_value_within_evidence_cap(iqm, pid, fname, val_cap, str_pct_cap, basis):
    """absorption_structured.value must not exceed evidence-supported cap."""
    form = iqm.get(pid, {}).get('forms', {}).get(fname)
    assert form is not None, f'{pid}::{fname} missing from IQM — if removed, update test'
    val = (form.get('absorption_structured') or {}).get('value')
    if val is None:
        return
    assert val <= val_cap, (
        f'{pid}::{fname}: struct.value={val} exceeds evidence cap {val_cap}. '
        f'Basis: {basis}.'
    )


@pytest.mark.parametrize('pid,fname,val_cap,str_pct_cap,basis', EVIDENCE_CAPS)
def test_adaptogen_absorption_string_not_inflated(iqm, pid, fname, val_cap, str_pct_cap, basis):
    """Absorption free-text string must not claim higher than evidence cap.

    Parses any plain %-number in the string (ignoring common non-absorption
    patterns like fold-change or ng/mL Cmax).
    """
    import re
    form = iqm.get(pid, {}).get('forms', {}).get(fname)
    assert form is not None, f'{pid}::{fname} missing from IQM'
    s = form.get('absorption') or ''
    # Strip fold-change (e.g., "5×", "5.6x", "18× AUC")
    s2 = re.sub(r'\d+(?:\.\d+)?\s*[x×]', '', s)
    # Strip ng/mL Cmax-like patterns
    s2 = re.sub(r'\d+(?:\.\d+)?\s*ng(?:/mL)?', '', s2)
    # Extract plain percent numbers
    pcts = [float(m) for m in re.findall(r'(\d+(?:\.\d+)?)\s*%', s2)]
    if not pcts:
        return  # no %-claim in string
    max_claim = max(pcts)
    assert max_claim <= str_pct_cap, (
        f'{pid}::{fname}: absorption string claims ~{max_claim:g}% but evidence '
        f'cap is {str_pct_cap}%. String: {s!r}. Basis: {basis}.'
    )


def test_bacopa_unspecified_not_higher_than_specified(iqm):
    """bacopa::bacopa (unspecified) struct.value must not exceed the
    standardized bacosides forms under the same parent (inversion check).
    """
    forms = iqm['bacopa']['forms']
    specified_values = []
    for fname in ('bacosides 45%', 'bacosides 50% (bacognize)'):
        form = forms.get(fname, {})
        v = (form.get('absorption_structured') or {}).get('value')
        if v is not None:
            specified_values.append((fname, v))
    unspec = forms.get('bacopa (unspecified)', {})
    unspec_val = (unspec.get('absorption_structured') or {}).get('value')
    if unspec_val is None or not specified_values:
        return
    max_spec = max(v for _, v in specified_values)
    assert unspec_val <= max_spec, (
        f'bacopa::(unspecified) value={unspec_val} must not exceed its '
        f'specified extracts {specified_values} — unspecified forms are '
        f'fallback and should score more conservatively.'
    )


def test_cordyceps_forms_reflect_cordycepin_nonabsorption(iqm):
    """Cordyceps forms must reflect PMID:31673018 — cordycepin not orally
    absorbed. Struct.value cannot exceed 0.25 for any cordyceps form.
    """
    forms = iqm.get('cordyceps', {}).get('forms', {})
    violations = []
    for fname, form in forms.items():
        v = (form.get('absorption_structured') or {}).get('value')
        if v is None:
            continue
        if v > 0.25:
            violations.append((fname, v))
    assert not violations, (
        f'Cordyceps forms claim struct.value > 0.25 despite PMID:31673018 '
        f'evidence that intact cordycepin is not orally absorbed: {violations}'
    )
