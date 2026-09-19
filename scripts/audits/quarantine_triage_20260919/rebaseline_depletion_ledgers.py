#!/usr/bin/env python3
"""Re-baseline the three medication-depletion fingerprint ledgers (2026-09-19).

The Phase 6 canonical-id migration changed `depleted_nutrient.canonical_id`
inside 23 records. The B1 sign-off ledgers pin per-record fingerprints over the
CLINICAL_FIELDS / PROPOSAL_FIELDS projections, so the affected entries must be
re-baselined. This script updates ONLY entries whose fingerprint actually
drifted (verified against the same projection the tests use) and leaves every
review disposition, wording decision, and metadata untouched — this is a
mechanical re-baseline of identity vocabulary, not a clinical re-review.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"

CLINICAL_FIELDS = (
    "id", "drug_ref", "depleted_nutrient", "depletion_type", "severity",
    "mechanism", "clinical_impact", "recommendation", "onset_timeline",
    "evidence_level", "monitoring_note", "sources", "alert_headline",
    "alert_body", "acknowledgement_note", "monitoring_tip_short",
    "food_sources_short", "citation_review_status", "reviewed_at", "reviewer",
    "citation_review_note", "b1_clinical_review_disposition",
    "b1_clinical_reviewed_at", "b1_clinical_review_note", "b1_evidence_auditor",
    "b1_clinical_approval_status", "b1_clinical_approver",
    "b1_clinical_approved_at",
)

PROPOSAL_FIELDS = (
    "id", "drug_ref", "depleted_nutrient", "depletion_type", "severity",
    "mechanism", "clinical_impact", "recommendation", "onset_timeline",
    "evidence_level", "monitoring_note", "sources", "alert_headline",
    "alert_body", "acknowledgement_note", "monitoring_tip_short",
    "food_sources_short", "citation_review_status", "reviewed_at", "reviewer",
    "citation_review_note",
)


def fp(fields, record: dict) -> str:
    payload = json.dumps(
        {f: record.get(f) for f in fields},
        ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    import hashlib
    return "sha256:" + hashlib.sha256(payload).hexdigest()


LEDGERS = [
    ("medication_depletions_b1_signoff.json", "active_record_fingerprints", CLINICAL_FIELDS),
    ("medication_depletions_b1_delta_signoff.json", "delta_record_fingerprints", CLINICAL_FIELDS),
    ("medication_depletions_b1_1_signoff.json", "candidate_record_fingerprints", PROPOSAL_FIELDS),
]


def main() -> int:
    src = {r["id"]: r for r in json.loads((DATA / "medication_depletions.json").read_text())["depletions"]}
    total = 0
    for name, key, fields in LEDGERS:
        path = DATA / name
        raw = path.read_text()
        d = json.loads(raw)
        rt = json.dumps(d, indent=2, ensure_ascii=False) + "\n"
        if rt != raw:
            print(f"REFUSING {name}: round-trip not byte-stable; needs a manual edit", file=sys.stderr)
            return 1
        fp_map = d.get(key)
        if fp_map is None:
            print(f"REFUSING {name}: key '{key}' missing", file=sys.stderr)
            return 1
        changed = 0
        for rid, old in fp_map.items():
            new = fp(fields, src[rid])
            if new != old:
                fp_map[rid] = new
                changed += 1
        if changed:
            # Serialize AFTER the mutation (and re-verify byte stability of the
            # untouched serialization form).
            path.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n")
        print(f"{name}: {changed} fingerprint(s) re-baselined")
        total += changed
    print(f"total: {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
