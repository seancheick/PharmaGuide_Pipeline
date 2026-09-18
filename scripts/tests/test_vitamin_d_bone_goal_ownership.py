#!/usr/bin/env python3
"""Two owners, two different claims — do not collapse them.

    backed_clinical_studies.json  ->  INTERVENTION evidence (what a trial showed)
                                      surfaces on the clinical evidence card
    synergy_cluster.json          ->  NUTRIENT-FUNCTION relationship (physiology)
                                      surfaces as product-facing goal_matches

INGR_VITAMIN_D3 cites PMID 30293909 (Lancet Diabetes Endocrinol 2018), which
pooled 81 RCTs and found NO reduction in fractures or falls and no clinically
meaningful BMD gain from supplementation. A bone claim on that record is a claim
its own citation refutes, so it was removed.

That removal is NOT a product-facing regression, because goal_matches never read
this file: compute_goal_matches() resolves goals from synergy clusters. Vitamin D's
real bone relationship — it aids intestinal calcium absorption, per the NIH ODS
fact sheets cited by the cluster — lives in the bone_health cluster and is
untouched.

Regression for the cycle where the removal was applied, reverted on the belief
that it cost ~819 products their bone goal, and re-applied once the ownership
split was measured. Hermetic.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import build_final_db as b  # noqa: E402

DATA = Path(__file__).parent.parent / "data"
BONE_GOAL = "Joint & Bone Health"


def _record(entry_id):
    payload = json.loads((DATA / "backed_clinical_studies.json").read_text())
    return next(e for e in payload["backed_clinical_studies"] if e["id"] == entry_id)


def _bone_cluster():
    payload = json.loads((DATA / "synergy_cluster.json").read_text())
    return next(c for c in payload["synergy_clusters"] if c["id"] == "bone_health")


def _cluster_hit(meets_minimum):
    return {
        "cluster_id": "bone_health",
        "matched_ingredients": [
            {"cluster_ingredient": "vitamin d3",
             "meets_minimum": meets_minimum,
             "min_effective_dose": 1000},
        ],
    }


def _product(clusters, n_actives=2):
    return {
        "activeIngredients": [{"i": i} for i in range(n_actives)],
        "formulation_data": {"synergy_clusters": clusters},
    }


# ── 1. the evidence card no longer claims what its citation refutes ───────────

def test_vitamin_d3_clinical_record_makes_no_bone_claim():
    entry = _record("INGR_VITAMIN_D3")

    assert BONE_GOAL not in entry["health_goals_supported"]
    assert not any("bone" in k.lower() for k in entry["key_endpoints"])
    assert not any("bone" in o.lower()
                   for o in entry["applicability"]["supported_outcomes"])
    # The refuting citation stays attached — it is why the claim is gone.
    assert "30293909" in entry["applicability"]["source_pmids"]


def test_vitamin_d3_studied_population_is_population_metadata_only():
    """It describes who was studied. Interpretation and open questions
    belong in notes, not mixed into a population field."""
    population = _record("INGR_VITAMIN_D3")["applicability"]["studied_population"]

    assert population.startswith("Adults")
    for leaked in ("OPEN:", "health_goals_supported", "pending", "NOT creditable"):
        assert leaked not in population, f"{leaked!r} leaked into studied_population"


# ── 2. the nutrient-function owner still carries the relationship ─────────────

def test_bone_health_relationship_still_lives_in_the_synergy_cluster():
    cluster = _bone_cluster()

    assert "vitamin d3" in cluster["ingredients"]
    assert "vitamin d3" in cluster["primary_ingredients"]
    assert cluster["allow_single_ingredient"] is True
    assert cluster["min_effective_doses"]["vitamin d3"] == 1000
    # Sourced to nutrient-function authorities, not to an intervention trial.
    assert any(s.get("source_type") == "nih_ods" for s in cluster["sources"])


def test_qualifying_vitamin_d_product_still_gets_the_shipped_bone_goal():
    """The whole point: goal_matches is synergy-owned, so the evidence-card
    cleanup cannot take a product's bone goal away."""
    result = b.compute_goal_matches(_product([_cluster_hit(meets_minimum=True)]))

    assert any("bone" in g.lower() for g in result["goal_matches"])
    assert not any("bone" in g.lower() for g in result["goal_matches_underdosed"])


# ── 3. below-anchor products behave exactly as they did before ────────────────

def test_below_anchor_vitamin_d_stays_underdosed():
    """A 400 IU infant drop sits under the cluster's 1000 IU anchor. It was
    underdosed before this change and must still be — the dose gate owns that
    outcome, not the evidence record."""
    result = b.compute_goal_matches(_product([_cluster_hit(meets_minimum=False)]))

    assert not any("bone" in g.lower() for g in result["goal_matches"])
    assert any("bone" in g.lower() for g in result["goal_matches_underdosed"])


def test_goal_matches_never_reads_the_clinical_evidence_registry():
    """Structural guard on the ownership split. If a future change wires
    backed_clinical_studies into goal derivation, the two owners have merged
    and this whole test file is lying."""
    source = (Path(__file__).parent.parent / "build_final_db.py").read_text()
    start = source.index("def compute_goal_matches(")
    end = source.index("\ndef ", start + 1)
    body = source[start:end]

    assert "backed_clinical_studies" not in body
    assert "health_goals_supported" not in body


# ── 4. behavioural ownership: the registry cannot reach goal derivation ───────
#
# The source-inspection test above is an architecture tripwire, not a guarantee.
# A refactor could rename its way past the literals, or introduce registry
# dependence indirectly without any of them appearing. These two drive the real
# function and compare real output, from both directions the registry could
# arrive: baked into the product blob, and read live through the owner.

D3_CARD_WITH_BONE = {
    "id": "INGR_VITAMIN_D3",
    "health_goals_supported": ["Immune Support", "Healthy Aging/Longevity", BONE_GOAL],
    "key_endpoints": ["bone health ↑", "immunity ↑"],
}
D3_CARD_WITHOUT_BONE = {
    "id": "INGR_VITAMIN_D3",
    "health_goals_supported": ["Immune Support", "Healthy Aging/Longevity"],
    "key_endpoints": ["immunity ↑"],
}


def _product_with_card(card):
    product = _product([_cluster_hit(meets_minimum=True)])
    product["evidence_data"] = {"clinical_matches": [card]}
    return product


def test_bone_fields_on_the_embedded_evidence_card_do_not_change_goal_matches():
    """The enriched blob carries a copy of the clinical record. Removing the
    bone claim from that copy must not move a single shipped goal."""
    with_bone = b.compute_goal_matches(_product_with_card(D3_CARD_WITH_BONE))
    without_bone = b.compute_goal_matches(_product_with_card(D3_CARD_WITHOUT_BONE))

    assert with_bone == without_bone
    # And the goal is genuinely there to lose - otherwise this passes vacuously.
    assert any("bone" in g.lower() for g in without_bone["goal_matches"])


def test_mutating_the_live_registry_record_does_not_change_goal_matches(monkeypatch):
    """Same claim from the other direction: swap the record the canonical owner
    hands out. If goal derivation ever grows an indirect read of the evidence
    registry, this fails even though no literal string appears in its source."""
    import clinical_applicability

    bone_record = dict(_record("INGR_VITAMIN_D3"))
    bone_record["health_goals_supported"] = [*bone_record["health_goals_supported"], BONE_GOAL]
    bone_record["key_endpoints"] = ["bone health ↑", *bone_record["key_endpoints"]]

    product = _product([_cluster_hit(meets_minimum=True)])
    monkeypatch.setattr(clinical_applicability, "reviewed_entries",
                        lambda: {"INGR_VITAMIN_D3": bone_record})
    with_bone = b.compute_goal_matches(json.loads(json.dumps(product)))

    monkeypatch.setattr(clinical_applicability, "reviewed_entries",
                        lambda: {"INGR_VITAMIN_D3": _record("INGR_VITAMIN_D3")})
    without_bone = b.compute_goal_matches(json.loads(json.dumps(product)))

    assert with_bone == without_bone
    assert any("bone" in g.lower() for g in without_bone["goal_matches"])
