#!/usr/bin/env python3
"""One read-only pass over the per-brand enriched + scored corpora (2026-09-17).

Writes a slim JSONL, one row per unique scored product, holding only what the
Phase 1 evidence audit needs: the shipped Evidence pillar, the scorable active
rows, and the evidence joins as the production scorer sees them.

Evidence joins are NOT re-derived here. They come from the production seam:
``generic_evidence.resolved_clinical_matches`` (accepted) and
``clinical_applicability.filter_clinical_matches`` over the enricher's matches
plus the scorer's contract recoveries (rejected, with the scorer's reason code).
Nothing in scripts/data or scripts/products is written.

    python3 scripts/audits/evidence_expansion_2026_09/extract_corpus.py --out <slim.jsonl>
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "scoring_v4" / "modules"))

from clinical_applicability import filter_clinical_matches, reviewed_entries  # noqa: E402
from scoring_v4.modules import generic_evidence as ge  # noqa: E402

ROW_FIELDS = ("name", "standard_name", "canonical_id", "form_id", "matched_form", "category",
              "quantity", "unit_normalized", "has_dose", "mapped", "identity_confidence",
              "is_proprietary_blend", "parent_blend", "is_nested_ingredient", "raw_source_path",
              "role_classification", "form_unmapped", "source_section", "score_exclusion_reason")
ACTIVE_ROLES = {"active_scorable", "recognized_non_scorable", "active_unmapped"}


def _evidence_pillar(scored: dict) -> float | None:
    pillar = ((scored.get("quality_pillars_v4") or {}).get("evidence") or {})
    value = pillar.get("score")
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _entry_summary(entry_id: str) -> dict:
    ref = reviewed_entries().get(entry_id) or {}
    return {"id": entry_id, "study_type": ref.get("study_type"), "evidence_level": ref.get("evidence_level"),
            "effect_direction": ref.get("effect_direction"), "in_registry": bool(ref)}


def _slim(brand_dir: str, scored: dict, enriched: dict) -> dict:
    iq = enriched.get("ingredient_quality_data") or {}
    # Every active row, not only IQM-scorable ones: recognized non-scorable actives still
    # join evidence by name, and label-active rows the enricher demoted explain Evidence=0.
    rows = [{k: r.get(k) for k in ROW_FIELDS} for r in iq.get("ingredients") or []
            if isinstance(r, dict) and (r.get("role_classification") in ACTIVE_ROLES
                                        or r.get("source_section") == "active")]
    enricher_matches = [m for m in (enriched.get("evidence_data") or {}).get("clinical_matches") or []
                        if isinstance(m, dict)]
    accepted, recovered = ge.resolved_clinical_matches(enriched)
    recovered_all = ge._recover_contract_evidence_matches(enriched, list(enricher_matches))
    _, rejected = filter_clinical_matches(enriched, enricher_matches + recovered_all)
    breakdown = (scored.get("_v4_module_breakdown") or {}).get("dimensions") or {}
    ev_meta = ((breakdown.get("evidence") or {}).get("metadata") or {})
    return {
        "dsld_id": str(scored.get("dsld_id")),
        "brand_dir": brand_dir,
        "brand_name": scored.get("brand_name"),
        "product_name": scored.get("product_name"),
        "module": scored.get("_v4_module"),
        "quality_status": scored.get("_v4_quality_status"),
        "quality_score_v4_100": scored.get("_v4_quality_score_100"),
        "evidence": _evidence_pillar(scored),
        "evidence_metadata": {k: ev_meta.get(k) for k in (
            "matched_entries", "ingredient_points", "sub_clinical_canonicals", "recovered_matches",
            "primary_evidence_floor", "primary_evidence_floor_canonical",
            "nutrition_authority_floor_applied", "flags") if k in ev_meta},
        "total_scorable_active_count": iq.get("total_scorable_active_count"),
        "unmapped_scorable_count": iq.get("unmapped_scorable_count"),
        "skipped_reasons_breakdown": iq.get("skipped_reasons_breakdown") or {},
        "unmapped_actives": scored.get("unmapped_actives") or [],
        "mapped_coverage": scored.get("mapped_coverage"),
        "rows": rows,
        "enricher_match_ids": sorted({str(m.get("id")) for m in enricher_matches if m.get("id")}),
        "accepted_matches": [_entry_summary(str(ge._entry_id(m))) | {"recovered": m in recovered}
                             for m in accepted],
        "rejected_matches": [{"id": r.get("id"), "reason_code": r.get("reason_code"), "status": r.get("status")}
                             for r in rejected],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    seen: set[str] = set()
    duplicates = written = missing_enriched = 0
    with args.out.open("w") as handle:
        for scored_dir in sorted(glob.glob(str(ROOT / "scripts/products/output_*_scored"))):
            brand_dir = Path(scored_dir).name.removeprefix("output_").removesuffix("_scored")
            scored_by_id = {}
            for path in sorted(glob.glob(f"{scored_dir}/scored/*.json")):
                for product in json.load(open(path)):
                    if product.get("_v4_quality_status") == "scored":
                        scored_by_id.setdefault(str(product.get("dsld_id")), product)
            pending = dict(scored_by_id)
            for path in sorted(glob.glob(str(ROOT / f"scripts/products/output_{brand_dir}_enriched/enriched/*.json"))):
                for enriched in json.load(open(path)):
                    dsld_id = str(enriched.get("dsld_id"))
                    scored = pending.pop(dsld_id, None)
                    if scored is None:
                        continue
                    if dsld_id in seen:
                        duplicates += 1
                        continue
                    seen.add(dsld_id)
                    handle.write(json.dumps(_slim(brand_dir, scored, enriched), sort_keys=True) + "\n")
                    written += 1
            missing_enriched += len(pending)
            print(f"{brand_dir}: scored={len(scored_by_id)} unpaired={len(pending)}", file=sys.stderr)
    print(json.dumps({"written": written, "duplicate_dsld_ids_skipped": duplicates,
                      "scored_without_enriched": missing_enriched}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
