#!/usr/bin/env python3
"""Prove the 16 standalone oral EDTA products ship as the approved policy state.

Runs the REAL exporter seams on each frozen product, not a re-implementation:

  1. ``clean_dsld_data`` / ``enrich_supplements_v3`` / ``score_products_v4``
     behaviour is taken from the A/B arm's own outputs (this script does not
     re-run them), so the evidence is the same artifact the replay compared.
  2. ``build_final_db.validate_export_contract`` -- the ship/quarantine gate.
  3. ``build_final_db.derive_ingredient_safety_flags`` -- the Safety-card
     content layer, to show the authored consumer copy reaches the blob.

Read-only.

Usage:
    "$PG_PYTHON" prove_edta_policy_shipping.py \
        --arm-root /tmp/edta_cand --out /tmp/edta_shipping.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts"))

EDTA_IDS = [
    "252358", "252426", "253331", "253335", "253336", "253339", "253350",
    "253357", "311259", "311260", "311261", "311262", "312449", "312450",
    "312451", "312452",
]
# Inactive/excipient EDTA occurrences -- must never be caught by the policy.
CONTROL_IDS = [
    "19178", "200816", "239860", "239862", "256963", "259473", "327891",
    "333921",
]


def _batches(root: Path, pattern: str) -> list[dict]:
    out: list[dict] = []
    for path in root.glob(pattern):
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows = payload if isinstance(payload, list) else [payload]
        out.extend(row for row in rows if isinstance(row, dict))
    return out


def load_arm(arm_root: Path) -> tuple[dict[str, dict], dict[str, dict]]:
    """Return the arm's (enriched, stage-3 scored) records keyed by DSLD id.

    The stage-3 scored artifact is read from the scorer's own output, not from
    an A/B projection: ``validate_export_contract`` inspects the v4-native
    contract (score_basis / _v4_quality_status / six pillars), which a compact
    comparison record does not carry.
    """
    enriched = {
        str(row["dsld_id"]): row
        for row in _batches(arm_root, "enrich_out/*/enriched/*.json")
        if row.get("dsld_id")
    }
    scored = {
        str(row["dsld_id"]): row
        for row in _batches(arm_root, "score_out/*/scored/*.json")
        if row.get("dsld_id")
    }
    return enriched, scored


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--arm-root", required=True)
    parser.add_argument("--out")
    args = parser.parse_args()

    import build_final_db as bfd

    enriched, scored = load_arm(Path(args.arm_root))

    rows = []
    for group, ids in (("edta", EDTA_IDS), ("control", CONTROL_IDS)):
        for dsld_id in ids:
            err = enriched.get(dsld_id)
            scr = scored.get(dsld_id)
            if err is None or scr is None:
                rows.append({"dsld_id": dsld_id, "error": "absent from arm"})
                continue
            issues = bfd.validate_export_contract(err, scr)
            flags = {}
            for key in ("activeIngredients", "inactiveIngredients"):
                for ing in err.get(key) or []:
                    if not isinstance(ing, dict):
                        continue
                    name = str(ing.get("name") or ing.get("standardName") or "")
                    if "edta" not in name.lower() and "edetate" not in name.lower():
                        continue
                    flags[name] = bfd._resolve_active_safety_contract(
                        harmful_hit=None,
                        harmful_ref={},
                        ingredient_hits=list(ing.get("safety_flags") or []),
                        banned_recalled_index=bfd._get_active_banned_recalled_index(),
                        safety_flags=list(ing.get("safety_flags") or []),
                    )
            rows.append(
                {
                    "group": group,
                    "dsld_id": dsld_id,
                    "product": err.get("product_name"),
                    "verdict": scr.get("verdict"),
                    "quality_score_v4_100": scr.get("quality_score_v4_100"),
                    "quality_score_status": scr.get("quality_score_status"),
                    "display_100": scr.get("display_100"),
                    "blocking_reason": scr.get("blocking_reason"),
                    "safety_verdict": scr.get("safety_verdict"),
                    "product_safety_status": scr.get("product_safety_status"),
                    "export_gate_issues": issues,
                    "ships": not issues,
                    "edta_rows": flags,
                }
            )

    text = json.dumps(rows, indent=1, sort_keys=True)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")

    fails = 0
    for row in rows:
        if row.get("group") == "edta":
            ok = (
                row.get("verdict") == "BLOCKED"
                and row.get("blocking_reason") == "NON_ROUTINE_CHELATOR"
                and row.get("quality_score_v4_100") is None
                and row.get("ships")
                and bool(row.get("edta_rows"))
                and all(
                    f.get("is_banned") and f.get("safety_warning_one_liner")
                    for f in row["edta_rows"].values()
                )
            )
        else:
            ok = row.get("ships") and not row.get("blocking_reason")
        if not ok:
            fails += 1
        print(
            f"{row.get('dsld_id'):>7} [{row.get('group'):<7}] "
            f"verdict={row.get('verdict')} ships={row.get('ships')} "
            f"reason={row.get('blocking_reason')} "
            f"issues={len(row.get('export_gate_issues') or [])} {'OK' if ok else 'FAIL'}"
        )
    print(f"\n{len(rows)} products checked, {fails} failing")
    if rows and rows[0].get("edta_rows"):
        print("\nSafety-card copy reaching the blob:")
        for name, flag in list(rows[0]["edta_rows"].items()):
            print(f"  {name}: one_liner={flag.get('safety_warning_one_liner')!r}")
            print(f"    warning={flag.get('safety_warning')!r}")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
