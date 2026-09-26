"""B0 and the Safety/Hygiene base read the safety gate's policy, not a second one.

The gate (scoring_v4.gate_safety.evaluate_safety_gate) decides which banned_recalled
signals count: regional rules become B0_REGIONAL_ADVISORY, role-retired rules are
ignored, excipient warnings stay warnings. The B0 penalty used to charge every
exact/alias contaminant row with no policy at all, and the Safety/Hygiene base used
its own filter over enricher signals only. On the full corpus that meant:

- 328464 (Life Extension Ginkgo): EU-only CONTAM_GINKGOLIC_ACID -> gate regional
  advisory and SAFE, but B0 -5.
- 19598 (GNC Trisynex): FD&C Red No. 3 in the "Artificial Colors" forms -> gate
  CAUTION (B0_HIGH_RISK_SUBSTANCE), but no B0 and Safety/Hygiene 9/10.
- 315305 (GNC Yohimbe 451): one yohimbe rule on two label rows -> B0 charged twice.

Both consumers now read SafetyResult.ingredient_concerns (the signals that survived
the gate's policy) through one scoped gate evaluation.
"""

from __future__ import annotations

import copy
import json
import logging
import sys
from pathlib import Path

import pytest

SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

logging.disable(logging.CRITICAL)

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def pipeline():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3

    normalizer, enricher = EnhancedDSLDNormalizer(), SupplementEnricherV3()

    def enrich(dsld_id: str) -> dict:
        raw = json.loads((FIXTURES / f"b0_policy_{dsld_id}_raw.json").read_text())
        enriched, _issues = enricher.enrich_product(normalizer.normalize_product(raw))
        return enriched

    return {dsld_id: enrich(dsld_id) for dsld_id in ("328464", "19598", "315305")}


def _score(enriched: dict) -> dict:
    from score_supplements_v4 import score_product_v4

    return score_product_v4(copy.deepcopy(enriched))


def _b0(scored: dict) -> float:
    formulation = scored["v4_breakdown"]["module"]["dimensions"]["formulation"]
    return formulation["penalties"]["B0_moderate_watchlist"]


def test_regional_rule_costs_no_b0(pipeline) -> None:
    scored = _score(pipeline["328464"])
    assert "B0_REGIONAL_ADVISORY" in scored["v4_breakdown"]["safety_gate"]["safety_signals"]
    assert _b0(scored) == 0
    assert scored["quality_pillars_v4"]["safety_hygiene"]["score"] == 10


def test_gate_concern_charges_b0_and_the_safety_base(pipeline) -> None:
    scored = _score(pipeline["19598"])
    assert scored["v4_verdict"] == "CAUTION"
    assert "B0_HIGH_RISK_SUBSTANCE" in scored["v4_breakdown"]["safety_gate"]["safety_signals"]
    assert _b0(scored) < 0
    pillar = scored["quality_pillars_v4"]["safety_hygiene"]
    assert pillar["score"] == 0, pillar
    assert "high-risk ingredient" in pillar["reason"], pillar["reason"]


def test_one_rule_on_two_rows_is_one_charge(pipeline) -> None:
    from scoring_v4.modules.generic_formulation import B0_HIGH_RISK_PENALTY

    enriched = pipeline["315305"]
    substances = enriched["contaminant_data"]["banned_substances"]["substances"]
    assert [s["banned_id"] for s in substances].count("RISK_YOHIMBE") == 2
    assert _b0(_score(enriched)) == -B0_HIGH_RISK_PENALTY


def test_routed_module_reuses_the_gate_evaluation(pipeline, monkeypatch) -> None:
    """score_product_v4 evaluates the gate once; B0 and the Safety/Hygiene base
    read that scoped result instead of re-interpreting the product."""
    import scoring_v4.gate_safety as gate

    calls = []
    original = gate.evaluate_safety_gate

    def counting(product, **kwargs):
        calls.append(product.get("dsld_id"))
        return original(product, **kwargs)

    monkeypatch.setattr(gate, "evaluate_safety_gate", counting)
    scored = _score(pipeline["19598"])
    assert _b0(scored) < 0
    assert calls == []
