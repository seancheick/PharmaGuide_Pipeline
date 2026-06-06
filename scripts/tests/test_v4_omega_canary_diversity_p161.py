"""v4 Omega P1.6.1 canary diversity — ≥12 real-catalog products.

Per Sean's 2026-05-20 directive: 'I think you need to run with more canaries
than those 2 you're running with, at least 10 to find some edge cases we
can fix while building.'

This file is the omega-class equivalent of the v4 canary coverage gate.
It runs P1.6.1 Formulation against real DSLD products from the enriched
catalog and locks expected Formulation score ranges so a future regression
(rubric tweak, regex drift, ingredient-canonicalization change) lights up
loudly.

Coverage targets:
  - max-reachable rTG/TG (Sports Research, Garden of Life Dr. Formulated) — 2
  - krill PL form (CVS, Nordic, Spring Valley, GNC, Nature Made,
    Nutricost, Pure Encapsulations) — ≥3 brands
  - EE form (Spring Valley) — 1
  - cod liver source (Garden of Life Alaskan Cod Liver Oil) — 1
  - undefined-form fallthrough (Nordic Naturals Ultimate Omega — DSLD label
    omits molecular form, but source/sustainability still score) — 1
  - false-positive guard (a product that pre-fix wrongly routed omega
    via fatty_acid plurality — must NOT route here) — 2

Tests are bound to specific DSLD IDs. If the enriched catalog isn't
available in this checkout (e.g. CI worker without scripts/products/),
tests skip rather than fail."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))


# DSLD IDs and expected behavior, gathered from the P1.6.1 catalog sweep.
# Each entry: (expected_route, expected_form, expected_score_min, expected_score_max, label)
CANARY_TARGETS = {
    # --- Max-reachable 23/25 (TG + source + premium + sustainability + concentration) ---
    "326270": ("omega", "rtg", 23.0, 23.0,
               "Sports Research Omega-3 1055 mg Fish Oil 1250 mg (one of several SKUs)"),
    "327776": ("omega", "rtg", 23.0, 23.0,
               "Sports Research Omega-3 1055 mg Fish Oil 1250 mg (original canary)"),
    "273630": ("omega", "tg", 23.0, 23.0,
               "Garden of Life Dr. Formulated Advanced Omega Lemon Flavor"),
    "273636": ("omega", "tg", 20.0, 20.0,
               "Garden of Life Dr. Formulated Alaskan Cod Liver Oil Lemon Flavor "
               "— cod liver source"),
    "292796": ("omega", "tg", 21.0, 21.0,  # re-baseline 2026-06-06: concentration partial (2.0)
               "Garden of Life Dr. Formulated Advanced Omega Citrus Flavor"),

    # --- 18/25 (PL krill + source + premium + sustainability) ---
    "239592": ("omega", "pl", 19.0, 19.0,
               "CVS Health 100% Pure Omega-3 Krill Oil 350 mg"),
    "223169": ("omega", "pl", 18.0, 18.0,
               "Nordic Naturals Omega-3 Phospholipids"),

    # --- 16-17/25 (PL krill mid-tier — no sustainability cert) ---
    "1072":   ("omega", "pl", 16.0, 16.0,
               "GNC Ultra Omega Krill Oil"),
    "179775": ("omega", "pl", 17.0, 17.0,
               "Nature Made Krill Oil 300 mg"),
    "223318": ("omega", "pl", 16.0, 16.0,
               "Nutricost Krill Oil 1000 mg"),
    "182968": ("omega", "pl", 16.0, 16.0,
               "Pure Encapsulations Krill-Plex"),

    # --- 19/25 EE form with concentration (rare in catalog) ---
    "239845": ("omega", "ee", 19.0, 19.0,
               "Spring Valley Omega-3 520 mg Natural Lemon Flavor — EE form"),

    # --- 8/25 undefined-form, source + sustainability in current enriched artifact ---
    # Nordic Naturals Ultimate Omega + CoQ10 — label omits molecular form in
    # this artifact, so form remains 'undefined'. Source and Friend of the Sea
    # sustainability are real signals and still score.
    "288740": ("omega", "undefined", 8.0, 8.0,
               "Nordic Naturals Ultimate Omega + CoQ10 Lemon"),
}


# False-positive guard — these products PRE-FIX routed to omega via
# the removed category_breakdown plurality check. Must now route generic.
FALSE_POSITIVE_TARGETS = {
    "182799": "Pure Encapsulations CLA 1,000 mg (CLA = omega-6 isomer)",
    "184340": "Pure Encapsulations Borage Oil (GLA = omega-6)",
    "13567":  "Pure Encapsulations Flax Seed Oil (Organic) (ALA-only, no EPA/DHA)",
    "184571": "Pure Encapsulations Liposomal Glutathione (lecithin carrier)",
}


_canary_cache: dict | None = None
_ALL_CANARY_IDS = set(CANARY_TARGETS.keys()) | set(FALSE_POSITIVE_TARGETS.keys())


def _load_canaries(ids: set[str]) -> dict:
    """One-shot loader scanning enriched batches for ALL canary dsld_ids
    on first call. Subsequent calls hit the cache. The catalog is ~6GB
    across 41 batch files — one scan per session, not per parametrize."""
    global _canary_cache
    if _canary_cache is not None:
        return {did: _canary_cache[did] for did in ids if did in _canary_cache}

    enriched_root = SCRIPTS_ROOT / "products"
    if not enriched_root.exists():
        _canary_cache = {}
        pytest.skip("no enriched products dir in this checkout")

    # Load ALL canary IDs in one pass — not just the request set — so the
    # next parametrize iteration hits the cache instead of rescanning.
    target_ids = _ALL_CANARY_IDS
    found = {}
    for path in enriched_root.glob("output_*_enriched/enriched/enriched_cleaned_batch_*.json"):
        try:
            data = json.loads(path.read_text())
        except Exception:
            continue
        items = data if isinstance(data, list) else (
            data.get("products") or data.get("items") or []
        )
        for item in items:
            if not isinstance(item, dict):
                continue
            did = str(item.get("dsld_id") or item.get("id") or "")
            if did in target_ids:
                found[did] = item
        if len(found) == len(target_ids):
            break
    _canary_cache = found
    return {did: _canary_cache[did] for did in ids if did in _canary_cache}


# --- Per-canary tests (parametrized over CANARY_TARGETS) ----------------


@pytest.mark.parametrize("dsld_id,expected", [(k, v) for k, v in CANARY_TARGETS.items()])
def test_omega_canary_routes_and_scores_in_range(dsld_id, expected):
    """Each P1.6.1 canary product routes to omega and scores in its
    documented Formulation range. Lock locks router + form-detection +
    sub-component scoring together."""
    from scoring_v4.router import class_for_product
    from scoring_v4.modules.omega_formulation import score_formulation

    expected_route, expected_form, score_min, score_max, label = expected
    canaries = _load_canaries({dsld_id})
    if dsld_id not in canaries:
        pytest.skip(f"canary {dsld_id} ({label}) not in enriched catalog")

    product = canaries[dsld_id]
    route = class_for_product(product)
    assert route == expected_route, (
        f"canary {dsld_id} ({label}) routed to {route!r}, expected {expected_route!r}"
    )

    payload = score_formulation(product)
    score = payload["score"]
    form = payload["metadata"]["form_detected"]
    assert form == expected_form, (
        f"canary {dsld_id} form detected {form!r}, expected {expected_form!r}. "
        f"Components: {payload['components']}"
    )
    assert score_min <= score <= score_max, (
        f"canary {dsld_id} ({label}) Formulation score {score} not in "
        f"[{score_min}, {score_max}]. Components: {payload['components']}"
    )


# --- False-positive guards ----------------------------------------------


@pytest.mark.parametrize("dsld_id,label", list(FALSE_POSITIVE_TARGETS.items()))
def test_false_positive_omega_routes_to_generic(dsld_id, label):
    """These real-catalog products used to wrongly route to omega via the
    removed category_breakdown plurality check. Lock them to generic so
    a future router change doesn't reintroduce the false positives."""
    from scoring_v4.router import class_for_product

    canaries = _load_canaries({dsld_id})
    if dsld_id not in canaries:
        pytest.skip(f"false-positive canary {dsld_id} ({label}) not in catalog")

    product = canaries[dsld_id]
    route = class_for_product(product)
    assert route == "generic", (
        f"FALSE POSITIVE: {dsld_id} ({label}) wrongly routes to {route!r} "
        f"instead of generic"
    )


# --- Summary integrity --------------------------------------------------


def test_canary_set_covers_all_form_tiers():
    """The diversity canary set covers disclosed form tiers plus undefined.

    TG/rTG is not inferred from brand reputation or product-name marketing;
    it only enters this canary set when the current enriched artifact has
    explicit label evidence.
    """
    expected_forms = {expected[1] for expected in CANARY_TARGETS.values()}
    assert {"pl", "ee", "undefined"}.issubset(expected_forms), (
        f"canary set missing form tier(s): "
        f"{ {'pl', 'ee', 'undefined'} - expected_forms }"
    )


def test_canary_set_covers_score_ranges():
    """The canary set must cover low/mid/high Formulation score bands so
    future rubric changes that compress or stretch scores are visible."""
    scores = {expected[2] for expected in CANARY_TARGETS.values()}
    assert max(scores) >= 20.0, "missing max-reachable canary (20+/25)"
    assert any(15.0 <= s <= 20.0 for s in scores), "missing mid-tier canary (15-20/25)"
    assert any(s <= 10.0 for s in scores), "missing low-tier canary (<=10/25)"


def test_canary_set_size_at_least_10() -> None:
    """Per Sean's 2026-05-20 directive: at least 10 omega canaries.
    Locks the floor so future trimming doesn't drop coverage."""
    assert len(CANARY_TARGETS) >= 10


# --- Edge-case canaries (Sean 2026-05-20: explicit list) ----------------
#
# Real-catalog products cover the dominant population; these synthetic
# edge-case canaries lock the boundary behavior:
#   - pure EPA / pure DHA components
#   - fish-oil parent-only (no breakdown)
#   - rTG explicit, EE explicit, MCT carrier
#   - CLA 3-6-9 mixed fatty acid
#   - prenatal DHA routing guard
#   - DHEA false-positive guard
# Each test exercises the full P1.6.1 pipeline: router → completeness gate
# → Formulation. Per Sean: "make sure it includes edge cases."


def test_edge_pure_epa_synthetic_canary() -> None:
    """Pure EPA product (e.g. prescription-grade icosapent ethyl) — must
    route omega, pass completeness (at least one EPA/DHA disclosed), score
    based on whatever form/source/sustainability is labeled."""
    from scoring_v4.router import class_for_product
    from scoring_v4.gate_completeness import evaluate_completeness_gate
    from scoring_v4.modules.omega_formulation import score_formulation

    product = {
        "status": "active", "form_factor": "softgel",
        "product_name": "Pure EPA 1000 mg Ethyl Esters",
        "supplement_type": {"type": "specialty"},
        "ingredient_quality_data": {
            "ingredients_scorable": [
                {"name": "EPA", "canonical_id": "epa", "mapped": True,
                 "quantity": 1000, "unit": "mg"},
            ]
        },
    }
    assert class_for_product(product) == "omega"
    assert evaluate_completeness_gate(product, "omega").is_live_eligible
    payload = score_formulation(product)
    assert payload["metadata"]["form_detected"] == "ee"
    assert payload["score"] > 0


def test_edge_pure_dha_algal_synthetic_canary() -> None:
    """Pure DHA algal product (vegan-friendly) — must route omega, pass
    completeness, get source disclosed credit (algal/algae)."""
    from scoring_v4.router import class_for_product
    from scoring_v4.gate_completeness import evaluate_completeness_gate
    from scoring_v4.modules.omega_formulation import score_formulation

    product = {
        "status": "active", "form_factor": "softgel",
        "product_name": "Vegan Algal DHA 300 mg",
        "supplement_type": {"type": "specialty"},
        "ingredient_quality_data": {
            "ingredients_scorable": [
                {"name": "DHA", "canonical_id": "dha", "mapped": True,
                 "quantity": 300, "unit": "mg"},
            ]
        },
    }
    assert class_for_product(product) == "omega"
    assert evaluate_completeness_gate(product, "omega").is_live_eligible
    payload = score_formulation(product)
    assert "source_disclosed" in payload["components"]


def test_edge_fish_oil_parent_only_routes_omega_but_fails_completeness() -> None:
    """A 'Fish Oil 1000 mg' product routes to omega identity, then fails the
    omega completeness gate because EPA/DHA is not disclosed."""
    from scoring_v4.router import class_for_product
    from scoring_v4.gate_completeness import evaluate_completeness_gate

    product = {
        "status": "active", "form_factor": "softgel",
        "product_name": "Fish Oil 1000 mg",
        "supplement_type": {"type": "specialty"},
        "ingredient_quality_data": {
            "ingredients_scorable": [
                {"name": "Fish Oil", "canonical_id": "fish_oil",
                 "quantity": 1000, "unit": "mg", "mapped": True},
            ]
        },
    }
    assert class_for_product(product) == "omega"
    result = evaluate_completeness_gate(
        {**product, "supplement_taxonomy": {"primary_type": "omega_3"}},
        "omega",
    )
    assert result.is_live_eligible
    assert "epa_or_dha_not_disclosed" in result.soft_missing
    assert result.score_cap is None
    assert result.verdict_ceiling is None


def test_edge_rtg_explicit_form_canary() -> None:
    """Re-esterified triglyceride form explicitly labeled — must detect rTG
    and score it at the premium triglyceride tier."""
    from scoring_v4.modules.omega_formulation import score_formulation

    product = {
        "status": "active", "form_factor": "softgel",
        "product_name": "Re-esterified Omega-3 1280 mg EPA+DHA",
        "supplement_type": {"type": "targeted"},
        "ingredient_quality_data": {
            "ingredients_scorable": [
                {"name": "EPA", "canonical_id": "epa", "quantity": 650, "unit": "mg"},
                {"name": "DHA", "canonical_id": "dha", "quantity": 450, "unit": "mg"},
            ]
        },
    }
    payload = score_formulation(product)
    assert payload["metadata"]["form_detected"] == "rtg"
    assert payload["components"]["form_tier"] == 8.0


def test_edge_mct_carrier_in_vitamin_d_routes_generic() -> None:
    """Vitamin D3 with MCT (Medium Chain Triglyceride) carrier must route
    GENERIC, not omega — D3 is the primary active, MCT is delivery, no
    EPA/DHA present. Codex's MCT-pattern fix prevents the form-tier
    over-credit even if such a product somehow reached omega routing."""
    from scoring_v4.router import class_for_product
    from scoring_v4.modules.omega_formulation import score_formulation

    product = {
        "status": "active", "form_factor": "softgel",
        "product_name": "Vitamin D3 5000 IU with Medium Chain Triglycerides",
        "supplement_type": {"type": "targeted"},
        "ingredient_quality_data": {
            "ingredients_scorable": [
                {"name": "Vitamin D", "canonical_id": "vitamin_d",
                 "quantity": 125, "unit": "mcg"},
                {"name": "Medium Chain Triglycerides", "canonical_id": "mct_oil",
                 "quantity": 500, "unit": "mg"},
            ]
        },
    }
    # Routes to generic — no EPA/DHA canonical, no omega name keyword,
    # no standalone EPA/DHA (D3 is not EPA).
    assert class_for_product(product) == "generic"

    # And even if directly score_formulation is called, MCT does not
    # award TG form credit (Codex's _MCT_TRIGLYCERIDE_PATTERN guard).
    payload = score_formulation(product)
    assert payload["metadata"]["form_detected"] != "tg"


def test_edge_cla_omega_3_6_9_mixed_routes_generic() -> None:
    """An 'Omega 3-6-9' mixed fatty acid product (CLA / GLA / oleic blend)
    must route GENERIC unless the panel actually has EPA/DHA canonical.
    Marketing names like 'Super Omega 3-6-9' often package ALA + GLA +
    oleic without any actual EPA/DHA — must not route omega and inherit
    therapeutic dose claims."""
    from scoring_v4.router import class_for_product

    product = {
        "status": "active", "form_factor": "softgel",
        "product_name": "Super Omega 3-6-9 Complex",
        "supplement_type": {"type": "specialty",
                            "category_breakdown": {"fatty_acid": 3}},
        "ingredient_quality_data": {
            "ingredients_scorable": [
                {"name": "Alpha-Linolenic Acid",
                 "canonical_id": "alpha_linolenic_acid",
                 "quantity": 500, "unit": "mg"},
                {"name": "Gamma-Linolenic Acid",
                 "canonical_id": "gamma_linolenic_acid",
                 "quantity": 200, "unit": "mg"},
                {"name": "Oleic Acid", "canonical_id": "oleic_acid",
                 "quantity": 100, "unit": "mg"},
            ]
        },
    }
    assert class_for_product(product) == "generic"


def test_edge_prenatal_dha_routes_omega_not_multi() -> None:
    """A single-purpose prenatal DHA product (actives are primarily EPA/DHA)
    routes OMEGA, not multi_or_prenatal: it has no prenatal nutrient panel for
    the multi module to evaluate, so routing it to multi crushed it on
    panel-coverage. The omega module scores it on the prenatal DHA target."""
    from scoring_v4.router import class_for_product

    product = {
        "status": "active", "form_factor": "softgel",
        "product_name": "Prenatal DHA 200 mg",
        "supplement_type": {"type": "specialty"},
        "ingredient_quality_data": {
            "ingredients_scorable": [
                {"name": "DHA", "canonical_id": "dha", "quantity": 200,
                 "unit": "mg", "mapped": True},
            ]
        },
    }
    assert class_for_product(product) == "omega"


def test_edge_dhea_does_not_match_dha_word_boundary() -> None:
    """DHEA (dehydroepiandrosterone) hormone product must NOT route omega
    even though 'DHA' is a substring of 'DHEA'. Word-boundary regex
    `\\bDHA\\b` must NOT match inside DHEA. Critical false-positive guard
    — if this regresses, every DHEA hormone product on the catalog
    wrongly routes to omega."""
    from scoring_v4.router import class_for_product

    for name in (
        "DHEA 25 mg",
        "Pure DHEA 50 mg Hormone Support",
        "Micronized DHEA Daily",
        "DHEA Complex with Pregnenolone",
    ):
        product = {"product_name": name}
        assert class_for_product(product) == "generic", (
            f"DHEA product wrongly routed to omega: {name!r}"
        )


def test_edge_pure_epa_quantity_without_unit_fails_completeness() -> None:
    """Codex's completeness-gate tightening: positive quantity alone is
    NOT sufficient. A unit must accompany the quantity for the EPA/DHA
    disclosure to count. NP / empty / missing units fail."""
    from scoring_v4.gate_completeness import evaluate_completeness_gate

    cases = [
        # quantity but no unit field at all
        {"name": "EPA", "canonical_id": "epa", "quantity": 500, "mapped": True},
        # quantity + NP unit (placeholder)
        {"name": "EPA", "canonical_id": "epa", "quantity": 500, "unit": "NP", "mapped": True},
        # quantity + empty string unit
        {"name": "EPA", "canonical_id": "epa", "quantity": 500, "unit": "", "mapped": True},
    ]
    for ing in cases:
        product = {
            "status": "active", "form_factor": "capsule",
            "supplement_type": {"type": "specialty"},
            "ingredient_quality_data": {"ingredients_scorable": [ing]},
        }
        result = evaluate_completeness_gate(product, "omega")
        assert result.is_live_eligible, (
            f"EPA with bad unit '{ing.get('unit', '<missing>')}' should stay scoreable "
            "with soft disclosure debt"
        )
        assert "epa_or_dha_not_disclosed" in result.soft_missing
