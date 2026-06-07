#!/usr/bin/env python3
"""Defense-in-depth at the cleaner: the normalizer must not stamp a recognized
single ingredient as an opaque proprietary blend just because its name carries
a marketing suffix token ("Complex"/"Matrix"/"Formula").

`_is_proprietary_blend_name` matches bare tokens as substrings, so a branded
single active ("EpiCor dried Yeast Fermentate Complex", "Curcumin C3 Complex",
"Boron Complex") gets `proprietaryBlend=True` + `disclosureLevel="none"` — the
maximally-opaque raw flags that seed the downstream B5 opacity penalty.

Guard: when a row resolves to a known single ingredient whose canonical name is
NOT itself a blend/proprietary label, lists no nested sub-ingredients, and
carries a real disclosed dose, it hides nothing — clear the weak proprietary
flag. Genuine blends either don't resolve, or resolve to a blend-category name
("General Proprietary Blends", "Stimulant Blends"), and keep the flag. The
enricher's chemical-identity gate remains the authoritative scoring backstop.
"""

import logging
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
logging.disable(logging.CRITICAL)

import enhanced_normalizer as _enorm  # noqa: E402

_NORM_CLASS = next(
    getattr(_enorm, _n)
    for _n in dir(_enorm)
    if isinstance(getattr(_enorm, _n), type)
    and hasattr(getattr(_enorm, _n), "_process_single_ingredient_enhanced")
    and hasattr(getattr(_enorm, _n), "_is_proprietary_blend_name")
)


@pytest.fixture(scope="module")
def normalizer():
    return _NORM_CLASS()


def _raw(name, qty=250, unit="mg", nested=None):
    row = {"name": name, "quantity": [{"quantity": qty, "unit": unit}], "forms": []}
    if nested is not None:
        row["nestedRows"] = nested
    return row


def _process(normalizer, name, **kw):
    out = normalizer._process_single_ingredient_enhanced(_raw(name, **kw), True)
    return out[0] if isinstance(out, list) and out else out


# Branded single-actives: the weak proprietary flag must be cleared.
@pytest.mark.parametrize(
    "name",
    [
        "Curcumin C3 Complex",
        "EpiCor dried Yeast Fermentate Complex",
        "Boron Complex",
        "Clarinol CLA Complex",
        "Citrus Bioflavonoid Complex",
    ],
)
def test_recognized_single_active_complex_is_not_proprietary(normalizer, name):
    row = _process(normalizer, name)
    assert row.get("proprietaryBlend") is False, (
        f"{name!r} resolves to a single ingredient ({row.get('standardName')!r}) with a "
        f"disclosed dose and no sub-ingredients — it must not be flagged proprietary."
    )
    # When not proprietary, the opaque disclosure flag must not be emitted.
    assert row.get("disclosureLevel") in (None, "", "full")


# Genuine blends: the flag and opaque disclosure must remain.
@pytest.mark.parametrize(
    "name",
    [
        "Proprietary Blend",            # resolves to "General Proprietary Blends"
        "Energy Blend",                 # resolves to "Stimulant Blends"
        "Super Greens Blend",           # does not resolve
        "Probiotic & Microbiome Blend",  # does not resolve
    ],
)
def test_genuine_blend_stays_proprietary_and_opaque(normalizer, name):
    row = _process(normalizer, name)
    assert row.get("proprietaryBlend") is True, (
        f"Genuine blend {name!r} must remain flagged proprietary."
    )
    assert row.get("disclosureLevel") == "none", (
        f"Genuine blend {name!r} discloses only a total — disclosure must stay 'none'."
    )


def test_undisclosed_dose_complex_stays_proprietary(normalizer):
    """A 'Complex' with NO disclosed amount (unit NP) is genuinely undisclosed —
    the guard requires a real disclosed dose, so the flag stays."""
    row = _process(normalizer, "Curcumin C3 Complex", qty=0, unit="NP")
    assert row.get("proprietaryBlend") is True


def test_complex_with_nested_children_stays_proprietary(normalizer):
    """A 'Complex' parent that actually has nested sub-ingredients is a real
    container — the guard requires zero nested rows, so the flag stays."""
    row = _process(
        normalizer,
        "Curcumin C3 Complex",
        nested=[
            {"name": "Curcumin", "quantity": [{"quantity": 0, "unit": "NP"}]},
            {"name": "Demethoxycurcumin", "quantity": [{"quantity": 0, "unit": "NP"}]},
        ],
    )
    assert row.get("proprietaryBlend") is True
