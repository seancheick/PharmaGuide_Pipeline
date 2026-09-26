"""Omega Evidence contracts: directed exposure, purpose scope and stable output."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))


def _epa_dha_product(
    *,
    name: str = "Test Omega",
    epa: float = 600,
    dha: float = 300,
    daily_servings: tuple = (1.0, 1.0),
    evidence_data: dict | None = None,
) -> dict:
    """Build a minimal omega product."""
    product = {
        "status": "active",
        "form_factor": "softgel",
        "product_name": name,
        "supplement_type": {"type": "specialty"},
        "servingSizes": [{"minDailyServings": daily_servings[0],
                          "maxDailyServings": daily_servings[1]}],
        "ingredient_quality_data": {"ingredients_scorable": [
            {"name": "EPA", "canonical_id": "epa", "quantity": epa, "unit": "mg"},
            {"name": "DHA", "canonical_id": "dha", "quantity": dha, "unit": "mg"},
        ]},
    }
    if evidence_data is not None:
        product["evidence_data"] = evidence_data
    return product


# --- Component contract --------------------------------------------------


def test_returns_normalized_payload_shape() -> None:
    from scoring_v4.modules.omega_evidence import score_evidence

    payload = score_evidence(_epa_dha_product())
    for key in ("score", "max", "components", "penalties", "metadata"):
        assert key in payload
    assert payload["max"] == 20.0
    assert payload["metadata"]["phase"] == "P1.6.3_omega_evidence"


def test_empty_product_scores_zero() -> None:
    from scoring_v4.modules.omega_evidence import score_evidence

    payload = score_evidence({})
    assert payload["score"] == 0.0


def test_none_input_scores_zero_safely() -> None:
    from scoring_v4.modules.omega_evidence import score_evidence

    payload = score_evidence(None)
    assert payload["score"] == 0.0


# --- Indication relevance bonus -----------------------------------------


def test_one_to_two_grams_graduates_reviewed_record_applicability() -> None:
    """Exposure gates which reviewed record applies; it is not a Dose bonus."""
    from scoring_v4.modules.omega_evidence import score_evidence

    below = score_evidence(_epa_dha_product(epa=599, dha=400))   # 999 mg/day
    at = score_evidence(_epa_dha_product(epa=700, dha=400))      # 1100 mg/day
    assert "indication_relevance" not in at["components"]
    assert at["metadata"]["indication_relevance_awarded"] is False
    assert at["score"] > below["score"]


def test_evidence_applicability_is_monotonic_across_reviewed_exposure_range() -> None:
    from scoring_v4.modules.omega_evidence import score_evidence

    scores = [score_evidence(_epa_dha_product(epa=mg / 2, dha=mg / 2))["score"]
              for mg in (600, 1000, 1500, 2400, 4500)]
    assert scores == sorted(scores)
    assert scores[0] == 10.4
    assert scores[-1] == 20.0


def test_indication_relevance_not_awarded_below_threshold() -> None:
    """<1000 mg/day → 0 indication relevance."""
    from scoring_v4.modules.omega_evidence import score_evidence

    product = _epa_dha_product(epa=500, dha=300)  # 800 mg/day
    payload = score_evidence(product)
    assert "indication_relevance" not in payload["components"]
    assert payload["metadata"]["indication_relevance_awarded"] is False


def test_per_day_arithmetic_is_still_recorded() -> None:
    """Per-day EPA+DHA stays in the metadata (Dose scores it; Evidence reads it
    only for the prenatal indication)."""
    from scoring_v4.modules.omega_evidence import score_evidence

    product = _epa_dha_product(epa=300, dha=200, daily_servings=(2.0, 2.0))
    payload = score_evidence(product)
    assert payload["metadata"]["per_day_epa_dha_mg"] == 1000.0
    assert "indication_relevance" not in payload["components"]


def test_pure_dha_without_a_prenatal_indication_earns_no_bonus() -> None:
    """A high-dose algal DHA product is a Dose fact, not evidence applicability."""
    from scoring_v4.modules.omega_evidence import score_evidence

    product = {
        "servingSizes": [{"minDailyServings": 1, "maxDailyServings": 1}],
        "ingredient_quality_data": {"ingredients_scorable": [
            {"name": "DHA", "canonical_id": "dha", "quantity": 1200, "unit": "mg"},
        ]},
    }
    payload = score_evidence(product)
    assert "indication_relevance" not in payload["components"]


def test_indication_relevance_awarded_for_prenatal_dha_target() -> None:
    """Prenatal DHA products should use the prenatal DHA indication target,
    not only the AHA cardiovascular 1000 mg EPA+DHA threshold.

    Locks Thorne Prenatal DHA's shape: 650 mg DHA + 200 mg EPA is below the
    CV threshold, but is clearly above the prenatal DHA target already used by
    omega_dose.
    """
    from scoring_v4.modules.omega_evidence import score_evidence

    product = _epa_dha_product(name="Prenatal DHA 650 mg", epa=200, dha=650)
    payload = score_evidence(product)

    assert payload["components"]["clinical_evidence"] == 11.1
    assert payload["metadata"]["indication_relevance_awarded"] is True
    assert payload["metadata"]["indication_relevance_reason"] == "prenatal_dha_intake_authority"


# --- Clinical evidence (generic pipeline delegation) --------------------


def test_reviewed_omega_standard_owns_the_full_evidence_pillar() -> None:
    from scoring_v4.modules.omega_evidence import score_evidence

    payload = score_evidence(_epa_dha_product())
    assert payload["metadata"]["clinical_sub_cap"] == 20.0


def test_generic_addin_evidence_cannot_own_omega_evidence(monkeypatch) -> None:
    import scoring_v4.modules.omega_evidence as omega_evidence

    monkeypatch.setattr(
        omega_evidence,
        "score_generic_evidence",
        lambda _product: {
            "score": 15.0,
            "components": {},
            "penalties": {},
            "metadata": {},
        },
    )

    payload = omega_evidence.score_evidence(_epa_dha_product(epa=1600, dha=400))
    assert payload["components"] == {"clinical_evidence": 20.0}
    assert payload["score"] == 20.0


def test_reviewed_record_is_resolved_without_enrichment_match() -> None:
    from scoring_v4.modules.omega_evidence import score_evidence

    product = _epa_dha_product(epa=700, dha=400)  # 1100 mg/day, no evidence
    payload = score_evidence(product)
    assert payload["components"]["clinical_evidence"] == 11.36
    assert "indication_relevance" not in payload["components"]
    assert payload["metadata"]["generic_evidence_raw_score"] == 0.0
    assert payload["metadata"]["disclosed_epa_dha_clinical_floor_awarded"] is False


def test_reviewed_weak_record_applies_below_efsa_dose_zone() -> None:
    from scoring_v4.modules.omega_evidence import score_evidence

    product = _epa_dha_product(epa=300, dha=200)  # 500 mg/day, within reviewed range
    payload = score_evidence(product)

    assert payload["components"]["clinical_evidence"] == 10.4
    assert "indication_relevance" not in payload["components"]
    assert payload["metadata"]["disclosed_epa_dha_clinical_floor_awarded"] is False


def test_omega3_detail_is_not_a_scoring_input() -> None:
    """EPA/DHA comes from the label rows only. ``omega3_detail`` was a retired
    v3 blob block (never on an enriched product, always empty in the blob), so
    it must not be able to create EPA/DHA credit."""
    from scoring_v4.modules.omega_evidence import score_evidence

    product = {
        "product_name": "Final Blob Fish Oil",
        "omega3_detail": {
            "epa_mg_per_unit": 690.0,
            "dha_mg_per_unit": 310.0,
            "per_day_mid_mg": 1000.0,
        },
        "serving_info": {
            "min_servings_per_day": 1,
            "max_servings_per_day": 1,
        },
    }

    payload = score_evidence(product)

    assert not payload["metadata"].get("per_day_epa_dha_mg")
    assert not payload["components"].get("clinical_evidence")


# --- Score ceiling ------------------------------------------------------


def test_max_evidence_score_is_20() -> None:
    """Cap defense: even synthetic max-credit input cannot exceed 20."""
    from scoring_v4.modules.omega_evidence import score_evidence, CAP_EVIDENCE

    assert CAP_EVIDENCE == 20.0


def test_total_score_clamps_to_20() -> None:
    """If clinical+indication ever exceeds 20, the clamp triggers."""
    from scoring_v4.modules.omega_evidence import score_evidence

    product = _epa_dha_product(epa=700, dha=400)
    payload = score_evidence(product)
    assert payload["score"] <= 20.0


# --- Real canary integration --------------------------------------------


_CANARY_EVIDENCE_IDS = {"327776", "326270", "288740", "273630", "239592", "184654"}
_canary_cache = None


def _load_canaries(ids):
    global _canary_cache
    if _canary_cache is not None:
        return {did: _canary_cache[did] for did in ids if did in _canary_cache}
    root = SCRIPTS_ROOT / "products"
    if not root.exists():
        _canary_cache = {}
        pytest.skip("no enriched products dir")
    found = {}
    target = _CANARY_EVIDENCE_IDS
    for path in root.glob("output_*_enriched/enriched/enriched_cleaned_batch_*.json"):
        try:
            data = json.loads(path.read_text())
        except Exception:
            continue
        items = data if isinstance(data, list) else (data.get("products") or data.get("items") or [])
        for item in items:
            if not isinstance(item, dict):
                continue
            did = str(item.get("dsld_id") or item.get("id") or "")
            if did in target:
                found[did] = item
        if len(found) == len(target):
            break
    _canary_cache = found
    return {did: _canary_cache[did] for did in ids if did in _canary_cache}


# Only a prenatal DHA indication earns the bonus since 2026-09-18.
@pytest.mark.parametrize("dsld_id,expected_indication", [
    ("327776", False),    # Sports Research: 1000 mg/day
    ("326270", False),    # Sports Research alt
    ("288740", False),    # Nordic: 1100 mg/day
    ("273630", False),    # GoL Advanced Omega: 1160 mg/day
    ("239592", False),   # CVS Krill: 74 mg/day
    ("184654", False),   # Pure Encap Krill-Plex
])
def test_canary_indication_relevance(dsld_id, expected_indication):
    """Real-catalog indication relevance: high-dose canaries qualify,
    krill low-dose do not."""
    from scoring_v4.modules.omega_evidence import score_evidence

    canaries = _load_canaries({dsld_id})
    if dsld_id not in canaries:
        pytest.skip(f"canary {dsld_id} not in catalog")

    payload = score_evidence(canaries[dsld_id])
    assert payload["metadata"]["indication_relevance_awarded"] == expected_indication


@pytest.mark.parametrize("dsld_id,min_score,max_score", [
    ("327776", 5.0, 20.0),    # Sports Research
    ("288740", 5.0, 20.0),    # Nordic
    ("273630", 5.0, 20.0),    # GoL Advanced Omega
    ("239592", 0.0, 15.0),    # CVS Krill: clinical only
    ("184654", 0.0, 15.0),    # Pure Encap Krill: clinical only
])
def test_canary_evidence_score_in_range(dsld_id, min_score, max_score):
    """Real-catalog Evidence scores fall within rubric-expected ranges.
    Loose ranges because clinical pipeline output depends on
    evidence_data.clinical_matches which can drift slightly with
    enrichment improvements."""
    from scoring_v4.modules.omega_evidence import score_evidence

    canaries = _load_canaries({dsld_id})
    if dsld_id not in canaries:
        pytest.skip(f"canary {dsld_id} not in catalog")

    payload = score_evidence(canaries[dsld_id])
    assert min_score <= payload["score"] <= max_score, (
        f"canary {dsld_id} Evidence score {payload['score']} not in "
        f"[{min_score}, {max_score}]"
    )


# --- Orchestrator roll-forward ------------------------------------------


def test_omega_orchestrator_phase_rolls_forward_to_p163() -> None:
    from scoring_v4.modules.omega import score_omega

    breakdown = score_omega(_epa_dha_product()).to_breakdown()
    assert breakdown["phase"].startswith("P1.6.")


def test_omega_evidence_dimension_score_populated_in_breakdown() -> None:
    """After P1.6.3 lands, the evidence dimension carries a numeric score
    in score_omega's breakdown."""
    from scoring_v4.modules.omega import score_omega

    breakdown = score_omega(_epa_dha_product(epa=700, dha=400)).to_breakdown()
    # Even without evidence_data, indication relevance fires at 1100 mg/day.
    assert breakdown["dimensions"]["evidence"]["score"] is not None


# --- Architecture lock --------------------------------------------------


def test_omega_evidence_does_not_import_v3_scorer() -> None:
    import ast
    import scoring_v4.modules.omega_evidence as oe

    tree = ast.parse(Path(oe.__file__).read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module_name = node.module or ""
            assert not module_name.startswith("score_supplements"), (
                f"v4→v3 import: from {module_name}"
            )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith("score_supplements"), (
                    f"v4→v3 import: import {alias.name}"
                )


# --- Config-as-truth ----------------------------------------------------


def test_evidence_weights_match_rubric_config() -> None:
    from scoring_v4.modules.omega_evidence import _load_rubric

    rubric = _load_rubric()
    ev = rubric["evidence"]
    assert ev["cap"] == 20
    assert ev["omega_canonicals"] == ["epa", "dha", "epa_dha"]
    assert ev["registry_record_id"] == "INGR_OMEGA3"
    assert ev["retired_fields"]["disclosed_epa_dha_clinical_floor"]["score"] == 0
    assert ev["retired_fields"]["prenatal_indication_bonus"]["score"] == 0
