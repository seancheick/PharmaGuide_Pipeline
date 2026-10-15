"""V4.1 Step 4: one numerical owner for formula checks (approved option
R:reviewed_sixth_existing_B7, transforms mirrors/b0_sixth/additive_sixth/
source_guards).

- Additive and sugar findings are charged once, by the formula-checks (sixth)
  pillar, within its shared 10-point budget; Formulation no longer subtracts them.
- A confirmed high-risk or watchlist ingredient zeroes that pillar's base; it is
  no longer also a Formulation penalty. An unconfirmed match keeps its warning
  but is not a numerical finding.
"""
import sys
from pathlib import Path
from types import SimpleNamespace

SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from scoring_v4 import quality_score as qs  # noqa: E402
from scoring_v4.modules import generic_formulation as gf  # noqa: E402
from scoring_v4.modules import safety_hygiene as sh  # noqa: E402


def _additive_product(*severities, sugar_level=None):
    product = {"contaminant_data": {"harmful_additives": {"additives": [
        {"additive_id": f"ADD_TEST_{i}", "severity_level": sev, "source_section": "inactive"}
        for i, sev in enumerate(severities)]}}}
    if sugar_level:
        product["dietary_sensitivity_data"] = {"sugar": {
            "level": sugar_level, "contains_sugar": True, "has_added_sugar": True,
            "sugar_sources": ["cane sugar"]}}
    return product


def _bd(checks, details=(), base=4.0):
    return {
        "safety_hygiene_base": {"score": base, "max": 4.0},
        "dimensions": {"formulation": {"penalties": {}, "metadata": {
            "formula_checks": dict(checks), "inactive_penalty_details": list(details)}}},
    }


def test_shared_formulation_detail_no_longer_charges_formulation():
    detail = gf.shared_formulation_penalty_detail(_additive_product("moderate", "high", sugar_level="high"))
    assert not any(key.startswith(("B0_", "B1_")) for key in detail["penalties"])
    checks = detail["metadata"]["formula_checks"]
    assert checks == {"B1_harmful_additives": 5.0, "B1_dietary_sugar": 4.0}


def test_formula_checks_are_charged_once_in_the_sixth_pillar_up_to_ten():
    cfg = qs._config()
    pillar = qs._pillar_safety_hygiene(_bd({"B1_harmful_additives": 6.0, "B1_dietary_sugar": 3.0}), 10.0, cfg)
    assert pillar["score"] == 1.0
    assert pillar["components"]["additive_or_sweetener_penalty"] == 9.0
    capped = qs._pillar_safety_hygiene(_bd({"B1_harmful_additives": 9.0, "B1_dietary_sugar": 4.0}), 10.0, cfg)
    assert capped["score"] == 0.0
    assert capped["components"]["additive_or_sweetener_penalty"] == 10.0


def test_low_concern_additives_are_charged_but_worded_as_quality_not_safety():
    cfg = qs._config()
    details = [{"penalty_tier": "low", "penalty_applied": 0.5, "name": "Maltodextrin"}]
    pillar = qs._pillar_safety_hygiene(_bd({"B1_harmful_additives": 0.5}, details), 10.0, cfg)
    assert pillar["score"] == 9.5
    assert not pillar["reason"].startswith("Safety concern")
    assert pillar["reason"] == ("Formula check: it contains low-concern additives or "
                                "sweeteners that lower formula quality.")


def test_moderate_additive_keeps_its_concern_wording():
    cfg = qs._config()
    details = [{"penalty_tier": "moderate", "penalty_applied": 2.0, "name": "Red 40"}]
    pillar = qs._pillar_safety_hygiene(_bd({"B1_harmful_additives": 2.0}, details), 10.0, cfg)
    assert pillar["score"] == 8.0
    assert pillar["reason"] == "Safety concern: it contains additive or sweetener/form-factor concerns."


def _gate(*signals):
    return SimpleNamespace(ingredient_concerns=[
        SimpleNamespace(status=status, match_resolution=resolution, evidence_text=name, severity=None)
        for status, resolution, name in signals])


def test_unconfirmed_watchlist_match_does_not_zero_the_base(monkeypatch):
    monkeypatch.setattr(sh, "resolve_safety_gate", lambda product: _gate(("watchlist", "likely", "Carob color")))
    result = sh.score_safety_hygiene_base({"dsld_id": "1", "product_name": "x"})
    assert result.score == 4.0
    assert not result.failed_components


def test_confirmed_high_risk_match_zeroes_the_base(monkeypatch):
    monkeypatch.setattr(sh, "resolve_safety_gate", lambda product: _gate(("high_risk", "confirmed", "Yohimbe")))
    result = sh.score_safety_hygiene_base({"dsld_id": "1", "product_name": "x"})
    assert result.score == 0.0
    assert result.metadata["drivers"] == [{"status": "high_risk", "name": "Yohimbe"}]
