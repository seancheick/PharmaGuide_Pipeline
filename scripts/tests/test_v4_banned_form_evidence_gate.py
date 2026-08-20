"""v4 safety gate — policy-relevant form / raw_source_text evidence.

Regression for the export↔v4 divergence found on a full-corpus shadow build:
8 products that the EXPORT hard-blocks via ``has_banned_substance`` were scored
58.9–70.5 by v4 (verdict SAFE/CAUTION, finite raw score) because the v4 safety
gate's resolver pass read a NARROWER evidence set than the export.

Root cause (verified):
  ``scoring_v4.gate_safety._iter_resolver_safety_hits`` fed the inactive
  resolver only ``name`` / ``raw_source_text`` / ``standardName`` (first-wins),
  never the ``forms[]`` array. The export's
  ``build_final_db._active_banned_recall_evidence_terms`` scans ``forms[].name``
  + ``forms[].prefix`` AND passes ``name`` and ``raw_source_text`` as separate
  terms. So a banned *form* of a generic active (Boron → ``Sodium Tetraborate``)
  or a banned substance the cleaner moved into ``raw_source_text`` while leaving
  a generic ``name`` (Partially Hydrogenated Soybean Oil) was invisible to v4.

Both indices (the export's ``_get_active_banned_recalled_index`` and the
resolver's ``_banned_index``) are built from the SAME filtered entries with the
SAME normalizer, so feeding the gate's resolver the SAME evidence terms yields
parity — the gate now BLOCKs natively, no longer depending on the export net.

Current policy outcomes covered:
  1. Sodium tetraborate is a recognized supplemental boron form and must not
     inherit the retired food-additive hard block.
  2. Partially Hydrogenated Oils / PHOs remain a verified US block.

Each product below is a faithful reconstruction of the real blob shape: a
generic, non-banned ``name``/``standardName`` with the banned substance living
ONLY in ``forms[]`` and/or ``raw_source_text`` — exactly the channels the gate
previously ignored.
"""

from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))


def _clean_contaminant_data() -> dict:
    """Empty contaminant snapshot — forces the verdict to come from the
    resolver evidence path (the path under test), not the legacy snapshot."""
    return {"banned_substances": {"found": False, "substances": []}}


# --------------------------------------------------------------------------- #
# Supplemental boron forms — Sodium Tetraborate
# --------------------------------------------------------------------------- #


def test_boron_with_sodium_tetraborate_form_does_not_block() -> None:
    """NIH ODS identifies sodium tetraborate as a supplemental boron form."""
    from scoring_v4.gate_safety import evaluate_safety_gate

    product = {
        "dsld_id": "221112",
        "fullName": "Infinite Test",
        "contaminant_data": _clean_contaminant_data(),
        "activeIngredients": [
            {
                "name": "Boron",
                "standardName": "Boron",
                "mapped": True,
                "raw_source_text": "Boron (as Sodium Tetraborate)",
                "forms": [{"prefix": "as", "name": "Sodium Tetraborate"}],
            }
        ],
        "inactiveIngredients": [],
    }
    result = evaluate_safety_gate(product)
    assert result.verdict not in {"BLOCKED", "UNSAFE"}
    assert result.short_circuits_scoring is False
    assert result.blocking_reason is None
    assert result.quarantine_required is False


def test_boron_with_tetraborate_decahydrate_form_does_not_block() -> None:
    """The decahydrate form follows the same supplemental-boron policy."""
    from scoring_v4.gate_safety import evaluate_safety_gate

    product = {
        "dsld_id": "26631",
        "fullName": "Joint Support Complex",
        "contaminant_data": _clean_contaminant_data(),
        "activeIngredients": [
            {"name": "Glucosamine Sulfate", "standardName": "Glucosamine", "mapped": True},
            {"name": "Chondroitin Sulfate", "standardName": "Chondroitin", "mapped": True},
            {
                "name": "Boron",
                "standardName": "Boron",
                "mapped": True,
                "raw_source_text": "Boron (as Sodium Tetraborate Decahydrate)",
                "forms": [{"prefix": "as", "name": "Sodium Tetraborate Decahydrate"}],
            },
        ],
        "inactiveIngredients": [],
    }
    result = evaluate_safety_gate(product)
    assert result.verdict not in {"BLOCKED", "UNSAFE"}
    assert result.short_circuits_scoring is False
    assert result.blocking_reason is None
    assert result.quarantine_required is False


def test_bare_boron_without_banned_form_does_not_block() -> None:
    """Elemental boron and boron citrate must not be hard-blocked."""
    from scoring_v4.gate_safety import evaluate_safety_gate

    product = {
        "dsld_id": "BORON_CITRATE",
        "fullName": "Boron Citrate 3mg",
        "contaminant_data": _clean_contaminant_data(),
        "activeIngredients": [
            {
                "name": "Boron",
                "standardName": "Boron",
                "mapped": True,
                "raw_source_text": "Boron (as Boron Citrate)",
                "forms": [{"prefix": "as", "name": "Boron Citrate"}],
            }
        ],
        "inactiveIngredients": [],
    }
    result = evaluate_safety_gate(product)
    assert result.verdict != "BLOCKED", (
        f"benign boron citrate must not hard-block; got {result.verdict!r}"
    )


def test_inactive_tetraborate_duplicate_of_active_boron_does_not_block() -> None:
    """DSLD sometimes repeats the active Boron source in Other Ingredients.
    Product context proves that row is a form duplicate, not an excipient."""
    from scoring_v4.gate_safety import evaluate_safety_gate

    product = {
        "dsld_id": "MEMBERS_MARK_SHAPE",
        "fullName": "Glucosamine with Boron",
        "contaminant_data": _clean_contaminant_data(),
        "activeIngredients": [{
            "name": "Boron",
            "standardName": "Boron",
            "canonical_id": "boron",
            "mapped": True,
        }],
        "inactiveIngredients": [{
            "name": "Sodium Tetraborate",
            "standardName": "Sodium Tetraborate",
            "raw_source_text": "Sodium Tetraborate",
        }],
    }

    result = evaluate_safety_gate(product)

    assert result.verdict != "BLOCKED"


def test_inactive_tetraborate_without_active_boron_has_no_unverified_us_block() -> None:
    from scoring_v4.gate_safety import evaluate_safety_gate

    product = {
        "dsld_id": "TRUE_INACTIVE_TETRABORATE",
        "fullName": "No Boron Active",
        "contaminant_data": _clean_contaminant_data(),
        "activeIngredients": [],
        "inactiveIngredients": [{
            "name": "Sodium Tetraborate",
            "standardName": "Sodium Tetraborate",
        }],
    }

    result = evaluate_safety_gate(product)

    assert result.verdict not in {"BLOCKED", "UNSAFE"}
    assert result.blocking_reason is None
    assert result.quarantine_required is False


# --------------------------------------------------------------------------- #
# Substance class 2 — Partially Hydrogenated Oils (PHOs)
# --------------------------------------------------------------------------- #


def test_pho_in_raw_source_text_blocks() -> None:
    """dsld 33212 'Decadent Delight Vanilla Milkshake' shape: cleaner left a
    generic 'name' ('Vegetable Oil') but the banned PHO text survives in
    raw_source_text. The export caught this via the raw_source_text term; the
    gate must too. Must BLOCK."""
    from scoring_v4.gate_safety import evaluate_safety_gate

    product = {
        "dsld_id": "33212",
        "fullName": "Decadent Delight Vanilla Milkshake",
        "contaminant_data": _clean_contaminant_data(),
        "activeIngredients": [],
        "inactiveIngredients": [
            {
                "name": "Vegetable Oil",
                "standardName": "Vegetable Oil",
                "raw_source_text": "Partially Hydrogenated Soybean Oil",
            }
        ],
    }
    result = evaluate_safety_gate(product)
    assert result.verdict == "BLOCKED", (
        f"PHO in raw_source_text must hard-block; got {result.verdict!r}"
    )
    assert result.short_circuits_scoring is True
    assert result.blocking_reason == "banned_ingredient"
    assert "Hydrogenated" in (result.matched_substance or "")


def test_pho_in_form_blocks() -> None:
    """PHO carried in forms[] (e.g. 'Shortening' base with a partially
    hydrogenated palm oil form). Must BLOCK."""
    from scoring_v4.gate_safety import evaluate_safety_gate

    product = {
        "dsld_id": "PHO_FORM",
        "fullName": "Chewable Shortening Base",
        "contaminant_data": _clean_contaminant_data(),
        "activeIngredients": [],
        "inactiveIngredients": [
            {
                "name": "Shortening",
                "standardName": "Shortening",
                "forms": [{"name": "Partially Hydrogenated Palm Oil"}],
            }
        ],
    }
    result = evaluate_safety_gate(product)
    assert result.verdict == "BLOCKED"
    assert result.short_circuits_scoring is True
    assert result.blocking_reason == "banned_ingredient"


# --------------------------------------------------------------------------- #
# Robustness — the broadened evidence path must never raise
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "ingredient",
    [
        {"name": "Boron", "forms": None},
        {"name": "Boron", "forms": "not-a-list"},
        {"name": "Boron", "forms": [None, "str-form", {"name": None}]},
        {"name": None, "raw_source_text": None, "forms": []},
        {"forms": [{"prefix": "as", "name": "Sodium Tetraborate"}]},  # name absent, form present
    ],
)
def test_malformed_forms_do_not_crash(ingredient: dict) -> None:
    from scoring_v4.gate_safety import evaluate_safety_gate

    product = {
        "contaminant_data": _clean_contaminant_data(),
        "activeIngredients": [ingredient],
        "inactiveIngredients": [],
    }
    # Must not raise; the retired tetraborate rule must not hard-block.
    evaluate_safety_gate(product)


# --------------------------------------------------------------------------- #
# Full-corpus PHO guard (corpus-gated; skips when the enriched corpus is absent).
# --------------------------------------------------------------------------- #

_TARGET_BANNED_RULE_IDS = {"BANNED_PHO"}


def _load_enriched_corpus() -> dict:
    rows: dict = {}
    pattern = str(REPO_ROOT / "scripts/products/output_*_enriched/enriched/*.json")
    for path in glob.glob(pattern):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for rec in data if isinstance(data, list) else [data]:
            if isinstance(rec, dict):
                dsld_id = str(rec.get("dsld_id") or rec.get("id") or "")
                if dsld_id:
                    rows[dsld_id] = rec
    return rows


def _target_banned_rule(product: dict, resolver) -> str | None:
    """Return the PHO rule_id if any ingredient
    of the product carries it in name / raw_source_text / forms; else None.

    Re-derives detection independently of the gate so this is a genuine
    end-to-end check, not a tautology against the gate's own term collection.
    """
    from inactive_ingredient_resolver import (
        SOURCE_BANNED_RECALLED,
        active_form_duplicate_candidate,
    )

    for key in ("activeIngredients", "inactiveIngredients"):
        for ing in product.get(key) or []:
            if not isinstance(ing, dict):
                continue
            terms = [ing.get("name"), ing.get("raw_source_text"), ing.get("standardName")]
            for form in ing.get("forms") or []:
                if isinstance(form, dict):
                    terms += [form.get("name"), form.get("prefix")]
                elif form:
                    terms.append(form)
            if key == "inactiveIngredients" and active_form_duplicate_candidate(
                resolver,
                active_ingredients=product.get("activeIngredients") or [],
                raw_name=str(ing.get("name") or ing.get("raw_source_text") or ""),
                additional_terms=[str(term) for term in terms if term],
            ):
                continue
            for term in terms:
                if not term:
                    continue
                res = resolver.resolve(raw_name=str(term))
                if (
                    res.matched_source == SOURCE_BANNED_RECALLED
                    and res.is_banned
                    and res.matched_rule_id in _TARGET_BANNED_RULE_IDS
                ):
                    return res.matched_rule_id
    return None


def test_corpus_pho_products_are_v4_native_blocked() -> None:
    enriched = _load_enriched_corpus()
    if not enriched:
        pytest.skip("enriched corpus not present (scripts/products/*_enriched/)")

    from inactive_ingredient_resolver import InactiveIngredientResolver
    from score_supplements_v4 import score_product_v4

    resolver = InactiveIngredientResolver()
    matched = 0
    failures = []
    for dsld_id, product in enriched.items():
        rule = _target_banned_rule(product, resolver)
        if not rule:
            continue
        matched += 1
        out = score_product_v4(product)
        verdict = out.get("v4_verdict")
        if verdict != "BLOCKED":
            failures.append(
                (dsld_id, rule, verdict, out.get("raw_score_v4_100"),
                 product.get("fullName") or product.get("product_name"))
            )

    assert matched > 0, (
        "corpus present but no PHO products found — expected canary 33212"
    )
    assert failures == [], (
        f"{len(failures)} PHO product(s) did not reach v4-native BLOCKED: "
        + json.dumps(failures[:10], default=str)
    )
