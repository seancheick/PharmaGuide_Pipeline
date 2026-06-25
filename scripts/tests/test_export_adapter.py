"""Unit tests for the v4 → export adapter (`scoring_v4.export_adapter`).

These pin the MAPPING CONTRACT only: the v4 scorer is monkeypatched with canned
outputs so the test is independent of v4 scoring internals. The full scorer is
exercised by the v4 module/quality tests and the integration build tests.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from scoring_v4 import export_adapter  # noqa: E402
from scoring_v4.export_adapter import overlay_v4_scored  # noqa: E402


def _canned_v4(
    *,
    status="scored",
    quality_100=87.5,
    verdict="SAFE",
    tier="Strong",
    safety_verdict=None,
    blocking_reason=None,
    safety_signals=None,
    suppressed_reason=None,
):
    """A minimal but structurally-faithful v4 result."""
    return {
        "raw_score_v4_100": 87.5,
        "v4_module": "generic",
        "v4_verdict": verdict,
        "v4_confidence": "high",
        "v4_anchored": False,
        "v4_display_100": 92.0,  # experimental — must be IGNORED by the adapter
        "v4_breakdown": {
            "provenance": {
                "scoring_engine_version": "4.0.0",
                "classification_schema_version": "5.3.0",
                "config_versions": {"quality_score": "1.0.0", "gate_safety": "2.1.0"},
                "module_route": "generic",
                "mode": "production",
            },
            "safety_gate": {
                "verdict": safety_verdict,
                "blocking_reason": blocking_reason,
                "matched_substance": None,
                "safety_signals": safety_signals or [],
                "needs_review": False,
                "short_circuits_scoring": verdict in ("BLOCKED", "UNSAFE"),
                "clean_label_hits": [],
            },
            "completeness_gate": {
                "module": "generic",
                "is_live_eligible": status != "not_scored",
                "verdict": None if status != "not_scored" else "NOT_SCORED",
            },
            "module": {"dimensions": {"formulation": {"score": 20}}},
        },
        "raw_score_v4_100": 87.5,
        "quality_score_v4_100": quality_100,
        "quality_pillars_v4": (
            {"formulation": {"score": 18.0, "max": 20, "reason": "ok"}} if status == "scored" else None
        ),
        "quality_tier": tier,
        "quality_score_status": status,
        "quality_score_suppressed_reason": suppressed_reason,
        "clean_label_flags_v4": None,
        "quality_score_version": "1.0.0-test",
    }


def _v3_scored():
    """A v3 scored blob with the scaffolding the export consumes."""
    return {
        "score_80": 64.0,
        "score_100_equivalent": 80.0,
        "verdict": "SAFE",
        "safety_verdict": "SAFE",
        "grade": "B",
        "blocking_reason": None,
        "section_scores": {
            "A_ingredient_quality": {"score": 20.0, "max": 25},
            "B_safety_purity": {"score": 28.0, "max": 30},
            "C_evidence_research": {"score": 12.0, "max": 20},
            "D_brand_trust": {"score": 4.0, "max": 5},
        },
        "badges": ["third_party_tested"],
        "flags": ["proprietary_blend"],
        "category_percentile": {"available": True, "percentile_rank": 71.0},
        "strict_scoring_contract": {"passed": True},
        "scoring_metadata": {"scoring_version": "3.4.0"},
    }


def _patch(monkeypatch, v4_result):
    monkeypatch.setattr(export_adapter, "score_product_v4", lambda enriched: v4_result)


def test_scored_overlays_v4_headline(monkeypatch):
    _patch(monkeypatch, _canned_v4(status="scored", quality_100=87.5, verdict="SAFE", tier="Strong"))
    out = overlay_v4_scored({"dsld_id": "1"}, _v3_scored())

    assert out["verdict"] == "SAFE"
    assert out["safety_verdict"] == "SAFE"  # safety_gate.verdict None → SAFE
    assert out["score_100_equivalent"] == 87.5
    assert out["display_100"] == "88/100"
    assert out["grade"] == "Strong"  # legacy grade column now carries the v4 tier
    assert out["_score_model_version"] == "v4"
    assert out["_v4_quality_score_100"] == 87.5
    assert out["_v4_quality_status"] == "scored"
    assert out["_v4_quality_tier"] == "Strong"
    assert out["_v4_raw_score_100"] == 87.5
    assert out["_v4_module"] == "generic"
    assert out["_v4_scoring_engine_version"] == "4.0.0"
    assert out["_v4_classification_schema_version"] == "5.3.0"
    # config fingerprint is a stable JSON string of config_versions
    assert json.loads(out["_v4_config_fingerprint"])["quality_score"] == "1.0.0"


def test_module_breakdown_is_stashed_for_tradeoffs(monkeypatch):
    """derive_v4_tradeoffs sources the B-code penalties from
    v4_breakdown.module.dimensions.*.penalties — the overlay must stash that
    sub-tree under _v4_module_breakdown (the module *name* lives in _v4_module)."""
    _patch(monkeypatch, _canned_v4(status="scored"))
    out = overlay_v4_scored({"dsld_id": "1"}, _v3_scored())
    assert out["_v4_module_breakdown"] == {"dimensions": {"formulation": {"score": 20}}}


def test_suppressed_safety_nulls_score_but_is_not_quarantined(monkeypatch):
    _patch(
        monkeypatch,
        _canned_v4(
            status="suppressed_safety",
            quality_100=None,
            verdict="BLOCKED",
            tier=None,
            safety_verdict="BLOCKED",
            blocking_reason="banned_ingredient",
            suppressed_reason="banned_ingredient",
        ),
    )
    out = overlay_v4_scored({"dsld_id": "2"}, _v3_scored())

    assert out["verdict"] == "BLOCKED"
    assert out["safety_verdict"] == "BLOCKED"
    assert out["score_100_equivalent"] is None
    assert out["display_100"] == "N/A"
    assert out["blocking_reason"] == "banned_ingredient"
    assert out["_v4_quality_status"] == "suppressed_safety"
    assert out["_v4_quality_score_100"] is None
    assert out["_v4_suppressed_reason"] == "banned_ingredient"


def test_not_scored_sets_verdict_and_nulls(monkeypatch):
    _patch(
        monkeypatch,
        _canned_v4(status="not_scored", quality_100=None, verdict="NOT_SCORED", tier=None),
    )
    out = overlay_v4_scored({"dsld_id": "3"}, _v3_scored())

    assert out["verdict"] == "NOT_SCORED"
    assert out["score_100_equivalent"] is None
    assert out["display_100"] == "N/A"
    assert out["_v4_quality_status"] == "not_scored"


def test_caution_keeps_score(monkeypatch):
    _patch(
        monkeypatch,
        _canned_v4(status="scored", quality_100=72.0, verdict="CAUTION", tier="Acceptable",
                   safety_verdict="CAUTION", safety_signals=["B0_HIGH_RISK_SUBSTANCE"]),
    )
    out = overlay_v4_scored({"dsld_id": "4"}, _v3_scored())

    assert out["verdict"] == "CAUTION"
    assert out["safety_verdict"] == "CAUTION"
    assert out["score_100_equivalent"] == 72.0
    assert out["_v4_quality_status"] == "scored"
    assert out["_v4_safety_signal_reason"] == "B0_HIGH_RISK_SUBSTANCE"


def test_inputs_are_never_mutated(monkeypatch):
    _patch(monkeypatch, _canned_v4())
    enriched = {"dsld_id": "5", "activeIngredients": [{"name": "x"}]}
    scored = _v3_scored()
    enriched_before = copy.deepcopy(enriched)
    scored_before = copy.deepcopy(scored)

    overlay_v4_scored(enriched, scored)

    assert enriched == enriched_before
    assert scored == scored_before


def test_v3_scaffolding_is_preserved(monkeypatch):
    _patch(monkeypatch, _canned_v4())
    v3 = _v3_scored()
    out = overlay_v4_scored({"dsld_id": "6"}, v3)

    # The export still reads these off the scored blob; they must survive intact.
    assert out["section_scores"] == v3["section_scores"]
    assert out["badges"] == v3["badges"]
    assert out["flags"] == v3["flags"]
    assert out["category_percentile"] == v3["category_percentile"]
    assert out["strict_scoring_contract"] == v3["strict_scoring_contract"]
    assert out["scoring_metadata"] == v3["scoring_metadata"]
    # score_80 (v3 scorer field) is left untouched for build_decision_highlights.
    assert out["score_80"] == 64.0


def test_detail_blob_provenance_keys_present(monkeypatch):
    _patch(monkeypatch, _canned_v4())
    out = overlay_v4_scored({"dsld_id": "7"}, _v3_scored())

    assert out["_v4_safety_gate"] is not None
    assert out["_v4_completeness_gate"] is not None
    assert out["_v4_provenance"]["mode"] == "production"
    assert out["_v4_pillars"] is not None
