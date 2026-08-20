"""EU-banned additive safety entries (Green 3, Propylparaben, Azodicarbonamide).

These three additives are PROHIBITED for food use in the EU (verified citations,
2026-06-07). They are added to banned_recalled_ingredients.json as `high_risk` +
`penalize_anyway` so they fire a CAUTION even when present as an inactive/excipient
(an inactive `watchlist` is filtered to 'informational' and never warns — verified;
`high_risk` is the only status that surfaces a warning for an inactive additive).

Titanium dioxide is intentionally NOT changed here (deferred — its 10.5% blast radius
needs a separate soft-flag decision).
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

import pytest

EU_BANNED = ["FD&C Green No. 3", "propylparaben", "azodicarbonamide"]


@pytest.mark.parametrize("name", EU_BANNED)
def test_eu_banned_additive_is_safety_concern_as_inactive(name: str) -> None:
    """Each EU-banned additive must surface as a safety concern (not filtered)."""
    from inactive_ingredient_resolver import InactiveIngredientResolver

    res = InactiveIngredientResolver().resolve(name)
    assert res.is_safety_concern is True, f"{name} should be a safety concern (high_risk)"


@pytest.mark.parametrize("name", EU_BANNED)
def test_eu_only_additive_is_advisory_without_a_us_verdict(name: str) -> None:
    """EU-only policy must remain visible without becoming a US verdict."""
    from scoring_v4.gate_safety import evaluate_safety_gate

    product = {
        "dsld_id": "TEST",
        "fullName": f"Test product with {name}",
        "inactiveIngredients": [{"name": name}],
    }
    result = evaluate_safety_gate(product)
    assert result.verdict is None
    assert result.short_circuits_scoring is False
    assert "B0_REGIONAL_ADVISORY" in result.safety_signals


@pytest.mark.parametrize("label", ["Propyl Paraben", "Propyl Parabens", "Green 3", "FD&C Green No. 3"])
def test_eu_banned_real_world_label_variants_remain_regional_advisories(label: str) -> None:
    """Real label spellings must retain EU metadata without a US verdict."""
    from scoring_v4.gate_safety import evaluate_safety_gate

    product = {"dsld_id": "TEST", "fullName": "x", "inactiveIngredients": [{"name": label}]}
    result = evaluate_safety_gate(product)
    assert result.verdict is None
    assert "B0_REGIONAL_ADVISORY" in result.safety_signals


def test_eu_banned_entries_present_with_eu_citation() -> None:
    """Each entry exists in banned_recalled with status high_risk + an EU citation."""
    import json

    data = json.loads((SCRIPTS_ROOT / "data" / "banned_recalled_ingredients.json").read_text())
    by_name = {}
    for e in data["ingredients"]:
        terms = [str(e.get("standard_name", "")).lower()] + [str(a).lower() for a in e.get("aliases", [])]
        by_name[e.get("id")] = (e, " ".join(terms))

    for needle, expect_status in (("green no. 3", "high_risk"),
                                  ("propylparaben", "high_risk"),
                                  ("azodicarbonamide", "high_risk")):
        hit = next((e for e, terms in by_name.values() if needle in terms), None)
        assert hit is not None, f"{needle} missing from banned_recalled_ingredients.json"
        assert hit.get("status") == expect_status
        assert hit.get("inactive_policy") == "penalize_anyway"
        refs = json.dumps(hit.get("references_structured") or hit.get("jurisdictions") or [])
        assert ("1333/2008" in refs or "2006/52" in refs or "REACH" in refs or "1907/2006" in refs), \
            f"{needle} missing an EU regulation citation"
