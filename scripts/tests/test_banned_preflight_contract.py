"""
Sprint E1.1.4 — regression tests for banned-substance preflight propagation.

End-to-end coverage from enriched banned-substances input through to the
detail-blob's top-level ``banned_substance_detail`` key. Flutter Sprint
27.7's stack-add CRITICAL preflight sheet reads directly from this key,
so the contract is:

  1. Every product with ``has_banned_substance == 1`` has
     ``banned_substance_detail`` populated with both
     ``safety_warning_one_liner`` (≤80 chars) and ``safety_warning``
     (≤200 chars) non-empty.
  2. Non-banned products emit ``banned_substance_detail = None``.
  3. The build-time validator raises on any banned product missing
     the preflight copy.
  4. Dr Pham's char-limit contract (80/200) is enforced.

Covers the 5 canonical banned substances from the sprint DoD:
CBD, ephedra, DMAA, kratom, higenamine.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_final_db import (  # noqa: E402
    build_banned_substance_detail,
    build_detail_blob,
    _validate_banned_preflight_propagation,
    _BANNED_PREFLIGHT_ONE_LINER_MAX,
    _BANNED_PREFLIGHT_BODY_MAX,
)

sys.path.insert(0, str(Path(__file__).parent))
from test_build_final_db import make_enriched, make_scored  # noqa: E402


# ---------------------------------------------------------------------------
# Fixture helper
# ---------------------------------------------------------------------------

def _banned_enriched(
    ingredient: str,
    one_liner: str = "FDA-banned stimulant. Talk to a clinician.",
    safety_warning: str = (
        "FDA-banned ingredient removed from the lawful US supplement "
        "category; avoid products still listing it."
    ),
) -> dict:
    """Produce an enriched dict with a single banned-substance hit carrying
    Dr Pham's authored copy in the realistic shape the enricher emits."""
    e = make_enriched()
    e["contaminant_data"]["banned_substances"]["substances"] = [{
        "ingredient": ingredient,
        "banned_name": ingredient,
        "status": "banned",
        "match_type": "exact",
        "reason": f"{ingredient} is banned under FDA regulation.",
        "safety_warning": safety_warning,
        "safety_warning_one_liner": one_liner,
        "ban_context": "substance",
    }]
    return e


# ---------------------------------------------------------------------------
# Contract 1 — 5 canonical banned products propagate copy end-to-end
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("substance,one_liner", [
    ("CBD",        "Not lawful as a US dietary supplement. Consult your clinician."),
    ("Ephedra",    "FDA-banned stimulant tied to cardiovascular events. Avoid."),
    ("DMAA",       "FDA-banned stimulant; removed from lawful supplements."),
    ("Kratom",     "Not approved as a supplement; dependence and overdose risk."),
    ("Higenamine", "FDA-banned stimulant with cardiovascular risk profile."),
])
def test_five_canonical_banned_substances_propagate(substance: str, one_liner: str) -> None:
    e = _banned_enriched(substance, one_liner=one_liner)
    blob = build_detail_blob(e, make_scored())

    bsd = blob.get("banned_substance_detail")
    assert isinstance(bsd, dict), f"{substance}: banned_substance_detail missing"
    assert bsd["safety_warning_one_liner"] == one_liner
    assert bsd["safety_warning"].startswith("FDA-banned ingredient")
    assert substance in (bsd.get("substance_name") or ""), (
        f"substance_name should surface {substance}; got {bsd.get('substance_name')!r}"
    )


# ---------------------------------------------------------------------------
# Contract 2 — non-banned products emit None
# ---------------------------------------------------------------------------

def test_non_banned_product_has_none_detail() -> None:
    e = make_enriched()
    # Default make_enriched has no banned_substances; confirm emission is None
    blob = build_detail_blob(e, make_scored())
    assert blob.get("banned_substance_detail") is None


def test_recalled_only_product_has_none_detail() -> None:
    """Recalled != banned for this contract — preflight copy is only
    emitted for banned-status hits."""
    e = make_enriched()
    e["contaminant_data"]["banned_substances"]["substances"] = [{
        "ingredient": "Soy Protein Isolate",
        "banned_name": "Soy Protein Isolate",
        "status": "recalled",
        "match_type": "exact",
        "reason": "Voluntary recall for Listeria concern.",
        "safety_warning": "Recalled lot — verify lot number against recall notice.",
        "safety_warning_one_liner": "Recalled lot — check your bottle.",
    }]
    blob = build_detail_blob(e, make_scored())
    assert blob.get("banned_substance_detail") is None


# ---------------------------------------------------------------------------
# Contract 3 — validator raises on missing / empty copy
# ---------------------------------------------------------------------------

def test_validator_raises_when_detail_missing_on_banned() -> None:
    e = _banned_enriched("DMAA")
    bad_blob = {"banned_substance_detail": None}
    with pytest.raises(ValueError, match="E1.1.4"):
        _validate_banned_preflight_propagation(bad_blob, e, "DSLD-MISSING")


def test_validator_raises_on_empty_one_liner() -> None:
    e = _banned_enriched("DMAA")
    bad_blob = {"banned_substance_detail": {
        "safety_warning_one_liner": "",
        "safety_warning": "Non-empty body.",
    }}
    with pytest.raises(ValueError, match="safety_warning_one_liner"):
        _validate_banned_preflight_propagation(bad_blob, e, "DSLD-EMPTY-OL")


def test_validator_raises_on_empty_body() -> None:
    e = _banned_enriched("DMAA")
    bad_blob = {"banned_substance_detail": {
        "safety_warning_one_liner": "Valid one-liner.",
        "safety_warning": "",
    }}
    with pytest.raises(ValueError, match="safety_warning empty"):
        _validate_banned_preflight_propagation(bad_blob, e, "DSLD-EMPTY-B")


def test_validator_silent_on_non_banned_products() -> None:
    e = make_enriched()  # no banned substances
    _validate_banned_preflight_propagation({}, e, "DSLD-CLEAN")


# ---------------------------------------------------------------------------
# Contract 4 — char limits enforced
# ---------------------------------------------------------------------------

def test_validator_raises_on_one_liner_exceeding_80_chars() -> None:
    e = _banned_enriched("DMAA")
    too_long = "x" * (_BANNED_PREFLIGHT_ONE_LINER_MAX + 1)
    bad_blob = {"banned_substance_detail": {
        "safety_warning_one_liner": too_long,
        "safety_warning": "OK body.",
    }}
    with pytest.raises(ValueError, match=f"{_BANNED_PREFLIGHT_ONE_LINER_MAX}-char"):
        _validate_banned_preflight_propagation(bad_blob, e, "DSLD-LONG-OL")


def test_validator_raises_on_body_exceeding_200_chars() -> None:
    e = _banned_enriched("DMAA")
    too_long = "x" * (_BANNED_PREFLIGHT_BODY_MAX + 1)
    bad_blob = {"banned_substance_detail": {
        "safety_warning_one_liner": "OK",
        "safety_warning": too_long,
    }}
    with pytest.raises(ValueError, match=f"{_BANNED_PREFLIGHT_BODY_MAX}-char"):
        _validate_banned_preflight_propagation(bad_blob, e, "DSLD-LONG-B")


def test_validator_accepts_fields_at_exact_char_limit() -> None:
    """Boundary: exactly at the limit must pass, only > limit fails."""
    e = _banned_enriched("DMAA")
    at_limit_one = "x" * _BANNED_PREFLIGHT_ONE_LINER_MAX
    at_limit_body = "x" * _BANNED_PREFLIGHT_BODY_MAX
    ok_blob = {"banned_substance_detail": {
        "safety_warning_one_liner": at_limit_one,
        "safety_warning": at_limit_body,
    }}
    _validate_banned_preflight_propagation(ok_blob, e, "DSLD-EXACT")


# ---------------------------------------------------------------------------
# Helper direct-test coverage
# ---------------------------------------------------------------------------

def test_helper_returns_none_for_non_banned_product() -> None:
    e = make_enriched()
    assert build_banned_substance_detail(e, []) is None


def test_helper_skips_warning_with_empty_authored_copy() -> None:
    """If the only banned-substance warning has empty one_liner/body, the
    helper returns None (not a partial dict). The validator then fires."""
    e = _banned_enriched("DMAA")
    empty_warnings = [{
        "type": "banned_substance",
        "title": "Banned substance: DMAA",
        "safety_warning_one_liner": "",
        "safety_warning": "",
    }]
    assert build_banned_substance_detail(e, empty_warnings) is None


def test_helper_extracts_substance_name_from_title() -> None:
    e = _banned_enriched("Ephedra")
    warnings = [{
        "type": "banned_substance",
        "title": "Banned substance: Ephedra",
        "safety_warning_one_liner": "Ephedra is banned.",
        "safety_warning": "Long-form safety warning.",
    }]
    bsd = build_banned_substance_detail(e, warnings)
    assert bsd is not None
    assert bsd["substance_name"] == "Ephedra"


def test_contract_test_auto_gate_now_fires() -> None:
    """Sanity check — the E1.0.2 invariant #4 contract test gates on
    the presence of banned_substance_detail OR ingredient-level copy.
    A realistic banned fixture now triggers the top-level gate."""
    e = _banned_enriched("DMAA")
    blob = build_detail_blob(e, make_scored())
    # Either top-level or ingredient-level path must be populated
    assert (
        blob.get("banned_substance_detail")
        or any(
            ing.get("is_banned") and (
                ing.get("safety_warning_one_liner") or ing.get("safety_warning")
            )
            for ing in blob.get("ingredients") or []
        )
    )
