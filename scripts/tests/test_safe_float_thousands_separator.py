"""
Review follow-up — _safe_float must not silently zero comma-grouped doses.

EnhancedDSLDNormalizer._safe_float / _safe_float_flagged did a bare
``float(value)`` with no thousands-separator handling, so a string quantity like
"1,000" raised ValueError and fell back to the default 0.0 — a 1,000 mg dose
silently became 0 mg (looks absent/underdosed downstream). dosage_normalizer
already strips commas (`float(qty_str.replace(',', ''))`); this aligns the
general float coercion (US thousands convention).
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from enhanced_normalizer import EnhancedDSLDNormalizer


@pytest.fixture(scope="module")
def norm() -> EnhancedDSLDNormalizer:
    return EnhancedDSLDNormalizer()


def test_safe_float_strips_thousands_separator(norm):
    assert norm._safe_float("1,000") == 1000.0
    assert norm._safe_float("2,500.5") == 2500.5


def test_safe_float_flagged_strips_thousands_separator(norm):
    val, ok = norm._safe_float_flagged("1,000")
    assert val == 1000.0
    assert ok is True


def test_safe_int_strips_thousands_separator(norm):
    # _safe_int shares the same silent-zero bug: int(float("1,000")) raised.
    assert norm._safe_int("1,000") == 1000
    assert norm._safe_int("2,500") == 2500


def test_safe_float_plain_values_unchanged(norm):
    assert norm._safe_float("500") == 500.0
    assert norm._safe_float(750) == 750.0
    assert norm._safe_float("") == 0.0          # empty → default
    assert norm._safe_float("none") == 0.0       # sentinel → default
