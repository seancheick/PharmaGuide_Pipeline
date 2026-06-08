"""v4 safety gate — banned substance carried in form / raw_source_text evidence.

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

Substance classes covered (one block per class):
  1. Boron — banned salt form ``Sodium Tetraborate`` (dsld 221112, 26631).
  2. Partially Hydrogenated Oils / PHOs (dsld 33212).

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
# Substance class 1 — Boron salt form (Sodium Tetraborate)
# --------------------------------------------------------------------------- #


def test_boron_with_sodium_tetraborate_form_blocks() -> None:
    """dsld 221112 'Infinite Test' shape: active 'Boron' (NOT banned) whose
    banned salt form 'Sodium Tetraborate' lives in forms[]. Must BLOCK."""
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
    assert result.verdict == "BLOCKED", (
        f"banned salt form in forms[] must hard-block; got {result.verdict!r}"
    )
    assert result.short_circuits_scoring is True
    assert result.blocking_reason == "banned_ingredient"
    assert "Tetraborate" in (result.matched_substance or "")


def test_boron_with_tetraborate_decahydrate_form_blocks() -> None:
    """dsld 26631 shape (glucosamine/chondroitin + Boron): banned form
    'Sodium Tetraborate Decahydrate' carried in forms[]. Must BLOCK."""
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
    assert result.verdict == "BLOCKED"
    assert result.short_circuits_scoring is True
    assert result.blocking_reason == "banned_ingredient"


def test_bare_boron_without_banned_form_does_not_block() -> None:
    """Precision guard: elemental Boron itself is NOT banned — only the
    Sodium Tetraborate salt is. A boron product with a benign form (boron
    citrate) must NOT be hard-blocked by the broadened evidence terms."""
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
    # Must not raise; verdict may be BLOCKED (last case) or None.
    evaluate_safety_gate(product)


# --------------------------------------------------------------------------- #
# Full-corpus guard (corpus-gated; skips when the enriched corpus is absent)
#
# The existing test_v4_safety_parity_release keys off the v3 *scorer* verdict,
# which these export-banned products do NOT carry (the export overrides the
# verdict in build_final_db). So that test cannot catch this class. This guard
# closes the loop the task asks for: every corpus product whose Boron-salt /
# PHO banned substance lives in name / raw_source_text / forms must produce a
# v4-NATIVE BLOCKED — no reliance on the export net.
# --------------------------------------------------------------------------- #

_TARGET_BANNED_RULE_IDS = {"ADD_SODIUM_TETRABORATE", "BANNED_PHO"}


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
    """Return the target rule_id (Sodium Tetraborate / PHO) if any ingredient
    of the product carries it in name / raw_source_text / forms; else None.

    Re-derives detection independently of the gate so this is a genuine
    end-to-end check, not a tautology against the gate's own term collection.
    """
    from inactive_ingredient_resolver import SOURCE_BANNED_RECALLED

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


def test_corpus_boron_and_pho_products_are_v4_native_blocked() -> None:
    enriched = _load_enriched_corpus()
    if not enriched:
        pytest.skip("enriched corpus not present (scripts/products/*_enriched/)")

    from inactive_ingredient_resolver import InactiveIngredientResolver
    from score_supplements_v4_shadow import score_product_v4_shadow

    resolver = InactiveIngredientResolver()
    matched = 0
    failures = []
    for dsld_id, product in enriched.items():
        rule = _target_banned_rule(product, resolver)
        if not rule:
            continue
        matched += 1
        out = score_product_v4_shadow(product)
        verdict = out.get("shadow_score_v4_verdict")
        if verdict != "BLOCKED":
            failures.append(
                (dsld_id, rule, verdict, out.get("shadow_score_v4_100"),
                 product.get("fullName") or product.get("product_name"))
            )

    assert matched > 0, (
        "corpus present but no Sodium-Tetraborate / PHO products found — "
        "expected the known canaries (e.g. 221112, 33212, 26631)"
    )
    assert failures == [], (
        f"{len(failures)} Boron/PHO product(s) did not reach v4-native BLOCKED: "
        + json.dumps(failures[:10], default=str)
    )
