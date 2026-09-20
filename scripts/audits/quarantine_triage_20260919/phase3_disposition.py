#!/usr/bin/env python3
"""Phase-3 quarantined-population disposition table — integration gate (2026-09-20).

For every product in the frozen Phase-3 quarantine baseline, classify the
integrated result:

  fixed_mechanically            — blocked at baseline, scoreable now, and the
                                  cleaner/identity delta is an accepted fix
  already_scoreable_at_base     — the frozen baseline was already stale for this
                                  product before the accepted commits
  still_quarantined_correctly   — still blocked, and the blocker is a genuine
                                  missing dose / unresolved identity
  needs_safety_policy_review    — EDTA-family (policy, not engineering)
  needs_source_refresh          — source record must be re-retrieved
  needs_clinical_review         — clinical judgement required
  return_to_engineering         — a pipeline defect remains
  other                         — anything not yet explained

Usage:
  phase3_disposition.py --baseline reports/.../baseline_products.json \
      --before ARM_A/scored_records.jsonl --after ARM_B/scored_records.jsonl \
      --cleaner-diff diff_base_int.json --out phase3_disposition.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

EDTA_TOKENS = ("edta",)
MARKER_TOKENS = ("miroestrol", "withaferin")


def load_jsonl(path: Path) -> dict:
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            record = json.loads(line)
            out[str(record.get("dsld_id"))] = record
    return out


def blocked(record: dict) -> bool:
    if str(record.get("scoring_status") or "") != "scored":
        return True
    return any(
        record.get(field)
        for field in (
            "score_unavailable_reason",
            "blocking_reason",
            "not_scorable_reason",
            "quality_score_suppressed_reason",
        )
    )


def classify(
    dsld_id: str,
    baseline_entry: dict,
    before: dict | None,
    after: dict | None,
    cleaner_entry: dict | None,
    groups: dict,
) -> tuple:
    if after is None:
        return "other", "product absent from the integrated replay"
    conflict_names = [
        str(row.get("source_label_name") or "").lower()
        for row in baseline_entry.get("conflict_rows") or []
    ]
    joined = " ".join(conflict_names)
    gate = baseline_entry.get("gate_readiness") or {}
    dose_reason = (gate.get("dose") or {}).get("reason_code")
    identity_reason = (gate.get("identity") or {}).get("reason_code")
    reasons = (cleaner_entry or {}).get("reasons") or []

    if any(token in joined for token in EDTA_TOKENS) or dsld_id in groups["safety_policy"]:
        return (
            "needs_safety_policy_review",
            "standalone orally-marketed EDTA product (or explicit safety_policy_review_required); "
            "BLOCKED/hidden treatment is a pending safety-policy decision",
        )

    if dsld_id in groups["unit_receipt"]:
        return (
            "needs_source_refresh",
            "E2 unit-corruption family: a reviewed correction receipt (label image / manufacturer source) "
            "is required; no plausibility conversion is permitted",
        )

    if dsld_id in groups["bulk1340"]:
        if dsld_id == "243808":
            return (
                "needs_clinical_review",
                "max-labeled-exposure UL finding (niacin/magnesium) plus a per-SKU review; the folate row "
                "duplication is an additional engineering defect (see note)",
            )
        return (
            "needs_clinical_review",
            "max-labeled-exposure UL finding at the label's own maxDailyServings, plus completeness anomalies",
        )

    if dsld_id in groups["intentional"]:
        return (
            "intentional_non_scoreable",
            "product class is intentionally non-scoreable (emergency-use / external-use designation)",
        )

    if not blocked(after):
        if before is not None and not blocked(before):
            return "already_scoreable_at_base", "scoreable before the accepted commits"
        return (
            "fixed_mechanically",
            f"gate cleared; cleaner/identity delta families = {reasons or ['identity-resolution']}",
        )

    if any(token in joined for token in MARKER_TOKENS):
        return "needs_clinical_review", "standardization-marker product still blocked downstream"

    reason = after.get("score_unavailable_reason") or after.get("blocking_reason") or after.get(
        "not_scorable_reason"
    )
    if dose_reason in ("no_scoreable_active_dose", "no_score_eligible_active_rows"):
        return (
            "still_quarantined_correctly",
            f"genuine missing/undosed actives ({dose_reason}); no dose may be inferred",
        )
    if identity_reason in (
        "scoring_identity_incomplete",
        "missing_sports_relevant_identity",
        "unmapped_source_actives",
    ):
        return (
            "still_quarantined_correctly",
            f"unresolved ingredient identity remains ({identity_reason}); identity must not be guessed",
        )
    if reason:
        return "return_to_engineering", f"blocked after integration with reason {reason!r}"
    return "other", "blocked with no reason code recorded"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--before", required=True)
    parser.add_argument("--after", required=True)
    parser.add_argument("--cleaner-diff", required=True)
    parser.add_argument("--e2-ids", default="223563,223572,231334,231335,263865,328644")
    parser.add_argument("--bulk1340-ids", default="228823,243799,243808,243812,243815")
    parser.add_argument("--intentional-ids", default="315691")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    groups = {
        "unit_receipt": {t.strip() for t in args.e2_ids.split(",") if t.strip()},
        "bulk1340": {t.strip() for t in args.bulk1340_ids.split(",") if t.strip()},
        "intentional": {t.strip() for t in args.intentional_ids.split(",") if t.strip()},
        "safety_policy": set(),
    }

    baseline = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    before = load_jsonl(Path(args.before))
    after = load_jsonl(Path(args.after))
    cleaner = json.loads(Path(args.cleaner_diff).read_text(encoding="utf-8"))
    cleaner_by_id = {str(item["id"]): item for item in cleaner.get("changed", [])}

    rows = []
    counts: dict = {}
    for dsld_id in sorted(baseline, key=lambda x: int(x) if x.isdigit() else x):
        entry = baseline[dsld_id]
        if str(entry.get("score_unavailable_reason") or "") == "safety_policy_review_required":
            groups["safety_policy"].add(dsld_id)
        disposition, reason = classify(
            dsld_id,
            entry,
            before.get(dsld_id),
            after.get(dsld_id),
            cleaner_by_id.get(dsld_id),
            groups,
        )
        counts[disposition] = counts.get(disposition, 0) + 1
        after_record = after.get(dsld_id) or {}
        rows.append(
            {
                "dsld_id": dsld_id,
                "product": entry.get("product_name"),
                "brand": entry.get("brand_name"),
                "baseline_gate": {
                    "score_unavailable_reason": entry.get("score_unavailable_reason"),
                    "dose": (entry.get("gate_readiness") or {}).get("dose"),
                    "identity": (entry.get("gate_readiness") or {}).get("identity"),
                },
                "conflict_rows": [
                    {
                        "name": row.get("source_label_name"),
                        "recognition_source": row.get("recognition_source"),
                        "safety_identity_id": row.get("safety_identity_id"),
                    }
                    for row in entry.get("conflict_rows") or []
                ],
                "integrated_state": {
                    "scoring_status": after_record.get("scoring_status"),
                    "score_unavailable_reason": after_record.get("score_unavailable_reason"),
                    "blocking_reason": after_record.get("blocking_reason"),
                    "not_scorable_reason": after_record.get("not_scorable_reason"),
                    "score": after_record.get("quality_score_v4_100"),
                    "safety_verdict": after_record.get("safety_verdict"),
                    "safety_signal_reason": after_record.get("safety_signal_reason"),
                },
                "cleaner_delta_families": (cleaner_by_id.get(dsld_id) or {}).get("reasons"),
                "disposition": disposition,
                "reason": reason,
                "owner": {
                    "fixed_mechanically": "engineering (done)",
                    "already_scoreable_at_base": "none",
                    "still_quarantined_correctly": "none (by design)",
                    "needs_safety_policy_review": "safety policy owner",
                    "needs_clinical_review": "licensed pharmacist",
                    "needs_source_refresh": "data pipeline owner + reviewer (correction receipt)",
                    "intentional_non_scoreable": "none (by design)",
                    "return_to_engineering": "engineering",
                    "other": "integrator",
                }.get(disposition),
            }
        )

    payload = {"counts": counts, "products": rows}
    Path(args.out).write_text(json.dumps(payload, indent=1, sort_keys=True), encoding="utf-8")
    print(json.dumps(counts, indent=1))
    print(f"detail -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
