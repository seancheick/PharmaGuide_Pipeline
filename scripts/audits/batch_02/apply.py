"""Apply med–nutrient content audit BATCH 02 to the canonical source.

Per-entry, explicit, self-verifying, idempotent. Sets citation_review_status +
reviewed_at/reviewer, and firms up citations on the verified entries (relabel
vague-but-real PubMed labels, replace one placeholder source, add primary
anchors). The 2 OCP entries are marked needs_revision; their larger revision
(reframe + evidence downgrade + the over-UL B6 dose) is the tracked follow-up.

Run: python3 scripts/audits/batch_02/apply.py
"""

import json
import os

SOURCE = os.path.join(
    os.path.dirname(__file__), os.pardir, os.pardir, "data", "medication_depletions.json"
)
REVIEWED_AT = "2026-07-23"
REVIEWER = "lead_clinician_audit_2026_07"

STATUS = {
    "DEP_ANTICOAGULANTS_VITAMINK": "verified",
    "DEP_ORLISTAT_VITAMIND": "verified",
    "DEP_CHOLESTYRAMINE_VITAMINK": "verified",
    "DEP_SULFASALAZINE_FOLATE": "verified",
    "DEP_COLCHICINE_VITAMINB12": "verified",
    "DEP_METHOTREXATE_FOLATE": "verified",
    "DEP_ISONIAZID_VITAMINB6": "verified",
    "DEP_SSRIS_SODIUM": "verified",
    "DEP_OCP_VITAMINB6": "needs_revision",
    "DEP_OCP_FOLATE": "needs_revision",
}

# Relabel a real-but-vaguely-labelled source (matched by URL fragment).
RELABEL = {
    "DEP_ISONIAZID_VITAMINB6": {
        "/21477422/": "van der Watt JJ et al. Polyneuropathy, anti-tuberculosis "
        "treatment and the role of pyridoxine in the HIV/AIDS era: a systematic "
        "review. Int J Tuberc Lung Dis. 2011;15(6):722-8",
    },
    "DEP_METHOTREXATE_FOLATE": {
        "/18020507/": "Morgan SL, Baggott JE, Alarcon GS. Methotrexate in "
        "rheumatoid arthritis: folate supplementation should always be given. "
        "BioDrugs. 1997;8(3):164-75",
    },
}

# Remove a placeholder source (matched by URL fragment).
REMOVE = {
    "DEP_SSRIS_SODIUM": ["Sodium-HealthProfessional"],
}

# Add primary anchors (idempotent by URL).
ADD = {
    "DEP_SSRIS_SODIUM": [
        {
            "source_type": "pubmed",
            "label": "De Picker L et al. Antidepressants and the risk of "
            "hyponatremia: a class-by-class review of literature. Psychosomatics. "
            "2014;55(6):536-47",
            "url": "https://pubmed.ncbi.nlm.nih.gov/25262043/",
        }
    ],
    "DEP_METHOTREXATE_FOLATE": [
        {
            "source_type": "pubmed",
            "label": "Shea B et al. Folic acid and folinic acid for reducing side "
            "effects in patients receiving methotrexate for rheumatoid arthritis. "
            "Cochrane Database Syst Rev. 2013;(5):CD000951",
            "url": "https://pubmed.ncbi.nlm.nih.gov/23728635/",
        }
    ],
    "DEP_COLCHICINE_VITAMINB12": [
        {
            "source_type": "pubmed",
            "label": "Webb DI et al. Mechanism of vitamin B12 malabsorption in "
            "patients receiving colchicine. N Engl J Med. 1968;279(16):845-50",
            "url": "https://pubmed.ncbi.nlm.nih.gov/5677718/",
        }
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

    for eid, relabels in RELABEL.items():
        for frag, new_label in relabels.items():
            hits = [s for s in by[eid]["sources"] if frag in s.get("url", "")]
            assert len(hits) == 1, f"{eid}: expected 1 source matching {frag}, got {len(hits)}"
            hits[0]["label"] = new_label

    for eid, frags in REMOVE.items():
        e = by[eid]
        e["sources"] = [
            s for s in e["sources"] if not any(f in s.get("url", "") for f in frags)
        ]

    for eid, new_sources in ADD.items():
        e = by[eid]
        have = {s.get("url") for s in e["sources"]}
        e["sources"].extend(s for s in new_sources if s["url"] not in have)

    # Invariants.
    marked = sum(
        1
        for e in doc["depletions"]
        if e.get("citation_review_status") in ("verified", "needs_revision")
    )
    # 11 from batch 01 (1 verified + 10 needs_revision) + 10 from batch 02.
    assert marked >= len(STATUS), f"expected >= {len(STATUS)} marked, got {marked}"
    ssri_urls = " ".join(s.get("url", "") for s in by["DEP_SSRIS_SODIUM"]["sources"])
    assert "/25262043/" in ssri_urls and "Sodium-HealthProfessional" not in ssri_urls

    with open(SOURCE, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"applied {len(STATUS)} status marks + source firm-ups (relabel/replace/add)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
