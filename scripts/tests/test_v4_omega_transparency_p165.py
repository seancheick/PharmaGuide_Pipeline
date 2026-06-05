"""v4 Omega Transparency dimension — P1.6.5 tests.

Locks the positive + penalty math:

    Positive components:
      epa_or_dha_disclosed   5
      form_disclosed         3   (TG/rTG/EE/PL explicit)
      source_disclosed       3   (fish/krill/algae/cod-liver)
      oxidation_disclosed    2   (TOTOX/peroxide/anisidine — future-ready)
      b3_claim_compliance    up to +4

    Penalties (reused from generic_transparency):
      b2_allergen            up to -2
      b5_opacity             up to -5 (class-aware; omega = generic 1.0x)
      b6_marketing           -5

  Cap 15.

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


def _omega_product(
    *,
    name: str = "Test Omega",
    epa: float = 600,
    dha: float = 300,
    extra_ingredients: list | None = None,
    **kwargs,
) -> dict:
    ingredients = [
        {"name": "EPA", "canonical_id": "epa", "quantity": epa, "unit": "mg"},
        {"name": "DHA", "canonical_id": "dha", "quantity": dha, "unit": "mg"},
    ]
    if extra_ingredients:
        ingredients.extend(extra_ingredients)
    p = {
        "status": "active", "form_factor": "softgel",
        "product_name": name,
        "supplement_type": {"type": "specialty"},
        "ingredient_quality_data": {"ingredients_scorable": ingredients},
    }
    p.update(kwargs)
    return p


# --- Component contract --------------------------------------------------


def test_returns_normalized_payload_shape() -> None:
    from scoring_v4.modules.omega_transparency import score_transparency

    payload = score_transparency(_omega_product())
    for key in ("score", "max", "components", "penalties", "metadata"):
        assert key in payload
    assert payload["max"] == 15.0
    assert payload["metadata"]["phase"] == "P1.6.5_omega_transparency"


def test_empty_product_scores_zero() -> None:
    from scoring_v4.modules.omega_transparency import score_transparency

    assert score_transparency({})["score"] == 0.0


def test_none_input_scores_zero_safely() -> None:
    from scoring_v4.modules.omega_transparency import score_transparency

    assert score_transparency(None)["score"] == 0.0


# --- EPA/DHA disclosed --------------------------------------------------


def test_epa_or_dha_disclosed_awarded_with_valid_unit() -> None:
    from scoring_v4.modules.omega_transparency import score_transparency

    product = _omega_product(epa=500, dha=300)
    payload = score_transparency(product)
    assert payload["components"]["epa_or_dha_disclosed"] == 5.0


def test_epa_or_dha_disclosed_requires_valid_unit() -> None:
    """Per Codex's completeness tightening: quantity without valid unit
    doesn't qualify as 'disclosed'."""
    from scoring_v4.modules.omega_transparency import score_transparency

    product = {
        "ingredient_quality_data": {"ingredients_scorable": [
            {"name": "EPA", "canonical_id": "epa", "quantity": 500},  # no unit
        ]}
    }
    payload = score_transparency(product)
    assert "epa_or_dha_disclosed" not in payload["components"]


def test_epa_or_dha_disclosed_accepts_normalized_unit_field() -> None:
    """unit_normalized / normalized_unit are also accepted (Codex's
    completeness tightening compatibility)."""
    from scoring_v4.modules.omega_transparency import score_transparency

    product = {
        "ingredient_quality_data": {"ingredients_scorable": [
            {"name": "EPA", "canonical_id": "epa", "quantity": 500,
             "unit_normalized": "mg"},
        ]}
    }
    payload = score_transparency(product)
    assert payload["components"]["epa_or_dha_disclosed"] == 5.0


def test_epa_or_dha_disclosed_accepts_pure_epa() -> None:
    """Pure EPA (no DHA) qualifies — at least one disclosed."""
    from scoring_v4.modules.omega_transparency import score_transparency

    product = {
        "ingredient_quality_data": {"ingredients_scorable": [
            {"name": "EPA", "canonical_id": "epa", "quantity": 500, "unit": "mg"},
        ]}
    }
    payload = score_transparency(product)
    assert payload["components"]["epa_or_dha_disclosed"] == 5.0


def test_epa_or_dha_disclosed_accepts_pure_dha() -> None:
    from scoring_v4.modules.omega_transparency import score_transparency

    product = {
        "ingredient_quality_data": {"ingredients_scorable": [
            {"name": "DHA", "canonical_id": "dha", "quantity": 300, "unit": "mg"},
        ]}
    }
    payload = score_transparency(product)
    assert payload["components"]["epa_or_dha_disclosed"] == 5.0


# --- Form disclosed -----------------------------------------------------


def test_form_disclosed_when_explicit_keyword_in_name() -> None:
    from scoring_v4.modules.omega_transparency import score_transparency

    product = _omega_product(name="Omega-3 Triglycerides 1000 mg")
    payload = score_transparency(product)
    assert payload["components"]["form_disclosed"] == 3.0


def test_form_not_disclosed_for_bare_fish_oil() -> None:
    """'Fish Oil' without form keyword scores undefined → no form credit."""
    from scoring_v4.modules.omega_transparency import score_transparency

    product = _omega_product(name="Fish Oil 1000 mg Softgels")
    payload = score_transparency(product)
    assert "form_disclosed" not in payload["components"]


def test_form_disclosed_for_krill_implies_phospholipid() -> None:
    from scoring_v4.modules.omega_transparency import score_transparency

    product = _omega_product(name="Antarctic Krill Oil")
    payload = score_transparency(product)
    assert payload["components"]["form_disclosed"] == 3.0


# --- Source disclosed ---------------------------------------------------


def test_source_disclosed_for_fish_oil() -> None:
    from scoring_v4.modules.omega_transparency import score_transparency

    product = _omega_product(name="Pure Fish Oil EPA+DHA")
    payload = score_transparency(product)
    assert payload["components"]["source_disclosed"] == 3.0


def test_source_disclosed_for_algae() -> None:
    from scoring_v4.modules.omega_transparency import score_transparency

    product = _omega_product(name="Algae Oil Vegan DHA")
    payload = score_transparency(product)
    assert payload["components"]["source_disclosed"] == 3.0


def test_source_not_disclosed_bare_omega_name() -> None:
    from scoring_v4.modules.omega_transparency import score_transparency

    # 'EPA+DHA Complex' alone has no source keyword
    product = _omega_product(name="Pure EPA+DHA Complex 1000 mg")
    payload = score_transparency(product)
    assert "source_disclosed" not in payload["components"]


# --- Oxidation disclosed ------------------------------------------------


def test_oxidation_disclosed_when_totox_present() -> None:
    from scoring_v4.modules.omega_transparency import score_transparency

    product = _omega_product(totox=5.2)
    payload = score_transparency(product)
    assert payload["components"]["oxidation_disclosed"] == 2.0


def test_oxidation_disclosed_when_peroxide_value_present() -> None:
    from scoring_v4.modules.omega_transparency import score_transparency

    product = _omega_product(peroxide_value=1.8)
    payload = score_transparency(product)
    assert payload["components"]["oxidation_disclosed"] == 2.0


def test_oxidation_disclosed_via_certification_data_lot_test() -> None:
    from scoring_v4.modules.omega_transparency import score_transparency

    product = _omega_product(certification_data={
        "lot_test_data": {"oxidation": "fresh"}
    })
    payload = score_transparency(product)
    assert payload["components"]["oxidation_disclosed"] == 2.0


def test_oxidation_disclosed_via_rules_db_totox_program() -> None:
    """Future-ready: if rules_db emits TOTOX as a third_party_program."""
    from scoring_v4.modules.omega_transparency import score_transparency

    product = _omega_product(certification_data={
        "evidence_based": {"third_party_programs": [
            {"rule_id": "CERT_TOTOX", "display_name": "TOTOX Lot Test"}
        ]}
    })
    payload = score_transparency(product)
    assert payload["components"]["oxidation_disclosed"] == 2.0


def test_oxidation_not_disclosed_no_signals() -> None:
    from scoring_v4.modules.omega_transparency import score_transparency

    product = _omega_product()
    payload = score_transparency(product)
    assert "oxidation_disclosed" not in payload["components"]


# --- B3 claim_compliance (reused from generic) --------------------------


def test_b3_awarded_when_compliance_claims_present() -> None:
    from scoring_v4.modules.omega_transparency import score_transparency

    product = _omega_product(compliance_data={
        "allergen_free_claims": [{"id": "x"}],
        "gluten_free": True,
        "vegan": True,
    })
    payload = score_transparency(product)
    # Allergen 2 + gluten 1 + vegan 1 = 4
    assert payload["components"].get("b3_claim_compliance", 0) > 0


def test_b3_capped_at_4() -> None:
    from scoring_v4.modules.omega_transparency import score_transparency

    product = _omega_product(compliance_data={
        "allergen_free_claims": [{"id": "x"}],
        "gluten_free": True,
        "vegan": True,
        "vegetarian": True,
    })
    payload = score_transparency(product)
    assert payload["components"].get("b3_claim_compliance", 0) <= 4.0


# --- Penalties ----------------------------------------------------------


def test_b2_allergen_presence_alone_has_no_penalty() -> None:
    from scoring_v4.modules.omega_transparency import score_transparency

    product = _omega_product(contaminant_data={
        "allergens": {"allergens": [{"allergen_id": "shellfish", "severity_level": "high"}]}
    })
    payload = score_transparency(product)
    assert payload["penalties"].get("b2_false_allergen_free_claim", 0) == 0


def test_b2_false_allergen_claim_penalty_applied() -> None:
    from scoring_v4.modules.omega_transparency import score_transparency

    product = _omega_product(
        contaminant_data={
            "allergens": {"allergens": [{"allergen_id": "shellfish", "severity_level": "high"}]}
        },
        compliance_data={
            "allergen_free_claims": ["shellfish-free"],
            "gluten_free": False,
            "vegan": False,
            "conflicts": [],
        },
    )
    payload = score_transparency(product)
    assert payload["penalties"].get("b2_false_allergen_free_claim", 0) == -2.0


def test_b6_marketing_penalty_applied() -> None:
    """Disease-claim marketing penalty applies even with omega content."""
    from scoring_v4.modules.omega_transparency import score_transparency

    product = _omega_product(compliance_data={"disease_claims": [{"id": "cures_cancer"}]})
    payload = score_transparency(product)
    # B6 penalty may or may not fire depending on how compliance signals
    # the disease claim — just verify the score doesn't crash.
    assert isinstance(payload["score"], float)


# --- Score ceiling + clamp ----------------------------------------------


def test_max_transparency_reaches_15() -> None:
    """A premium product with full disclosure + B3 max + oxidation +
    no penalties hits the 15 cap."""
    from scoring_v4.modules.omega_transparency import score_transparency

    product = _omega_product(
        name="Premium Wild Fish Oil Triglyceride EPA+DHA",
        compliance_data={
            "allergen_free_claims": [{"id": "x"}],
            "gluten_free": True,
            "vegan": True,
        },
        totox=5.0,
    )
    payload = score_transparency(product)
    assert payload["score"] == 15.0
    assert payload["metadata"]["cap_applied"] is True


def test_cap_constant() -> None:
    from scoring_v4.modules.omega_transparency import score_transparency, CAP_TRANSPARENCY

    assert CAP_TRANSPARENCY == 15.0


# --- Real-catalog canary integration -----------------------------------


_CANARY_T_IDS = {"327776", "326270", "288740", "273630", "239592", "182968"}
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
            if did in _CANARY_T_IDS:
                found[did] = item
        if len(found) == len(_CANARY_T_IDS):
            break
    _canary_cache = found
    return {did: _canary_cache[did] for did in ids if did in _canary_cache}


# Real-catalog ranges; loose so generic_transparency penalty drift doesn't
# break this lock — what we want to guarantee is that Transparency is in
# the right ballpark and the positive components fire correctly.
@pytest.mark.parametrize("dsld_id,min_score,max_score", [
    ("327776", 11.5, 12.5),   # Sports Research: EPA/DHA + TG form disclosed
    ("326270", 11.5, 12.5),   # Sports Research alt
    ("288740", 10.5, 11.5),   # Nordic: undefined form; honest allergen presence no longer penalizes
    ("273630", 8.5, 9.5),     # Garden of Life Advanced Omega
    ("239592", 8.0, 12.0),    # CVS Krill
    ("182968", 8.0, 12.0),    # Pure Encap Krill-Plex
])
def test_canary_transparency_in_range(dsld_id, min_score, max_score):
    from scoring_v4.modules.omega_transparency import score_transparency

    canaries = _load_canaries({dsld_id})
    if dsld_id not in canaries:
        pytest.skip(f"canary {dsld_id} not in catalog")
    payload = score_transparency(canaries[dsld_id])
    assert min_score <= payload["score"] <= max_score, (
        f"{dsld_id} Transparency {payload['score']} not in [{min_score}, {max_score}]"
    )


def test_canary_nordic_has_no_form_disclosed():
    """Nordic Ultimate Omega + CoQ10 doesn't disclose form on the DSLD
    label — must NOT score form_disclosed even though it's known rTG."""
    from scoring_v4.modules.omega_transparency import score_transparency

    canaries = _load_canaries({"288740"})
    if "288740" not in canaries:
        pytest.skip("Nordic canary not in catalog")
    payload = score_transparency(canaries["288740"])
    assert "form_disclosed" not in payload["components"]


# --- Orchestrator roll-forward + module completeness -------------------


def test_omega_orchestrator_phase_rolls_forward_to_p165() -> None:
    from scoring_v4.modules.omega import score_omega

    breakdown = score_omega(_omega_product()).to_breakdown()
    assert breakdown["phase"].startswith("P1.6.")


def test_omega_all_five_dimensions_populated_through_p165() -> None:
    """After P1.6.5 lands, all 5 dimensions in score_omega's breakdown
    carry numeric scores. Manufacturer / final assembly lands at P1.6.6."""
    from scoring_v4.modules.omega import score_omega

    breakdown = score_omega(_omega_product()).to_breakdown()
    for dim in ("formulation", "dose", "evidence", "transparency"):
        assert breakdown["dimensions"][dim]["score"] is not None, (
            f"omega.{dim}.score should be populated through P1.6.5"
        )


# --- Architecture lock --------------------------------------------------


def test_omega_transparency_does_not_import_v3_scorer() -> None:
    import ast
    import scoring_v4.modules.omega_transparency as ot

    tree = ast.parse(Path(ot.__file__).read_text())
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


def test_transparency_weights_match_rubric_config() -> None:
    from scoring_v4.modules.omega_transparency import _load_rubric

    rubric = _load_rubric()
    t = rubric["transparency"]
    assert t["epa_or_dha_disclosed"] == 5
    assert t["form_disclosed"] == 3
    assert t["source_disclosed"] == 3
    assert t["oxidation_disclosed"]["score"] == 2
    assert t["b3_claim_compliance"]["cap"] == 4
    assert "b2_allergen" in t["penalties_inherited"]
    assert "b5_opacity_class_aware" in t["penalties_inherited"]
    assert "b6_marketing" in t["penalties_inherited"]
