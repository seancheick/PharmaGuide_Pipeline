#!/usr/bin/env python3
"""Scored-artifact A/B comparator — Phase-3 integration gate (2026-09-20).

Compares two ``drive_pipeline_ab.py`` scored_records.jsonl arms and reports the
release-gate outputs the team asked for: score changes with component
attribution, quarantine exits/entries, every Safety-gate change, changes
outside the expected defect families, and the largest score deltas.

Usage:
  compare_scored_arms.py --before ARM/re scored_records.jsonl \
      --after OTHER/scored_records.jsonl --out scored_diff.json \
      [--expected-ids changed_ids.json] [--baseline-ids phase3_ids.json]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

# Fields whose change is a scored-conclusion change (not bookkeeping).
CONCLUSION_FIELDS = (
    "quality_score_v4_100",
    "raw_score_v4_100",
    "display_100",
    "quality_tier",
    "grade",
    "verdict",
    "scoring_status",
    "quality_score_status",
    "quality_score_suppressed_reason",
    "score_unavailable_reason",
    "blocking_reason",
    "not_scorable_reason",
    "safety_verdict",
    "product_safety_status",
    "safety_decision",
    "safety_signal_reason",
)
BOOKKEEPING_FIELDS = {"scored_date", "_config_fingerprint", "run_id"}


def load(path: Path) -> dict:
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        record = json.loads(line)
        out[str(record.get("dsld_id"))] = record
    return out


def score_of(record: dict):
    for field in ("quality_score_v4_100", "display_100", "raw_score_v4_100"):
        value = record.get(field)
        if isinstance(value, (int, float)):
            return float(value), field
    return None, None


def readiness_of(record: dict):
    ready = record.get("assessment_readiness") or {}
    disposition = (ready.get("catalog_disposition") or {}).get("disposition")
    reason = record.get("score_unavailable_reason") or record.get("blocking_reason")
    return {
        "disposition": disposition,
        "score_unavailable_reason": reason,
        "not_scorable_reason": record.get("not_scorable_reason"),
        "blocking_reason": record.get("blocking_reason"),
        "scoring_status": record.get("scoring_status"),
    }


def blocked(record: dict, readiness: dict) -> bool:
    """True when the artifact carries a quarantine/blocking condition."""
    status = str(record.get("scoring_status") or "")
    if status and status != "scored":
        return True
    for field in (
        "score_unavailable_reason",
        "blocking_reason",
        "not_scorable_reason",
        "quality_score_suppressed_reason",
    ):
        if record.get(field):
            return True
    if readiness.get("disposition") not in (None, "score_candidate"):
        return True
    return False


def safety_of(record: dict):
    gate = record.get("_v4_safety_gate") or {}
    return {
        "verdict": record.get("safety_verdict"),
        "status": record.get("product_safety_status"),
        "decision": record.get("safety_decision"),
        "signal_reason": record.get("safety_signal_reason"),
        "gate_verdict": gate.get("verdict"),
        "gate_decision": gate.get("safety_decision"),
        "gate_quarantine_required": gate.get("quarantine_required"),
        "gate_quarantine_reason": gate.get("quarantine_reason"),
        "gate_blocking_reason": gate.get("blocking_reason"),
        "gate_signals": gate.get("safety_signals"),
        "gate_matched_substance": gate.get("matched_substance"),
        "clean_label_hits": gate.get("clean_label_hits"),
        "review_records": record.get("_safety_review_records"),
        "dose_safety": record.get("_dose_safety"),
    }


def breakdown_of(record: dict):
    payload = record.get("_module_breakdown") or {}
    if not isinstance(payload, dict):
        return {}
    components = payload.get("components") if isinstance(payload.get("components"), dict) else payload
    return {
        key: value
        for key, value in components.items()
        if isinstance(value, (int, float))
    }


def deep_diff(before, after, path="") -> list:
    out = []
    if isinstance(before, dict) and isinstance(after, dict):
        for key in sorted(set(before) | set(after)):
            out.extend(deep_diff(before.get(key), after.get(key), f"{path}/{key}"))
    elif isinstance(before, list) and isinstance(after, list):
        if before != after:
            out.append({"path": path, "before": before, "after": after})
    elif before != after:
        out.append({"path": path, "before": before, "after": after})
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--before", required=True)
    parser.add_argument("--after", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--expected-ids", help="JSON list of cleaner-level changed ids")
    parser.add_argument("--baseline-ids", help="JSON list of baseline/quarantined ids")
    parser.add_argument("--label-before", default="before")
    parser.add_argument("--label-after", default="after")
    args = parser.parse_args()

    before = load(Path(args.before))
    after = load(Path(args.after))
    expected = set()
    if args.expected_ids:
        expected = {str(x) for x in json.loads(Path(args.expected_ids).read_text())}
    baseline = set()
    if args.baseline_ids:
        baseline = {str(x) for x in json.loads(Path(args.baseline_ids).read_text())}

    shared = sorted(set(before) & set(after), key=lambda x: int(x) if x.isdigit() else x)
    report: dict = {
        "before_arm": args.label_before,
        "after_arm": args.label_after,
        "records_before": len(before),
        "records_after": len(after),
        "records_compared": len(shared),
        "only_in_before": sorted(set(before) - set(after)),
        "only_in_after": sorted(set(after) - set(before)),
        "crash_like_before": sorted(
            [k for k, v in before.items() if str(v.get("scoring_status") or "").startswith(("error", "crash"))]
        ),
        "crash_like_after": sorted(
            [k for k, v in after.items() if str(v.get("scoring_status") or "").startswith(("error", "crash"))]
        ),
        "score_changes": [],
        "conclusion_changes": [],
        "quarantine_exits": [],
        "quarantine_entries": [],
        "safety_changes": [],
        "outside_expected_families": [],
        "bookkeeping_only_changes": [],
    }

    for dsld_id in shared:
        left, right = before[dsld_id], after[dsld_id]
        left_score, field = score_of(left)
        right_score, _ = score_of(right)
        name = right.get("product_name") or left.get("product_name")

        changed_fields = {
            key
            for key in set(left) | set(right)
            if key not in BOOKKEEPING_FIELDS and left.get(key) != right.get(key)
        }
        conclusion_fields = sorted(changed_fields & set(CONCLUSION_FIELDS))

        if left_score is not None and right_score is not None and left_score != right_score:
            components_before = breakdown_of(left)
            components_after = breakdown_of(right)
            component_deltas = {
                key: {
                    "before": components_before.get(key),
                    "after": components_after.get(key),
                    "delta": (components_after.get(key, 0) - components_before.get(key, 0)),
                }
                for key in sorted(set(components_before) | set(components_after))
                if components_before.get(key) != components_after.get(key)
            }
            report["score_changes"].append(
                {
                    "dsld_id": dsld_id,
                    "name": name,
                    "score_field": field,
                    "before": left_score,
                    "after": right_score,
                    "delta": round(right_score - left_score, 4),
                    "component_deltas": component_deltas,
                    "conclusion_fields": conclusion_fields,
                    "readiness_before": readiness_of(left),
                    "readiness_after": readiness_of(right),
                }
            )

        if conclusion_fields:
            entry = {
                "dsld_id": dsld_id,
                "name": name,
                "fields": conclusion_fields,
            }
            if "safety_verdict" in changed_fields or "product_safety_status" in changed_fields:
                entry["safety_before"] = safety_of(left)
                entry["safety_after"] = safety_of(right)
            report["conclusion_changes"].append(entry)

        readiness_before, readiness_after = readiness_of(left), readiness_of(right)
        if readiness_before != readiness_after:
            # The artifact's own quarantine signal is ``scoring_status`` +
            # ``score_unavailable_reason`` (what the frozen triage baseline
            # keyed on); ``catalog_disposition`` alone under-reports it.
            was_blocked = blocked(left, readiness_before)
            is_blocked = blocked(right, readiness_after)
            entry = {
                "dsld_id": dsld_id,
                "name": name,
                "before": readiness_before,
                "after": readiness_after,
                "in_baseline_quarantine": dsld_id in baseline if baseline else None,
            }
            if was_blocked and not is_blocked:
                report["quarantine_exits"].append(entry)
            elif is_blocked and not was_blocked:
                report["quarantine_entries"].append(entry)

        if safety_of(left) != safety_of(right):
            report["safety_changes"].append(
                {
                    "dsld_id": dsld_id,
                    "name": name,
                    "before": safety_of(left),
                    "after": safety_of(right),
                    "gate_diff": deep_diff(safety_of(left), safety_of(right)),
                }
            )

        if expected and dsld_id not in expected and conclusion_fields:
            report["outside_expected_families"].append(
                {"dsld_id": dsld_id, "name": name, "fields": conclusion_fields}
            )

        if changed_fields and not conclusion_fields and not (
            left_score is not None and right_score is not None and left_score != right_score
        ):
            report["bookkeeping_only_changes"].append(
                {"dsld_id": dsld_id, "fields": sorted(changed_fields)}
            )

    report["score_changes"].sort(key=lambda item: abs(item["delta"]), reverse=True)
    report["largest_score_deltas"] = report["score_changes"][:25]
    report["summary"] = {
        "records_compared": report["records_compared"],
        "score_changes": len(report["score_changes"]),
        "conclusion_changes": len(report["conclusion_changes"]),
        "quarantine_exits": len(report["quarantine_exits"]),
        "quarantine_entries": len(report["quarantine_entries"]),
        "safety_changes": len(report["safety_changes"]),
        "outside_expected_families": len(report["outside_expected_families"]),
        "bookkeeping_only_changes": len(report["bookkeeping_only_changes"]),
        "max_abs_delta": max(
            (abs(item["delta"]) for item in report["score_changes"]), default=0
        ),
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1, sort_keys=True), encoding="utf-8")
    print(json.dumps(report["summary"], indent=1))
    print(f"detail -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
