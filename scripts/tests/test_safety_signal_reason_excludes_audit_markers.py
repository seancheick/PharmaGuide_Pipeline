"""safety_signal_reason names a reason, never an audit marker.

The gate records B0_RETIRED_POLICY_SIGNAL_IGNORED / B0_STALE_POLICY_SIGNAL_IGNORED
in its signal list as an audit trail (the rule was seen and deliberately not
applied). scored_artifact took the first signal as the product's stated reason,
so 14 shipped products named an ignored rule as their safety reason; DSLD 312980
(caution) hid its real DOSE_OVER_UL_CRITICAL reason behind it. The markers stay
in `flags` for audit; the reason skips them.
"""

import pytest

from enrich_supplements_v3 import SupplementEnricherV3
from scoring_v4.gate_safety import AUDIT_ONLY_SAFETY_SIGNALS, stated_safety_signal
from scoring_v4.scored_artifact import build_scored_artifact


@pytest.fixture(scope="module")
def enricher():
    return SupplementEnricherV3()


def _row(name, quantity, unit, order, canonical_id, forms=()):
    return {
        "name": name, "standardName": name, "raw_source_text": name, "order": order,
        "canonical_id": canonical_id, "canonical_source_db": "ingredient_quality_map",
        "quantity": quantity, "unit": unit, "forms": [{"name": f, "prefix": None} for f in forms],
    }


def _scored(enricher, rows):
    product = {
        "id": "audit-marker", "dsld_id": "audit-marker", "product_name": "test", "fullName": "test",
        "activeIngredients": rows, "inactiveIngredients": [],
        "servingSizes": [{"order": 1, "minQuantity": 1, "maxQuantity": 1, "unit": "Tablet(s)",
                          "minDailyServings": 1, "maxDailyServings": 1}],
    }
    enriched, _ = enricher.enrich_product(product)
    return build_scored_artifact(enriched)


BORON_TETRABORATE = ("Boron", 1, "mg", 1, "boron", ("Sodium Tetraborate",))


def test_retired_marker_alone_is_not_a_reason(enricher):
    scored = _scored(enricher, [_row(*BORON_TETRABORATE)])
    assert "B0_RETIRED_POLICY_SIGNAL_IGNORED" in scored["flags"]
    assert scored["safety_signal_reason"] is None


def test_real_reason_is_not_hidden_behind_a_retired_marker(enricher):
    scored = _scored(enricher, [_row(*BORON_TETRABORATE), _row("Niacin", 500, "mg", 2, "vitamin_b3_niacin")])
    assert scored["product_safety_status"] == "caution"
    real = [f for f in scored["flags"] if f not in AUDIT_ONLY_SAFETY_SIGNALS]
    assert "B0_RETIRED_POLICY_SIGNAL_IGNORED" in scored["flags"] and real
    assert scored["safety_signal_reason"] == real[0]


@pytest.mark.parametrize("signals,expected", [
    (["B0_REGIONAL_ADVISORY", "B0_WATCHLIST_EXCIPIENT_WARNING_ONLY", "DOSE_OVER_UL_CRITICAL"], "DOSE_OVER_UL_CRITICAL"),
    (["B0_REGIONAL_ADVISORY", "B0_WATCHLIST_EXCIPIENT_WARNING_ONLY"], "B0_REGIONAL_ADVISORY"),
    (["B0_LOWCONF_BANNED", "B0_WATCHLIST_SUBSTANCE"], "B0_WATCHLIST_SUBSTANCE"),
    (["B0_STALE_POLICY_SIGNAL_IGNORED"], None),
    ([], None),
])
def test_stated_reason_is_the_verdict_driver(signals, expected):
    """DSLD 207381 / 26394 (caution) stated an EU-only advisory as the reason
    for a caution set by DOSE_OVER_UL_CRITICAL."""
    assert stated_safety_signal(signals) == expected
