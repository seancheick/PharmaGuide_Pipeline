"""SP-3 C2 — enricher writes form_factor_canonical to the enriched product blob.

Lightweight contract test that exercises `_collect_serving_basis_data`
without instantiating the full SupplementEnricherV3 (which loads ~40
reference databases and builds heavy indexes).

We use `__new__` to skip __init__ — the helper only needs `self` for
calls into pure logic, not for database state.

Locks three invariants:
  1. The return dict contains `form_factor_canonical` (new contract field).
  2. The legacy `form_factor` field is preserved unchanged.
  3. DSLD langual codes map to the canonical IDs we agreed in C1
     (especially: softgel is now distinct from capsule).
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from enrich_supplements_v3 import SupplementEnricherV3


@pytest.fixture(scope="module")
def enricher():
    """SupplementEnricherV3 with __init__ bypassed.

    `_collect_serving_basis_data` only calls pure helpers (`_normalize_form_factor`,
    `_select_canonical_serving`, `_parse_serving_directions`) that don't touch
    the database registry, so bypassing the full constructor is safe here.
    """
    inst = SupplementEnricherV3.__new__(SupplementEnricherV3)
    # Minimal attribute surface for the methods called by
    # `_collect_serving_basis_data` — empty/no-op stand-ins.
    inst._last_delivery_data = None
    inst.config = {"processing_config": {}}
    import logging
    inst.logger = logging.getLogger("test")
    return inst


def _raw_product(physical_state=None, serving_sizes=None, **extra):
    p = {
        "physicalState": physical_state or {},
        "servingSizes": serving_sizes or [],
        "statements": [],
        "userGroups": [],
    }
    p.update(extra)
    return p


@pytest.mark.parametrize("langual_code,langual_desc,expected", [
    ("e0159", "Capsule", "capsule"),
    ("e0161", "Softgel Capsule", "softgel"),
    ("e0155", "Tablet or Pill", "tablet"),
    ("e0162", "Powder", "powder"),
    ("e0176", "Gummy or Jelly", "gummy"),
    ("e0165", "Liquid", "liquid"),
    ("e0174", "Lozenge", "lozenge"),
    ("e0164", "Bar", "bar"),
    # DSLD e0172 is officially "Other (e.g. tea bag)" — a catch-all bucket,
    # not literally tea bag. Map to `other`. Products that are actually
    # tea bags get mapped to `tea_bag` via text aliases when the label says
    # "tea bag" without the e0172 catch-all code.
    ("e0172", "Other (e.g. tea bag)", "other"),
    ("e0177", "Unknown", "unknown"),
])
def test_dsld_physical_state_canonicalized(enricher, langual_code, langual_desc, expected):
    product = _raw_product(physical_state={
        "langualCode": langual_code,
        "langualCodeDescription": langual_desc,
    })
    result = enricher._collect_serving_basis_data(product)
    assert result["form_factor_canonical"] == expected, (
        f"DSLD {langual_code} {langual_desc!r} → expected {expected!r}, "
        f"got {result['form_factor_canonical']!r}."
    )


def test_softgel_distinct_from_capsule(enricher):
    """The pre-SP-3 enricher collapsed Softgel Capsule into 'capsule'. The
    new canonical field must preserve the distinction (softgels matter
    for fat-soluble vitamin D, omega-3, vitamin E bioavailability scoring)."""
    softgel = _raw_product(physical_state={
        "langualCode": "e0161", "langualCodeDescription": "Softgel Capsule",
    })
    capsule = _raw_product(physical_state={
        "langualCode": "e0159", "langualCodeDescription": "Capsule",
    })
    assert enricher._collect_serving_basis_data(softgel)["form_factor_canonical"] == "softgel"
    assert enricher._collect_serving_basis_data(capsule)["form_factor_canonical"] == "capsule"


def test_legacy_form_factor_preserved(enricher):
    """The legacy `form_factor` field must remain in the returned dict so
    pre-2026-05-21 consumers still work."""
    product = _raw_product(physical_state={
        "langualCode": "e0159", "langualCodeDescription": "Capsule",
    })
    result = enricher._collect_serving_basis_data(product)
    assert "form_factor" in result
    assert "form_factor_canonical" in result


def test_missing_physical_state_returns_unknown(enricher):
    product = _raw_product()  # empty physicalState dict
    result = enricher._collect_serving_basis_data(product)
    assert result["form_factor_canonical"] == "unknown"


def test_canonical_field_present_in_returned_dict(enricher):
    """Contract — every call must populate form_factor_canonical."""
    product = _raw_product(physical_state={"langualCode": "e0159"})
    result = enricher._collect_serving_basis_data(product)
    assert "form_factor_canonical" in result
    assert isinstance(result["form_factor_canonical"], str)
    assert result["form_factor_canonical"]  # non-empty
