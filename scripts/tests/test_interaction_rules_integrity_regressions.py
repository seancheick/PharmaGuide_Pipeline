#!/usr/bin/env python3
"""Regression guards for interaction-rule data-integrity issues found in review.

These checks intentionally stay structural and hermetic. Clinical content is
still source-reviewed separately, but these failure modes should never re-enter
the data file unnoticed.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path


DATA = Path(__file__).resolve().parents[1] / "data"
RULES = json.loads((DATA / "ingredient_interaction_rules.json").read_text())[
    "interaction_rules"
]

SEVERITY_RANK = {
    "informational": 1,
    "monitor": 2,
    "caution": 3,
    "avoid": 4,
    "contraindicated": 5,
}


def _targets(rule: dict) -> set[tuple[str, str]]:
    out = set()
    for item in rule.get("condition_rules") or []:
        out.add(("condition", item.get("condition_id")))
    for item in rule.get("drug_class_rules") or []:
        out.add(("drug_class", item.get("drug_class_id")))
    for item in rule.get("dose_thresholds") or []:
        out.add((item.get("scope"), item.get("target_id")))
    return {x for x in out if x[1]}


def test_non_form_scoped_duplicate_canonicals_do_not_overlap_targets():
    """Two unscoped rows for one canonical_id must not own the same target.

    Form-scoped variants are allowed; overlapping unscoped rows double-fire and
    can ship conflicting thresholds/copy.
    """
    by_canonical = defaultdict(list)
    for rule in RULES:
        canonical_id = (rule.get("subject_ref") or {}).get("canonical_id")
        if canonical_id and not rule.get("form_scope"):
            by_canonical[canonical_id].append((rule["id"], _targets(rule)))

    overlaps = []
    for canonical_id, entries in by_canonical.items():
        for i, (left_id, left_targets) in enumerate(entries):
            for right_id, right_targets in entries[i + 1 :]:
                overlap = left_targets & right_targets
                if overlap:
                    overlaps.append((canonical_id, left_id, right_id, sorted(overlap)))

    assert not overlaps, f"overlapping unscoped canonical rules: {overlaps}"


def test_pregnancy_condition_rules_do_not_conflict_with_pregnancy_lactation_no_data():
    contradictions = []
    for rule in RULES:
        pregnancy_lactation = rule.get("pregnancy_lactation") or {}
        if pregnancy_lactation.get("pregnancy_category") != "no_data":
            continue
        for item in rule.get("condition_rules") or []:
            if item.get("condition_id") == "pregnancy":
                contradictions.append(rule["id"])

    assert not contradictions, (
        "condition_rules[pregnancy] cannot coexist with "
        f"pregnancy_lactation.pregnancy_category=no_data: {contradictions}"
    )


def test_dose_thresholds_do_not_lower_matching_baseline_severity():
    downgrades = []
    for rule in RULES:
        baseline = {}
        for item in rule.get("condition_rules") or []:
            baseline[("condition", item.get("condition_id"))] = item.get("severity")
        for item in rule.get("drug_class_rules") or []:
            baseline[("drug_class", item.get("drug_class_id"))] = item.get("severity")

        for threshold in rule.get("dose_thresholds") or []:
            key = (threshold.get("scope"), threshold.get("target_id"))
            if key not in baseline:
                continue
            base = baseline[key]
            met = threshold.get("severity_if_met")
            if SEVERITY_RANK.get(met, 0) < SEVERITY_RANK.get(base, 0):
                downgrades.append((rule["id"], key, base, met))

    assert not downgrades, f"dose thresholds lower baseline severity: {downgrades}"


def test_vitamin_k_rules_target_vitamin_k_antagonists_not_all_anticoagulants():
    vitamin_k_rules = [
        r
        for r in RULES
        if (r.get("subject_ref") or {}).get("canonical_id") == "vitamin_k"
    ]
    assert vitamin_k_rules

    broad_rules = []
    for vitamin_k in vitamin_k_rules:
        drug_class_ids = {
            item.get("drug_class_id") for item in vitamin_k.get("drug_class_rules") or []
        }
        if "anticoagulants" in drug_class_ids:
            broad_rules.append(vitamin_k["id"])

    assert not broad_rules
    assert any(
        "vitamin_k_antagonists"
        in {
            item.get("drug_class_id")
            for item in vitamin_k.get("drug_class_rules") or []
        }
        for vitamin_k in vitamin_k_rules
    )


def test_probiotic_severe_infection_rule_is_not_autoimmune_gated():
    probiotics = next(
        r
        for r in RULES
        if r.get("id") == "RULE_IQM_PROBIOTICS_IMMUNOCOMPROMISED"
    )
    condition_ids = {
        item.get("condition_id") for item in probiotics.get("condition_rules") or []
    }
    assert "immunocompromised" in condition_ids
    assert "autoimmune" not in condition_ids


def test_holy_basil_pregnancy_rule_aligns_severity_scope_and_evidence():
    rule = next(
        r for r in RULES if r.get("id") == "RULE_IQM_HOLY_BASIL_PREGNANCY"
    )
    pregnancy = next(
        item
        for item in rule.get("condition_rules") or []
        if item.get("condition_id") == "pregnancy"
    )
    pregnancy_lactation = rule["pregnancy_lactation"]

    assert pregnancy["severity"] == "caution"
    assert pregnancy_lactation["pregnancy_category"] == "caution"
    assert pregnancy["evidence_level"] == "limited"
    assert pregnancy_lactation["evidence_level"] == "limited"
    assert "concentrated extract" in pregnancy["action"].lower()
    assert "culinary" in pregnancy["action"].lower()

    copy = " ".join(
        (
            pregnancy["mechanism"],
            pregnancy["alert_body"],
            pregnancy_lactation["alert_body"],
        )
    ).lower()
    assert "uterotonic" not in copy
    assert "human pregnancy" in copy
    assert "https://pubmed.ncbi.nlm.nih.gov/34315377/" in pregnancy["sources"]
    assert "https://pubmed.ncbi.nlm.nih.gov/34315377/" in pregnancy_lactation[
        "sources"
    ]


# Content-verified sources for the anthranoid stimulant-laxative rules
# (receipts: scripts/audits/interaction_rules/laxative_resourcing_2026_09/research.md).
EMA_CASCARA = (
    "https://www.ema.europa.eu/en/documents/herbal-monograph/"
    "final-european-union-herbal-monograph-rhamnus-purshiana-dc-cortex-revision-1_en.pdf"
)
LIVERTOX_CASCARA = "https://www.ncbi.nlm.nih.gov/books/NBK548113/"
LACTMED_CASCARA = "https://www.ncbi.nlm.nih.gov/books/NBK501328/"
DIGOXIN_LABEL = (
    "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?"
    "setid=d91e3646-4c63-4512-ab22-db39c085c4dc"
)
EMA_SENNA_LEAF = (
    "https://www.ema.europa.eu/en/documents/herbal-monograph/"
    "final-european-union-herbal-monograph-senna-alexandrina-mill-cassia-senna-l-"
    "cassia-angustifolia-vahl-folium-revision-1_en.pdf"
)
EMA_SENNA_POD = (
    "https://www.ema.europa.eu/en/documents/herbal-monograph/"
    "final-european-union-herbal-monograph-senna-alexandrina-mill-cassia-senna-l-"
    "cassia-angustifolia-vahl-fructus-revision-1_en.pdf"
)
# Wrong-topic PMIDs once cited by the cascara and senna rules: a cascaroside
# chromatography paper and a Cassiae Semen (Cassia obtusifolia/tora seed) review.
LAXATIVE_GHOST_PMIDS = ("32876395", "36702448")


def _rule(rule_id: str) -> dict:
    return next(r for r in RULES if r.get("id") == rule_id)


def _sub_rule(rule: dict, key: str, value: str) -> dict:
    bucket = "condition_rules" if key == "condition_id" else "drug_class_rules"
    return next(item for item in rule[bucket] if item.get(key) == value)


def test_cascara_rule_cites_the_eu_monograph_and_drops_unsourced_claims():
    rule = _rule("RULE_IQM_CASCARA_SAGRADA_PREGNANCY")
    pregnancy = _sub_rule(rule, "condition_id", "pregnancy")
    liver = _sub_rule(rule, "condition_id", "liver_disease")
    kidney = _sub_rule(rule, "condition_id", "kidney_disease")
    digoxin = _sub_rule(rule, "drug_class_id", "cardiac_glycosides")
    pregnancy_lactation = rule["pregnancy_lactation"]

    assert pregnancy["sources"] == [EMA_CASCARA, LACTMED_CASCARA]
    assert liver["sources"] == [LIVERTOX_CASCARA, EMA_CASCARA]
    assert kidney["sources"] == [EMA_CASCARA]
    assert digoxin["sources"] == [EMA_CASCARA, DIGOXIN_LABEL]
    assert pregnancy_lactation["sources"] == [LACTMED_CASCARA, EMA_CASCARA]

    # Severities are unchanged by the re-sourcing.
    assert (pregnancy["severity"], liver["severity"], kidney["severity"]) == (
        "avoid", "caution", "caution",
    )
    assert digoxin["severity"] == "avoid"
    assert pregnancy_lactation["pregnancy_category"] == "avoid"
    assert pregnancy_lactation["lactation_category"] == "avoid"

    assert "genotoxic" in pregnancy["mechanism"]
    assert "genotoxic" in pregnancy_lactation["notes"]
    assert "breast milk" in pregnancy_lactation["notes"]
    assert "digoxin toxicity" in digoxin["mechanism"]

    copy = json.dumps(rule).lower()
    for stale in (
        "prostaglandin",
        "uterine",
        "maternal plasma",
        "partly on safety grounds",
        "rodent",
        "hepatocytes",
        "hypomagnesemia",
        "dialysis",
        "depends on kidney clearance",
        "choose an osmotic agent",
        # EMA 5.3: genotoxic in vitro, "not proven in in vivo systems"
        "show a genotoxic risk",
        # EMA 4.5 ties hypokalaemia to long-term laxative abuse, not any use
        "long-term stimulant laxative use potentiates",
        "makes digoxin more toxic",
        # neither LiverTox nor the EU monograph contraindicates liver disease
        "do not use cascara sagrada in liver disease",
    ):
        assert stale not in copy, stale
    assert rule["last_reviewed"] == "2026-04-26"  # agent re-sourcing, not a clinical review


def test_laxative_ghost_pmids_are_not_cited_anywhere():
    text = json.dumps(RULES)
    for pmid in LAXATIVE_GHOST_PMIDS:
        assert f"pubmed.ncbi.nlm.nih.gov/{pmid}" not in text


def test_senna_kidney_and_digoxin_rules_cite_the_eu_monographs():
    rule = _rule("RULE_IQM_SENNA_PREGNANCY")
    kidney = _sub_rule(rule, "condition_id", "kidney_disease")
    digoxin = _sub_rule(rule, "drug_class_id", "cardiac_glycosides")

    assert kidney["sources"] == [EMA_SENNA_LEAF, EMA_SENNA_POD]
    assert digoxin["sources"] == [EMA_SENNA_LEAF, EMA_SENNA_POD, DIGOXIN_LABEL]
    assert (kidney["severity"], digoxin["severity"]) == ("caution", "avoid")
    assert "digoxin toxicity" in digoxin["mechanism"]

    copy = json.dumps([kidney, digoxin]).lower()
    for stale in (
        "hyperkalemia rebound",
        "hyponatremia",
        "3.5 to 3.0",
        "binding affinity",
        "depends on kidney clearance",
    ):
        assert stale not in copy, stale
