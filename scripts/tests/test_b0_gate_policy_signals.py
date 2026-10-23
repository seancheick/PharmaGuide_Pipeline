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

Both consumers read SafetyResult.ingredient_concerns (the signals that survived
the gate's policy) through one scoped gate evaluation. Since V4.1 Step 4 the
Safety/Hygiene base is the only numerical owner: Formulation has no B0.
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


def _base(scored: dict) -> dict:
    """The formula-checks pillar's safety base: the one owner of a confirmed
    high-risk or watchlist finding since V4.1 Step 4 (no Formulation B0)."""
    module = scored["v4_breakdown"]["module"]
    assert "B0_moderate_watchlist" not in module["dimensions"]["formulation"]["penalties"]
    return module["safety_hygiene_base"]


def test_regional_rule_does_not_zero_the_safety_base(pipeline) -> None:
    scored = _score(pipeline["328464"])
    assert "B0_REGIONAL_ADVISORY" in scored["v4_breakdown"]["safety_gate"]["safety_signals"]
    assert _base(scored)["score"] == 4.0
    assert scored["quality_pillars_v4"]["safety_hygiene"]["components"]["clean_base"] == 10


def test_gate_concern_zeroes_the_safety_base_once(pipeline) -> None:
    scored = _score(pipeline["19598"])
    # The reviewed constituent expansion now exposes missing individual
    # amounts, so Quality is held. Safety remains assessed independently.
    assert scored["quality_score_status"] == "not_scored"
    assert scored["quality_pillars_v4"] is None
    assert "B0_HIGH_RISK_SUBSTANCE" in scored["v4_breakdown"]["safety_gate"]["safety_signals"]
    from scoring_v4.modules.safety_hygiene import score_safety_hygiene_base
    base = score_safety_hygiene_base(pipeline["19598"])
    assert base.score == 0
    assert base.metadata["hard_cleanliness_failure"] is True
    from scoring_v4.scored_artifact import build_scored_artifact
    artifact = build_scored_artifact(pipeline["19598"])
    assert artifact["product_safety_status"] == "caution"
    assert artifact["safety_verdict"] == "CAUTION"


def test_one_rule_on_two_rows_is_one_charge(pipeline) -> None:
    enriched = pipeline["315305"]
    substances = enriched["contaminant_data"]["banned_substances"]["substances"]
    assert [s["banned_id"] for s in substances].count("RISK_YOHIMBE") == 2
    base = _base(_score(enriched))
    assert base["score"] == 0.0
    assert [d["status"] for d in base["metadata"]["drivers"]] == ["high_risk"]


def test_routed_module_reuses_the_gate_evaluation(pipeline, monkeypatch) -> None:
    """score_product_v4 evaluates the gate once; the Safety/Hygiene base reads
    that scoped result instead of re-interpreting the product."""
    import scoring_v4.gate_safety as gate

    calls = []
    original = gate.evaluate_safety_gate

    def counting(product, **kwargs):
        calls.append(product.get("dsld_id"))
        return original(product, **kwargs)

    monkeypatch.setattr(gate, "evaluate_safety_gate", counting)
    scored = _score(pipeline["315305"])
    assert _base(scored)["score"] == 0.0
    assert calls == []
