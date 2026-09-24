"""Supplemental beta-carotene lung-cancer warnings, exactly as approved by the
PharmaGuide Clinical Team (Dr. Pham, 2026-09-21; PHASE3_CLINICAL_POLICY_20260921.md
section 5), P4 of the v41 recovery:

- under 15 mg/day: no warning (informational, suppressed; the repo's threshold-gated pattern);
- 15 mg/day or more with current/former smoking or asbestos exposure: caution;
- 20 mg/day or more with a risk factor: stronger caution (same severity, its own copy);
- 20 mg/day or more, risk status unknown: one contextual card for every viewer
  (the ADR v6 pure-dose threshold: scope None, gate_type dose; projected by the
  exporter's generic dose-hit path, which knows nothing about beta-carotene).

15 mg/day is a PharmaGuide operational threshold, not an upper limit. Amounts are
compared in mcg RAE (NIH ODS: 2 mcg supplemental beta-carotene = 1 mcg RAE;
1 IU = 0.3 mcg RAE), so 15 mg = 7,500 and 20 mg = 10,000 mcg RAE.
"""
import json
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
DATA = SCRIPTS / "data"
FIXTURES = Path(__file__).parent / "fixtures"
RULE_ID = "RULE_IQM_BETA_CAROTENE_LUNG_CANCER"
VITA_RULE_ID = "RULE_IQM_VITAMIN_A_BETA_CAROTENE_LUNG_CANCER"
CONDITIONS = ("current_smoker", "former_smoker", "asbestos_exposure")
HIGH_HEADLINE = "Beta-carotene at a dose linked to lung cancer"


def _json(name):
    return json.loads((DATA / name).read_text())


def _rule(rule_id):
    matches = [r for r in _json("ingredient_interaction_rules.json")["interaction_rules"] if r["id"] == rule_id]
    assert len(matches) == 1
    return matches[0]


@pytest.fixture(scope="module")
def enricher():
    from enrich_supplements_v3 import SupplementEnricherV3
    return SupplementEnricherV3()


def _hits(enricher, rows):
    product = {"dsld_id": "TEST_BETA_CAROTENE", "product_name": "test",
               "ingredient_quality_data": {"ingredients_scorable": rows, "ingredients": rows}}
    profile = enricher._collect_interaction_profile(product)
    hits = {(alert["rule_id"], hit["condition_id"]): hit
            for alert in profile.get("ingredient_alerts") or [] for hit in alert.get("condition_hits") or []}
    return {"interaction_profile": profile}, hits


def _card_fires(profile):
    """A pure-dose hit the consumer sees: dose gate, disposition review."""
    return any(hit["profile_gate"]["gate_type"] == "dose"
               and hit["dose_threshold_evaluation"]["consumer_disposition"] == "review"
               for alert in profile["ingredient_alerts"] if alert["rule_id"] in (RULE_ID, VITA_RULE_ID)
               for hit in alert.get("dose_hits") or [])


def _row(canonical_id, form_id, name, quantity, unit, matched_forms=()):
    return {"name": name, "raw_source_text": name, "standard_name": name, "canonical_id": canonical_id,
            "form_id": form_id, "matched_form": form_id, "matched_forms": [{"form_key": k} for k in matched_forms],
            "quantity": quantity, "unit": unit, "unit_normalized": unit}


def test_three_conditions_are_selectable_and_coded():
    conditions = {c["id"]: c for c in _json("clinical_risk_taxonomy.json")["conditions"]}
    codes = {cid: {ref["code"] for ref in conditions[cid]["icd10"]} for cid in CONDITIONS}
    assert codes == {"current_smoker": {"F17", "Z72.0"}, "former_smoker": {"Z87.891"},
                     "asbestos_exposure": {"Z77.090"}}
    assert all(conditions[cid]["user_selectable"] for cid in CONDITIONS)


@pytest.mark.parametrize("rule_id", [RULE_ID, VITA_RULE_ID])
def test_rule_carries_exactly_the_approved_thresholds(rule_id):
    rule = _rule(rule_id)
    assert {c["condition_id"]: c["severity"] for c in rule["condition_rules"]} == dict.fromkeys(CONDITIONS, "caution")
    tiers = sorted((t["target_id"], t["value"], t["unit"], t["severity_if_met"], t["consumer_disposition_if_not_met"],
                    bool(t.get("alert_headline_if_met"))) for t in rule["dose_thresholds"] if t["scope"] is not None)
    assert tiers == sorted([(cid, v, "mcg RAE", "caution", "suppress", v == 10000)
                            for cid in CONDITIONS for v in (10000, 7500)])
    pure = [t for t in rule["dose_thresholds"] if t["scope"] is None]
    assert [(t["value"], t["unit"], t["severity_if_met"], t["profile_gate"]["gate_type"]) for t in pure] == [
        (10000, "mcg RAE", "caution", "dose")]
    assert rule["review_owner"] == "pharmaguide_clinical_team"


def test_vitamin_a_rule_needs_every_declared_form_to_be_beta_carotene(enricher):
    rule = _rule(VITA_RULE_ID)
    assert rule["form_scope_match"] == "all"
    assert set(rule["form_scope"]) <= set(_json("ingredient_quality_map.json")["vitamin_a"]["forms"])
    pure = _row("vitamin_a", "beta-carotene synthetic", "Vitamin A", 10000, "mcg RAE")
    mixed = _row("vitamin_a", "beta-carotene synthetic", "Vitamin A", 10000, "mcg RAE",
                 matched_forms=("beta-carotene synthetic", "retinyl acetate"))
    assert (VITA_RULE_ID, "current_smoker") in _hits(enricher, [pure])[1]
    assert (VITA_RULE_ID, "current_smoker") not in _hits(enricher, [mixed])[1]


@pytest.mark.parametrize("quantity,unit,disposition,high", [
    (10, "mg", "suppress", False),        # under 15 mg: no warning
    (15, "mg", "review", False),          # 15 mg: caution
    (25000, "IU", "review", False),       # 25,000 IU = 7,500 mcg RAE = 15 mg
    (20, "mg", "review", True),           # 20 mg: stronger caution copy
    (30, "mg", "review", True),
])
def test_tiers_follow_the_approved_policy(enricher, quantity, unit, disposition, high):
    enriched, hits = _hits(enricher, [_row("beta_carotene", "beta-carotene (unspecified)", "Beta-Carotene", quantity, unit)])
    for cid in CONDITIONS:
        hit = hits[(RULE_ID, cid)]
        assert hit["severity"] == ("caution" if disposition == "review" else "informational")
        assert hit["dose_threshold_evaluation"]["consumer_disposition"] == disposition
        assert (hit["alert_headline"] == HIGH_HEADLINE) is high
    assert _card_fires(enriched["interaction_profile"]) is high


def test_unknown_amount_is_not_a_warning(enricher):
    _, hits = _hits(enricher, [_row("beta_carotene", "beta-carotene (unspecified)", "Beta-Carotene", 0.0, "NP")])
    assert hits[(RULE_ID, "current_smoker")]["dose_threshold_evaluation"]["consumer_disposition"] == "suppress"


@pytest.mark.parametrize("pid,high", [("79660", False), ("184325", True)])
def test_real_labels(pid, high):
    """79660: 25,000 IU once daily (15 mg) -> caution; 184325: 7,500 mcg RAE per
    softgel, up to 2 a day (30 mg) -> stronger caution and the contextual card."""
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    import build_final_db as B
    from scoring_v4.scored_artifact import build_scored_artifact
    raw = json.loads((FIXTURES / f"beta_carotene_{pid}_raw.json").read_text())
    enriched, _ = SupplementEnricherV3().enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))
    hits = [h for a in enriched["interaction_profile"]["ingredient_alerts"] if a["rule_id"] == RULE_ID
            for h in a["condition_hits"] if h["condition_id"] in CONDITIONS]
    assert {h["condition_id"] for h in hits} == set(CONDITIONS)
    assert all(h["dose_threshold_evaluation"]["consumer_disposition"] == "review" for h in hits)
    assert all((h["alert_headline"] == HIGH_HEADLINE) is high for h in hits)
    blob = B.build_detail_blob(enriched, build_scored_artifact(enriched))
    cards = [w for w in blob["warnings"] if (w.get("profile_gate") or {}).get("gate_type") == "dose"
             and (w.get("dose_decision") or {}).get("consumer_disposition") == "review"]
    assert [w["alert_headline"] for w in cards] == (["High-dose beta-carotene: check your lung risk"] if high else [])
