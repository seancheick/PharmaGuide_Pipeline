"""Clean-label matching must read nested sub-ingredient forms.

`_iter_resolver_clean_label_hits` collected only `name` / `standardName`, so an
additive declared as a child of a compound excipient was invisible to the
clean-label lane. A `Film Coating` row listing Polyethylene Glycol, Polyvinyl
Alcohol, Riboflavin, Talc and Titanium Dioxide produced no clean-label flag at
all, on a women's multivitamin.

This is a different gap from the active-form duplicate escape fixed in the
safety lane: that one suppressed a row it had already matched, this one never
looked at the terms. Measured on the enriched corpus, 33 products gain a
Titanium Dioxide flag from reading forms, and zero products carry duplicate
clean-label rule ids today — so per-product deduplication by rule id costs
nothing and stops one additive being penalised twice.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for candidate in (ROOT, ROOT / "scripts"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from scoring_v4.gate_safety import _iter_resolver_clean_label_hits  # noqa: E402


def _product(active, inactive):
    return {
        "dsld_id": "CLEAN_LABEL_CANARY",
        "activeIngredients": active,
        "inactiveIngredients": inactive,
    }


def _row(name, forms=None):
    row = {"name": name, "standardName": name, "raw_source_text": name}
    if forms:
        row["forms"] = [{"name": f} for f in forms]
    return row


def _rules(hits):
    return {h.get("matched_rule_id") for h in hits}


# --------------------------------------------------------------------------- #
# The gap
# --------------------------------------------------------------------------- #


def test_additive_nested_in_a_compound_excipient_is_flagged() -> None:
    hits = _iter_resolver_clean_label_hits(
        _product(
            [_row("Riboflavin")],
            [_row("Film Coating", ["Polyethylene Glycol", "Polyvinyl Alcohol",
                                   "Riboflavin", "Talc", "Titanium Dioxide"])],
        )
    )
    assert "BANNED_ADD_TITANIUM_DIOXIDE" in _rules(hits), (
        f"Titanium Dioxide inside forms[] was not flagged; got {_rules(hits)}"
    )
    flagged = [h for h in hits if h["matched_rule_id"] == "BANNED_ADD_TITANIUM_DIOXIDE"]
    assert len(flagged) == 1
    assert "titanium" in str(flagged[0]["name"]).lower(), (
        "the flag must name the additive, not the compound row it hid in"
    )
    assert flagged[0]["role"] == "inactive"


def test_a_top_level_additive_still_flags() -> None:
    hits = _iter_resolver_clean_label_hits(
        _product([_row("Vitamin C")], [_row("Titanium Dioxide")])
    )
    assert "BANNED_ADD_TITANIUM_DIOXIDE" in _rules(hits)
    assert len(hits) == 1


def test_one_additive_declared_twice_is_flagged_once() -> None:
    """The penalty sums per hit, so a duplicate would charge twice."""
    hits = _iter_resolver_clean_label_hits(
        _product(
            [_row("Vitamin C")],
            [
                _row("Titanium Dioxide"),
                _row("Film Coating", ["Titanium Dioxide", "Talc"]),
            ],
        )
    )
    tio2 = [h for h in hits if h["matched_rule_id"] == "BANNED_ADD_TITANIUM_DIOXIDE"]
    assert len(tio2) == 1, f"expected one titanium dioxide flag, got {len(tio2)}"


# --------------------------------------------------------------------------- #
# Negative canaries
# --------------------------------------------------------------------------- #


def test_a_clean_compound_row_flags_nothing() -> None:
    hits = _iter_resolver_clean_label_hits(
        _product(
            [_row("Vitamin D3")],
            [_row("Soft Gel Capsule", ["Gelatin", "Glycerin", "purified Water"])],
        )
    )
    assert not _rules(hits), f"clean excipients must not flag; got {_rules(hits)}"


def test_a_form_that_merely_restates_an_active_is_not_flagged() -> None:
    """Reuses the safety lane's term scoping, so a duplicate child is skipped."""
    hits = _iter_resolver_clean_label_hits(
        _product(
            [_row("Vitamin B6")],
            [_row("Pyridoxine Hydrochloride")],
        )
    )
    assert not _rules(hits)


def test_no_product_gets_a_flag_from_an_empty_row() -> None:
    assert _iter_resolver_clean_label_hits(_product([], [])) == []
    assert _iter_resolver_clean_label_hits(
        _product([], [{"forms": [{"name": ""}]}])
    ) == []


# --------------------------------------------------------------------------- #
# Real product
# --------------------------------------------------------------------------- #


def test_corpus_canary_178791_flags_its_film_coating_additives() -> None:
    """Women's Multivitamin: Talc + Titanium Dioxide inside `Film Coating`."""
    import glob
    import json

    files = sorted(glob.glob("scripts/products/output_*_enriched/enriched/*.json"))
    files = [f for f in files if not f.endswith(".stage_manifest.json")]
    if not files:
        pytest.skip("enriched corpus not present")

    product = None
    for path in files:
        try:
            payload = json.loads(Path(path).read_text())
        except Exception:
            continue
        rows = payload if isinstance(payload, list) else (
            payload.get("products") or payload.get("items")
            or payload.get("data") or [payload]
        )
        for candidate in rows:
            if isinstance(candidate, dict) and str(
                candidate.get("dsld_id") or candidate.get("dsldId") or ""
            ) == "178791":
                product = candidate
                break
        if product:
            break
    if product is None:
        pytest.skip("178791 not present in the enriched corpus")

    assert "BANNED_ADD_TITANIUM_DIOXIDE" in _rules(
        _iter_resolver_clean_label_hits(product)
    )
