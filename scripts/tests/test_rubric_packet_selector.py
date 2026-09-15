"""Regression tests for the reproducible rubric packet selector."""

from __future__ import annotations

import sys
from pathlib import Path


AUDIT_DIR = Path(__file__).resolve().parents[1] / "audits" / "rubric_proxy_removal_2026_09_14"
if str(AUDIT_DIR) not in sys.path:
    sys.path.insert(0, str(AUDIT_DIR))

from select_packet import _flag, _positive, _verification_selection_flags  # noqa: E402


def test_positive_treats_numeric_zero_string_as_empty() -> None:
    assert not _positive("0")
    assert not _positive("not-a-number")
    assert _positive("2")


def test_flag_does_not_treat_false_string_as_present() -> None:
    assert not _flag("false")
    assert not _flag("0")
    assert _flag("true")


def test_current_reputation_component_is_not_a_plain_unknown() -> None:
    assert _verification_selection_flags({"reputation": 1.0}) == (False, True)


def test_legacy_soft_reputation_component_is_not_a_plain_unknown() -> None:
    assert _verification_selection_flags({"soft": 1.0}) == (False, True)


def test_label_only_gmp_claim_is_not_an_unknown_reputation_group() -> None:
    assert _verification_selection_flags({}, claim_only=True) == (False, False)


def test_label_claim_with_reputation_remains_in_reputation_group() -> None:
    # A label-only GMP claim must not hide an independent brand/reputation
    # signal or make the selector drop the product from pass 2.
    assert _verification_selection_flags({"reputation": 1.0}, claim_only=True) == (False, True)


def test_hard_product_signal_is_not_a_reputation_or_plain_unknown_group() -> None:
    assert _verification_selection_flags({"cert": "9"}) == (False, False)
