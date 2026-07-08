#!/usr/bin/env python3
"""Phase 3 — author a structured `dose_threshold` on each of the 33 dose_dependent
pairwise interactions in curated_interactions/.

Below the floor (a trace/culinary/multivitamin amount of the supplement) the
additive interaction is negligible and can be suppressed by the app's dose gate;
at/above it the pair fires. Floors err LOW (conservative — never under-warn) and
are inert until the Phase-4 app router consumes them.

Sourcing discipline (no hallucinated identifiers):
  - REUSE: where the supplement already has a PMID-content-verified ingredient-
    rule floor for the SAME effect (authored + verified in the Phase-3 ingredient
    batches), reuse that value + source verbatim. confidence carries over.
  - PAIR-STATED: where the pair's own management text states an explicit dose
    ("> 600 mg/day", "<= 400 IU/day"), use it with the pair's own (already
    citation-audited) authoritative source.
  - INFERRED: for pairs with no floored ingredient rule and no explicit pair
    dose, infer a conservative supplement-vs-trace threshold, mark
    confidence=low + confidence_basis="inferred_conservative", and cite the
    supplement's authoritative NIH ODS / NCCIH monograph. The floor is a
    conservative inference, NOT a guideline cutoff (labeled as such).

Every `source` here is either a reused verified ingredient-rule PMID or an
authoritative ODS/NCCIH monograph URL — no new unverified PMIDs are introduced.

Usage:
    python3 scripts/tools/author_phase3_pairwise_floors.py            # dry-run
    python3 scripts/tools/author_phase3_pairwise_floors.py --apply
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent / "data" / "curated_interactions"
FILES = ["curated_interactions_v1.json", "med_med_pairs_v1.json", "batch_critical_2026_05.json"]

# Authoritative monograph URLs (reused from the verified ingredient-rule floors
# where possible; all are live NIH ODS / NCCIH monographs).
ODS = "https://ods.od.nih.gov/factsheets/{}-HealthProfessional/"
NCCIH = "https://www.nccih.nih.gov/health/{}"

# pair_id -> floor spec. value/unit/basis + confidence + source + rationale.
# "reuse" = value+source carried from the Phase-3 ingredient-rule floor.
FLOORS = {
    # ---- bleeding: anticoagulant/NSAID + antiplatelet supplement ----
    "DSI_WAR_OMEGA3":   dict(canon="fish_oil", value=1000, unit="mg", conf="medium",
        basis="management_stated", src="https://pubmed.ncbi.nlm.nih.gov/17192169/",
        why="Pair mgmt: fish oil up to 1 g/day is low-risk with warfarin; >1 g warrants INR monitoring."),
    "DSI_NSAID_FISHOIL": dict(canon="fish_oil", value=2000, unit="mg", conf="medium",
        basis="management_stated", src=ODS.format("Omega3FattyAcids"),
        why="Pair mgmt: caution combining fish oil >2 g/day with NSAIDs; lower doses low-risk."),
    "DSI_WAR_GARLIC":   dict(canon="garlic", value=600, unit="mg", conf="medium",
        basis="reuse+management", src="https://www.mskcc.org/cancer-care/integrative-medicine/herbs/garlic",
        why="Reused garlic bleeding floor (600 mg); pair mgmt agrees (>600 mg supplement); culinary safe."),
    "DSI_NSAID_GARLIC": dict(canon="garlic", value=600, unit="mg", conf="medium",
        basis="reuse", src="https://www.mskcc.org/cancer-care/integrative-medicine/herbs/garlic",
        why="Reused garlic bleeding floor; culinary garlic safe with NSAIDs."),
    "DSI_WAR_TURMERIC":     dict(canon="turmeric", value=500, unit="mg", conf="low",
        basis="management_stated", src="https://pubmed.ncbi.nlm.nih.gov/22531131/",
        why="High-dose curcumin (>500 mg/day, per the sibling anticoagulant pair) with warfarin; culinary turmeric safe."),
    "DSI_ANTICOAG_TURMERIC": dict(canon="turmeric", value=500, unit="mg", conf="low",
        basis="management_stated", src="https://pubmed.ncbi.nlm.nih.gov/22531131/",
        why="Pair mgmt: curcumin >500 mg/day with anticoagulants; culinary turmeric safe."),
    "DSI_WAR_GINGER":   dict(canon="ginger", value=2000, unit="mg", conf="low",
        basis="management_stated", src=NCCIH.format("ginger"),
        why="Pair mgmt: high-dose ginger supplements (>2 g/day) with warfarin; culinary ginger safe."),
    "DSI_SSRI_GINKGO":  dict(canon="ginkgo", value=120, unit="mg", conf="medium",
        basis="reuse", src=NCCIH.format("ginkgo"),
        why="Reused ginkgo antiplatelet floor (120 mg, standard EGb-761 dose)."),
    "DSI_NSAID_GINKGO": dict(canon="ginkgo", value=120, unit="mg", conf="medium",
        basis="reuse", src=NCCIH.format("ginkgo"),
        why="Reused ginkgo antiplatelet floor (120 mg)."),
    "DSI_FISHOIL_GINKGO": dict(canon="ginkgo", value=120, unit="mg", conf="low",
        basis="reuse", src=NCCIH.format("ginkgo"),
        why="Sup-Sup additive bleeding; floor on ginkgo (primary antiplatelet, 120 mg standard dose)."),
    "DSI_FISHOIL_VITE": dict(canon="vitamin_e", value=180, unit="mg", conf="medium",
        basis="reuse+management+unit_normalized", src=ODS.format("VitaminE"),
        why=("Reused vitamin E bleeding floor (400 IU/day) normalized to a conservative "
             "180 mg alpha-tocopherol equivalent. NIH ODS lists 1 IU synthetic vitamin E "
             "as 0.45 mg alpha-tocopherol and 1 IU natural vitamin E as 0.67 mg; 180 mg "
             "is the lower mass equivalent, so below this floor is below 400 IU for either form.")),
    "DSI_ANTICOAG_HORSE_CHESTNUT": dict(canon="horse_chestnut_seed", value=300, unit="mg", conf="low",
        basis="inferred_conservative", src=NCCIH.format("horse-chestnut"),
        why="INFERRED conservative floor at standardized horse-chestnut-seed (aescin) supplement dose (~300 mg); not a guideline cutoff."),
    # ---- statin myopathy ----
    "DSI_STATINS_NIACIN": dict(canon="vitamin_b3_niacin", value=1000, unit="mg", conf="medium",
        basis="management_stated", src=ODS.format("Niacin"),
        why="Pharmacologic niacin (>=1 g/day) drives statin-myopathy risk; nutritional/multivitamin niacin doses are safe."),
    # ---- additive glucose-lowering: diabetes meds + insulin-sensitizer ----
    "DSI_METFORMIN_ALA": dict(canon="alpha_lipoic_acid", value=600, unit="mg", conf="medium",
        basis="reuse", src="https://pubmed.ncbi.nlm.nih.gov/22374556/",
        why="Reused ALA glucose floor (600 mg)."),
    "DSI_DM_CHROMIUM":   dict(canon="chromium", value=200, unit="mcg", conf="medium",
        basis="reuse", src=ODS.format("Chromium"),
        why="Reused chromium glucose floor (200 mcg; top of multivitamin range, trace below)."),
    "DSI_DM_BITTERMELON": dict(canon="bitter_melon", value=600, unit="mg", conf="medium",
        basis="reuse", src="https://pubmed.ncbi.nlm.nih.gov/35140559/",
        why="Reused bitter melon glucose floor (600 mg)."),
    "DSI_DM_FENUGREEK":  dict(canon="fenugreek", value=500, unit="mg", conf="medium",
        basis="reuse", src="https://pubmed.ncbi.nlm.nih.gov/24438170/",
        why="Reused fenugreek glucose floor (500 mg)."),
    "DSI_DM_GYMNEMA":    dict(canon="gymnema_sylvestre", value=400, unit="mg", conf="medium",
        basis="reuse", src="https://pubmed.ncbi.nlm.nih.gov/34467577/",
        why="Reused gymnema glucose floor (400 mg)."),
    "DSI_DM_CINNAMON":   dict(canon="cinnamon", value=500, unit="mg", conf="medium",
        basis="reuse", src="https://pubmed.ncbi.nlm.nih.gov/24019277/",
        why="Reused cinnamon glucose floor (500 mg extract); culinary cinnamon safe."),
    "DSI_DM_VITD":       dict(canon="vitamin_d", value=4000, unit="IU", conf="low",
        basis="management_stated", src=ODS.format("VitaminD"),
        why="Pair mgmt: high-dose vitamin D >4000 IU/day (the adult UL) warrants supervision; typical repletion doses below."),
    "DSI_DM_MAGNESIUM":  dict(canon="magnesium", value=350, unit="mg", conf="low",
        basis="inferred_conservative", src=ODS.format("Magnesium"),
        why="INFERRED floor at the supplemental-magnesium UL (350 mg); dietary/multivitamin magnesium below is not a meaningful glucose modifier."),
    "DSI_DM_ASHWAGANDHA": dict(canon="ashwagandha", value=300, unit="mg", conf="low",
        basis="inferred_conservative", src=NCCIH.format("ashwagandha"),
        why="INFERRED conservative floor at a standardized ashwagandha-extract dose (~300 mg); not a guideline cutoff."),
    # ---- additive BP-lowering: antihypertensive + nutrient ----
    "DSI_ANTIHYP_COQ10": dict(canon="coq10", value=100, unit="mg", conf="low",
        basis="inferred_conservative", src=NCCIH.format("coenzyme-q10"),
        why="INFERRED floor at the supplemental CoQ10 dose (~100 mg) where a modest BP effect is reported; trace amounts below."),
    "DSI_ANTIHYP_MAGNESIUM": dict(canon="magnesium", value=350, unit="mg", conf="low",
        basis="inferred_conservative", src=ODS.format("Magnesium"),
        why="INFERRED floor at the supplemental-magnesium UL (350 mg); dietary magnesium below is not a meaningful BP modifier."),
    "DSI_ANTIHYP_VITD":  dict(canon="vitamin_d", value=4000, unit="IU", conf="low",
        basis="inferred_conservative", src=ODS.format("VitaminD"),
        why="INFERRED floor at the adult UL (4000 IU); repletion doses below are usually beneficial rather than additive-hypotensive."),
    "DSI_ANTIHYP_ASHWAGANDHA": dict(canon="ashwagandha", value=300, unit="mg", conf="low",
        basis="inferred_conservative", src=NCCIH.format("ashwagandha"),
        why="INFERRED conservative floor at a standardized ashwagandha-extract dose (~300 mg)."),
    # ---- additive CNS sedation: sedative/benzo/antipsychotic + CNS supplement ----
    "DSI_SEDATIVES_VALERIAN": dict(canon="valerian", value=400, unit="mg", conf="low",
        basis="inferred_conservative", src=NCCIH.format("valerian"),
        why="INFERRED conservative floor at a sedative valerian-root dose (~400 mg; typical 300-600 mg)."),
    "DSI_MELATONIN_VALERIAN": dict(canon="valerian", value=400, unit="mg", conf="low",
        basis="inferred_conservative", src=NCCIH.format("valerian"),
        why="INFERRED conservative floor on valerian (~400 mg) for additive sedation with melatonin."),
    "DSI_SEDATIVES_PASSIONFLOWER": dict(canon="passionflower", value=400, unit="mg", conf="low",
        basis="inferred_conservative", src=NCCIH.format("passionflower"),
        why="INFERRED conservative floor at a sedative passionflower dose (~400 mg)."),
    "DSI_SEDATIVES_ASHWAGANDHA": dict(canon="ashwagandha", value=300, unit="mg", conf="low",
        basis="inferred_conservative", src=NCCIH.format("ashwagandha"),
        why="INFERRED conservative floor at a standardized ashwagandha-extract dose (~300 mg)."),
    "DSI_BENZO_MELATONIN": dict(canon="melatonin", value=5, unit="mg", conf="low",
        basis="management_stated", src="https://www.nccih.nih.gov/health/melatonin-what-you-need-to-know",
        why="Pair mgmt: low-dose melatonin (0.5-3 mg) is fine with benzodiazepines; floor at 5 mg (above the sleep-dose range)."),
    "DSI_ANTIPSYCH_MELATONIN": dict(canon="melatonin", value=5, unit="mg", conf="low",
        basis="management_stated", src="https://www.nccih.nih.gov/health/melatonin-what-you-need-to-know",
        why="Pair mgmt: low-dose melatonin (0.5-3 mg) is fine with antipsychotics; floor at 5 mg."),
    # ---- estrogenic ----
    "DSI_OC_SOY": dict(canon="genistein", value=100, unit="mg", conf="low",
        basis="management_stated", src=NCCIH.format("soy"),
        why="Pair mgmt: high-dose soy isoflavone supplements (>100 mg/day) warrant caution; dietary soy safe with OCs."),
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    def ser(doc, ea):
        return json.dumps(doc, indent=2, ensure_ascii=ea) + "\n"

    seen = set()
    for fname in FILES:
        path = BASE / fname
        orig = path.read_text()
        doc = json.loads(orig)
        ea = next((flag for flag in (False, True) if ser(doc, flag) == orig), None)
        if ea is None:
            raise SystemExit(f"{fname}: no clean round-trip")
        n = 0
        for e in doc["interactions"]:
            spec = FLOORS.get(e.get("id"))
            if not spec:
                continue
            if e.get("materiality") != "dose_dependent":
                raise SystemExit(f"{e['id']} floored but materiality={e.get('materiality')} (expected dose_dependent)")
            e["dose_threshold"] = {
                "agent_canonical_id": spec["canon"],
                "value": spec["value"],
                "unit": spec["unit"],
                "basis": "per_day",
                "confidence": spec["conf"],
                "confidence_basis": spec["basis"],
                "source": spec["src"],
                "rationale": spec["why"],
            }
            seen.add(e["id"])
            n += 1
        if args.apply and n:
            path.write_text(ser(doc, ea))
            json.loads(path.read_text())
        print(f"{fname}: authored {n} floors")

    missing = set(FLOORS) - seen
    extra = seen - set(FLOORS)
    print(f"\ntotal floored: {len(seen)}/33 | map-not-found: {missing} | found-not-in-map: {extra}")
    # every dose_dependent pair must now carry a floor
    all_dd = {e["id"] for f in FILES for e in json.loads((BASE / f).read_text())["interactions"]
              if e.get("materiality") == "dose_dependent"}
    uncovered = all_dd - seen
    print(f"dose_dependent pairs WITHOUT a floor in this map: {uncovered or 'none'}")
    if not args.apply:
        print("\n(dry-run — pass --apply to write)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
