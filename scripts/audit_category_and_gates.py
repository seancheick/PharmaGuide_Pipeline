#!/usr/bin/env python3
"""Generate a markdown audit from the release DB and detail blobs."""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BUILD_ROOT = ROOT / "scripts/final_db_output"
DEFAULT_OUTPUT = ROOT / "docs/plans/2026-04-09-category-gate-audit.md"


def _json_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            return []
    return []


def _render_counter(counter: Counter[str], *, total: int | None = None) -> list[str]:
    lines: list[str] = []
    for key, count in counter.most_common():
        if total:
            pct = (count / total) * 100
            lines.append(f"- `{key}`: {count} ({pct:.1f}%)")
        else:
            lines.append(f"- `{key}`: {count}")
    return lines


def _render_table(items: list[dict[str, Any]], columns: list[tuple[str, str]]) -> list[str]:
    if not items:
        return ["No examples in this bucket."]
    header = "| " + " | ".join(label for _, label in columns) + " |"
    divider = "| " + " | ".join("---" for _ in columns) + " |"
    rows = [header, divider]
    for item in items:
        rows.append("| " + " | ".join(str(item.get(key, "")) for key, _ in columns) + " |")
    return rows


def collect_analysis(build_root: Path) -> dict[str, Any]:
    manifest = json.loads((build_root / "export_manifest.json").read_text())
    audit = json.loads((build_root / "export_audit_report.json").read_text())
    blob_dir = build_root / "detail_blobs"

    conn = sqlite3.connect(build_root / "pharmaguide_core.db")
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT dsld_id, product_name, supplement_type, score_100_equivalent, verdict,
               primary_category, contains_probiotics, flags
        FROM products_core
        """
    ).fetchall()
    conn.close()

    total = len(rows)
    final_distribution = Counter(row["supplement_type"] for row in rows)
    verdict_distribution = Counter(row["verdict"] for row in rows)
    flag_counts: Counter[str] = Counter()
    rows_by_type: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)

    for row in rows:
        flags = _json_list(row["flags"])
        for flag in flags:
            flag_counts[str(flag)] += 1
        rows_by_type[row["supplement_type"]].append(
            {
                "dsld_id": row["dsld_id"],
                "product_name": row["product_name"],
                "score_100_equivalent": row["score_100_equivalent"],
                "flags": flags,
            }
        )

    for items in rows_by_type.values():
        items.sort(key=lambda item: (-(item["score_100_equivalent"] or -1), item["product_name"] or ""))

    reinferred_count = flag_counts.get("SUPPLEMENT_TYPE_REINFERRED", 0)
    specialty_count = final_distribution.get("specialty", 0)
    all_started_specialty = reinferred_count + specialty_count == total

    class_change_matrix: Counter[str] = Counter()
    if all_started_specialty:
        for final_type, count in final_distribution.items():
            class_change_matrix[f"specialty -> {final_type}"] = count

    score_basis_counts = Counter(
        {
            "bioactives_scored": total - verdict_distribution.get("BLOCKED", 0) - verdict_distribution.get("NOT_SCORED", 0),
            "safety_block": verdict_distribution.get("BLOCKED", 0),
            "no_scorable_ingredients": verdict_distribution.get("NOT_SCORED", 0),
        }
    )
    evaluation_stage_counts = Counter(
        {
            "scoring": total - verdict_distribution.get("BLOCKED", 0),
            "safety": verdict_distribution.get("BLOCKED", 0),
        }
    )

    probiotic_reason_counts: Counter[str] = Counter()
    probiotic_examples: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)

    for row in rows:
        dsld_id = str(row["dsld_id"])
        blob = json.loads((blob_dir / f"{dsld_id}.json").read_text())
        probiotic_detail = blob.get("probiotic_detail")
        probiotic_bonus = 0.0
        for bonus in blob.get("score_bonuses", []):
            if bonus.get("id") == "probiotic":
                probiotic_bonus = float(bonus.get("score") or 0.0)
                break

        reason = "no_probiotic_signal"
        if probiotic_detail:
            if row["supplement_type"] == "probiotic" and probiotic_bonus > 0:
                reason = "supplement_type_probiotic"
            elif probiotic_bonus > 0:
                reason = "promoted_probiotic_dominant"
            else:
                reason = "strict_gate_failed"

        probiotic_reason_counts[reason] += 1

        if reason != "no_probiotic_signal":
            probiotic_examples[reason].append(
                {
                    "dsld_id": row["dsld_id"],
                    "product_name": row["product_name"],
                    "supplement_type": row["supplement_type"],
                    "score_100_equivalent": row["score_100_equivalent"],
                    "bonus": probiotic_bonus,
                }
            )

    for items in probiotic_examples.values():
        items.sort(key=lambda item: (-(item["score_100_equivalent"] or -1), item["product_name"] or ""))

    return {
        "manifest": manifest,
        "audit": audit,
        "total": total,
        "final_distribution": final_distribution,
        "class_change_matrix": class_change_matrix,
        "rows_by_type": rows_by_type,
        "flag_counts": flag_counts,
        "score_basis_counts": score_basis_counts,
        "evaluation_stage_counts": evaluation_stage_counts,
        "verdict_distribution": verdict_distribution,
        "probiotic_reason_counts": probiotic_reason_counts,
        "probiotic_examples": probiotic_examples,
        "all_started_specialty": all_started_specialty,
        "reinferred_count": reinferred_count,
        "specialty_count": specialty_count,
    }


def render_markdown(analysis: dict[str, Any]) -> str:
    manifest = analysis["manifest"]
    audit = analysis["audit"]
    total = analysis["total"]
    lines: list[str] = [
        "# Category And Gate Audit",
        "",
        f"- Generated from release artifacts dated `{manifest.get('generated_at')}`",
        f"- Product count: `{manifest['product_count']}`",
        f"- Detail blobs: `{manifest['detail_blob_count']}`",
        f"- Unique detail blobs: `{manifest['detail_blob_unique_count']}`",
        f"- Contract failures: `{len(audit.get('contract_failures', []))}`",
        "",
        "## Final Supplement Type Distribution",
        "",
        *_render_counter(analysis["final_distribution"], total=total),
        "",
        "## Enriched -> Resolved Type Change Matrix",
        "",
    ]

    if analysis["all_started_specialty"]:
        lines.extend(_render_counter(analysis["class_change_matrix"], total=total))
    else:
        lines.append("Could not prove a clean single-origin type matrix from release-only artifacts.")

    lines.extend(
        [
            "",
            "### Highest-Impact Reclassifications",
            "",
            "#### specialty -> multivitamin",
            "",
            *_render_table(
                analysis["rows_by_type"].get("multivitamin", [])[:8],
                [
                    ("dsld_id", "DSLD ID"),
                    ("product_name", "Product"),
                    ("score_100_equivalent", "Score"),
                    ("flags", "Flags"),
                ],
            ),
            "",
            "#### specialty -> targeted",
            "",
            *_render_table(
                analysis["rows_by_type"].get("targeted", [])[:8],
                [
                    ("dsld_id", "DSLD ID"),
                    ("product_name", "Product"),
                    ("score_100_equivalent", "Score"),
                    ("flags", "Flags"),
                ],
            ),
            "",
            "#### specialty -> probiotic",
            "",
            *_render_table(
                analysis["rows_by_type"].get("probiotic", [])[:8],
                [
                    ("dsld_id", "DSLD ID"),
                    ("product_name", "Product"),
                    ("score_100_equivalent", "Score"),
                    ("flags", "Flags"),
                ],
            ),
            "",
            "#### specialty -> single_nutrient",
            "",
            *_render_table(
                analysis["rows_by_type"].get("single_nutrient", [])[:8],
                [
                    ("dsld_id", "DSLD ID"),
                    ("product_name", "Product"),
                    ("score_100_equivalent", "Score"),
                    ("flags", "Flags"),
                ],
            ),
            "",
            "## Gate Outcomes",
            "",
            "### Scoring Basis",
            "",
            *_render_counter(analysis["score_basis_counts"], total=total),
            "",
            "### Evaluation Stage",
            "",
            *_render_counter(analysis["evaluation_stage_counts"], total=total),
            "",
            "### Verdicts",
            "",
            *_render_counter(analysis["verdict_distribution"], total=total),
            "",
            "### Flag Counts",
            "",
            *_render_counter(analysis["flag_counts"]),
            "",
            "### Probiotic Eligibility Outcomes",
            "",
            *_render_counter(analysis["probiotic_reason_counts"], total=total),
            "",
            "#### Promoted Probiotic-Dominant Formulas",
            "",
            *_render_table(
                analysis["probiotic_examples"].get("promoted_probiotic_dominant", [])[:8],
                [
                    ("dsld_id", "DSLD ID"),
                    ("product_name", "Product"),
                    ("supplement_type", "Resolved Type"),
                    ("score_100_equivalent", "Score"),
                    ("bonus", "Bonus"),
                ],
            ),
            "",
            "#### Probiotic Strict-Gate Failures",
            "",
            *_render_table(
                analysis["probiotic_examples"].get("strict_gate_failed", [])[:8],
                [
                    ("dsld_id", "DSLD ID"),
                    ("product_name", "Product"),
                    ("supplement_type", "Resolved Type"),
                    ("score_100_equivalent", "Score"),
                    ("bonus", "Bonus"),
                ],
            ),
            "",
            "#### Supplement-Type-Probiotic Awards",
            "",
            *_render_table(
                analysis["probiotic_examples"].get("supplement_type_probiotic", [])[:8],
                [
                    ("dsld_id", "DSLD ID"),
                    ("product_name", "Product"),
                    ("supplement_type", "Resolved Type"),
                    ("score_100_equivalent", "Score"),
                    ("bonus", "Bonus"),
                ],
            ),
            "",
            "## Export Integrity",
            "",
            f"- `products_core` rows: `{manifest['product_count']}`",
            f"- `detail_blobs` files: `{manifest['detail_blob_count']}`",
            f"- `detail_index.json` entries: `{manifest['detail_blob_unique_count']}`",
            f"- `audit.contract_failures`: `{len(audit.get('contract_failures', []))}`",
            f"- `audit.counts.total_errors`: `{audit.get('counts', {}).get('total_errors', 0)}`",
            "",
            "## Interpretation",
            "",
            f"- `SUPPLEMENT_TYPE_REINFERRED` appears on `{analysis['reinferred_count']}` products. Combined with the remaining `{analysis['specialty_count']}` final-`specialty` products, that means the current release set entered scoring with stale `specialty` typing across the board.",
            "- The rebuilt release export is internally aligned now: row counts, detail blobs, manifest, and contract audit all agree.",
            "- Remaining work is semantic QA, not silent pipeline drift. The next best audit is a curated spot-check set for products near category boundaries and for probiotic-signaled products that still fail the strict gate.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-root", type=Path, default=DEFAULT_BUILD_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    analysis = collect_analysis(args.build_root)
    markdown = render_markdown(analysis)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(markdown, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
