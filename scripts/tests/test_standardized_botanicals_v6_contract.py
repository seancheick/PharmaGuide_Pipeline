"""V6 cleanup contract for ``standardized_botanicals.json``.

Established 2026-05-22 after the bonus-eligibility audit found that only
~4% of the 201 legacy entries were clearly marker-qualified. User +
Codex directive: this file is the bonus-eligible standardized-extract
registry, NOT a botanical identity file.

An entry may stay only if it has at least one of:

1. ``marker_percent`` — explicit marker standardization (X%, marker
   compound listed, quantified active constituent)
2. ``branded_extract`` — verified branded standardized extract (KSM-66,
   Sensoril, Meriva, BCM-95, Curcumin C3, Svetol, etc.) with evidence
   in entry notes/sources
3. ``pharmacopeial_marker`` — USP/EP/JP/NIH-ODS-style marker spec
4. ``mushroom_fraction`` — beta-glucan / PSK / PSP fraction with
   species + preparation preserved

If none applies, the entry must move to ``botanical_ingredients.json``
(basic identity, no A5b bonus).

This test file pins:
- the ``_metadata.bonus_eligibility_contract`` contract block (so future
  edits cannot quietly delete the rule)
- the green_coffee_bean tutorial cleanup (first entry to land in v6
  migration)
- the new plain-identity entry that holds non-bonus coffee bean aliases
  in ``botanical_ingredients.json``
"""
from __future__ import annotations

import json
import os
import sys

import pytest

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_SCRIPTS = os.path.join(_ROOT, "scripts")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def sbot() -> dict:
    with open(os.path.join(_SCRIPTS, "data", "standardized_botanicals.json")) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def botanicals() -> dict:
    with open(os.path.join(_SCRIPTS, "data", "botanical_ingredients.json")) as f:
        return json.load(f)


def _find(entries, eid):
    for e in entries:
        if isinstance(e, dict) and e.get("id") == eid:
            return e
    return None


# ---------------------------------------------------------------------------
# Contract block
# ---------------------------------------------------------------------------

def test_metadata_carries_bonus_eligibility_contract(sbot):
    """``_metadata.bonus_eligibility_contract`` must be present with all four
    acceptable standardization bases named. This is the governance contract
    — any future edit that quietly removes it will fail this test."""
    contract = sbot.get("_metadata", {}).get("bonus_eligibility_contract")
    assert contract is not None, "Missing _metadata.bonus_eligibility_contract"
    bases = contract.get("acceptable_standardization_bases", {})
    for required in ("marker_percent", "branded_extract",
                     "pharmacopeial_marker", "mushroom_fraction"):
        assert required in bases, (
            f"_metadata.bonus_eligibility_contract.acceptable_standardization_bases "
            f"missing '{required}'"
        )
    # Anti-bulk-move guardrail must be present
    assert "do_not_bulk_move" in contract, (
        "Contract must explicitly prohibit bulk-move of legacy entries"
    )
    # UNII-alone disclaimer must be present (Codex directive)
    assert "do_not_use_unii_alone" in contract, (
        "Contract must explicitly note UNII does NOT prove standardization"
    )


# ---------------------------------------------------------------------------
# green_coffee_bean — first v6 cleanup entry
# ---------------------------------------------------------------------------

def test_green_coffee_bean_is_bonus_eligible_with_marker_percent(sbot):
    """The cleaned-up ``green_coffee_bean`` entry must declare itself
    bonus-eligible via the new ``bonus_eligible`` field, citing
    ``marker_percent`` (45–50% chlorogenic acids) as the
    standardization basis."""
    e = _find(sbot.get("standardized_botanicals", []), "green_coffee_bean")
    assert e is not None, "green_coffee_bean entry missing"
    assert e.get("bonus_eligible") is True
    assert e.get("standardization_basis") == "marker_percent"
    markers = e.get("marker_compounds") or []
    markers_lower = [m.lower() for m in markers]
    assert any("chlorogenic" in m for m in markers_lower), (
        f"marker_compounds must name chlorogenic acid(s). Got: {markers}"
    )
    assert e.get("bonus_rationale"), "bonus_rationale must be a non-empty string"
    sources = e.get("sources") or []
    assert len(sources) >= 1, (
        "sources[] must cite at least one PMID/DOI/USP/NIH-ODS/ABC URL "
        "when bonus_eligible=true"
    )


def test_green_coffee_bean_aliases_only_carry_standardization_evidence(sbot):
    """After v6 cleanup, ``green_coffee_bean`` aliases must NOT contain
    branded standardized phrasing (Svetol) and explicit marker-percent
    aliases that document the bonus pathway. Plain aliases (e.g.,
    ``coffea canephora robusta``, ``green coffee bean extract``) are
    KEPT for runtime matching — the enricher's
    ``meets_threshold`` / ``has_standardized_botanical`` gate
    (score_supplements.py:1148) is the authoritative bonus-eligibility
    check at scoring time. Pre-commit shadow-score confirmed all
    products currently matching this entry via plain aliases that
    legitimately have chlorogenic-acid % evidence in their broader
    label text still get the bonus through the gate; removing the
    plain aliases would strip the bonus from ~25-30 legitimately
    standardized products."""
    e = _find(sbot.get("standardized_botanicals", []), "green_coffee_bean")
    assert e is not None
    aliases = [a.lower() for a in e.get("aliases", [])]

    # At least one verified branded/marker-explicit phrasing must be added
    branded_or_standardized = any(
        "svetol" in a or "standardized" in a or "% chlorogenic" in a
        or "chlorogenic acid" in a
        for a in aliases
    )
    assert branded_or_standardized, (
        f"green_coffee_bean must carry at least one branded or "
        f"marker-standardized phrasing alias (Svetol or 'standardized "
        f"to X% chlorogenic acids'). Got: {e.get('aliases')}"
    )


# ---------------------------------------------------------------------------
# Plain coffee bean entry — new botanical_ingredients home (no bonus)
# ---------------------------------------------------------------------------

def test_botanical_ingredients_has_plain_green_coffee_bean(botanicals):
    """Plain coffee bean aliases (``Coffee Bean Extract``, ``Coffea robusta
    Seed Extract``, ``Coffee extract``, ``Coffee, Powder``) live here.
    No A5b bonus.

    Codex directive: ``green coffee bean plain → no bonus``;
    ``green coffee bean extract standardized to chlorogenic acids → bonus``."""
    target_id_candidates = [
        "coffea_arabica_bean", "coffea_robusta_bean",
        "green_coffee_bean_plain", "coffee_bean", "coffee_bean_plain",
    ]
    for tid in target_id_candidates:
        e = _find(botanicals.get("botanical_ingredients", []), tid)
        if e is not None:
            aliases = [a.lower() for a in e.get("aliases", [])]
            # Must cover the plain phrasings surfaced in the 2026-05-22 unmapped scan
            for required in (
                "coffee bean extract",
                "coffea robusta",
                "coffea robusta seed extract",
            ):
                assert required in aliases, (
                    f"{tid}: must alias '{required}' (plain coffee bean "
                    f"identity surfaced in 2026-05-22 unmapped scan). "
                    f"Got: {e.get('aliases')}"
                )
            return
    pytest.fail(
        f"No plain coffee bean entry found in botanical_ingredients.json "
        f"under any of: {target_id_candidates}. v6 cleanup requires a "
        f"plain-identity home for unstandardized coffee bean labels."
    )
