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
        "long-term stimulant laxative use potentiates",
        "makes digoxin more toxic",
    ):
        assert stale not in copy, stale
    assert rule["last_reviewed"] == "2026-04-26"  # agent re-sourcing, not a clinical review


# Citation triage 2026-09 (verify_interaction_rules_citations.py --strict suspects).
# Receipts: scripts/audits/interaction_rules/citation_triage_2026_09/research.md.
def _pmid(pmid: str) -> str:
    return f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"


MSKCC_RED_CLOVER = "https://www.mskcc.org/cancer-care/integrative-medicine/herbs/red-clover"


def test_red_clover_anticoagulant_rule_no_longer_cites_a_soy_thyroid_paper():
    rule = _rule("RULE_IQM_RED_CLOVER")
    anticoagulants = _sub_rule(rule, "drug_class_id", "anticoagulants")
    bleeding = _sub_rule(rule, "condition_id", "bleeding_disorders")
    thyroid = _sub_rule(rule, "condition_id", "thyroid_disorder")

    # 9464451 is a soybean thyroid-peroxidase paper: a constituent source for
    # thyroid, nothing for anticoagulants.
    assert anticoagulants["sources"] == [
        _pmid("10902065"), _pmid("29541484"), MSKCC_RED_CLOVER,
    ]
    assert bleeding["sources"] == [MSKCC_RED_CLOVER, _pmid("29541484")]
    assert thyroid["sources"] == [_pmid("30132047"), _pmid("9464451")]
    assert (anticoagulants["severity"], bleeding["severity"], thyroid["severity"]) == (
        "caution", "monitor", "monitor",
    )

    assert "antiplatelet" in anticoagulants["mechanism"]
    assert "antiplatelet" in bleeding["mechanism"]
    assert "formononetin" in thyroid["mechanism"]
    copy = json.dumps([anticoagulants, bleeding, thyroid]).lower()
    for stale in (
        "coumestrol",
        "vitamin k antagonists",
        "no direct clinical evidence",
        "at significant concentrations",
        "competitively inhibit",
    ):
        assert stale not in copy, stale
    assert rule["last_reviewed"] == "2026-04-24"  # agent re-sourcing, not a clinical review


FDA_GRAPEFRUIT = (
    "https://www.fda.gov/consumers/consumer-updates/grapefruit-juice-and-some-drugs-dont-mix"
)


def test_bergamot_drug_rules_cite_bergamottin_not_an_osteosarcopenia_review():
    rule = _rule("RULE_IQM_CITRUS_BERGAMOT_CHOLESTEROL")
    bridge = [_pmid("18830151"), _pmid("15592332"), _pmid("23184849")]
    expected = {
        "statins": ("avoid", bridge + [FDA_GRAPEFRUIT]),
        "calcium_channel_blockers": ("avoid", bridge + [FDA_GRAPEFRUIT]),
        "immunosuppressants": ("contraindicated", bridge + [FDA_GRAPEFRUIT]),
        "antiarrhythmics": ("avoid", bridge + [FDA_GRAPEFRUIT]),
        "anticoagulants": ("caution", bridge),
        "oral_contraceptives": ("monitor", bridge),
    }
    for drug_class, (severity, sources) in expected.items():
        sub = _sub_rule(rule, "drug_class_id", drug_class)
        assert sub["sources"] == sources, drug_class
        assert sub["severity"] == severity, drug_class
        # Bergamot evidence is a constituent (bergamottin) plus grapefruit
        # extrapolation, not an established bergamot-drug interaction.
        assert sub["evidence_level"] == "limited", drug_class
        assert "bergamottin" in sub["mechanism"], drug_class
        assert "inferred from grapefruit" in sub["mechanism"], drug_class
        copy = json.dumps(sub).lower()
        for stale in ("5-15", "p-gp", "dramatically", "small but documented",
                      "documented but small", "mildly"):
            assert stale not in copy, (drug_class, stale)
    assert _pmid("39517207") not in json.dumps(rule)
    assert rule["last_reviewed"] == "2026-04-09"  # agent re-sourcing, not a clinical review


NCCIH_SAW_PALMETTO = "https://www.nccih.nih.gov/health/saw-palmetto"


def test_saw_palmetto_rules_drop_pancreatitis_and_alopecia_citations():
    rule = _rule("RULE_IQM_SAW_PALMETTO_LIVER")
    ttc = _sub_rule(rule, "condition_id", "ttc")
    anticoagulants = _sub_rule(rule, "drug_class_id", "anticoagulants")
    antiplatelets = _sub_rule(rule, "drug_class_id", "antiplatelets")
    nsaids = _sub_rule(rule, "drug_class_id", "nsaids")
    pregnancy_lactation = rule["pregnancy_lactation"]

    # 16800417 is a pancreatitis case, 30980598 a hair-loss review, and
    # 10902065 does not name saw palmetto.
    assert pregnancy_lactation["sources"] == [NCCIH_SAW_PALMETTO, _pmid("16985705")]
    assert ttc["sources"] == [_pmid("16985705"), _pmid("31002161"), NCCIH_SAW_PALMETTO]
    assert anticoagulants["sources"] == [
        _pmid("11489067"), _pmid("20120986"), _pmid("18090773"), _pmid("19719333"),
    ]
    assert ttc["evidence_level"] == "theoretical"
    assert (ttc["severity"], anticoagulants["severity"]) == ("caution", "monitor")
    assert pregnancy_lactation["pregnancy_category"] == "avoid"
    assert pregnancy_lactation["lactation_category"] == "avoid"

    assert "has not been studied" in ttc["mechanism"]
    assert "coagulopathy" in anticoagulants["mechanism"]
    copy = json.dumps(rule).lower()
    for stale in (
        "can impair semen quality",
        "may adversely affect semen parameters",
        "no documented case reports of saw palmetto altering inr",
        "has mild antiplatelet",
    ):
        assert stale not in copy, stale
    for sub in (antiplatelets, nsaids):
        assert "platelet tests in volunteers were normal" in sub["alert_body"]
    assert rule["last_reviewed"] == "2026-04-26"  # agent re-sourcing, not a clinical review


EMA_VALERIAN = (
    "https://www.ema.europa.eu/en/documents/herbal-monograph/"
    "final-european-union-herbal-monograph-valeriana-officinalis-l-radix_en.pdf"
)
LACTMED_VALERIAN = "https://www.ncbi.nlm.nih.gov/books/NBK501815/"


def test_valerian_pregnancy_rule_cites_the_eu_monograph_not_a_liver_case():
    rule = _rule("RULE_IQM_VALERIAN_LIVER")
    pregnancy_lactation = rule["pregnancy_lactation"]
    liver = _sub_rule(rule, "condition_id", "liver_disease")

    assert pregnancy_lactation["sources"] == [EMA_VALERIAN, LACTMED_VALERIAN]
    assert _pmid("18431248") in liver["sources"]  # the liver case stays where it fits
    assert pregnancy_lactation["pregnancy_category"] == "avoid"
    assert pregnancy_lactation["lactation_category"] == "avoid"
    assert "has not been established" in pregnancy_lactation["mechanism"]
    assert "baldrinals" in pregnancy_lactation["mechanism"]
    assert rule["last_reviewed"] == "2026-04-09"  # agent re-sourcing, not a clinical review


NCCIH_KAVA = "https://www.nccih.nih.gov/health/kava"


def test_kava_pregnancy_and_seizure_rules_say_what_their_sources_say():
    rule = _rule("RULE_IQM_KAVALACTONES_LIVER")
    pregnancy_lactation = rule["pregnancy_lactation"]
    seizure = _sub_rule(rule, "condition_id", "seizure_disorder")

    # 27092496 is a hepatotoxicity review: nothing on pregnancy or lactation.
    assert pregnancy_lactation["sources"] == [NCCIH_KAVA]
    assert "pyrone" in pregnancy_lactation["mechanism"]
    # 12383029's withdrawal sentence is about conventional anxiolytics; the
    # kava withdrawal and proconvulsant statements need their own sources.
    assert seizure["sources"] == [
        _pmid("12383029"), _pmid("22062945"), _pmid("38829029"), NCCIH_KAVA,
    ]
    assert seizure["evidence_level"] == "limited"
    assert seizure["severity"] == "caution"
    assert "proconvulsant" in seizure["mechanism"]
    assert "heavy users" in seizure["mechanism"] and "heavily" in seizure["action"]
    assert "after regular use may produce withdrawal seizures" not in seizure["mechanism"]
    assert pregnancy_lactation["pregnancy_category"] == "contraindicated"
    assert rule["last_reviewed"] == "2026-04-09"  # agent re-sourcing, not a clinical review


NCCIH_COQ10 = "https://www.nccih.nih.gov/health/coenzyme-q10"


def test_coq10_heart_rule_cites_q_symbio_for_its_heart_failure_claim():
    rule = _rule("RULE_IQM_COQ10_HEART_DISEASE_STATINS")
    heart = _sub_rule(rule, "condition_id", "heart_disease")

    # 17723077 carries only the warfarin caveat; 12083489 has no readable result.
    assert heart["sources"] == [_pmid("25282031"), NCCIH_COQ10, _pmid("17723077")]
    assert heart["severity"] == "informational"
    assert "Q-SYMBIO" in heart["mechanism"]
    assert "inconclusive" in heart["mechanism"]
    assert "ejection fraction" not in heart["mechanism"].lower()
    assert rule["last_reviewed"] == "2026-04-09"  # agent re-sourcing, not a clinical review


EMA_SALIX = (
    "https://www.ema.europa.eu/en/documents/herbal-monograph/"
    "final-european-union-herbal-monograph-salix-various-species-including-s-purpurea-l-"
    "s-daphnoides-vill-s-fragilis-l-cortex_en.pdf"
)


def test_willow_bark_rules_describe_willow_not_aspirin():
    rule = _rule("RULE_IQM_WHITE_WILLOW_BARK_BLEEDING")
    subs = {
        "bleeding_disorders": _sub_rule(rule, "condition_id", "bleeding_disorders"),
        "surgery_scheduled": _sub_rule(rule, "condition_id", "surgery_scheduled"),
        "anticoagulants": _sub_rule(rule, "drug_class_id", "anticoagulants"),
        "antiplatelets": _sub_rule(rule, "drug_class_id", "antiplatelets"),
        "nsaids": _sub_rule(rule, "drug_class_id", "nsaids"),
    }
    severities = {
        "bleeding_disorders": "caution", "surgery_scheduled": "avoid",
        "anticoagulants": "caution", "antiplatelets": "caution", "nsaids": "avoid",
    }
    for key, sub in subs.items():
        # 25997859 is an efficacy review that says nothing about bleeding.
        assert sub["sources"] == [EMA_SALIX, _pmid("11345689")], key
        assert sub["severity"] == severities[key], key
    assert subs["surgery_scheduled"]["evidence_level"] == "limited"
    assert "far less than" in subs["bleeding_disorders"]["mechanism"]
    assert "coumarin" in subs["anticoagulants"]["mechanism"]

    copy = json.dumps(list(subs.values())).lower()
    for stale in (
        "irreversibl",
        "lifespan of the platelet",
        "7-10 days",
        "displaces warfarin",
        "treat similarly to aspirin",
        "aspirin-like",
    ):
        assert stale not in copy, stale
    assert rule["last_reviewed"] == "2026-04-14"  # agent re-sourcing, not a clinical review


def test_tansy_pregnancy_rule_cites_reproductive_sources():
    rule = _rule("RULE_BANNED_TANSY_PREGNANCY")
    pregnancy = _sub_rule(rule, "condition_id", "pregnancy")

    # 28472675 is a rat/brine-shrimp thujone toxicity study with no pregnancy data.
    assert pregnancy["sources"] == [_pmid("33673548"), _pmid("232204")]
    assert pregnancy["severity"] == "contraindicated"
    assert "miscarriage" in pregnancy["mechanism"]
    assert "thujone" in pregnancy["mechanism"]
    assert rule["last_reviewed"] == "2026-04-26"  # agent re-sourcing, not a clinical review


def test_yerba_mate_anticoagulant_rule_drops_the_unsourced_vitamin_k_claim():
    rule = _rule("RULE_IQM_YERBA_MATE_CARDIOVASCULAR")
    anticoagulants = _sub_rule(rule, "drug_class_id", "anticoagulants")

    # 39708247 is an endothelial-function trial; no source says mate carries vitamin K.
    assert anticoagulants["sources"] == [_pmid("25562195"), _pmid("23134458")]
    assert (anticoagulants["severity"], anticoagulants["evidence_level"]) == (
        "caution", "theoretical",
    )
    assert "thromboxane" in anticoagulants["mechanism"]
    copy = json.dumps(anticoagulants).lower()
    for stale in ("vitamin k", "phylloquinone", "consistent intake"):
        assert stale not in copy, stale
    assert rule["last_reviewed"] == "2026-04-09"  # agent re-sourcing, not a clinical review
