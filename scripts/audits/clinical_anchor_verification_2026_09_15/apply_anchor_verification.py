#!/usr/bin/env python3
"""Apply the verified anchor decisions to rda_optimal_uls.json, one entry at a time.

Usage: apply_anchor_verification.py [--apply]   (dry run by default; run from repo root)

For every ledger entry the current reference entry must match what the ledger
says was reviewed (anchor value on every data row, lower bound of optimal_range)
before anything changes. Corrected anchors get the new rda_ai on every row and a
new optimal_range lower bound; verified ones get their added references. Every
entry gets a dated provenance sentence in notes. The reference data contract
fingerprint and version are restamped so enrichment knows the data changed.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from reference_data_contract import semantic_rda_ul_fingerprint, validate_declared_reference_stamp  # noqa: E402

DATA = ROOT / "scripts/data/rda_optimal_uls.json"
LEDGER = json.loads((HERE / "anchor_verification.json").read_text())
CHECKED_ON = LEDGER["_metadata"]["checked_on"]
REFERENCE_VERSION = f"5.1.2-{CHECKED_ON}"
NOTE = {
    "verified": f"Anchor dose content-verified against PubMed on {CHECKED_ON}.",
    "corrected": f"Anchor dose corrected from {{old}} {{unit}} after content verification against PubMed on {CHECKED_ON}.",
    "supported_uncontrolled": f"Anchor dose supported only by uncontrolled evidence (PubMed review {CHECKED_ON}); not used for graduated dose credit.",
    "not_established": f"Anchor dose not established by the cited sources (PubMed review {CHECKED_ON}); not used for graduated dose credit.",
}
# A review sentence from any run: the NOTE templates with the date, old value and unit
# generalised. Matching "up to the next period" broke on "3.2 g" and duplicated sentences.
REVIEW_SENTENCE = re.compile("|".join(
    r"\s*" + re.escape(template).replace(re.escape(CHECKED_ON), r"\d{4}-\d{2}-\d{2}")
    .replace(re.escape("{old}"), r"[\d.]+").replace(re.escape("{unit}"), r"\S+")
    for template in NOTE.values()
))


def _same(a, b) -> bool:
    return float(a) == float(b)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    raw = DATA.read_text(encoding="utf-8")
    data = json.loads(raw)
    if json.dumps(data, indent=2, ensure_ascii=False) + "\n" != raw:
        raise SystemExit("REFUSED: rda_optimal_uls.json is not byte-stable through json.dumps(indent=2, ensure_ascii=False)")
    by_id = {entry["id"]: entry for entry in data["nutrient_recommendations"]}
    for item in LEDGER["anchors"]:
        entry = by_id.get(item["id"])
        if entry is None:
            raise SystemExit(f"REFUSED {item['id']}: not in rda_optimal_uls.json")
        if entry.get("unit") != item["unit"]:
            raise SystemExit(f"REFUSED {item['id']}: unit {entry.get('unit')} != ledger {item['unit']}")
        # Re-runnable: an entry may still carry the reviewed anchor, or already the
        # corrected one from an earlier apply. Anything else is refused.
        accepted = {float(item["anchor_current"]), float(item.get("anchor_proposed", item["anchor_current"]))}
        values = {row.get("rda_ai") for row in entry["data"]}
        if len(values) != 1 or float(next(iter(values))) not in accepted:
            raise SystemExit(f"REFUSED {item['id']}: data rows do not all carry the reviewed anchor {sorted(accepted)}")
        lower = str(entry.get("optimal_range") or "").split("-")[0]
        if not lower or float(lower) not in accepted:
            raise SystemExit(f"REFUSED {item['id']}: optimal_range {entry.get('optimal_range')!r} does not start at the reviewed anchor")
        changes = []
        if item["decision"] == "corrected" and not _same(next(iter(values)), item["anchor_proposed"]):
            for row in entry["data"]:
                row["rda_ai"] = item["anchor_proposed"]
            entry["optimal_range"] = item["optimal_range_proposed"]
            changes.append(f"rda_ai {item['anchor_current']} -> {item['anchor_proposed']}")
        if item.get("replace_references"):
            changes.append(f"references {entry.get('references')} -> {item['replace_references']}")
            entry["references"] = list(item["replace_references"])
        for pmid in item.get("add_references", []):
            if pmid not in entry["references"]:
                entry["references"].append(pmid)
                changes.append(f"+ref {pmid}")
        note = NOTE[item["decision"]].format(old=item["anchor_current"], unit=item["unit"])
        # One review sentence per entry: drop every earlier review sentence first.
        notes = REVIEW_SENTENCE.sub("", entry.get("notes") or "")
        entry["notes"] = f"{notes} {note}".strip()
        cited = {e["pmid"] for e in item["evidence"]} & set(entry["references"])
        if item["graduation_eligible"] and not cited:
            raise SystemExit(f"REFUSED {item['id']}: eligible anchor cites none of its verifying PMIDs")
        print(f"{item['decision']:23s} {item['id']:34s} {'; '.join(changes) or 'notes only'}")
    meta = data["_metadata"]
    meta["last_updated"] = CHECKED_ON
    contract = meta["reference_data_contract"]
    contract["reference_version"] = REFERENCE_VERSION
    contract["semantic_fingerprint"] = semantic_rda_ul_fingerprint(data)
    validate_declared_reference_stamp(data)
    print(f"reference_version -> {REFERENCE_VERSION}; fingerprint -> {contract['semantic_fingerprint'][:23]}")
    if args.apply:
        DATA.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print("WRITTEN", DATA)
    else:
        print("dry run; data unchanged")


if __name__ == "__main__":
    main()
