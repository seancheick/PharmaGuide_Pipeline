"""Shared barcode comparison rules for submission review and import."""

from __future__ import annotations

import re


GTIN_INPUT_PATTERN = re.compile(r"^[0-9\s-]+$")


def is_valid_gtin(value: str) -> bool:
    if len(value) not in {8, 12, 13, 14} or not value.isdigit():
        return False
    weighted_sum = 0
    for position_from_right, digit in enumerate(reversed(value[:-1]), start=1):
        weighted_sum += int(digit) * (3 if position_from_right % 2 else 1)
    return (10 - weighted_sum % 10) % 10 == int(value[-1])


def canonical_normalized_gtin14(value: object) -> str | None:
    """Canonicalize one established GTIN without inferring UPC-E identity.

    Known UPC-E barcodes are expanded before submission. A normalized
    eight-digit receipt therefore owns its EAN-8 identity only.
    """
    if not isinstance(value, str) or not is_valid_gtin(value):
        return None
    return value.rjust(14, "0")


def _expand_upce(value: str) -> str | None:
    if len(value) != 8 or not value.isdigit() or value[0] not in {"0", "1"}:
        return None
    number_system, d1, d2, d3, d4, d5, d6, check_digit = value
    if d6 in {"0", "1", "2"}:
        body = f"{number_system}{d1}{d2}{d6}0000{d3}{d4}{d5}"
    elif d6 == "3":
        body = f"{number_system}{d1}{d2}{d3}00000{d4}{d5}"
    elif d6 == "4":
        body = f"{number_system}{d1}{d2}{d3}{d4}00000{d5}"
    else:
        body = f"{number_system}{d1}{d2}{d3}{d4}{d5}0000{d6}"
    expanded = body + check_digit
    return expanded if is_valid_gtin(expanded) else None


def canonical_gtin14_candidates(value: object) -> set[str]:
    """Return exact canonical interpretations using the Flutter GTIN rules."""
    raw = str(value or "").strip()
    if not raw or not GTIN_INPUT_PATTERN.fullmatch(raw):
        return set()
    digits = re.sub(r"[^0-9]", "", raw)
    candidates: set[str] = set()
    primary = canonical_normalized_gtin14(digits)
    if primary is not None:
        candidates.add(primary)
    if len(digits) == 8:
        expanded = _expand_upce(digits)
        if expanded is not None:
            candidates.add(expanded.rjust(14, "0"))
    return candidates
