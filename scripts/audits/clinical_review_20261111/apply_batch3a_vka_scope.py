"""Batch 3a follow-up: gate the warfarin-only findings on an identified vitamin K antagonist.

Run once from the repo root, after apply_batch3a_anticoagulant_scope.py:
    $PG_PYTHON scripts/audits/clinical_review_20261111/apply_batch3a_vka_scope.py

apply_batch3a_anticoagulant_scope.py scoped Dr. Pham's warfarin-only rows (A2, A4, A7, A8) as `anticoagulants`
minus `doacs`. The evaluator applies an exclusion to the whole profile, so an apixaban entry vetoed the finding
for someone who also takes warfarin (an independent review reproduced this, 2026-11-11). Each rule now carries:

- a `vitamin_k_antagonists` sub-rule, which fires for any identified warfarin-type medicine whatever else is
  entered;
- the existing `anticoagulants` sub-rule as the fallback for a blood thinner that is not identified ("Blood
  thinners" is the only user-selectable blood-thinner class): it excludes identified VKAs (the sub-rule above
  carries those) and DOACs.

Both carry one text, which names warfarin. Known limits, recorded for Dr. Pham: other VKAs (phenprocoumon,
acenocoumarol) receive the warfarin-label finding through the class; identified parenteral direct thrombin
inhibitors (argatroban, bivalirudin) have no subclass and fall into the fallback, as before 3a.

CoQ10 (A4): "mildly" left the headline (the warfarin label says "may decrease", not how much), and the cohort
the ginger rule cites (PMID 17723077, read 2026-11-11) is recorded: CoQ10 use was associated with self-reported
bleeding in warfarin users, an observational finding that does not establish cause.
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts"))
import data_batch  # noqa: E402

RULES = REPO / "scripts/data/ingredient_interaction_rules.json"
CURATED = REPO / "scripts/data/curated_interactions/curated_interactions_v1.json"
GOLD_CASES = REPO / "scripts/data/profile_gate_test_cases.json"
GHOST_REVIEW = REPO / "scripts/data/interaction_rules_ghost_review.json"

WARFARIN_ONLY = (
    "RULE_INGREDIENT_ST_JOHNS_WORT",
    "RULE_INGREDIENT_GLUCOSAMINE",
    "RULE_INGREDIENT_CRANBERRY",
    "RULE_IQM_COQ10_HEART_DISEASE_STATINS",
)
COHORT = "https://pubmed.ncbi.nlm.nih.gov/17723077/"
COHORT_SENTENCE = (
    "In one cohort of warfarin users, CoQ10 use was associated with self-reported bleeding; that observational "
    "finding does not establish cause."
)


def coq10(sub: dict) -> None:
    assert sub["alert_headline"] == "May mildly reduce warfarin effect"
    sub["alert_headline"] = "May reduce warfarin effect"
    assert sub["mechanism"].endswith("Clinical evidence is mixed.")
    sub["mechanism"] = f"{sub['mechanism']} {COHORT_SENTENCE}"
    sub["sources"] = [*sub["sources"], COHORT]


def rules(blob: dict) -> None:
    by_id = {r["id"]: r for r in blob["interaction_rules"]}
    for rule_id in WARFARIN_ONLY:
        subs = by_id[rule_id]["drug_class_rules"]
        assert not [s for s in subs if s["drug_class_id"] == "vitamin_k_antagonists"], rule_id
        [i] = [n for n, s in enumerate(subs) if s["drug_class_id"] == "anticoagulants"]
        fallback = subs[i]
        assert fallback["profile_gate"]["excludes"]["drug_classes_any"] == ["doacs"], rule_id
        if rule_id == "RULE_IQM_COQ10_HEART_DISEASE_STATINS":
            coq10(fallback)
        vka = copy.deepcopy(fallback)
        vka["drug_class_id"] = "vitamin_k_antagonists"
        vka["profile_gate"]["requires"]["drug_classes_any"] = ["vitamin_k_antagonists"]
        vka["profile_gate"]["excludes"]["drug_classes_any"] = []
        fallback["profile_gate"]["excludes"]["drug_classes_any"] = ["doacs", "vitamin_k_antagonists"]
        subs.insert(i, vka)


def curated(blob: dict) -> None:
    pair = next(r for r in blob["interactions"] if r["id"] == "DSI_WAR_COQ10")
    assert "17723077" not in pair["source_pmids"]
    pair["source_pmids"] = [*pair["source_pmids"], "17723077"]
    pair["source_urls"] = [*pair["source_urls"], COHORT]
    pair["evidence_notes"] = f"{pair['evidence_notes']} PMID 17723077: {COHORT_SENTENCE}"


def _gate(requires: list[str], excludes: list[str]) -> dict:
    return {
        "gate_type": "drug_class",
        "requires": {"conditions_any": [], "drug_classes_any": requires, "profile_flags_any": []},
        "excludes": {"conditions_any": [], "drug_classes_any": excludes, "profile_flags_any": [],
                     "product_forms_any": [], "nutrient_forms_any": []},
        "dose": None,
    }


def _case(name: str, description: str, gate: dict, drug_classes: list[str], fires: bool) -> dict:
    return {
        "name": name,
        "description": description,
        "gate": gate,
        "user_profile": {"conditions": [], "drug_classes": drug_classes, "profile_flags": []},
        "product_context": {"product_form": None, "nutrient_form": None, "dose_per_day": None, "dose_unit": None},
        "base_severity": "avoid",
        "expected": {"fires": fires, "severity": "avoid" if fires else None},
    }


def gold(blob: dict) -> None:
    cases = blob["test_cases"]
    old = {"gold_warfarin_only_gate_skips_a_doac_user", "gold_warfarin_only_gate_keeps_an_unknown_blood_thinner"}
    assert old <= {c["name"] for c in cases}
    keep = [c for c in cases if c["name"] not in old]
    vka, fallback = _gate(["vitamin_k_antagonists"], []), _gate(["anticoagulants"], ["doacs", "vitamin_k_antagonists"])
    warfarin, apixaban = ["anticoagulants", "vitamin_k_antagonists"], ["anticoagulants", "doacs"]
    blob["test_cases"] = keep + [
        _case("gold_warfarin_only_vka_gate_fires_for_warfarin",
              "Warfarin-specific St. John's wort evidence fires for an identified warfarin-type medicine",
              vka, warfarin, True),
        _case("gold_warfarin_only_vka_gate_keeps_warfarin_with_a_doac",
              "A DOAC elsewhere in the medicine list does not veto the warfarin finding",
              vka, sorted(set(warfarin) | set(apixaban)), True),
        _case("gold_warfarin_only_vka_gate_skips_a_doac_user",
              "Warfarin-specific evidence does not fire for a DOAC user",
              vka, apixaban, False),
        _case("gold_warfarin_only_fallback_skips_an_identified_warfarin",
              "The fallback stays quiet when the VKA sub-rule carries the finding, so it is not shown twice",
              fallback, warfarin, False),
        _case("gold_warfarin_only_fallback_skips_a_doac_user",
              "The fallback does not fire when the blood thinner is an identified DOAC (a 'Blood thinners' "
              "selection alongside an entered DOAC reads as that DOAC)",
              fallback, apixaban, False),
        _case("gold_warfarin_only_fallback_keeps_an_unknown_blood_thinner",
              "Warfarin-specific evidence still fires when the blood thinner is not identified",
              fallback, ["anticoagulants"], True),
    ]
    blob["_metadata"]["case_count"] = len(blob["test_cases"])


def ghost_review(blob: dict) -> None:
    """The glucosamine teaching case moves with the finding to the new sub-rule; its review still holds."""
    reviewed = blob["reviewed"]
    [prior] = [r for r in reviewed if r["pmid"] == "23946031" and r["sub_rule"] == "drug:anticoagulants"]
    assert not [r for r in reviewed if r["pmid"] == "23946031" and r["sub_rule"] == "drug:vitamin_k_antagonists"]
    reviewed.insert(reviewed.index(prior) + 1, {
        **prior,
        "sub_rule": "drug:vitamin_k_antagonists",
        "rationale": f"{prior['rationale']} The same warfarin-only finding, carried by the vitamin_k_antagonists "
                     "sub-rule since the batch 3a scope fix (2026-11-11).",
        "reviewed_by": "agent citation triage 2026-11-11 (not clinician-reviewed)",
        "reviewed_at": "2026-11-11",
    })
    blob["_metadata"]["last_updated"] = "2026-11-11"


def edit(path: Path, fn) -> None:
    blob = data_batch.load(path)
    fn(blob)
    data_batch.save(path, blob)


if __name__ == "__main__":
    edit(RULES, rules)
    edit(CURATED, curated)
    edit(GOLD_CASES, gold)
    edit(GHOST_REVIEW, ghost_review)
