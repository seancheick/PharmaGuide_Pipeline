#!/usr/bin/env python3
"""
backed_clinical_studies.json — clinical-indication category canonicalization.

Per V1_1_ROADMAP.md §5b.2: 197 entries with 148 distinct `category`
values describing CLINICAL APPLICATION/INDICATION (anti-inflammatory,
joint health, cognitive, etc.) — collapses to 22 controlled buckets.

Canonical 22 buckets:
  Body system:        cardiovascular, joint_bone, digestive_gut,
                      cognitive_neurological, immune, eye_health,
                      skin_hair_collagen, urinary_genitourinary,
                      hormonal_endocrine, sleep_mood, sports_performance
  Mechanism:          anti_inflammatory, antioxidant,
                      adaptogen_stress, mitochondrial_energy,
                      aging_longevity, liver_detox
  Nutrient class:     vitamin_supplement, mineral_supplement,
                      probiotics, general_herbs
  Status:             metabolic_blood_sugar

Multi-indication originals ("antioxidant / detox", "joint/skin", etc.)
are mapped to PRIMARY-INDICATION bucket per inspection. First-pass
automated canonicalization — clinician spot-check pending; non-blocking
for V1.

Idempotent.
"""

import argparse, json, sys
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "backed_clinical_studies.json"


CANONICAL_BUCKETS = {
    "anti_inflammatory", "antioxidant", "cardiovascular",
    "cognitive_neurological", "digestive_gut", "joint_bone",
    "immune", "sleep_mood", "sports_performance",
    "metabolic_blood_sugar", "mitochondrial_energy",
    "skin_hair_collagen", "eye_health", "vitamin_supplement",
    "mineral_supplement", "hormonal_endocrine",
    "urinary_genitourinary", "aging_longevity",
    "liver_detox", "probiotics", "general_herbs",
    "adaptogen_stress",
}


# ---------------------------------------------------------------------------
# Mapping table — every distinct category value → canonical bucket.
# Where multi-indication, picks the PRIMARY (most clinically prominent
# or first-listed) bucket.
# ---------------------------------------------------------------------------

CATEGORY_MAP = {
    # --- ANTI-INFLAMMATORY ---
    "anti-inflammatory":                    "anti_inflammatory",
    "anti-inflammatory / antioxidant":      "anti_inflammatory",
    "anti-inflammatory/sleep":              "anti_inflammatory",
    "pain / inflammation modulation":       "anti_inflammatory",

    # --- ANTIOXIDANT ---
    "antioxidant":                          "antioxidant",
    "antioxidants":                         "antioxidant",
    "antioxidant / detox":                  "antioxidant",
    "antioxidant / cognitive":              "cognitive_neurological",
    "antioxidant / metabolic":              "metabolic_blood_sugar",
    "antioxidant / blood sugar":            "metabolic_blood_sugar",
    "antioxidant / anti-aging":             "aging_longevity",
    "antioxidant / eye health":             "eye_health",
    "antioxidant/thyroid":                  "hormonal_endocrine",

    # --- CARDIOVASCULAR ---
    "cardiovascular":                       "cardiovascular",
    "cardiovascular/exercise":              "cardiovascular",
    "vascular/exercise":                    "cardiovascular",
    "cardiometabolic / vascular":           "cardiovascular",
    "cardiovascular / anti-inflammatory":   "cardiovascular",
    "exercise performance / cardiovascular": "sports_performance",
    "fiber / cardiometabolic":              "cardiovascular",
    "mineral / cardiovascular":             "cardiovascular",
    "mitochondrial / cardiovascular":       "cardiovascular",
    "bone/cardiovascular":                  "joint_bone",
    "methyl donor":                         "cardiovascular",  # SAMe — homocysteine/CV
    "fatty_acids":                          "cardiovascular",  # generic fatty acids → CV

    # --- COGNITIVE / NEUROLOGICAL ---
    "cognitive":                            "cognitive_neurological",
    "cognitive / cholinergic":              "cognitive_neurological",
    "cognitive / energy":                   "cognitive_neurological",
    "cognitive / mitochondrial":            "cognitive_neurological",
    "cognitive / neurological":             "cognitive_neurological",
    "cognitive / nootropic":                "cognitive_neurological",
    "cognitive / sleep":                    "cognitive_neurological",
    "calm/focus":                           "cognitive_neurological",
    "calming/cognitive":                    "cognitive_neurological",
    "amino acid / cognitive":               "cognitive_neurological",
    "amino_acids":                          "cognitive_neurological",
    "nootropic / nerve health":             "cognitive_neurological",
    "vitamin / neurological":               "cognitive_neurological",
    "energy/focus":                         "cognitive_neurological",
    "mitochondrial / cognitive":            "mitochondrial_energy",

    # --- ADAPTOGEN / STRESS ---
    "adaptogen":                            "adaptogen_stress",
    "adaptogen / stress":                   "adaptogen_stress",
    "adaptogen / energy":                   "adaptogen_stress",
    "adaptogen / cognitive":                "adaptogen_stress",
    "stress/weight":                        "adaptogen_stress",
    "energy / adaptogen":                   "adaptogen_stress",
    "immune / adaptogen":                   "adaptogen_stress",
    "testosterone / adaptogen":             "adaptogen_stress",

    # --- JOINT / BONE / CONNECTIVE TISSUE ---
    "joint health":                         "joint_bone",
    "joint/skin":                           "joint_bone",
    "joint/skin health":                    "joint_bone",
    "joint/connective tissue":              "joint_bone",
    "mineral / bone health":                "joint_bone",
    "mineral / bone-energy metabolism":     "joint_bone",
    "trace mineral / bone-hormonal":        "joint_bone",
    "mood/joint":                           "joint_bone",
    "inflammation / joint":                 "joint_bone",

    # --- DIGESTIVE / GUT ---
    "digestive":                            "digestive_gut",
    "digestive / acid support":             "digestive_gut",
    "digestive / inflammation support":     "digestive_gut",
    "digestive / anti-inflammatory":        "digestive_gut",
    "gut health / immune":                  "digestive_gut",
    "gut / barrier":                        "digestive_gut",
    "gut / mucosal":                        "digestive_gut",
    "gastrointestinal support":             "digestive_gut",
    "prebiotic":                            "digestive_gut",
    "prebiotic / digestive":                "digestive_gut",

    # --- IMMUNE ---
    "immune":                               "immune",
    "immune / antiviral":                   "immune",
    "immune / oral health":                 "immune",
    "immune / respiratory":                 "immune",
    "upper respiratory / oral soothing":    "immune",
    "iron/immunity":                        "immune",
    "flavonoid / immune":                   "immune",
    "hormonal / immune":                    "immune",
    "vitamin c / immune":                   "immune",
    "vitamin / immune":                     "immune",
    "mineral / immune":                     "immune",
    "mineral / immune-hematologic":         "immune",
    "antifungal":                           "immune",

    # --- SLEEP / MOOD ---
    "sleep":                                "sleep_mood",
    "sleep / anxiety support":              "sleep_mood",
    "anxiety/sleep":                        "sleep_mood",
    "mood support":                         "sleep_mood",
    "mood / eye health":                    "sleep_mood",
    "mood/sleep":                           "sleep_mood",
    "mood/appetite":                        "sleep_mood",
    "amino acid / sleep":                   "sleep_mood",
    "natural melatonin / sleep":            "sleep_mood",
    "hormone / sleep":                      "sleep_mood",
    "stress / sleep support":               "sleep_mood",

    # --- SPORTS / PERFORMANCE ---
    "sports nutrition":                     "sports_performance",
    "sports nutrition / cognitive":         "sports_performance",
    "sports nutrition / muscle":            "sports_performance",
    "sports performance / neuromuscular":   "sports_performance",
    "testosterone / sports":                "sports_performance",
    "protein / muscle performance":         "sports_performance",
    "energy / men's health":                "sports_performance",

    # --- METABOLIC / BLOOD SUGAR ---
    "metabolic":                            "metabolic_blood_sugar",
    "metabolic health":                     "metabolic_blood_sugar",
    "metabolic_support":                    "metabolic_blood_sugar",
    "metabolic/anti-aging":                 "metabolic_blood_sugar",
    "metabolic / blood sugar":              "metabolic_blood_sugar",
    "blood sugar":                          "metabolic_blood_sugar",
    "blood sugar / metabolic":              "metabolic_blood_sugar",
    "blood sugar / testosterone":           "metabolic_blood_sugar",
    "energy/fat metabolism":                "metabolic_blood_sugar",
    "vitamin / metabolic":                  "metabolic_blood_sugar",
    "hormonal metabolism":                  "metabolic_blood_sugar",

    # --- MITOCHONDRIAL / ENERGY ---
    "mitochondrial":                        "mitochondrial_energy",
    "mitochondrial / energy":               "mitochondrial_energy",
    "energy":                               "mitochondrial_energy",
    "vitamin / energy":                     "mitochondrial_energy",

    # --- SKIN / HAIR / COLLAGEN ---
    "vitamin / hair & skin":                "skin_hair_collagen",
    "hair / skin / nails":                  "skin_hair_collagen",

    # --- EYE HEALTH ---
    "eye health":                           "eye_health",
    "eye health / visual performance":      "eye_health",
    "carotenoid / eye health":              "eye_health",
    "vitamin / eye health":                 "eye_health",

    # --- AGING / LONGEVITY ---
    "anti-aging":                           "aging_longevity",
    "senolytic":                            "aging_longevity",
    "autophagy":                            "aging_longevity",
    "anti-aging / metabolic":               "aging_longevity",

    # --- LIVER / DETOX ---
    "liver support":                        "liver_detox",
    "liver / lipids":                       "liver_detox",

    # --- VITAMIN ---
    "b-vitamin":                            "vitamin_supplement",
    "b_vitamins":                           "vitamin_supplement",
    "multivitamin":                         "vitamin_supplement",
    "vitamin c":                            "vitamin_supplement",
    "coenzyme q10":                         "vitamin_supplement",
    "vitamins":                             "vitamin_supplement",
    "vitamin / antioxidant":                "vitamin_supplement",
    "alfalfa":                              "vitamin_supplement",

    # --- MINERAL ---
    "mineral":                              "mineral_supplement",
    "minerals":                             "mineral_supplement",
    "mineral absorption":                   "mineral_supplement",
    "mineral complex":                      "mineral_supplement",
    "mineral / nervous system":             "mineral_supplement",
    "mineral / neuromuscular":              "mineral_supplement",
    "mineral / antioxidant enzyme support": "mineral_supplement",
    "mineral / thyroid":                    "mineral_supplement",

    # --- HORMONAL / ENDOCRINE ---
    "thyroid support":                      "hormonal_endocrine",

    # --- URINARY / GENITOURINARY ---
    "urinary health":                       "urinary_genitourinary",
    "prostate_health":                      "urinary_genitourinary",

    # --- PROBIOTICS ---
    "probiotics":                           "probiotics",
    "probiotic / stress":                   "probiotics",

    # --- GENERAL HERBS ---
    "herbs":                                "general_herbs",
    "absorption enhancer":                  "general_herbs",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    # Validate map targets
    bad_targets = [(k, v) for k, v in CATEGORY_MAP.items()
                   if v not in CANONICAL_BUCKETS]
    if bad_targets:
        print(f"FATAL: map targets not in canonical buckets: {bad_targets}",
              file=sys.stderr)
        return 2

    with open(DATA_PATH) as f:
        data = json.load(f)
    arr = data["backed_clinical_studies"]

    changes = []
    unmapped = []
    for e in arr:
        cur = e.get("category", "")
        if cur in CATEGORY_MAP:
            new = CATEGORY_MAP[cur]
            if cur != new:
                changes.append((e.get("id"), cur, new))
                e["category"] = new
        elif cur in CANONICAL_BUCKETS:
            pass  # already canonical (probiotics, etc.)
        elif cur:
            unmapped.append((e.get("id"), cur))

    if unmapped:
        print(f"WARNING: {len(unmapped)} entries with categories not in CATEGORY_MAP:")
        for eid, c in unmapped[:20]:
            print(f"  {eid}: {c!r}")
        return 2

    if not changes:
        print("clinical studies cleanup already applied — no-op.")
        return 0

    print(f"Renaming {len(changes)} entries to canonical buckets")
    from collections import Counter
    final = Counter(e.get("category", "") for e in arr)
    print(f"\nFinal distribution ({len(final)} canonical buckets):")
    for c, n in final.most_common():
        flag = "✓" if c in CANONICAL_BUCKETS else "✗"
        print(f"  {flag} {n:3d}  {c}")

    if args.dry_run:
        print(f"\n[dry-run] would write {DATA_PATH}")
        return 0

    md = data.get("_metadata", {})
    md["last_updated"] = "2026-04-30"
    data["_metadata"] = md

    with open(DATA_PATH, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"\nWrote {DATA_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
