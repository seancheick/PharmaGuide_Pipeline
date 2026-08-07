"""Every v4 formulation module that charges B1 must emit the inactive ledger.

`build_final_db._inactive_penalty_tones` colours the "Other ingredients" dots
from `_v4_inactive_penalty_details`. When that ledger is empty the tone falls
through to green — which the contract defines as "0 penalty AND no safety
concern" — so a charged additive renders as clean.

2026-08-07: generic, sports and fiber_digestive each built their returned
metadata by cherry-picking a single key::

    "dietary_sugar": shared["metadata"].get("dietary_sugar")

which silently dropped `inactive_penalty_details`. 5,116 products carried a real
B1_harmful_additives charge while shipping an empty ledger, so every additive
dot on them was green — including magnesium stearate and silicon dioxide that
the same product's "what to consider" listed as penalised. probiotic,
multi_prenatal, b_complex and omega used `metadata.update(...)` and were fine.

These tests pin the invariant at the seam rather than per module, so a future
module cannot reintroduce the cherry-pick.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from scoring_v4.modules.generic_formulation import (  # noqa: E402
    shared_formulation_penalty_detail,
)

MODULES = [
    "generic_formulation",
    "sports_formulation",
    "fiber_digestive_formulation",
    "probiotic_formulation",
    "multi_prenatal_formulation",
    "omega_formulation",
    "b_complex",
]


def _real_products_charging_b1(limit: int = 400):
    """Real enriched records whose B1 harmful-additive penalty actually fires.

    A synthetic fixture is not used here: the charge depends on the enricher's
    resolved inactive rows, so hand-building one only tests my guess at that
    shape. Skips cleanly when the corpus is not present.
    """
    import json, glob
    out = []
    for path in sorted(glob.glob(
        str(SCRIPTS / "products" / "output_*_enriched" / "enriched" / "*.json")
    )):
        try:
            data = json.loads(Path(path).read_text())
        except Exception:
            continue
        for rec in (data if isinstance(data, list) else data.get("products", [])):
            detail = shared_formulation_penalty_detail(rec)
            if detail["penalties"]["B1_harmful_additives"] < 0:
                out.append((rec, detail))
                if len(out) >= limit:
                    return out
    return out


def test_shared_detail_emits_the_ledger_when_b1_charges():
    """Every B1 charge must come with a ledger row to colour the dot."""
    samples = _real_products_charging_b1()
    if not samples:
        pytest.skip("enriched corpus not available")

    # Scope on the HIT's own source_section, not on whether the product
    # happens to have inactive rows. A harmful additive matched on an ACTIVE
    # ingredient (e.g. DSLD 252831 / 251796, Senna) is charged but deliberately
    # excluded from this ledger -- there is no "Other ingredients" row to
    # colour, and the concern surfaces on the active instead. Only a charge
    # traceable to a non-active row owes a ledger entry.
    def _has_inactive_hit(rec):
        return any(
            str(h.get("source_section") or "").lower() != "active"
            for h in (rec.get("harmful_additives") or [])
            if isinstance(h, dict)
        )

    silent = [
        rec.get("dsld_id")
        for rec, detail in samples
        if _has_inactive_hit(rec)
        and not detail["metadata"].get("inactive_penalty_details")
    ]
    assert not silent, (
        f"{len(silent)} of {len(samples)} products charge B1_harmful_additives "
        f"but emit an EMPTY inactive ledger, so their additive dots render "
        f"green. First few: {silent[:5]}"
    )

    for _rec, detail in samples[:50]:
        for row in detail["metadata"]["inactive_penalty_details"]:
            assert row.get("matched_rule_id"), f"ledger row without a rule id: {row}"
            assert row.get("penalty_tier") in {
                "low", "moderate", "high", "critical",
            }, row
            assert isinstance(row.get("penalty_applied"), (int, float)), row


def test_no_charged_inactive_row_renders_green():
    """green must mean "no penalty" — a charged row may never render green.

    Measured 2026-08-07 on the real corpus: 73 charged rows across 67 products
    rendered green because the enricher's harmful matcher and the display
    resolver assigned the same label DIFFERENT rule ids, so the ledger's rule-id
    join silently missed. 47 were dl-alpha-tocopherol and 19 were FD&C colour
    lakes — artificial colours reading "clean" is precisely the surface a user
    checks. The label join in ``_inactive_display_tone`` closes it; this pins the
    outcome rather than the mechanism, so any future re-derivation still has to
    keep charged rows visible.
    """
    import glob
    import json

    from build_final_db import (
        _form_match_terms,
        _inactive_display_tone,
        _inactive_penalty_tones,
        _inactive_penalty_tones_by_label,
    )
    from inactive_ingredient_resolver import InactiveIngredientResolver

    paths = sorted(
        glob.glob(
            str(SCRIPTS / "products" / "output_*_enriched" / "enriched" / "*.json")
        )
    )
    if not paths:
        pytest.skip("enriched corpus not available")

    resolver = InactiveIngredientResolver()

    def _norm(value):
        return " ".join(str(value or "").lower().split())

    offenders = []
    checked = 0
    for path in paths:
        try:
            data = json.loads(Path(path).read_text())
        except Exception:
            continue
        for rec in (data if isinstance(data, list) else data.get("products", [])):
            if not isinstance(rec, dict):
                continue
            # "Charged" is whatever the SCORER adjudicated, read straight off its
            # ledger — never re-derived from the raw hits. Re-deriving is the
            # exact mistake this file exists to prevent: the scorer legitimately
            # declines some hits (an active-section row, or the nutrient_synthetic
            # class, which is a nutrient-form quality signal and says nothing
            # about an excipient), and a test that recomputes the set instead of
            # reading it would demand green rows turn orange.
            detail = shared_formulation_penalty_detail(rec)
            ledger = detail["metadata"].get("inactive_penalty_details") or []
            charged = {
                _norm(label)
                for row in ledger
                if isinstance(row, dict) and float(row.get("penalty_applied") or 0) > 0
                for label in (row.get("matched_labels") or [])
                if _norm(label)
            }
            if not charged:
                continue

            scored = {"_v4_inactive_penalty_details": ledger}
            rule_tones = _inactive_penalty_tones(scored)
            label_tones = _inactive_penalty_tones_by_label(scored)

            for ing in (rec.get("inactiveIngredients") or []):
                if not isinstance(ing, dict):
                    continue
                raw = (ing.get("raw_source_text") or "").strip()
                name = (ing.get("name") or raw).strip()
                if _norm(raw) not in charged and _norm(name) not in charged:
                    continue
                res = resolver.resolve(
                    raw_name=name or raw,
                    standard_name=(ing.get("standardName") or "").strip() or None,
                    additional_terms=_form_match_terms(ing.get("forms")),
                )
                tone = _inactive_display_tone(
                    res.matched_source,
                    res.matched_rule_id,
                    rule_tones,
                    harmful_severity=res.harmful_severity,
                    label_tones=label_tones,
                    row_labels=(raw, name),
                )
                checked += 1
                if tone == "green":
                    offenders.append((rec.get("dsld_id"), raw or name))
            if checked >= 4000:
                break
        if checked >= 4000:
            break

    if not checked:
        pytest.skip("no charged inactive rows in the available corpus")
    assert not offenders, (
        f"{len(offenders)} of {checked} charged inactive rows render GREEN, so a "
        f"penalised additive reads as clean. First few: {offenders[:5]}"
    )


@pytest.mark.parametrize("module_name", MODULES)
def test_module_propagates_whole_shared_metadata(module_name):
    """No module may cherry-pick keys out of the shared metadata.

    Cherry-picking is the exact defect that emptied the ledger: it silently
    drops any key the author did not think to name, so adding a key to the
    shared helper would go missing again. Requiring the full spread/update
    keeps one brain.
    """
    source = (SCRIPTS / "scoring_v4" / "modules" / f"{module_name}.py").read_text()
    if "shared_formulation_penalty_detail" not in source:
        pytest.skip(f"{module_name} does not use the shared penalty detail")

    # Accept any form that copies the metadata WHOLESALE -- a ** spread
    # (with or without .get) or a dict.update(). What must never appear is a
    # per-key pick like `"dietary_sugar": shared["metadata"]["dietary_sugar"]`.
    import re
    spreads = bool(
        re.search(r'\*\*\s*shared[A-Za-z_]*(?:\.get\(\s*)?\[?["\']metadata', source)
        or re.search(r'metadata\.update\(\s*shared[A-Za-z_]*\[["\']metadata', source)
    )
    assert spreads, (
        f"{module_name} must spread or update the WHOLE shared metadata "
        f'(e.g. **shared["metadata"]). Cherry-picking individual keys drops '
        f"inactive_penalty_details and turns charged additive dots green."
    )
