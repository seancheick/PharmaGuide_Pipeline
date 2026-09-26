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
    # Alert verb matches the unchanged "avoid" severity.
    for drug_class in ("statins", "calcium_channel_blockers", "antiarrhythmics"):
        assert "avoid bergamot products" in _sub_rule(rule, "drug_class_id", drug_class)["alert_body"]
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
    # 16985705 hedges: "in vitro some studies suggest".
    assert "Some in vitro studies suggest" in ttc["mechanism"]
    assert "Some in vitro studies suggest" in pregnancy_lactation["mechanism"]
    pl_review = next(
        e for e in GHOST_REVIEW["reviewed"]
        if (e["pmid"], e["rule_id"], e["sub_rule"])
        == ("16985705", "RULE_IQM_SAW_PALMETTO_LIVER", "pregnancy_lactation")
    )
    assert "31002161" not in pl_review["rationale"]  # not a source of this sub-rule
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
    # Only willow vs placebo was randomised in PMID 11345689; aspirin was a separate group.
    assert "non-randomised group taking 100 mg aspirin" in subs["bleeding_disorders"]["mechanism"]

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


def test_andrographis_immune_rules_cite_trials_not_antiplatelet_papers():
    rule = _rule("RULE_IQM_ANDROGRAPHIS")
    autoimmune = _sub_rule(rule, "condition_id", "autoimmune")
    immunosuppressants = _sub_rule(rule, "drug_class_id", "immunosuppressants")

    # 28745507 and 21822619 are antiplatelet papers.
    assert autoimmune["sources"] == [_pmid("19408036"), _pmid("27215274"), _pmid("33372366")]
    assert immunosuppressants["sources"] == [_pmid("27215274"), _pmid("33372366")]
    assert (autoimmune["severity"], immunosuppressants["severity"]) == ("caution", "caution")
    assert "rheumatoid arthritis" in autoimmune["mechanism"]
    copy = json.dumps([autoimmune, immunosuppressants]).lower()
    for stale in ("upregulating t-cell", "nk cell", "triggering rejection", "may stimulate immune"):
        assert stale not in copy, stale
    assert rule["last_reviewed"] == "2026-04-24"  # agent re-sourcing, not a clinical review


def test_bacopa_rules_drop_a_pediatric_cognition_review():
    rule = _rule("RULE_IQM_BACOPA_THYROID")
    thyroid = _sub_rule(rule, "condition_id", "thyroid_disorder")
    thyroid_meds = _sub_rule(rule, "drug_class_id", "thyroid_medications")
    sedatives = _sub_rule(rule, "drug_class_id", "sedatives")

    # 27912958 reviews bacopa for cognition in children; it says nothing on
    # thyroid function or sedation.
    assert thyroid["sources"] == [_pmid("12065164")]
    assert thyroid_meds["sources"] == [_pmid("12065164")]
    assert sedatives["sources"] == [_pmid("36061899"), _pmid("18193203")]
    assert (thyroid["severity"], thyroid_meds["severity"], sedatives["severity"]) == (
        "monitor", "caution", "caution",
    )
    assert "41%" in thyroid["mechanism"]
    assert "theoretical" in sedatives["mechanism"]
    copy = json.dumps([thyroid, thyroid_meds, sedatives]).lower()
    for stale in (
        "iodide uptake",
        "thyroglobulin synthesis",
        "additive sedative effects when combined",
        "absorption",
        "has mild sedative effects",
    ):
        assert stale not in copy, stale
    assert rule["last_reviewed"] == "2026-04-14"  # agent re-sourcing, not a clinical review


def test_l_theanine_rules_say_what_the_blood_pressure_and_eeg_studies_say():
    rule = _rule("RULE_IQM_L_THEANINE_ANTIHYPERTENSIVES")
    antihypertensives = _sub_rule(rule, "drug_class_id", "antihypertensives")
    sedatives = _sub_rule(rule, "drug_class_id", "sedatives")

    # 18296328 (EEG) and 35378276 (anxiety NMA) measure no blood pressure.
    assert antihypertensives["sources"] == [_pmid("23107346"), _pmid("17891480")]
    assert sedatives["sources"] == [_pmid("18296328"), _pmid("35378276")]
    assert (antihypertensives["severity"], sedatives["severity"]) == ("caution", "caution")
    assert "caffeine" in antihypertensives["mechanism"]
    assert "without inducing drowsiness" in sedatives["mechanism"]
    # The action must not assert a driving impairment its sources contradict.
    assert "driving" not in sedatives["action"]
    copy = json.dumps([antihypertensives, sedatives]).lower()
    for stale in ("5-8 mmhg", "cns depressant", "glycine", "has mild sedative effects",
                  "has sedative activity"):
        assert stale not in copy, stale
    assert rule["last_reviewed"] == "2026-04-14"  # agent re-sourcing, not a clinical review


def test_guarana_sedative_rule_treats_guarana_as_a_stimulant():
    rule = _rule("RULE_IQM_GUARANA")
    sedatives = _sub_rule(rule, "drug_class_id", "sedatives")

    # 15961987 and 21676849 are weight-loss-product cardiovascular papers.
    assert sedatives["sources"] == [_pmid("23981847"), _pmid("11125871")]
    assert sedatives["severity"] == "caution"
    assert "midazolam" in sedatives["mechanism"]
    copy = json.dumps(sedatives).lower()
    for stale in ("has mild sedative effects", "sedative activity",
                  "add to sedative drowsiness", "sleep architecture"):
        assert stale not in copy, stale
    assert "stimulant" in sedatives["alert_body"].lower()
    assert rule["last_reviewed"] == "2026-04-09"  # agent re-sourcing, not a clinical review


ARICEPT_LABEL = (
    "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?"
    "setid=98e451e1-e4d7-4439-a675-c5457ba20975"
)


def test_huperzine_anticholinergic_rule_cites_ache_pharmacology_and_class_label():
    rule = _rule("RULE_IQM_HUPERZINE_A_ANTICHOLINERGICS")
    anticholinergics = _sub_rule(rule, "drug_class_id", "anticholinergics")

    # 19370686 is a Cochrane review of huperzine for vascular dementia.
    assert anticholinergics["sources"] == [_pmid("25191267"), ARICEPT_LABEL]
    assert anticholinergics["severity"] == "avoid"
    assert "interfere with the activity of anticholinergic" in anticholinergics["mechanism"]
    assert "toxidrome" not in anticholinergics["mechanism"]
    # Class-level label statement, no huperzine study: not "established".
    assert anticholinergics["evidence_level"] == "probable"
    # The label names no example drugs and states no two-way effect.
    for stale in ("each can blunt the other", "prescribing information for cholinesterase "
                  "inhibitors such as donepezil states that, because of their mechanism of "
                  "action, they have the potential to interfere with the activity of "
                  "anticholinergic medications (for example"):
        assert stale not in anticholinergics["mechanism"], stale
    assert rule["last_reviewed"] == "2026-04-14"  # agent re-sourcing, not a clinical review


EMA_RHODIOLA = (
    "https://www.ema.europa.eu/en/documents/herbal-monograph/"
    "final-european-union-herbal-monograph-rhodiola-rosea-l-rhizoma-et-radix-revision-1_en.pdf"
)


def test_rhodiola_sedative_rule_no_longer_claims_a_sedative_effect():
    rule = _rule("RULE_IQM_RHODIOLA_IMMUNE_BP")
    sedatives = _sub_rule(rule, "drug_class_id", "sedatives")

    # 26613955 is a CYP2C9 study; the EU monograph reports no clinically
    # relevant interactions and no sedation.
    assert sedatives["sources"] == [EMA_RHODIOLA]
    assert (sedatives["severity"], sedatives["evidence_level"]) == ("monitor", "theoretical")
    copy = json.dumps(sedatives).lower()
    for stale in ("mild sedative", "sedative activity", "bidirectional", "cyp2c9",
                  "add to sedative drowsiness"):
        assert stale not in copy, stale
    assert rule["last_reviewed"] == "2026-04-09"  # agent re-sourcing, not a clinical review


NCCIH_SAME = "https://www.nccih.nih.gov/health/sadenosyllmethionine-same-in-depth"


def test_same_maoi_rule_cites_serotonergic_sources_not_an_efficacy_meta_analysis():
    rule = _rule("RULE_IQM_SAME")
    maois = _sub_rule(rule, "drug_class_id", "maois")

    # 38423354 is a SAMe-for-depression efficacy meta-analysis.
    assert maois["sources"] == [NCCIH_SAME, _pmid("7854515"), _pmid("8434674")]
    assert (maois["severity"], maois["evidence_level"]) == ("avoid", "limited")
    assert "clomipramine" in maois["mechanism"]
    assert rule["last_reviewed"] == "2026-04-30"  # agent re-sourcing, not a clinical review


def test_chinese_skullcap_pregnancy_rule_reports_the_animal_data_it_cites():
    rule = _rule("RULE_IQM_CHINESE_SKULLCAP_LIVER")
    pregnancy = _sub_rule(rule, "condition_id", "pregnancy")
    pregnancy_lactation = rule["pregnancy_lactation"]

    # 31236960 is a general review; the reproductive-toxicity studies found no
    # teratogenicity, the opposite of the old "teratogenic signals" copy.
    expected = [_pmid("26303163"), _pmid("26033919")]
    assert pregnancy["sources"] == expected
    assert pregnancy_lactation["sources"] == expected
    assert pregnancy["severity"] == "avoid"
    assert pregnancy_lactation["pregnancy_category"] == "avoid"
    assert "precautionary" in pregnancy["mechanism"]
    copy = json.dumps([pregnancy, pregnancy_lactation]).lower()
    for stale in ("teratogenic signals", "possible teratogenic risk", "cyp1a2"):
        assert stale not in copy, stale
    assert rule["last_reviewed"] == "2026-04-14"  # agent re-sourcing, not a clinical review


SYNTHROID_LABEL = (
    "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?"
    "setid=1e11ad30-1041-4520-10b0-8f9d30d30fcc"
)


def test_genistein_levothyroxine_rule_cites_levothyroxine_evidence():
    rule = _rule("RULE_INGREDIENT_GENISTEIN__THYROID")
    thyroid = _sub_rule(rule, "condition_id", "thyroid_disorder")
    thyroid_meds = _sub_rule(rule, "drug_class_id", "thyroid_medications")

    # 36017706 is a rat study with no levothyroxine data.
    assert thyroid_meds["sources"] == [_pmid("30132047"), SYNTHROID_LABEL, _pmid("9464451")]
    assert thyroid["sources"] == [_pmid("9464451"), _pmid("36017706"), _pmid("30132047")]
    assert (thyroid["severity"], thyroid_meds["severity"]) == ("monitor", "caution")
    assert "did not change levothyroxine absorption" in thyroid_meds["mechanism"]
    assert "rats" in thyroid["mechanism"]
    assert rule["last_reviewed"] == "2026-04-09"  # agent re-sourcing, not a clinical review


NCCIH_CATS_CLAW = "https://www.nccih.nih.gov/health/cats-claw"


def test_cats_claw_anticoagulant_rule_drops_an_unverifiable_heck_citation():
    rule = _rule("RULE_INGREDIENT_CAT_S_CLAW")
    anticoagulants = _sub_rule(rule, "drug_class_id", "anticoagulants")

    # 10902065's abstract does not name cat's claw.
    assert anticoagulants["sources"] == [_pmid("33091497"), NCCIH_CATS_CLAW]
    assert (anticoagulants["severity"], anticoagulants["evidence_level"]) == (
        "caution", "theoretical",
    )
    assert "Heck" not in anticoagulants["mechanism"]
    assert "slow blood clotting" in anticoagulants["mechanism"]
    assert rule["last_reviewed"] == "2026-04-09"  # agent re-sourcing, not a clinical review


MSKCC_EPO = "https://www.mskcc.org/cancer-care/integrative-medicine/herbs/evening-primrose-oil"


def test_evening_primrose_anticoagulant_rule_cites_mskcc_not_heck():
    rule = _rule("RULE_INGREDIENT_EVENING_PRIMROSE_OIL")
    anticoagulants = _sub_rule(rule, "drug_class_id", "anticoagulants")

    # 10902065's abstract does not name evening primrose oil.
    assert anticoagulants["sources"] == [_pmid("19783511"), MSKCC_EPO]
    assert (anticoagulants["severity"], anticoagulants["evidence_level"]) == (
        "caution", "probable",
    )
    assert "9 of 12" in anticoagulants["mechanism"]
    copy = anticoagulants["mechanism"].lower()
    for stale in ("clinical pharmacology references", "pge1"):
        assert stale not in copy, stale
    assert rule["last_reviewed"] == "2026-04-24"  # agent re-sourcing, not a clinical review


def test_omega3_nsaid_rule_reports_the_aspirin_bleeding_data():
    rule = _rule("RULE_INGREDIENT_OMEGA_3")
    nsaids = _sub_rule(rule, "drug_class_id", "nsaids")

    # 10902065 is a warfarin review; it says nothing on NSAIDs or fish oil.
    assert nsaids["sources"] == [_pmid("18841286"), _pmid("26280541"), _pmid("17368277")]
    assert (nsaids["severity"], nsaids["evidence_level"]) == ("monitor", "theoretical")
    assert "did not raise" in nsaids["mechanism"]
    copy = json.dumps(nsaids).lower()
    for stale in ("may modestly increase gi bleeding", "can add to nsaid bleeding risk",
                  "may add to nsaid bleeding risk"):
        assert stale not in copy, stale
    assert rule["last_reviewed"] == "2026-04-09"  # agent re-sourcing, not a clinical review


def test_nettle_glucose_rules_cite_human_trials():
    rule = _rule("RULE_IQM_STINGING_NETTLE_DIABETES")
    subs = [_sub_rule(rule, "condition_id", "diabetes")] + [
        _sub_rule(rule, "drug_class_id", dc)
        for dc in ("hypoglycemics_high_risk", "hypoglycemics_lower_risk", "hypoglycemics_unknown")
    ]
    for sub in subs:
        # 35800714 is a general nettle review with no glucose data in its abstract.
        assert sub["sources"] == [_pmid("24273930"), _pmid("31802554")]
        assert "18 mg/dL" in sub["mechanism"]
    assert [s["severity"] for s in subs] == ["caution", "caution", "monitor", "caution"]
    assert rule["last_reviewed"] == "2026-04-14"  # agent re-sourcing, not a clinical review


def test_vanadium_glucose_rules_cite_vanadyl_sulfate_trials():
    rule = _rule("RULE_IQM_VANADIUM_DIABETES")
    subs = [_sub_rule(rule, "condition_id", "diabetes")] + [
        _sub_rule(rule, "drug_class_id", dc)
        for dc in ("hypoglycemics_high_risk", "hypoglycemics_lower_risk", "hypoglycemics_unknown")
    ]
    for sub in subs:
        assert sub["sources"] == [_pmid("11238540"), _pmid("10726921")]
        assert "150 mg/day" in sub["mechanism"]
        assert "PTP-1B" not in sub["mechanism"]
    assert [s["severity"] for s in subs] == ["caution", "caution", "monitor", "caution"]
    assert rule["last_reviewed"] == "2026-04-24"  # agent re-sourcing, not a clinical review


MSKCC_EPIMEDIUM = "https://www.mskcc.org/cancer-care/integrative-medicine/herbs/epimedium"
VIAGRA_LABEL = (
    "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?"
    "setid=0b0be196-0c62-461c-94f4-9a35339b4501"
)


def test_horny_goat_weed_rules_say_what_the_pde5_and_case_sources_say():
    rule = _rule("RULE_IQM_HORNY_GOAT_WEED_HEART")
    heart = _sub_rule(rule, "condition_id", "heart_disease")
    antihypertensives = _sub_rule(rule, "drug_class_id", "antihypertensives")

    assert heart["sources"] == [
        MSKCC_EPIMEDIUM, _pmid("18778098"), _pmid("15546831"), VIAGRA_LABEL,
    ]
    # The tachyarrhythmia case says nothing about blood pressure.
    assert antihypertensives["sources"] == [MSKCC_EPIMEDIUM, _pmid("18778098"), VIAGRA_LABEL]
    assert (heart["severity"], antihypertensives["severity"]) == ("caution", "caution")
    assert "tachyarrhythmia" in heart["mechanism"]
    # The nitrate risk is sildenafil's; icariin's own effect is unmeasured.
    assert "extreme hypotension risk" not in heart["action"]
    assert "nitrates" in heart["action"]
    copy = json.dumps([heart, antihypertensives]).lower()
    for stale in ("pde4", "estrogen receptor agonist", "producing additive hypotension"):
        assert stale not in copy, stale
    assert rule["last_reviewed"] == "2026-04-14"  # agent re-sourcing, not a clinical review


def test_black_seed_rules_cite_meta_analyses_and_drop_unsourced_numbers():
    rule = _rule("RULE_IQM_BLACK_SEED_OIL_DIABETES")
    review, glucose_ma, bp_ma = _pmid("34073784"), _pmid("40210172"), _pmid("27512971")
    glucose = [_sub_rule(rule, "condition_id", "diabetes")] + [
        _sub_rule(rule, "drug_class_id", dc)
        for dc in ("hypoglycemics_high_risk", "hypoglycemics_lower_risk", "hypoglycemics_unknown")
    ]
    for sub in glucose:
        assert sub["sources"] == [glucose_ma, review]
        assert "21 mg/dL" in sub["mechanism"]
    for sub in (_sub_rule(rule, "condition_id", "hypertension"),
                _sub_rule(rule, "drug_class_id", "antihypertensives")):
        assert sub["sources"] == [bp_ma]
        assert "3.3 mmHg" in sub["mechanism"]
    anticoagulants = _sub_rule(rule, "drug_class_id", "anticoagulants")
    pregnancy = _sub_rule(rule, "condition_id", "pregnancy")
    assert anticoagulants["sources"] == [review]
    assert "CYP2C9" in anticoagulants["mechanism"]
    assert pregnancy["sources"] == [review] == rule["pregnancy_lactation"]["sources"]
    assert "fetal resorption" in pregnancy["mechanism"]

    copy = json.dumps(rule).lower()
    for stale in ("ppar-gamma", "15-20 mg/dl", "5-10 mmhg", "calcium channel",
                  "thromboxane b2", "uterine-effect", "mild antiplatelet"):
        assert stale not in copy, stale
    assert rule["last_reviewed"] == "2026-04-14"  # agent re-sourcing, not a clinical review


def test_quercetin_rules_cite_thyroid_and_warfarin_studies():
    rule = _rule("RULE_IQM_QUERCETIN_THYROID")
    thyroid = _sub_rule(rule, "condition_id", "thyroid_disorder")
    anticoagulants = _sub_rule(rule, "drug_class_id", "anticoagulants")

    # 29127724's abstract says nothing about thyroid function or warfarin.
    assert thyroid["sources"] == [_pmid("8924586"), _pmid("24447974"), _pmid("39456456")]
    assert anticoagulants["sources"] == [_pmid("36239716"), _pmid("15613018")]
    assert (thyroid["severity"], anticoagulants["severity"]) == ("monitor", "caution")
    assert "authored" in thyroid["mechanism"]
    assert "63%" in anticoagulants["mechanism"]
    assert rule["last_reviewed"] == "2026-04-24"  # agent re-sourcing, not a clinical review


HC_5HTP = "https://webprod.hc-sc.gc.ca/nhpid-bdipsn/atReq?atid=5htp&lang=eng"
MSKCC_5HTP = "https://www.mskcc.org/cancer-care/integrative-medicine/herbs/5-htp-01"


def test_5htp_pregnancy_rules_drop_a_muscle_relaxant_bookshelf_chapter():
    rule = _rule("RULE_IQM_5HTP_SEROTONIN")
    pregnancy = _sub_rule(rule, "condition_id", "pregnancy")
    maois = _sub_rule(rule, "drug_class_id", "maois")
    pregnancy_lactation = rule["pregnancy_lactation"]

    # NBK548375 is LiverTox "Muscle Relaxants"; it never mentions 5-HTP.
    assert "NBK548375" not in json.dumps(rule)
    assert pregnancy["sources"] == [HC_5HTP, _pmid("16023217")]
    assert pregnancy_lactation["sources"] == [HC_5HTP, _pmid("16023217")]
    assert maois["sources"] == [MSKCC_5HTP, HC_5HTP, _pmid("31523132")]
    assert (pregnancy["severity"], maois["severity"]) == ("avoid", "contraindicated")
    assert "Health Canada" in pregnancy["mechanism"]
    assert "linezolid" in maois["mechanism"]
    assert rule["last_reviewed"] == "2026-04-14"  # agent re-sourcing, not a clinical review


def test_no_interaction_rule_cites_the_muscle_relaxant_chapter():
    assert "books/NBK548375" not in json.dumps(RULES)


MSKCC_BORAGE = "https://www.mskcc.org/cancer-care/integrative-medicine/herbs/borage"


def test_borage_seizure_rule_cites_the_borage_case_and_the_epo_counterpoint():
    rule = _rule("RULE_INGREDIENT_BORAGE_SEED_OIL__SEIZURE")
    seizure = _sub_rule(rule, "condition_id", "seizure_disorder")

    assert seizure["sources"] == [_pmid("21387119"), MSKCC_BORAGE, _pmid("17764919")]
    assert (seizure["severity"], seizure["evidence_level"]) == ("monitor", "limited")
    assert "status epilepticus" in seizure["mechanism"].lower()
    assert "spurious" in seizure["mechanism"]
    copy = json.dumps(seizure).lower()
    for stale in ("~24%", "neurotoxic risk", "applies similarly to borage"):
        assert stale not in copy, stale
    assert rule["last_reviewed"] == "2026-04-09"  # agent re-sourcing, not a clinical review


def test_red_yeast_rice_efsa_2025_sentence_cites_the_2025_opinion():
    rule = _rule("RULE_BANNED_RED_YEAST_RICE_STATINS")
    high_cholesterol = _sub_rule(rule, "condition_id", "high_cholesterol")

    assert "EFSA 2025" in high_cholesterol["mechanism"]
    assert _pmid("40027377") in high_cholesterol["sources"]  # EFSA NDA 2025
    assert _pmid("32626016") in high_cholesterol["sources"]  # EFSA ANS 2018
    assert rule["last_reviewed"] == "2026-04-09"  # agent re-sourcing, not a clinical review


def test_chasteberry_pregnancy_mechanism_matches_its_sources():
    rule = _rule("RULE_IQM_CHASTEBERRY_PREGNANCY")
    pregnancy = _sub_rule(rule, "condition_id", "pregnancy")

    assert pregnancy["sources"] == [
        "https://www.nccih.nih.gov/health/chasteberry", _pmid("23136064"),
    ]
    assert "prolactin" in pregnancy["mechanism"]
    assert "NCCIH" in pregnancy["mechanism"]
    for stale in ("D2 receptors", "LH/FSH"):
        assert stale not in pregnancy["mechanism"], stale
    assert rule["last_reviewed"] == "2026-04-26"  # agent re-sourcing, not a clinical review


def test_chondroitin_bleeding_rule_states_the_documented_inr_data():
    rule = _rule("RULE_IQM_CHONDROITIN")
    bleeding = _sub_rule(rule, "condition_id", "bleeding_disorders")

    assert bleeding["sources"] == [_pmid("14986566"), _pmid("18363538")]
    assert "2.3 to 3.9" in bleeding["mechanism"]
    assert "in vitro data suggest" not in bleeding["mechanism"].lower()
    # The 1200 mg BID escalation is reported in Knudsen & Sokol 2008.
    assert bleeding["min_effective_dose"]["source"] == _pmid("18363538")
    assert bleeding["min_effective_dose"]["value"] == 1200
    assert rule["last_reviewed"] == "2026-04-09"  # agent re-sourcing, not a clinical review


def test_green_tea_nadolol_rules_cite_the_primary_trial():
    rule = _rule("RULE_IQM_GREEN_TEA_HYPERTENSION")
    for sub in (_sub_rule(rule, "condition_id", "hypertension"),
                _sub_rule(rule, "drug_class_id", "antihypertensives")):
        assert sub["sources"] == [_pmid("24419562"), _pmid("25312732")]
        assert "85%" in sub["mechanism"]
        assert "OATP1A2" in sub["mechanism"]
    assert rule["last_reviewed"] == "2026-04-23"  # agent re-sourcing, not a clinical review


# Wrong-topic citations removed by the 2026-09 triage: (PMID, rule, sub-rule).
# They must not return to that sub-rule, and must never be exempted instead.
TRIAGE_GHOSTS = (
    ("9464451", "RULE_IQM_RED_CLOVER", "drug:anticoagulants"),
    ("39517207", "RULE_IQM_CITRUS_BERGAMOT_CHOLESTEROL", "drug:statins"),
    ("16800417", "RULE_IQM_SAW_PALMETTO_LIVER", "pregnancy_lactation"),
    ("30980598", "RULE_IQM_SAW_PALMETTO_LIVER", "condition:ttc"),
    ("10902065", "RULE_IQM_SAW_PALMETTO_LIVER", "drug:anticoagulants"),
    ("18431248", "RULE_IQM_VALERIAN_LIVER", "pregnancy_lactation"),
    ("27092496", "RULE_IQM_KAVALACTONES_LIVER", "pregnancy_lactation"),
    ("12083489", "RULE_IQM_COQ10_HEART_DISEASE_STATINS", "condition:heart_disease"),
    ("25997859", "RULE_IQM_WHITE_WILLOW_BARK_BLEEDING", "condition:bleeding_disorders"),
    ("28472675", "RULE_BANNED_TANSY_PREGNANCY", "condition:pregnancy"),
    ("39708247", "RULE_IQM_YERBA_MATE_CARDIOVASCULAR", "drug:anticoagulants"),
    ("28745507", "RULE_IQM_ANDROGRAPHIS", "condition:autoimmune"),
    ("21822619", "RULE_IQM_ANDROGRAPHIS", "condition:autoimmune"),
    ("27912958", "RULE_IQM_BACOPA_THYROID", "condition:thyroid_disorder"),
    ("18296328", "RULE_IQM_L_THEANINE_ANTIHYPERTENSIVES", "drug:antihypertensives"),
    ("15961987", "RULE_IQM_GUARANA", "drug:sedatives"),
    ("21676849", "RULE_IQM_GUARANA", "drug:sedatives"),
    ("19370686", "RULE_IQM_HUPERZINE_A_ANTICHOLINERGICS", "drug:anticholinergics"),
    ("26613955", "RULE_IQM_RHODIOLA_IMMUNE_BP", "drug:sedatives"),
    ("38423354", "RULE_IQM_SAME", "drug:maois"),
    ("31236960", "RULE_IQM_CHINESE_SKULLCAP_LIVER", "condition:pregnancy"),
    ("10902065", "RULE_INGREDIENT_CAT_S_CLAW", "drug:anticoagulants"),
    ("10902065", "RULE_INGREDIENT_EVENING_PRIMROSE_OIL", "drug:anticoagulants"),
    ("10902065", "RULE_INGREDIENT_OMEGA_3", "drug:nsaids"),
    ("35800714", "RULE_IQM_STINGING_NETTLE_DIABETES", "condition:diabetes"),
    ("37958659", "RULE_IQM_VANADIUM_DIABETES", "condition:diabetes"),
    ("29127724", "RULE_IQM_QUERCETIN_THYROID", "condition:thyroid_disorder"),
    ("29127724", "RULE_IQM_QUERCETIN_THYROID", "drug:anticoagulants"),
    ("36017706", "RULE_INGREDIENT_GENISTEIN__THYROID", "drug:thyroid_medications"),
    ("15546831", "RULE_IQM_HORNY_GOAT_WEED_HEART", "drug:antihypertensives"),
)
GHOST_REVIEW = json.loads((DATA / "interaction_rules_ghost_review.json").read_text())


def _cited(rule_id: str, sub_rule: str) -> list[str]:
    rule = _rule(rule_id)
    if sub_rule == "pregnancy_lactation":
        return rule["pregnancy_lactation"]["sources"]
    kind, _, key = sub_rule.partition(":")
    if kind == "condition":
        return _sub_rule(rule, "condition_id", key)["sources"]
    return _sub_rule(rule, "drug_class_id", key)["sources"]


def test_triage_ghost_citations_stay_gone_and_are_never_exempted():
    exempted = {(e["pmid"], e["rule_id"], e["sub_rule"]) for e in GHOST_REVIEW["reviewed"]}
    for pmid, rule_id, sub_rule in TRIAGE_GHOSTS:
        assert _pmid(pmid) not in _cited(rule_id, sub_rule), (pmid, rule_id, sub_rule)
        assert (pmid, rule_id, sub_rule) not in exempted, (pmid, rule_id, sub_rule)


def test_interaction_rules_ghost_review_entries_are_complete_and_current():
    meta = GHOST_REVIEW["_metadata"]
    reviewed = GHOST_REVIEW["reviewed"]
    assert meta["total_entries"] == len(reviewed)
    keys = [(e["pmid"], e["rule_id"], e["sub_rule"]) for e in reviewed]
    assert len(keys) == len(set(keys))
    for entry in reviewed:
        key = (entry["pmid"], entry["rule_id"], entry["sub_rule"])
        for field in ("live_title", "rationale", "reviewed_by", "reviewed_at"):
            assert entry.get(field), (key, field)
        assert len(entry["rationale"]) >= 80, key
        # Agent triage must not read as a clinician or owner review.
        assert "not clinician-reviewed" in entry["reviewed_by"], key
        # A stale exemption (citation since removed) must be deleted with it.
        source_id = entry["pmid"]
        url = (f"https://www.ncbi.nlm.nih.gov/books/{source_id}/"
               if source_id.startswith("NBK") else _pmid(source_id))
        assert url in _cited(entry["rule_id"], entry["sub_rule"]), key


def _min_effective_doses(rule: dict) -> list[dict]:
    found = []
    for sub in (rule.get("condition_rules") or []) + (rule.get("drug_class_rules") or []):
        if isinstance(sub.get("min_effective_dose"), dict):
            found.append(sub["min_effective_dose"])
    return found


def test_chondroitin_anticoagulant_copy_states_the_cited_inr_values():
    """Knudsen & Sokol 2008 (PMID 18363538): INR 2.3 before, 3.9 about three weeks
    after escalating to glucosamine 1500 mg / chondroitin 1200 mg twice a day.
    No readable source states "2.6 to 4.1" (receipt:
    scripts/audits/pending_items_20260926/research.md)."""
    mechanism = _sub_rule(_rule("RULE_IQM_CHONDROITIN"), "drug_class_id", "anticoagulants")["mechanism"]
    assert "2.6 to 4.1" not in mechanism
    assert "2.3" in mechanism and "3.9" in mechanism


def test_chondroitin_dose_floor_cites_the_case_report_that_states_1200_mg_bid():
    """"1200 mg BID" is Knudsen & Sokol's figure (PMID 18363538). PMID 14986566
    is a letter without an abstract, so it cannot carry that number."""
    for floor in _min_effective_doses(_rule("RULE_IQM_CHONDROITIN")):
        if "1200 mg BID" in floor["rationale"]:
            assert floor["source"] == _pmid("18363538"), floor
            assert "14986566" not in floor["rationale"], floor


def test_black_seed_dose_floor_does_not_credit_the_bp_meta_analysis_with_glucose_or_lipids():
    """PMID 27512971 (Sahebkar 2016) is a blood-pressure-only meta-analysis."""
    floors = _min_effective_doses(_rule("RULE_IQM_BLACK_SEED_OIL_DIABETES"))
    assert floors
    for floor in floors:
        if "27512971" in floor["source"] + floor["rationale"]:
            assert "glucose" not in floor["rationale"] and "lipid" not in floor["rationale"], floor


def test_evening_primrose_dose_floor_rationale_matches_its_rabbit_source():
    """PMID 19783511 (Riaz 2009) gave rabbits 90-360 microlitres/kg; it reports no
    human GLA dose and no bleeding time. The 3 g oil floor is the clinical-team
    threshold on the rule's dose_thresholds note."""
    floors = [f for f in _min_effective_doses(_rule("RULE_INGREDIENT_EVENING_PRIMROSE_OIL"))
              if "19783511" in f["source"]]
    assert floors
    for floor in floors:
        assert "300 mg GLA" not in floor["rationale"], floor
        assert "bleeding time" not in floor["rationale"], floor
        assert "rabbit" in floor["rationale"], floor
