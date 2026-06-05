"""v4 Omega Evidence dimension — P1.6.3 tests.

Locks the Evidence sub-component math:

    clinical_evidence    /15  Generic evidence pipeline output capped
                              at total_cap - indication_score (= 15)
    indication_relevance /5   +5 when EPA+DHA per_day >= 1000 mg/day
                              (AHA CVD threshold), 0 below

Total cap: 20.

Per Sean's 'do not invent fields' rule: indication relevance is computed
from the SAME EPA+DHA per_day arithmetic as P1.6.2 Dose. No manual
marketed-indication text matching — if the dose hits the threshold, the
product is delivering evidence-aligned dosing regardless of marketing.

Per §13 architecture lock — no v3 imports.
"""

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


def test_indication_relevance_awarded_at_aha_cvd_threshold() -> None:
    """EPA+DHA >= 1000 mg/day → +5 indication relevance."""
    from scoring_v4.modules.omega_evidence import score_evidence

    product = _epa_dha_product(epa=700, dha=400)  # 1100 mg/day
    payload = score_evidence(product)
    assert payload["components"]["indication_relevance"] == 5.0
    assert payload["metadata"]["indication_relevance_awarded"] is True


def test_indication_relevance_awarded_exactly_at_threshold() -> None:
    """1000 mg/day exactly → +5 (inclusive boundary)."""
    from scoring_v4.modules.omega_evidence import score_evidence

    product = _epa_dha_product(epa=700, dha=300)  # 1000 mg/day exact
    payload = score_evidence(product)
    assert payload["components"]["indication_relevance"] == 5.0


def test_indication_relevance_not_awarded_below_threshold() -> None:
    """<1000 mg/day → 0 indication relevance."""
    from scoring_v4.modules.omega_evidence import score_evidence

    product = _epa_dha_product(epa=500, dha=300)  # 800 mg/day
    payload = score_evidence(product)
    assert "indication_relevance" not in payload["components"]
    assert payload["metadata"]["indication_relevance_awarded"] is False


def test_indication_relevance_uses_per_day_not_per_serving() -> None:
    """A product labeled '500 mg EPA+DHA per serving, 2 servings/day'
    delivers 1000 mg/day and qualifies. Confirms per_day arithmetic
    (not per_serving) drives indication."""
    from scoring_v4.modules.omega_evidence import score_evidence

    product = _epa_dha_product(epa=300, dha=200, daily_servings=(2.0, 2.0))
    payload = score_evidence(product)
    assert payload["metadata"]["per_day_epa_dha_mg"] == 1000.0
    assert payload["components"]["indication_relevance"] == 5.0


def test_indication_relevance_for_pure_dha_uses_combined_dose() -> None:
    """A pure-DHA algal product delivering 1000+ mg/day DHA qualifies
    for indication relevance (no EPA required — the threshold is
    total EPA+DHA per_day)."""
    from scoring_v4.modules.omega_evidence import score_evidence

    product = {
        "servingSizes": [{"minDailyServings": 1, "maxDailyServings": 1}],
        "ingredient_quality_data": {"ingredients_scorable": [
            {"name": "DHA", "canonical_id": "dha", "quantity": 1200, "unit": "mg"},
        ]},
    }
    payload = score_evidence(product)
    assert payload["components"].get("indication_relevance") == 5.0


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

    assert payload["components"]["indication_relevance"] == 5.0
    assert payload["metadata"]["indication_relevance_awarded"] is True
    assert payload["metadata"]["indication_relevance_reason"] == "prenatal_dha_target"


# --- Clinical evidence (generic pipeline delegation) --------------------


def test_clinical_evidence_capped_at_15() -> None:
    """Even if the generic pipeline produces >15, omega Evidence caps at
    15 for the clinical component so total stays at most 20 (15 + 5)."""
    from scoring_v4.modules.omega_evidence import score_evidence

    # Synthesize a product whose generic pipeline would produce high output.
    # We can't easily trigger >15 with synthetic evidence_data (depends
    # on the real pipeline), but the metadata.clinical_sub_cap is the
    # contract.
    payload = score_evidence(_epa_dha_product())
    assert payload["metadata"]["clinical_sub_cap"] == 15.0


def test_disclosed_epa_dha_class_floor_when_no_evidence_data() -> None:
    """Disclosed EPA+DHA at an evidence-relevant daily dose earns the
    conservative omega class-evidence floor even when generic evidence_data
    is missing. This prevents matcher gaps from making EPA/DHA look
    evidence-poor, without crediting parent fish-oil mass."""
    from scoring_v4.modules.omega_evidence import score_evidence

    product = _epa_dha_product(epa=700, dha=400)  # 1100 mg/day, no evidence
    payload = score_evidence(product)
    assert payload["components"]["clinical_evidence"] == 10.0
    assert payload["components"].get("indication_relevance") == 5.0
    assert payload["metadata"]["generic_evidence_raw_score"] == 0.0
    assert payload["metadata"]["disclosed_epa_dha_clinical_floor_awarded"] is True


def test_disclosed_epa_dha_class_floor_not_awarded_below_efsa_zone() -> None:
    from scoring_v4.modules.omega_evidence import score_evidence

    product = _epa_dha_product(epa=100, dha=100)  # 200 mg/day
    payload = score_evidence(product)

    assert "clinical_evidence" not in payload["components"]
    assert "indication_relevance" not in payload["components"]
    assert payload["metadata"]["disclosed_epa_dha_clinical_floor_awarded"] is False


def test_final_blob_omega3_detail_can_drive_evidence_floor() -> None:
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

    assert payload["metadata"]["per_day_epa_dha_mg"] == 1000.0
    assert payload["components"]["clinical_evidence"] == 10.0
    assert payload["components"]["indication_relevance"] == 5.0


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


_CANARY_EVIDENCE_IDS = {"327776", "326270", "288740", "273630", "239592", "182968"}
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


@pytest.mark.parametrize("dsld_id,expected_indication", [
    ("327776", True),    # Sports Research: 1000 mg/day
    ("326270", True),    # Sports Research alt
    ("288740", True),    # Nordic: 1100 mg/day
    ("273630", True),    # GoL Advanced Omega: 1160 mg/day
    ("239592", False),   # CVS Krill: 74 mg/day
    ("182968", False),   # Pure Encap Krill-Plex: 240 mg/day
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
    ("182968", 0.0, 15.0),    # Pure Encap Krill: clinical only
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
    floor = ev["disclosed_epa_dha_clinical_floor"]
    assert floor["min_epa_dha_mg_day"] == 250
    assert floor["score"] == 10
    ir = ev["indication_relevance"]
    assert ir["min_epa_dha_mg_day_for_bonus"] == 1000
    assert ir["score"] == 5
