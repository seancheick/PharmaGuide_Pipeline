"""B0 Section-B active/inactive role-gate contract — regression locks.

CURRENT POLICY (v3.5.0, locked here so the next agent has a baseline):

  The enricher's `_check_banned_substances` walks both `activeIngredients[]`
  and `inactiveIngredients[]`, but for each banned_recalled entry whose
  `match_mode='active'` (the default), it SKIPS matches sourced from the
  inactive list. The historical reason (see SCORING_ENGINE_SPEC v3.5.0
  highlight) is to suppress ~2,000+ false-positive HIGH_RISK fires on
  ubiquitous excipients (talc, TiO2, simethicone) used in capsules / tablets.

  Net effect on scoring:
    * TiO2 / Talc / Docusate Sodium AS INACTIVE → no contaminant_data entry
      → no B0_HIGH_RISK_SUBSTANCE → no 10pt penalty → score unchanged.
    * Same ingredients AS ACTIVE → contaminant_data fires → 10pt penalty
      → score drops ~12 points and verdict can flip SAFE → CAUTION.

ARCHITECTURAL GAP (documented, not yet fixed):

  The 29 banned_recalled high_risk entries with match_mode='active' include
  both:
    (a) genuine excipients with context-dependent safety (TiO2, Talc,
        Docusate Sodium) — suppression is right for these.
    (b) substances that should NEVER appear as inactives without raising
        a flag (heavy metals: As/Pb/Hg/Cd, prohormones: 7-Keto-DHEA,
        hepatotoxic botanicals: Chaparral/Germander/Pennyroyal, controlled
        substances: Δ8-THC, Formaldehyde, Cascara Sagrada, Diiodothyronine,
        Kava, Yohimbe, Bitter Orange, Tansy).

  Suppressing class (b) is incorrect — appearing in the inactive panel is
  a labeling defect or hidden-active risk, not an "acceptable excipient
  use." Fix path (proposed, not yet implemented): per-entry
  `inactive_policy` field discriminating excipient-acceptable from
  never-acceptable. Until that lands, the warnings-array layer (commit
  3e4f9d6) IS the user-facing safety signal for these — they fire as
  warnings even when the score doesn't penalize.

This test file locks the CURRENT contract so any future change is
deliberate. When the per-entry inactive_policy lands, update the
expected outcomes here in the same commit as the policy change.
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path
from typing import Dict, Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))


# ---------------------------------------------------------------------------
# Fixtures: lightweight enriched-product builders
# ---------------------------------------------------------------------------

def _minimal_enriched_active(
    ing_name: str,
    standard_name: str = "",
) -> Dict[str, Any]:
    """Build a minimal enriched-product blob with a single active ingredient.
    Mirrors the shape `_check_banned_substances` consumes; intentionally
    omits everything else so the test is hermetic."""
    return {
        "dsld_id": "TEST_ACTIVE",
        "product_name": "Test Active Product",
        "brandName": "Test",
        "activeIngredients": [
            {"name": ing_name, "standardName": standard_name or ing_name},
        ],
        "inactiveIngredients": [],
    }


def _minimal_enriched_inactive(
    ing_name: str,
    standard_name: str = "",
) -> Dict[str, Any]:
    """Same but ingredient is in the inactive panel."""
    return {
        "dsld_id": "TEST_INACTIVE",
        "product_name": "Test Inactive Product",
        "brandName": "Test",
        "activeIngredients": [],
        "inactiveIngredients": [
            {"name": ing_name, "standardName": standard_name or ing_name},
        ],
    }


@pytest.fixture(scope="module")
def enricher():
    from scripts.enrich_supplements_v3 import SupplementEnricherV3
    return SupplementEnricherV3()


def _run_banned_check(enricher, product: Dict[str, Any]):
    """Drive the enricher's safety check exactly the way the pipeline does."""
    active = [
        {**ing, "_source_section": "active"}
        for ing in product.get("activeIngredients", [])
    ]
    inactive = [
        {**ing, "_source_section": "inactive"}
        for ing in product.get("inactiveIngredients", [])
    ]
    return enricher._check_banned_substances(active + inactive, product)


# ---------------------------------------------------------------------------
# Class (a): excipient-acceptable — current policy correctly suppresses
# ---------------------------------------------------------------------------

EXCIPIENT_ACCEPTABLE_CASES = [
    # (ingredient label, banned_recalled id we expect to be the entry)
    ("Titanium Dioxide",        "BANNED_ADD_TITANIUM_DIOXIDE"),
    ("Titanium Dioxide (E171)", "BANNED_ADD_TITANIUM_DIOXIDE"),
    ("Talc",                    "BANNED_ADD_TALC"),
    ("Docusate Sodium",         "ADD_DOCUSATE_SODIUM"),
]


@pytest.mark.parametrize("ing_name, expected_rule_id", EXCIPIENT_ACCEPTABLE_CASES)
def test_excipient_acceptable_inactive_does_not_fire_b0(enricher, ing_name, expected_rule_id):
    """Excipient-acceptable high_risk substances must NOT populate
    contaminant_data.banned_substances when sourced from inactives.
    Current contract: the warnings-array surfaces them user-side; the
    score is intentionally unaffected because suppressing this class is
    the design (else ~2,000+ FP HIGH_RISK fires on common capsules)."""
    product = _minimal_enriched_inactive(ing_name)
    result = _run_banned_check(enricher, product)
    substances = result.get("substances") or []
    assert not substances, (
        f"{ing_name!r} as INACTIVE produced {len(substances)} banned-substance entries — "
        f"current policy must suppress this class to avoid excipient FP penalties. "
        f"If you intentionally changed the inactive_policy for this entry, update this test."
    )


@pytest.mark.parametrize("ing_name, expected_rule_id", EXCIPIENT_ACCEPTABLE_CASES)
def test_excipient_acceptable_active_DOES_fire_b0(enricher, ing_name, expected_rule_id):
    """Same ingredient AS ACTIVE must fire B0 high_risk. This is the
    inverted half of the role-gate contract: dangerous as active,
    acceptable as excipient. If this assertion breaks, the active-side
    safety signal is gone — much worse than the inactive suppression
    we're locking next to it."""
    product = _minimal_enriched_active(ing_name)
    result = _run_banned_check(enricher, product)
    substances = result.get("substances") or []
    assert substances, (
        f"{ing_name!r} as ACTIVE produced 0 banned-substance entries — "
        f"role-gate is broken. Active dangerous-substance signal must fire."
    )
    statuses = {s.get("status") for s in substances}
    assert "high_risk" in statuses, (
        f"{ing_name!r} as ACTIVE: expected status='high_risk', got {statuses}"
    )


# ---------------------------------------------------------------------------
# Class (b): never-acceptable inactives — inactive_policy='penalize_anyway'.
# v3.5.2 (2026-05-12): per-entry policy landed. These tests now PASS as
# active assertions — heavy metals, prohormones, hepatotoxic botanicals,
# controlled substances, and watchlist contaminants fire B0 even when
# listed as inactives. Use aliases the data file recognizes (some entries
# require qualification like "Inorganic Arsenic" vs bare "arsenic").
# ---------------------------------------------------------------------------

NEVER_ACCEPTABLE_INACTIVE_CASES = [
    # (ingredient label, banned_recalled id) — use aliases the entries match.
    ("Inorganic Arsenic",      "HM_ARSENIC"),
    ("Lead",                   "HM_LEAD"),
    ("Mercury",                "HM_MERCURY"),
    ("Cadmium",                "HM_CADMIUM"),
    ("7-Keto DHEA",            "BANNED_7_KETO_DHEA"),
    ("Yohimbe",                "RISK_YOHIMBE"),
    ("Kava",                   "RISK_KAVA"),
    ("Chaparral",              "HIGH_RISK_CHAPARRAL"),
    ("Germander",              "HIGH_RISK_GERMANDER"),
    ("Pennyroyal Oil",         "HIGH_RISK_PENNYROYAL"),
    ("Bitter Orange",          "RISK_BITTER_ORANGE"),
    ("Formaldehyde",           "BANNED_ADD_FORMALDEHYDE"),
    ("Delta-8 THC",            "BANNED_DELTA8_THC"),
]


@pytest.mark.parametrize("ing_name, expected_rule_id", NEVER_ACCEPTABLE_INACTIVE_CASES)
def test_never_acceptable_inactive_fires_b0(enricher, ing_name, expected_rule_id):
    """v3.5.2 contract: high_risk entries with inactive_policy='penalize_anyway'
    must fire B0 even when listed as inactives. Heavy metals, prohormones,
    hepatotoxic botanicals, controlled substances appearing in the inactive
    panel is a labeling defect or hidden-active risk — not an excipient
    context the user can excuse. The score now aligns with the warnings
    layer (commit 3e4f9d6) for these substances."""
    product = _minimal_enriched_inactive(ing_name)
    result = _run_banned_check(enricher, product)
    substances = result.get("substances") or []
    assert substances, (
        f"{ing_name!r} as INACTIVE should fire B0 (never-acceptable class) "
        f"but contaminant_data is silent — policy gap."
    )
    # Status must be high_risk → B0 fires 10pt penalty (vs 5pt for watchlist).
    assert any(s.get("status") == "high_risk" for s in substances), (
        f"{ing_name!r} as INACTIVE: expected high_risk status hit, got "
        f"{[s.get('status') for s in substances]}"
    )


# ---------------------------------------------------------------------------
# Watchlist class: all 11 watchlist entries are penalize_anyway (5pt B0).
# ---------------------------------------------------------------------------

WATCHLIST_INACTIVE_CASES = [
    # (ingredient label, banned_recalled id) — these all have
    # inactive_policy='penalize_anyway' so they fire B0 watchlist 5pt
    # penalty when listed as inactives. None are legitimate excipients;
    # most are food-additive contaminants or alkaloids.
    ("Phthalates",       "BANNED_ADD_PHTHALATES"),
    ("Potassium Bromate","BANNED_ADD_POTASSIUM_BROMATE"),
    ("Anatabine",        "BANNED_ADD_ANATABINE"),
    ("Octopamine",       "BANNED_ADD_OCTOPAMINE"),
    ("Lobelia",          "RISK_LOBELIA"),
]


@pytest.mark.parametrize("ing_name, expected_rule_id", WATCHLIST_INACTIVE_CASES)
def test_watchlist_inactive_fires_b0_watchlist_5pt(enricher, ing_name, expected_rule_id):
    """Per user directive 2026-05-12: watchlist entries with
    inactive_policy='penalize_anyway' fire the 5pt B0 watchlist penalty
    when listed as inactives. The watchlist semantic ('informational')
    still applies at the warnings layer (commit 3e4f9d6) — at the score
    layer, watchlist contaminants in any panel get the 5pt nudge so the
    score reflects the regulatory tracking signal."""
    product = _minimal_enriched_inactive(ing_name)
    result = _run_banned_check(enricher, product)
    substances = result.get("substances") or []
    assert substances, (
        f"{ing_name!r} as INACTIVE (watchlist) should fire B0 5pt — silent"
    )
    assert any(s.get("status") == "watchlist" for s in substances), (
        f"{ing_name!r} as INACTIVE: expected watchlist status hit, got "
        f"{[s.get('status') for s in substances]}"
    )


# ---------------------------------------------------------------------------
# Review_required class: Cascara and Synthetic Food Acids stay silent at
# score layer until human review. Warnings layer surfaces them.
# ---------------------------------------------------------------------------

REVIEW_REQUIRED_INACTIVE_CASES = [
    ("Cascara Sagrada",  "ADD_CASCARA_SAGRADA"),
]


@pytest.mark.parametrize("ing_name, expected_rule_id", REVIEW_REQUIRED_INACTIVE_CASES)
def test_review_required_inactive_does_not_fire_b0(enricher, ing_name, expected_rule_id):
    """inactive_policy='review_required' substances must NOT fire B0
    until a human reviewer classifies them. Borderline cases — wrong
    direction is more expensive than waiting for clinical review.

    The warnings layer (build_final_db commit 3e4f9d6) IS visible to
    the user even when the score is silent — so the regulator-tracking
    signal isn't lost while review is pending."""
    product = _minimal_enriched_inactive(ing_name)
    result = _run_banned_check(enricher, product)
    substances = result.get("substances") or []
    assert not substances, (
        f"{ing_name!r} as INACTIVE (review_required) should be silent at "
        f"score layer; got {[s.get('id') for s in substances]}. Flip to "
        f"penalize_anyway or excipient_acceptable only after human review."
    )


# ---------------------------------------------------------------------------
# Score-level integration: pin the active-vs-inactive delta on TiO2
# ---------------------------------------------------------------------------

def _full_minimal_product(ing_name: str, where: str) -> Dict[str, Any]:
    """Build a minimal-but-scorable product. Same shape for both variants;
    only the section the ingredient lands in differs."""
    base = {
        "dsld_id": f"TEST_{where.upper()}",
        "product_name": f"Test {where} product",
        "brandName": "Test",
        "upcSku": "0",
        "imageUrl": "",
        "status": "active",
        "form_factor": "capsule",
        "supplement_type": {"type": "vitamin"},
        "enrichment_version": "3.1.0",
        "is_certified_organic": False,
        "is_trusted_manufacturer": True,
        "manufacturing_region": "USA",
        "named_cert_programs": [],
        "has_full_disclosure": True,
        "compliance_data": {},
        "probiotic_data": {"is_probiotic_product": False},
        "contaminant_data": {"banned_substances": {"substances": []}, "harmful_additives": {"additives": []}, "allergens": {"allergens": []}},
        "harmful_additives": [],
        "allergen_hits": [],
        "interaction_profile": {"ingredient_alerts": []},
        "dietary_sensitivity_data": {"warnings": []},
        "activeIngredients": [],
        "inactiveIngredients": [],
        "ingredient_quality_data": {"ingredients": [], "total_active": 0, "unmapped_count": 0, "ingredients_scorable": []},
        "dosage_normalization": {"normalized_ingredients": []},
        "certification_data": {},
        "proprietary_data": {"has_proprietary_blends": False, "blends": []},
        "serving_basis": {
            "basis_count": 1, "basis_unit": "capsule",
            "min_servings_per_day": 1, "max_servings_per_day": 1,
        },
        "manufacturer_data": {"violations": {}},
        "evidence_data": {"match_count": 0, "clinical_matches": [], "unsubstantiated_claims": []},
        "rda_ul_data": {
            "collection_enabled": True, "ingredients_with_rda": 0,
            "analyzed_ingredients": 0, "count": 0,
            "adequacy_results": [], "conversion_evidence": [],
            "safety_flags": [], "has_over_ul": False,
        },
    }
    entry = {"name": ing_name, "standardName": ing_name}
    if where == "active":
        base["activeIngredients"].append(entry)
    else:
        base["inactiveIngredients"].append(entry)
    return base


def _load_enriched_1007():
    """Load the real Mega Teen 1007 enriched product from the dev cache.
    This is the canary the entire warnings-array work was tracking;
    pinning the score-side asymmetry here against the same product makes
    the regression direct."""
    import glob, json
    for f in glob.glob("/tmp/reenrich_v3/GNC_enriched/enriched/enriched_*.json"):
        try:
            for p in json.load(open(f)):
                if p.get("dsld_id") == "1007":
                    return p
        except Exception:
            continue
    return None


def test_tio2_active_vs_inactive_score_delta(enricher):
    """Document the quantified delta on the real Mega Teen 1007 fixture:
    TiO2 as ACTIVE drops Section B by ~10pt + flips verdict SAFE→CAUTION;
    TiO2 as INACTIVE (its actual position on the label) leaves both
    unchanged.

    This isn't testing a 'good' outcome — it's locking the current
    asymmetry so a future fix has a clean baseline. If the per-entry
    inactive_policy lands, the inactive variant should drop too and this
    test must be updated alongside the policy change.

    Skip cleanly if the cached enriched fixture isn't on disk — keeps
    the suite green on a fresh checkout."""
    import copy

    base = _load_enriched_1007()
    if base is None:
        pytest.skip(
            "Mega Teen 1007 enriched fixture not cached at "
            "/tmp/reenrich_v3/GNC_enriched/enriched — skip score-delta lock"
        )

    from scripts.score_supplements import SupplementScorer

    # Variant A: TiO2 in inactiveIngredients (real label position)
    prod_inactive = copy.deepcopy(base)

    # Variant B: relocate TiO2 from inactiveIngredients → activeIngredients
    prod_active = copy.deepcopy(base)
    td_entries = [i for i in prod_active.get("inactiveIngredients", [])
                  if "titanium" in str(i.get("name", "")).lower()]
    prod_active["inactiveIngredients"] = [
        i for i in prod_active.get("inactiveIngredients", [])
        if "titanium" not in str(i.get("name", "")).lower()
    ]
    if td_entries:
        prod_active.setdefault("activeIngredients", []).append(copy.deepcopy(td_entries[0]))

    # Populate contaminant_data the way the pipeline would
    prod_active["contaminant_data"]["banned_substances"] = _run_banned_check(enricher, prod_active)
    prod_inactive["contaminant_data"]["banned_substances"] = _run_banned_check(enricher, prod_inactive)

    scorer = SupplementScorer()
    r_active = scorer.score_product(prod_active)
    r_inactive = scorer.score_product(prod_inactive)

    # Inactive variant: B0 silent
    inactive_b0 = [f for f in (r_inactive.get("flags") or []) if "HIGH_RISK" in f or "B0_" in f]
    assert not inactive_b0, (
        f"TiO2 as INACTIVE produced B0/HIGH_RISK flags {inactive_b0!r} — "
        "expected suppression per current contract"
    )

    # Active variant: B0 fires
    active_b0 = [f for f in (r_active.get("flags") or []) if "HIGH_RISK" in f or "B0_" in f]
    assert "B0_HIGH_RISK_SUBSTANCE" in active_b0, (
        f"TiO2 as ACTIVE missing B0_HIGH_RISK_SUBSTANCE — got flags {active_b0!r}"
    )

    # Section-B delta should be meaningful (>= 5pt). Locking magnitude loosely
    # because the abs values can drift with scoring-config tuning. In practice
    # the controlled test shows ~10pt (B_safety_purity 28.5 → 18.5).
    sb_active = ((r_active.get("section_scores") or {}).get("B_safety_purity") or {}).get("score") or 0
    sb_inactive = ((r_inactive.get("section_scores") or {}).get("B_safety_purity") or {}).get("score") or 0
    assert sb_inactive - sb_active >= 5.0, (
        f"Expected Section-B delta >= 5pt between TiO2-inactive ({sb_inactive}) "
        f"and TiO2-active ({sb_active}); got {sb_inactive - sb_active:.1f}"
    )

    # Final-score delta sanity: at least one of (score, verdict) must
    # differ. If they don't, the asymmetry has been silently neutralized.
    score_active = r_active.get("score_100_equivalent")
    score_inactive = r_inactive.get("score_100_equivalent")
    verdict_active = r_active.get("verdict")
    verdict_inactive = r_inactive.get("verdict")
    assert (score_active != score_inactive) or (verdict_active != verdict_inactive), (
        f"Expected meaningful asymmetry between TiO2-active and TiO2-inactive: "
        f"active=({score_active}, {verdict_active}) inactive=({score_inactive}, {verdict_inactive})"
    )
