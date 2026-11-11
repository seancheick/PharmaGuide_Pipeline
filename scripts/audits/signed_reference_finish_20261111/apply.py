"""Signed "does not score" records finish as reference-only (Sean, 2026-11-11; ADR-0007).

Five backed_clinical_studies records whose signed contexts are all scoring_eligible False
become reference-only: the record's research conclusion is recorded and finishes Evidence
at no credit. Fields that still asserted a benefit are rewritten from the verified sources.
INGR_OMEGA3 stays held (research.md). Receipts: research.md beside this file.
Run from the repo root with $PG_PYTHON.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
import data_batch  # noqa: E402

BACKED = ROOT / "scripts/data/backed_clinical_studies.json"
TODAY = "2026-11-11"
AGENT = (" Agent review with an independent agent check, 2026-11-11; not clinician review. "
         "Reference-only under ADR-0007: the review is finished and carries no Evidence points.")

PATCHES = {
    "INGR_ELDERBERRY": {
        "notes": (
            "Small randomized trials of proprietary elderberry extracts suggest possible shorter or milder "
            "colds and flu, but a GRADE-rated systematic review (PMID 33827515) judged this evidence low to "
            "very low certainty and found no clear effect on getting a cold; an earlier pooled analysis of "
            "180 participants (PMID 30670267) reported larger benefits but does not change that assessment. "
            "NCCIH describes the evidence as preliminary. The data do not justify antiviral or "
            "oseltamivir-equivalence claims." + AGENT),
        "notable_studies": (
            "PMID 33827515 (2021 systematic review, GRADE): low to very low certainty evidence of shorter "
            "symptom duration; no clear effect on cold incidence; no support for cytokine-storm concerns. "
            "PMID 30670267 (2019 pooled analysis, 180 participants): reported reduced upper-respiratory "
            "symptoms. Trials are small and preparation-specific."),
        "effect_direction_rationale": (
            "Descriptive direction mixed, low confidence: positive findings come from small "
            "preparation-specific trials that the GRADE-rated review (PMID 33827515) judged low to very low "
            "certainty. Legacy registry and enrollment totals were not reconciled trial-family counts and "
            "are removed."),
        "key_endpoints": [
            "Cold and flu symptom duration: low to very low certainty evidence (PMID 33827515)",
            "Cold incidence: no clear effect (PMID 33827515)",
        ],
        "effect_direction": "mixed",
        "effect_direction_confidence": "low",
        "health_goals_supported": [],
        "endpoint_relevance_tags": [],
        "total_enrollment": None,
        "registry_completed_trials_count": None,
    },
    "INGR_L_CARNITINE": {
        "notes": (
            "Meta-analyses report less post-exercise soreness and short-lived falls in muscle-damage markers "
            "(PMID 32154768) and a modest average weight loss of about 1.2 kg, mainly in adults with "
            "overweight or obesity (PMID 32359762), but these pooled mixed carnitine forms with inconsistent "
            "regimens. Longer-term studies show performance effects only in specific settings and raised "
            "fasting TMAO (PMID 32958033). NIH ODS describes the performance and weight evidence as mixed or "
            "equivocal. This record is not proof of energy, cardiovascular, fat-burning or "
            "athletic-performance efficacy. Included trial 26666519 carries expression of concern 36852455."
            + AGENT),
        "effect_direction_rationale": (
            "Descriptive direction mixed: recovery and modest weight outcomes were favorable in pooled "
            "analyses of mixed forms and regimens, while performance findings were conditional and long-term "
            "TMAO implications are unresolved. Not presented as universal efficacy."),
        "effect_direction_confidence": "medium",
        "health_goals_supported": [],
        "endpoint_relevance_tags": [],
    },
    "INGR_VITAMIN_D3": {
        "notes": (
            "Scope is supplementation outcomes only. An earlier pooled analysis found vitamin D3 modestly "
            "lowered the risk of acute respiratory infections (PMID 28202713), but the larger 2025 update by "
            "the same researchers (40 trials, 61,589 participants) found no statistically significant "
            "protection (PMID 39993397), and a review in older adults found little or no difference "
            "(PMID 38787821). The musculoskeletal reference (PMID 30293909) found no fracture or fall "
            "prevention and no clinically meaningful BMD gain from supplementation. Vitamin D's "
            "physiological role in calcium absorption is well established but is not a supplementation "
            "outcome; products still receive vitamin D's nutrition-authority Evidence floor. OWNERSHIP: this "
            "file owns INTERVENTION evidence (what a trial showed). Product-facing goal_matches are owned by "
            "the bone_health synergy cluster in synergy_cluster.json, which carries the NUTRIENT-FUNCTION "
            "relationship (vitamin D aids calcium absorption, NIH ODS) and is unaffected by this record. Do "
            "not restore a bone goal here to 'fix' a goal_matches question." + AGENT),
        "notable_studies": (
            "Martineau et al. (2017, PMID 28202713) individual-participant-data meta-analysis reported fewer "
            "acute respiratory infections, clearest in deficient individuals. Jolliffe et al. (2025, PMID "
            "39993397), the updated analysis of 40 trials and 61,589 participants, found no statistically "
            "significant protection (OR 0.94, 95% CI 0.88 to 1.00). Bolland et al. (2018, PMID 30293909) "
            "found that vitamin D did not prevent fractures or falls or meaningfully improve BMD."),
        "effect_direction_rationale": (
            "Descriptive direction mixed, low confidence: the 2017 pooled benefit (PMID 28202713) was not "
            "confirmed by the larger 2025 update (PMID 39993397). The earlier automated strong-benefit "
            "classification and its unverified registry and enrollment aggregates are removed."),
        "key_endpoints": [
            "Acute respiratory infection risk: reduced in a 2017 pooled analysis, not significant in the "
            "larger 2025 update (PMIDs 28202713, 39993397)",
            "Fractures, falls and BMD: no meaningful benefit (PMID 30293909)",
        ],
        "effect_direction": "mixed",
        "effect_direction_confidence": "low",
        "health_goals_supported": [],
        "endpoint_relevance_tags": [],
        "total_enrollment": None,
        "registry_completed_trials_count": None,
        "applicability": None,  # removed: its immune_support outcome came from the superseded benefit reading
    },
    "BRAND_ASTAREAL": {
        "notes": (
            "The only human study of this astaxanthin preparation (PMID 22428137), written entirely by staff "
            "of the manufacturer, reported some skin wrinkle, elasticity and moisture-loss improvements in a "
            "small six-week placebo-controlled trial in men and in an uncontrolled oral-plus-topical study in "
            "women; no independent trial has confirmed these skin effects. No eye-strain or exercise outcome "
            "is supported by this record. PMID 31221944 is BioCell cartilage, not astaxanthin, and is "
            "excluded." + AGENT),
        "notable_studies": (
            "Tominaga et al. (2012, PMID 22428137), Fuji Chemical Industry authors: a placebo-controlled oral "
            "study in 36 men and an uncontrolled oral-plus-topical study in 30 women reported selected skin "
            "endpoints. No independent replication."),
        "effect_direction_rationale": (
            "No descriptive direction: one manufacturer-authored publication, one arm uncontrolled, no "
            "independent trial. The earlier strong-benefit label and registry aggregate are removed."),
        "effect_direction": None,
        "effect_direction_confidence": "low",
        "health_goals_supported": [],
        "endpoint_relevance_tags": [],
        "total_enrollment": None,
        "registry_completed_trials_count": None,
    },
    "BRAND_TESTOFEN": {
        "notes": (
            "A sponsor-funded 12-week trial of this fenugreek extract reported improved aging-male symptom "
            "scores, sexual function and testosterone (PMID 26791805), but a later trial of a standardised "
            "fenugreek extract at the same 600 mg/day in men with prostate enlargement found no change in "
            "testosterone (PMID 31828857), and a 2026 meta-analysis found at most a small total-testosterone "
            "effect, rated very low certainty, and concluded the evidence does not support "
            "testosterone-boosting claims (PMID 42688439). PMID 21312304 tested Testofen with "
            "added minerals and measured libido and self-reported satisfaction, not objective strength."
            + AGENT),
        "effect_direction_rationale": (
            "Descriptive direction mixed, low confidence: sponsor-funded positive findings (PMIDs 26791805, "
            "21312304) are not supported for testosterone by a later trial in men with prostate enlargement "
            "(PMID 31828857) or a 2026 meta-analysis (PMID 42688439). The earlier strong-benefit label is "
            "removed."),
        "effect_direction": "mixed",
        "effect_direction_confidence": "low",
        "health_goals_supported": [],
        "endpoint_relevance_tags": [],
        "total_enrollment": None,
        "registry_completed_trials_count": None,
    },
}

CARNITINE_OLD = ("Weight review 32359762 remains pending an attributable constituent-integrity/sensitivity "
                 "and primary extraction disposition; included trial")
CARNITINE_NEW = ("Weight review 32359762 is finished as a bounded noncredit preparation-transfer "
                 "assessment; included trial")


def main():
    data = data_batch.load(BACKED)
    records = {r["id"]: r for r in data["backed_clinical_studies"]}
    for rid, patch in PATCHES.items():
        rec = records[rid]
        for key, value in patch.items():
            if key == "applicability":
                assert key in rec, rid
                del rec[key]
                continue
            rec[key] = value
        rec["study_type"] = "reference"
        rec["evidence_level"] = "reference"
        rec["last_updated"] = TODAY
    hits = 0
    for ctx in records["INGR_L_CARNITINE"]["study_contexts"]:
        lims = ctx.get("limitations") or []
        for i, text in enumerate(lims):
            if CARNITINE_OLD in text:
                lims[i] = text.replace(CARNITINE_OLD, CARNITINE_NEW)
                hits += 1
    assert hits == 1, hits
    data_batch.save(BACKED, data)


if __name__ == "__main__":
    main()
