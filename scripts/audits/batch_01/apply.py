"""Apply med–nutrient content audit BATCH 01 to the canonical source.

Per-entry, explicit, and self-verifying (no silent skips): sets the
citation_review_status assigned after live-literature verification (see
research.md), stamps reviewed_at/reviewer, and removes the two PubMed-confirmed
ghost references (replacing them with the content-verified primary sources).

Idempotent. Run: python3 scripts/audits/batch_01/apply.py
"""

import json
import os

SOURCE = os.path.join(
    os.path.dirname(__file__), os.pardir, os.pardir, "data", "medication_depletions.json"
)
REVIEWED_AT = "2026-07-23"
REVIEWER = "lead_clinician_audit_2026_07"

STATUS = {
    "DEP_METFORMIN_VITAMINB12": "verified",
    "DEP_STATINS_COQ10": "verified",
    "DEP_CORTICOSTEROIDS_CALCIUM": "verified",
    "DEP_ANTACIDS_VITAMINB12": "needs_revision",
    "DEP_ANTACIDS_MAGNESIUM": "needs_revision",
    "DEP_DIURETICS_POTASSIUM": "needs_revision",
    "DEP_DIURETICS_MAGNESIUM": "needs_revision",
    "DEP_CORTICOSTEROIDS_VITAMIND": "needs_revision",
    "DEP_ANTICONVULSANTS_VITAMIND": "needs_revision",
    "DEP_LEVOTHYROXINE_CALCIUM": "needs_revision",
    "DEP_LEVOTHYROXINE_IRON": "needs_revision",
}

GHOST_URL_FRAGMENTS = ("/19174283/", "/3003511/")

# Content-verified primary replacements for the two ghost citations.
REPLACEMENTS = {
    "DEP_LEVOTHYROXINE_CALCIUM": [
        {
            "source_type": "reference",
            "label": "Singh N et al. Effect of calcium carbonate on the absorption of "
            "levothyroxine. JAMA. 2000;283(21):2822-5",
            "url": "https://pubmed.ncbi.nlm.nih.gov/10838651/",
        },
        {
            "source_type": "reference",
            "label": "Singh N et al. The acute effect of calcium carbonate on the "
            "intestinal absorption of levothyroxine. Thyroid. 2001;11(10):967-71",
            "url": "https://pubmed.ncbi.nlm.nih.gov/11716045/",
        },
    ],
    "DEP_DIURETICS_MAGNESIUM": [
        {
            "source_type": "reference",
            "label": "Ellison DH. Divalent cation transport by the distal nephron. "
            "Am J Physiol Renal Physiol. 2000;279(4):F616-25",
            "url": "https://pubmed.ncbi.nlm.nih.gov/10997911/",
        },
        {
            "source_type": "reference",
            "label": "Dai LJ et al. Cellular mechanisms of chlorothiazide and cellular "
            "potassium depletion on Mg2+ uptake in distal convoluted tubule cells. "
            "Kidney Int. 1997;51(4):1008-17",
            "url": "https://pubmed.ncbi.nlm.nih.gov/9083264/",
        },
    ],
}


def main() -> int:
    with open(SOURCE, encoding="utf-8") as f:
        doc = json.load(f)
    by = {e["id"]: e for e in doc["depletions"]}

    missing = [eid for eid in STATUS if eid not in by]
    assert not missing, f"batch entries not found: {missing}"

    for eid, status in STATUS.items():
        e = by[eid]
        e["citation_review_status"] = status
        e["reviewed_at"] = REVIEWED_AT
        e["reviewer"] = REVIEWER

    for eid, repl in REPLACEMENTS.items():
        e = by[eid]
        before = len(e["sources"])
        e["sources"] = [
            s
            for s in e["sources"]
            if not any(g in s.get("url", "") for g in GHOST_URL_FRAGMENTS)
        ]
        removed = before - len(e["sources"])
        assert removed == 1, f"{eid}: expected to remove exactly 1 ghost, removed {removed}"
        # only add replacements the entry doesn't already carry (idempotent)
        have = {s.get("url") for s in e["sources"]}
        e["sources"].extend(s for s in repl if s["url"] not in have)

    # Global invariants before writing.
    for eid, e in by.items():
        for s in e.get("sources", []):
            for g in GHOST_URL_FRAGMENTS:
                assert g not in s.get("url", ""), f"{eid} still cites ghost {g}"
    marked = sum(
        1
        for e in doc["depletions"]
        if e.get("citation_review_status") in ("verified", "needs_revision")
    )
    assert marked == len(STATUS), f"expected {len(STATUS)} marked, got {marked}"

    with open(SOURCE, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"applied {len(STATUS)} status marks + {len(REPLACEMENTS)} ghost fixes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
