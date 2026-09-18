#!/usr/bin/env python3
"""Backfill queue for the 202 legacy records (read-only).

Grandfathered for Phase 1 means temporarily preserved, not permanently exempt.
Each legacy record still needs what newly curated evidence gets: study contexts,
trial-family handling, dose provenance, outcome classification, integrity checks
and a real review state. This orders that work by the catalog exposure the record
actually carries, and shows what it is missing today.

    python3 scripts/audits/evidence_expansion_2026_09/build_legacy_backfill_queue.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "scripts"))

from clinical_applicability import reviewed_entries  # noqa: E402


def main() -> int:
    inventory = json.loads((OUT / "inventory.json").read_text())
    exposure: dict[str, dict] = {}
    for identity in inventory["identities"]:
        for entry_id in identity["registry_entry_ids_key_overlap"]:
            row = exposure.setdefault(entry_id, {"slots": 0, "products": 0, "zero": 0, "le8": 0, "identities": []})
            row["slots"] += identity["slots"]
            row["products"] += identity["products"]
            row["zero"] += identity["evidence_zero_products"]
            row["le8"] += identity["evidence_le8_products"]
            row["identities"].append(identity["canonical_id"])

    rows = []
    for entry_id, entry in reviewed_entries().items():
        hit = exposure.get(entry_id, {"slots": 0, "products": 0, "zero": 0, "le8": 0, "identities": []})
        references = entry.get("references_structured") or []
        rows.append({
            "id": entry_id,
            "standard_name": entry.get("standard_name"),
            "catalog_slots": hit["slots"], "products": hit["products"],
            "evidence_zero_products": hit["zero"], "evidence_le8_products": hit["le8"],
            "identities": sorted(set(hit["identities"])),
            "study_type": entry.get("study_type"), "evidence_level": entry.get("evidence_level"),
            "effect_direction": entry.get("effect_direction"),
            "references": len(references),
            "pmids": len({r.get("pmid") for r in references if r.get("pmid")}),
            "study_contexts": len(entry.get("study_contexts") or []),
            "has_dose_policy": entry.get("min_clinical_dose") is not None
            or (entry.get("applicability") or {}).get("minimum_daily_dose") is not None,
            "has_applicability_scope": entry.get("applicability") is not None,
            "last_updated": entry.get("last_updated"),
            "review_state": "legacy_review_state_not_established",
        })
    rows.sort(key=lambda r: (-r["catalog_slots"], r["id"]))

    missing_contexts = sum(r["study_contexts"] == 0 for r in rows)
    payload = {"_metadata": {
        "records": len(rows), "records_without_study_contexts": missing_contexts,
        "records_without_dose_policy": sum(not r["has_dose_policy"] for r in rows),
        "records_without_applicability_scope": sum(not r["has_applicability_scope"] for r in rows),
        "records_with_no_catalog_exposure": sum(r["catalog_slots"] == 0 for r in rows),
        "note": "Exposure is identity-key overlap in the scorer's key space, not a per-product join."},
        "queue": rows}
    (OUT / "legacy_backfill_queue.json").write_text(json.dumps(payload, indent=1))

    lines = ["# Legacy record backfill queue (the grandfathered 202)", "",
             f"{len(rows)} records. **{missing_contexts}** have no study contexts, "
             f"{payload['_metadata']['records_without_dose_policy']} carry no dose policy, and "
             f"{payload['_metadata']['records_without_applicability_scope']} have no applicability scope. "
             "None has a review state. Ordered by the catalog exposure each record carries.", "",
             "| rank | record | name | slots | products | Ev=0 | Ev≤8 | study_type | direction | refs | PMIDs "
             "| contexts | dose policy | scope | last updated |",
             "|---:|---|---|---:|---:|---:|---:|---|---|---:|---:|---:|---|---|---|"]
    for rank, row in enumerate(rows[:60], 1):
        lines.append(
            f"| {rank} | `{row['id']}` | {row['standard_name']} | {row['catalog_slots']} | {row['products']} | "
            f"{row['evidence_zero_products']} | {row['evidence_le8_products']} | {row['study_type']} | "
            f"{row['effect_direction']} | {row['references']} | {row['pmids']} | {row['study_contexts']} | "
            f"{'yes' if row['has_dose_policy'] else '—'} | {'yes' if row['has_applicability_scope'] else '—'} | "
            f"{row['last_updated']} |")
    lines += ["", f"Records with no catalog exposure at all: {payload['_metadata']['records_with_no_catalog_exposure']} "
              "(they match no identity in the current scored corpus — worth checking whether the identity is "
              "unmapped rather than absent).", ""]
    (OUT / "LEGACY_BACKFILL.md").write_text("\n".join(lines) + "\n")
    print(json.dumps(payload["_metadata"], indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
