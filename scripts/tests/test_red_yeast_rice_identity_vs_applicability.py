#!/usr/bin/env python3
"""Red yeast rice: identity may be broad, applicability must stay precise.

Two entries split the concern deliberately:
  RISK_RED_YEAST_RICE    ordinary/traditional RYR   -> high_risk, NOT banned
  BANNED_RED_YEAST_RICE  monacolin-K / added-lovastatin forms -> banned

Adding a CUI to the banned entry must not let ordinary red yeast rice inherit
the narrower rule. That holds structurally -- the resolver matches on
standard_name + aliases ONLY (inactive_ingredient_resolver.py:31) and exposes
`cui` merely as an output identifier -- but these tests pin it so a future
change that starts matching on CUI fails loudly instead of silently widening a
ban.
"""

import json
from collections import Counter
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA = REPO_ROOT / "scripts" / "data" / "banned_recalled_ingredients.json"

BOTANICAL_CUI = "C0763533"   # UMLS "red yeast rice" -- owned by RISK_RED_YEAST_RICE
CONSTITUENT_CUI = "C0024027"  # UMLS "lovastatin"; UMLS maps "monacolin K" here


@pytest.fixture(scope="module")
def entries():
    return {e["id"]: e for e in json.loads(DATA.read_text())["ingredients"] if e.get("id")}


def test_banned_entry_uses_approved_null_cui_not_a_misleading_concept(entries):
    """_metadata.cui_audit_policy reserves no_single_umls_concept for a "class,
    policy, umbrella, product recall, or multi-substance record where one UMLS
    concept would be misleading". This record is the policy condition "RYR with
    enhanced/added lovastatin", and both candidate concepts mislead:
      - C0763533 is the botanical identity, owned by RISK_RED_YEAST_RICE;
      - C0024027 is the hazard constituent, and every sibling constituent-driven
        botanical carries the RECORD identity instead (bitter orange -> Citrus
        aurantium, not synephrine; pennyroyal -> pennyroyal, not pulegone).
    cui also ships to consumers via build_final_db.extract_identifiers.
    """
    e = entries["BANNED_RED_YEAST_RICE"]
    assert not e.get("cui"), (
        "BANNED_RED_YEAST_RICE must not carry a CUI: the botanical concept belongs "
        "to RISK_RED_YEAST_RICE and the constituent concept would ship 'lovastatin' "
        "as a red-yeast-rice supplement's identity"
    )
    assert e.get("cui") != CONSTITUENT_CUI
    assert e.get("cui_status") == "no_single_umls_concept"
    assert e.get("cui_note", "").strip(), "the approved null CUI must carry its rationale"


def test_botanical_concept_stays_with_the_non_banned_entry(entries):
    assert entries["RISK_RED_YEAST_RICE"].get("cui") == BOTANICAL_CUI


def test_cui_identity_is_unique_across_entries(entries):
    dupes = {c: n for c, n in Counter(
        e["cui"] for e in entries.values() if e.get("cui")).items() if n > 1}
    assert not dupes, f"CUI identity must stay 1:1 with an entry; shared: {dupes}"


def test_banned_aliases_never_cover_ordinary_red_yeast_rice(entries):
    """Applicability lives in standard_name + aliases -- it must stay narrow."""
    e = entries["BANNED_RED_YEAST_RICE"]
    terms = [e["standard_name"].lower()] + [a.lower() for a in e.get("aliases") or []]
    for bare in ("red yeast rice", "red yeast rice powder", "red yeast rice extract",
                 "monascus purpureus", "organic red yeast rice"):
        assert bare not in terms, (
            f"{bare!r} must not be a banned-entry match term -- ordinary red yeast "
            "rice is RISK_RED_YEAST_RICE, not banned"
        )
    assert any("monacolin" in t or "lovastatin" in t for t in terms), (
        "the narrowed monacolin-K/lovastatin condition must still be expressed"
    )


@pytest.mark.parametrize("label,expect_banned,expect_rule", [
    ("Red Yeast Rice", False, "RISK_RED_YEAST_RICE"),
    ("red yeast rice extract", False, "RISK_RED_YEAST_RICE"),
    ("organic red yeast rice powder", False, "RISK_RED_YEAST_RICE"),
    ("Red Yeast Rice with Monacolin K", True, "BANNED_RED_YEAST_RICE"),
    ("red yeast rice with added lovastatin", True, "BANNED_RED_YEAST_RICE"),
])
def test_resolver_keeps_ordinary_ryr_out_of_the_ban(label, expect_banned, expect_rule):
    from inactive_ingredient_resolver import InactiveIngredientResolver

    res = InactiveIngredientResolver().resolve(label)
    assert res.matched_rule_id == expect_rule, f"{label!r} routed to {res.matched_rule_id}"
    assert bool(res.is_banned) is expect_banned, (
        f"{label!r} is_banned={res.is_banned}, expected {expect_banned}"
    )
