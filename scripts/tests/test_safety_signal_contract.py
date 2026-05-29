"""SafetySignal v1 contract tests (kernel).

Locks the single chokepoint where raw matcher names (exact/alias/token_bounded)
map to the stable `match_resolution` enum. Scorers consume the enum and must
NEVER branch on raw match_type — see test_gate_safety_has_no_raw_match_type.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from identity.safety import (  # noqa: E402
    build_safety_signal,
    match_resolution_for,
    normalize_safety_signals,
)


# --- match_resolution_for ------------------------------------------------- #

def test_exact_and_alias_are_confirmed():
    assert match_resolution_for("exact", "BANNED_X") == "confirmed"
    assert match_resolution_for("alias", "BANNED_X") == "confirmed"
    assert match_resolution_for("explicit_form_evidence", "BANNED_X") == "confirmed"


def test_token_bounded_with_entry_id_is_likely():
    # DHEA / Kava shape: real word-boundary match with a populated banned_id.
    assert match_resolution_for("token_bounded", "BANNED_DHEA") == "likely"
    assert match_resolution_for("legacy_projection", "RISK_KAVA") == "likely"


def test_token_bounded_without_entry_id_is_review_only():
    assert match_resolution_for("token_bounded", "") == "review_only"
    assert match_resolution_for("token_bounded", None) == "review_only"


def test_fuzzy_and_unknown_match_types_are_review_only():
    assert match_resolution_for("fuzzy", "BANNED_X") == "review_only"
    assert match_resolution_for("substring", "BANNED_X") == "review_only"
    assert match_resolution_for("", "BANNED_X") == "review_only"


def test_numeric_confidence_fallback_when_match_type_unknown():
    assert match_resolution_for("", "BANNED_X", confidence=0.95) == "confirmed"
    assert match_resolution_for("", "BANNED_X", confidence=0.6) == "likely"
    assert match_resolution_for("", "BANNED_X", confidence=0.3) == "low_confidence"
    # likely floor requires an entry_id
    assert match_resolution_for("", "", confidence=0.6) == "review_only"


# --- build_safety_signal -------------------------------------------------- #

def test_build_signal_derives_policy_flags():
    confirmed = build_safety_signal(entry_id="BANNED_X", source_db="banned_recalled_ingredients",
                                    status="banned", match_type="exact")
    assert confirmed.match_resolution == "confirmed"
    assert confirmed.policy_eligible is True
    assert confirmed.review_required is False

    likely = build_safety_signal(entry_id="BANNED_DHEA", source_db="banned_recalled_ingredients",
                                 status="high_risk", match_type="token_bounded", confidence=0.7)
    assert likely.match_resolution == "likely"
    assert likely.policy_eligible is True
    assert likely.review_required is False
    assert likely.match_confidence == 0.7

    review = build_safety_signal(entry_id="", source_db="banned_recalled_ingredients",
                                 status="high_risk", match_type="fuzzy")
    assert review.match_resolution == "review_only"
    assert review.policy_eligible is False
    assert review.review_required is True


# --- normalize_safety_signals --------------------------------------------- #

def _dhea_product() -> dict:
    return {
        "dsld_id": "TEST",
        "contaminant_data": {
            "banned_substances": {
                "found": True,
                "substances": [
                    {
                        "ingredient": "Dehydroepiandrosterone, Micronized",
                        "banned_name": "Dehydroepiandrosterone (DHEA)",
                        "banned_id": "BANNED_DHEA",
                        "status": "high_risk",
                        "match_type": "token_bounded",
                        "match_method": "token_bounded",
                        "confidence": 0.7,
                        "severity_level": "moderate",
                        "source_section": "active",
                    }
                ],
            }
        },
    }


def test_normalize_dhea_yields_one_likely_high_risk_signal():
    signals = normalize_safety_signals(_dhea_product())
    assert len(signals) == 1
    sig = signals[0]
    assert sig.entry_id == "BANNED_DHEA"
    assert sig.status == "high_risk"
    assert sig.match_resolution == "likely"
    assert sig.policy_eligible is True
    assert sig.subject_role == "active"


def test_normalize_dedups_substance_and_safety_flag():
    product = _dhea_product()
    # add a redundant safety_flag pointing at the same entry/status
    product["contaminant_data"]["banned_substances"]["safety_flags"] = [
        {"entry_id": "BANNED_DHEA", "status": "high_risk", "match_type": "alias",
         "source_db": "banned_recalled_ingredients", "subject_role": "active",
         "matched_variant": "DHEA"}
    ]
    signals = normalize_safety_signals(product)
    # same (entry_id, status, role) → deduped to one
    assert sum(1 for s in signals if s.entry_id == "BANNED_DHEA") == 1


def test_normalize_consumes_resolver_hits_as_confirmed():
    signals = normalize_safety_signals(
        {"dsld_id": "T"},
        resolver_hits=[{"name": "BVO", "status": "banned", "role": "inactive",
                        "matched_rule_id": "BANNED_BVO", "inactive_policy": "disqualifying"}],
    )
    assert len(signals) == 1
    assert signals[0].status == "banned"
    assert signals[0].match_resolution == "confirmed"
    assert signals[0].subject_role == "inactive"


def test_normalize_top_level_boolean_fallback():
    signals = normalize_safety_signals({"has_banned_substance": True})
    assert any(s.status == "banned" and s.policy_eligible for s in signals)


def test_normalize_empty_product_is_safe():
    assert normalize_safety_signals({}) == []
    assert normalize_safety_signals(None) == []  # type: ignore[arg-type]


# --- architecture guard --------------------------------------------------- #

def test_gate_safety_has_no_raw_match_type_branching():
    """The v4 safety gate must branch only on the stable SafetySignal contract
    (match_resolution / status), never on raw matcher internals. Matcher names
    live exclusively in the kernel (identity/safety.py::match_resolution_for).

    Parses gate_safety.py and asserts no executable string constant, attribute,
    or name references a raw matcher term. Docstrings are excluded (they may
    describe history). This is the architecture lock for SafetySignal v1.
    """
    import ast

    src = (SCRIPTS_ROOT / "scoring_v4" / "gate_safety.py").read_text(encoding="utf-8")
    tree = ast.parse(src)

    # Collect docstring Constant node ids to exclude (history/comments allowed).
    docstring_ids: set = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", [])
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                docstring_ids.add(id(body[0].value))

    BANNED = {
        "match_type", "match_method", "token_bounded", "legacy_projection",
        "explicit_form_evidence", "fuzzy", "substring", "exact", "alias",
        "_verdict_match_types", "_caution_match_types", "_flag_verdict_match_types",
    }
    offenders = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                and id(node) not in docstring_ids):
            if node.value.strip().lower() in BANNED:
                offenders.append(("const", node.value))
        elif isinstance(node, ast.Attribute) and node.attr.lower() in BANNED:
            offenders.append(("attr", node.attr))
        elif isinstance(node, ast.Name) and node.id.lower() in BANNED:
            offenders.append(("name", node.id))

    assert not offenders, (
        "scoring_v4/gate_safety.py must not branch on raw matcher internals — "
        f"move that knowledge to identity/safety.py. Found: {offenders}"
    )
