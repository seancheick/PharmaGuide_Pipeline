"""Phase 0d R2 — the classifier must never fall through silently.

THE DEFECT
    `primary_type` is initialised to "general_supplement" at confidence 0.0, and
    the decision chain has NO terminal `else`. A product that no branch claims
    keeps those defaults and emits `classification_reasons == []` — the
    classifier says "this is a general supplement" while recording no reason at
    all, which is indistinguishable from "a rule decided that".

    SUPP_TYPE_CONSOLIDATION_PLAN.md §10 makes this a hard gate:
      "`general_supplement` reasons are **never empty**. Zero confidence **is**
       allowed when truthful, but only with an explicit reason code
       (`no_quantified_active_evidence`)."

    Measured: 503 products before R1, 287 after. R2 takes it to 0.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from supplement_taxonomy import (  # noqa: E402
    REASON_CODE_NO_QUANTIFIED_ACTIVE_EVIDENCE,
    REASON_CODE_UNCLASSIFIED_RESIDUAL,
    classify_supplement,
)


def _row(name, canonical_id, category, qty=100.0, unit="mg", **extra):
    row = {
        "name": name, "canonical_id": canonical_id, "standard_name": name,
        "category": category, "quantity": qty, "unit": unit, "mapped": True,
        "role_classification": "active_scorable",
        "cleaner_row_role": "active_scorable",
        "score_eligible_by_cleaner": True,
    }
    row.update(extra)
    return row


def _product(name, rows):
    return {
        "dsld_id": 950001, "product_name": name, "fullName": name,
        "ingredient_quality_data": {"ingredients_scorable": rows},
        "probiotic_data": {"is_probiotic_product": False, "total_cfu": 0},
    }


# The real fallthrough shape, taken from the corpus: dsld 294414
# "Lutein (with Zeaxanthin)" — two distinct antioxidant identities that no rule
# claims. (A SINGLE lutein routes to herbal_botanical via _BOTANICAL_ANTIOXIDANTS;
# it is the 2-active band that has no vocabulary.) 330 products land here.
_FALLTHROUGH_ROWS = [
    ("Lutein", "lutein", "antioxidant", 20.0),
    ("Zeaxanthin", "zeaxanthin", "antioxidant", 4.0),
]


def _fallthrough_product():
    return _product("Lutein (with Zeaxanthin)", [
        _row(name, cid, cat, qty) for name, cid, cat, qty in _FALLTHROUGH_ROWS
    ])


def test_a_product_no_branch_claims_still_states_a_reason():
    """The classifier may not know what this is, but it must say so."""
    taxonomy = classify_supplement(_fallthrough_product())

    assert taxonomy["primary_type"] == "general_supplement"
    assert taxonomy["classification_reasons"], (
        "§10 gate: general_supplement reasons are never empty"
    )
    assert REASON_CODE_UNCLASSIFIED_RESIDUAL in taxonomy["classification_reason_codes"]
    assert taxonomy["classification_confidence"] == 0.0, (
        "an unclassified residual must not claim confidence"
    )


def test_zero_active_product_uses_the_sanctioned_zero_confidence_code():
    """§10 sanctions zero confidence ONLY with an explicit code."""
    taxonomy = classify_supplement(_product("Empty Label", []))

    assert taxonomy["classification_confidence"] == 0.0
    assert taxonomy["classification_reasons"]
    assert (
        REASON_CODE_NO_QUANTIFIED_ACTIVE_EVIDENCE
        in taxonomy["classification_reason_codes"]
    )


def test_zero_confidence_always_carries_a_reason_code():
    """The invariant behind §10: never a bare 0.0."""
    for product in (
        _product("Empty Label", []),
        _fallthrough_product(),
    ):
        taxonomy = classify_supplement(product)
        if (taxonomy["classification_confidence"] or 0) == 0.0:
            assert taxonomy["classification_reason_codes"], (
                "zero confidence with no reason code is exactly what §10 forbids"
            )


def test_reason_codes_are_emitted_for_classified_products_too():
    """A confident classification must still be machine-explainable."""
    taxonomy = classify_supplement(_product("Magnesium Glycinate", [
        _row("Magnesium Glycinate", "magnesium", "mineral", 200.0),
    ]))

    assert taxonomy["primary_type"] == "single_mineral"
    assert isinstance(taxonomy["classification_reason_codes"], list)


def test_reason_codes_are_a_stable_vocabulary_not_prose():
    """The SoT gate consumes these; they must be tokens, not sentences."""
    taxonomy = classify_supplement(_fallthrough_product())
    for code in taxonomy["classification_reason_codes"]:
        assert code == code.lower()
        assert " " not in code, f"{code!r} is prose, not a code"


def test_no_general_supplement_branch_is_silent():
    """Source guard for §10: every site that assigns `general_supplement` must
    append a reason in the same breath.

    The defect was structural — `general_supplement` was the INITIAL value and
    the chain has no terminal `else`, so silence was the default. The sentinel
    fixes that, but a future branch that assigns the residual without speaking
    would re-open the gate. Cheap and blunt on purpose.
    """
    source = (SCRIPTS_DIR / "supplement_taxonomy.py").read_text()
    lines = source.splitlines()
    offenders = []
    for i, line in enumerate(lines):
        if 'primary_type = "general_supplement"' not in line:
            continue
        # a reason must be appended within the next few lines of the branch
        window = "\n".join(lines[i:i + 8])
        if "reasons.append" not in window:
            offenders.append(f"{i + 1}: {line.strip()}")
    assert not offenders, (
        "these sites assign general_supplement without stating why (§10):\n  "
        + "\n  ".join(offenders)
    )


def test_primary_type_starts_as_a_sentinel_not_a_default():
    """`general_supplement` as the initial value is what made silence possible:
    an unclaimed product inherited a real-looking answer."""
    source = (SCRIPTS_DIR / "supplement_taxonomy.py").read_text()
    start = source.index("def classify_supplement")
    end = source.index("\ndef ", start + 1)
    body = source[start:end]
    assert "primary_type: str | None = None" in body, (
        "primary_type must start as a sentinel so the fallthrough is explicit"
    )


def test_residual_reason_names_the_evidence_it_had():
    """'I don't know' is only useful if it says what it saw."""
    taxonomy = classify_supplement(_fallthrough_product())
    text = " ".join(taxonomy["classification_reasons"]).lower()
    assert "2" in text, f"the residual reason does not state the active count: {text!r}"
