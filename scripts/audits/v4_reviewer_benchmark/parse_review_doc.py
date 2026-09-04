"""Convert a complete returned document into the frozen response contract.

Only syntax is parsed here. Scores, enums, sources, provenance attestations,
and complete assignments are checked by the same validator used for analysis.
No baseline key is opened and no existing response file is overwritten.

Usage: parse_review_doc.py --freeze-dir FREEZE --doc REVIEW_ID.md --slotmap MAP --out DIR
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SCRIPTS_DIR))

from audits.v4_reviewer_benchmark_analysis import (  # noqa: E402
    ATTESTATION_FIELDS, PILLAR_REVIEW_FIELDS, RESPONSE_CONTRACT_VERSION,
    RESPONSE_FIELDS, AnalysisContractError, _as_float, _as_int,
    load_frozen_response_inputs, validate_and_select_responses,
)

PILLAR_LABELS = ("FORMULATION", "DOSE", "EVIDENCE", "TRANSPARENCY",
                 "VERIFICATION", "QUALITY")


def _line(text: str, label: str, *, required: bool = False) -> str:
    # Horizontal whitespace only: a blank must never consume the next line.
    matches = re.findall(rf"^{re.escape(label)}(?:[ \t]+\([^\n:]*\))?:[ \t]*([^\n]*)$", text, re.M)
    if len(matches) > 1:
        raise AnalysisContractError(f"{label} appears more than once")
    if required and not matches:
        raise AnalysisContractError(f"{label} is missing")
    return matches[0].strip() if matches else ""


def parse_document(text: str, slotmap: dict, frozen: dict) -> list[dict]:
    if not text.strip():
        raise AnalysisContractError("review document is empty")
    if slotmap.get("response_contract_version") != RESPONSE_CONTRACT_VERSION or not isinstance(slotmap.get("reviews"), dict):
        raise AnalysisContractError("legacy or missing sequence map; generate a new document from a new freeze, never guess review_sequence")
    if slotmap.get("freeze_id") != frozen["spec"]["freeze_id"]:
        raise AnalysisContractError("sequence map freeze_id does not match")
    for field, expected in frozen["hashes"].items():
        if slotmap.get(field) != expected:
            raise AnalysisContractError(f"sequence map {field} does not match frozen input")
    slot = _as_int(slotmap.get("slot"), field="sequence map slot")
    rid = str(slotmap.get("reviewer_id") or "")
    if slot not in frozen["orders"] or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", rid):
        raise AnalysisContractError("sequence map has invalid reviewer slot or ID")
    expected_reviews = {
        bid: {"review_sequence": frozen["sequences"][bid], "reviewer_order": order}
        for bid, order in frozen["orders"][slot].items()
    }
    if slotmap["reviews"] != expected_reviews:
        raise AnalysisContractError("sequence map assignments do not match frozen packet/template")
    if text.splitlines()[0] != f"# Supplement label review — {rid}":
        raise AnalysisContractError("document reviewer does not match sequence map")
    provenance = f'Freeze: `{frozen["spec"]["freeze_id"]}` · Response contract: `{RESPONSE_CONTRACT_VERSION}`'
    if provenance not in text.splitlines():
        raise AnalysisContractError("document freeze provenance is missing or changed")
    attestations = {field: _line(text, field.upper(), required=True) for field in ATTESTATION_FIELDS}

    rows = []
    for body in re.findall(r"```[^\n]*\n(.*?)```", text, re.S):
        if not re.search(r"^ID:", body, re.M):
            continue
        bid = _line(body, "ID", required=True)
        if bid not in expected_reviews:
            raise AnalysisContractError(f"unknown benchmark_id {bid}")
        values = {field: _line(body, label) for field, label in zip(PILLAR_REVIEW_FIELDS, PILLAR_LABELS)}
        total = sum(_as_float(raw, field=f"{bid}.{field}") for field, raw in values.items())
        sources = _line(body, "SOURCES")
        rows.append({
            **values, **attestations, **expected_reviews[bid],
            "benchmark_id": bid, "reviewer_slot": slot, "reviewer_id": rid,
            "review_round": 1, "correction_reason": "", "overall_0_100": total,
            "product_safety_status": _line(body, "SAFETY"),
            "safety_concern_driver": _line(body, "DRIVER"),
            "assessment_confidence": _line(body, "CONFIDENCE"),
            "label_facts_sufficient": _line(body, "LABEL ENOUGH?"),
            "source_citations_json": json.dumps([value.strip() for value in sources.split(";")] if sources else []),
            "rationale": _line(body, "WHY"),
            "protocol_deviation": _line(body, "ODD"),
        })
    return validate_and_select_responses(
        rows, {slot: {"reviewer_id": rid}}, frozen["sequences"],
        frozen["spec"], reviewer_orders=frozen["orders"],
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze-dir", required=True, type=Path)
    parser.add_argument("--doc", required=True, type=Path)
    parser.add_argument("--slotmap", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    try:
        frozen = load_frozen_response_inputs(
            manifest_path=args.freeze_dir / "manifest.json",
            analysis_spec_path=args.freeze_dir / "ANALYSIS_SPEC.json",
            analysis_script_path=SCRIPTS_DIR / "audits" / "v4_reviewer_benchmark_analysis.py",
            reviewer_packet_path=args.freeze_dir / "reviewer_packet.csv",
            reviewer_template_path=args.freeze_dir / "reviewer_response_template.csv",
        )
        slotmap = json.loads(args.slotmap.read_text(encoding="utf-8"))
        if not isinstance(slotmap, dict):
            raise AnalysisContractError("sequence map must be a JSON object")
        rows = parse_document(args.doc.read_text(encoding="utf-8"), slotmap, frozen)
        output = args.out / f"answers_{slotmap['reviewer_id']}.csv"
        args.out.mkdir(parents=True, exist_ok=True)
        with output.open("x", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=RESPONSE_FIELDS, lineterminator="\n")
            writer.writeheader()
            for row in sorted(rows, key=lambda row: row["reviewer_order"]):
                serialized = {field: row[field] for field in RESPONSE_FIELDS}
                serialized["source_citations_json"] = json.dumps(row["source_citations_json"], ensure_ascii=False)
                writer.writerow(serialized)
    except (AnalysisContractError, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR — no CSV written: {exc}")
        return 1
    print(f"OK — validated {len(rows)} responses; wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
