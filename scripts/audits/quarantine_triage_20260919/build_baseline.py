#!/usr/bin/env python3
"""Freeze the 2026-09-19 quarantine triage baseline.

Runs BEFORE any remediation change. Produces, under
reports/quarantine_triage_2026_09_19/:

  baseline_products.json        one row per quarantined product: issue tokens,
                                per-dimension gate readiness, conflict rows
  SUMMARY.md                    human-readable population breakdown
  phase2_banned_candidate_ids.json
                                the FROZEN candidate set for the Phase-2
                                safety-gate wiring fix: quarantined products
                                with at least one identity-conflict row whose
                                only recognition is banned_recalled_ingredients.
                                Phase 2 acceptance = only this set may move.

Read-only over scripts/dist, scripts/products/*_enriched, scripts/products/*_scored.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
DIST = REPO / "scripts" / "dist"
PRODUCTS = REPO / "scripts" / "products"
OUT = REPO / "reports" / "quarantine_triage_2026_09_19"

ROW_IDX = re.compile(r"ingredientRows\[\d+\](?:\.nestedRows\[\d+\])*")


def token_issue(p: str) -> str:
    return ROW_IDX.sub("ingredientRows[N]", p.strip())


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((DIST / "export_manifest.json").read_text())
    excluded = manifest.get("excluded_by_gate") or []
    quarantined: dict[str, dict] = {}
    for e in excluded:
        dsld = str(e.get("dsld_id"))
        quarantined[dsld] = {
            "dsld_id": dsld,
            "issue_tokens": sorted({
                token_issue(part)
                for part in (e.get("error") or "").split(";")
                if part.strip()
            }),
        }

    # join enriched (conflict rows, names) and scored (gate readiness) by dsld_id
    enriched_idx: dict[str, dict] = {}
    for path in sorted(PRODUCTS.glob("*_enriched/enriched/enriched_*.json")):
        data = json.loads(path.read_text())
        for rec in (data if isinstance(data, list) else []):
            dsld = str(rec.get("dsld_id"))
            if dsld in quarantined and dsld not in enriched_idx:
                enriched_idx[dsld] = rec

    scored_idx: dict[str, dict] = {}
    for path in sorted(PRODUCTS.glob("*_scored/scored/scored_*.json")):
        data = json.loads(path.read_text())
        for rec in (data if isinstance(data, list) else []):
            dsld = str(rec.get("dsld_id"))
            if dsld in quarantined and dsld not in scored_idx:
                scored_idx[dsld] = rec

    conflict_counter: Counter = Counter()
    source_counter: Counter = Counter()
    banned_candidates: list[dict] = []
    additive_conflict_products: set[str] = set()

    for dsld, row in quarantined.items():
        erec = enriched_idx.get(dsld) or {}
        row["product_name"] = erec.get("fullName") or erec.get("name")
        row["brand_name"] = erec.get("brand_name") or erec.get("brandName")
        conflicts = []
        iqd = erec.get("ingredient_quality_data") or {}
        for ing in iqd.get("ingredients") or []:
            if not isinstance(ing, dict):
                continue
            if ing.get("identity_disposition") != "identity_conflict":
                continue
            src = ing.get("recognition_source")
            conflicts.append({
                "source_label_name": ing.get("source_label_name")
                or ing.get("label_display_name"),
                "identity_decision_reason": ing.get("identity_decision_reason"),
                "recognition_source": src,
                "safety_identity_id": ing.get("safety_identity_id"),
                "score_eligible_by_cleaner": ing.get("score_eligible_by_cleaner"),
                "role_classification": ing.get("role_classification"),
            })
            conflict_counter[str(ing.get("source_label_name") or ing.get("label_display_name"))] += 1
            source_counter[str(src)] += 1
            if src == "banned_recalled_ingredients":
                additive_conflict_products.discard(dsld)  # banned dominates below
        row["conflict_rows"] = conflicts

        srec = scored_idx.get(dsld) or {}
        readiness = srec.get("_v4_assessment_readiness") or {}
        row["gate_readiness"] = {
            dim: {
                "readiness": (readiness.get(dim) or {}).get("readiness"),
                "reason_code": (readiness.get(dim) or {}).get("reason_code"),
            }
            for dim in readiness.get("enforced_dimensions") or []
        }
        row["score_unavailable_reason"] = srec.get("score_unavailable_reason")
        row["enriched_found"] = dsld in enriched_idx
        row["scored_found"] = dsld in scored_idx

    # banned candidate set: >=1 conflict row recognized from banned_recalled_ingredients
    for dsld, row in quarantined.items():
        srcs = {c.get("recognition_source") for c in row["conflict_rows"]}
        if "banned_recalled_ingredients" in srcs:
            banned_candidates.append({
                "dsld_id": dsld,
                "product_name": row.get("product_name"),
                "banned_ids": sorted({
                    c.get("safety_identity_id")
                    for c in row["conflict_rows"]
                    if c.get("recognition_source") == "banned_recalled_ingredients"
                }),
            })
            additive_conflict_products.discard(dsld)

    (OUT / "baseline_products.json").write_text(json.dumps(quarantined, indent=1))
    (OUT / "phase2_banned_candidate_ids.json").write_text(json.dumps({
        "_metadata": {
            "purpose": "Phase-2 safety-gate wiring acceptance set (FROZEN)",
            "contract": "only these dsld_ids may change disposition from the "
                        "Phase-2 fix; every mover must reconcile to the "
                        "canonical banned-safety wiring; zero unrelated movers",
            "baseline_release": "2026.09.19.082814",
            "generated_at_commit": "ad577f49b7d2cca21dc8cda7c3a002af54e90fc9",
            "candidate_count": len(banned_candidates),
        },
        "candidates": banned_candidates,
    }, indent=1))

    gate_counter: Counter = Counter()
    for row in quarantined.values():
        codes = tuple(sorted(
            f"{dim}:{d.get('reason_code') or d.get('readiness')}"
            for dim, d in row["gate_readiness"].items()
            if d.get("readiness") and d.get("readiness") != "complete"
        ))
        gate_counter["; ".join(codes) or "all-complete"] += 1

    lines = [
        "# Quarantine triage baseline — 2026-09-19",
        "",
        f"Baseline release: `2026.09.19.082814` · quarantined products: **{len(quarantined)}**",
        "",
        "## Conflict rows by ingredient name",
        "",
    ]
    for nm, v in conflict_counter.most_common():
        lines.append(f"- {v:4d} × {nm}")
    lines += ["", "## Conflict rows by recognition source", ""]
    for src, v in source_counter.most_common():
        lines.append(f"- {v:4d} × {src}")
    lines += ["", "## Gate readiness reason codes (from scored artifacts)", ""]
    for code, v in gate_counter.most_common():
        lines.append(f"- {v:4d} × {code}")
    lines += [
        "",
        f"## Phase-2 banned-safety candidate set",
        "",
        f"- {len(banned_candidates)} products (see phase2_banned_candidate_ids.json)",
        "",
        "## Files",
        "",
        "- `baseline_products.json` — full per-product baseline",
        "- `phase2_banned_candidate_ids.json` — frozen Phase-2 acceptance set",
    ]
    (OUT / "SUMMARY.md").write_text("\n".join(lines) + "\n")

    print(f"quarantined={len(quarantined)} "
          f"conflict_rows={sum(conflict_counter.values())} "
          f"banned_candidates={len(banned_candidates)} "
          f"additive_conflict_products={len(additive_conflict_products)}")
    print(f"missing enriched: {sum(1 for r in quarantined.values() if not r['enriched_found'])}, "
          f"missing scored: {sum(1 for r in quarantined.values() if not r['scored_found'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
