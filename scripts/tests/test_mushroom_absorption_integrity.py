"""Regression test: mushroom absorption strings must NOT claim high systemic F.

Per IQM audit 2026-04-24 Step 4 Batch 1: the mushroom β-glucan bioavailability
research (verified PMIDs 41943369, 34451676, 18680305, 34119545, 40284172)
established that medicinal mushroom polysaccharides are poorly absorbed
systemically (~0.1-0.2 fraction), not 60-85% as previously stated in marketing
language. This test guards against regression to the inflated claims.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

IQM_PATH = Path(__file__).parent.parent / 'data' / 'ingredient_quality_map.json'

MUSHROOM_PARENTS = ('turkey_tail', 'shiitake', 'chaga', 'lions_mane')

# Any absorption value >= 50% claimed for a mushroom form is a regression — the
# best-evidence range for medicinal mushroom polysaccharide systemic F is
# 5-20%. Lipophilic secondary metabolites (e.g., chaga triterpenes) may be
# slightly higher but still single-digit percent in verified rodent PK.
HIGH_PCT_PATTERNS = [
    re.compile(r'(?<!\d)([5-9]\d|1\d{2})\s*%'),  # 50-199% as absorption claim
]


@pytest.fixture(scope='module')
def iqm():
    with IQM_PATH.open() as f:
        return json.load(f)


@pytest.mark.parametrize('parent_id', MUSHROOM_PARENTS)
def test_mushroom_absorption_not_inflated(iqm, parent_id):
    """No mushroom form should claim 50%+ systemic oral bioavailability.

    The best available PubMed evidence (PMIDs 41943369, 34451676, 18680305)
    places medicinal mushroom polysaccharide systemic F in the 5-20% range.
    """
    parent = iqm.get(parent_id)
    assert parent is not None, f'mushroom parent {parent_id!r} missing from IQM'

    violations = []
    for form_name, form in parent.get('forms', {}).items():
        absorption_str = form.get('absorption') or ''
        for pat in HIGH_PCT_PATTERNS:
            if pat.search(absorption_str):
                violations.append((form_name, absorption_str))
    assert not violations, (
        f'{parent_id}: absorption string contains claim of >=50% bioavailability, '
        f'which contradicts best-evidence PubMed data (PMIDs 41943369, 34451676, '
        f'18680305). Violations: {violations}'
    )


@pytest.mark.parametrize('parent_id', MUSHROOM_PARENTS)
def test_mushroom_struct_value_in_evidence_range(iqm, parent_id):
    """absorption_structured.value for mushroom forms must stay in [0.02, 0.25]."""
    parent = iqm[parent_id]
    violations = []
    for form_name, form in parent.get('forms', {}).items():
        struct = form.get('absorption_structured') or {}
        val = struct.get('value')
        if val is None:
            continue
        if not (0.02 <= val <= 0.25):
            violations.append((form_name, val))
    assert not violations, (
        f'{parent_id}: absorption_structured.value out of evidence-supported '
        f'range [0.02, 0.25] for mushroom polysaccharide systemic F. '
        f'Violations: {violations}'
    )
