"""SP-2 T5 — ADOPT-1 regression test for `scoring_v4.confidence`.

Before T5: confidence drop fired only on legacy `supplement_type.confidence < 0.80`.

After Phase 2: reads only `supplement_taxonomy.classification_confidence`
(canonical signal, threshold 0.70). A compatibility mirror is not confidence
evidence when taxonomy is absent.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scoring_v4.confidence import _supp_type_driver

# NOTE: _supp_type_driver is not yet a public symbol; the patch will expose it.
# If this import fails RED, the patch must extract the supp/taxonomy block into
# a helper and re-export it. The test asserts the behavior, not the function name.


def _make_product(taxonomy_conf=None, supp_conf=None, taxonomy_present=True):
    product = {}
    if taxonomy_present:
        product["supplement_taxonomy"] = {
            "primary_type": "multivitamin",
            "classification_confidence": taxonomy_conf if taxonomy_conf is not None else 0.95,
        }
    if supp_conf is not None:
        product["supplement_type"] = {"type": "multivitamin", "confidence": supp_conf}
    return product


def test_taxonomy_high_confidence_does_not_drop():
    """Taxonomy conf >= 0.70 → no driver added."""
    drivers = _supp_type_driver(_make_product(taxonomy_conf=0.95))
    assert "supplement_type_low_confidence" not in drivers
    assert "taxonomy_classification_low_confidence" not in drivers


def test_taxonomy_low_confidence_drops_moderate():
    """Taxonomy conf < 0.70 → 'taxonomy_classification_low_confidence' driver."""
    drivers = _supp_type_driver(_make_product(taxonomy_conf=0.50))
    assert "taxonomy_classification_low_confidence" in drivers


def test_taxonomy_zero_confidence_drops_moderate():
    """conf=0.0 (e.g. general_supplement no signal) → drops."""
    drivers = _supp_type_driver(_make_product(taxonomy_conf=0.0))
    assert "taxonomy_classification_low_confidence" in drivers


def test_no_taxonomy_does_not_read_compatibility_mirror_confidence():
    drivers = _supp_type_driver(_make_product(taxonomy_present=False, supp_conf=0.50))
    assert drivers == []


def test_no_taxonomy_high_mirror_confidence_does_not_drop():
    drivers = _supp_type_driver(_make_product(taxonomy_present=False, supp_conf=0.95))
    assert drivers == []


def test_taxonomy_present_legacy_low_does_not_double_drop():
    """When taxonomy is present, legacy supp.confidence is NOT also evaluated —
    avoids double-counting the same signal."""
    drivers = _supp_type_driver(_make_product(taxonomy_conf=0.95, supp_conf=0.50))
    # Taxonomy high → no drop. Legacy must not fire either.
    assert "supplement_type_low_confidence" not in drivers
    assert "taxonomy_classification_low_confidence" not in drivers


def test_no_signal_anywhere_does_not_drop():
    """Neither taxonomy nor legacy present — no driver added."""
    drivers = _supp_type_driver({})
    assert "supplement_type_low_confidence" not in drivers
    assert "taxonomy_classification_low_confidence" not in drivers


def test_none_product_is_defensive():
    """Defensive — should not raise on None."""
    drivers = _supp_type_driver(None)
    assert drivers == []
