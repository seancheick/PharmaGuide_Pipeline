#!/usr/bin/env python3
"""Parity of the moved children's-product rule over every canonical cleaned record.

The omega Evidence check (evidence_resolver, main 951a05415) decided "child or baby" inline; the
rule now lives in rda_ul_calculator.label_is_for_children. This compares the original inline code,
copied verbatim below, with the shared function on every record of a replay capture.

    $PG_PYTHON scripts/audits/pediatric_ul_rows_20261019/child_rule_parity.py RECORDS_DIR
"""
from __future__ import annotations

import gzip
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from rda_ul_calculator import label_child_ul_ages, label_is_for_children  # noqa: E402


def _canonical_text(val: Any) -> str:  # evidence_resolver._canonical_text at 951a05415
    return re.sub(r"[^a-z0-9]+", " ", str(val or "").strip().lower()).strip()


def original_child_or_baby(prod: Mapping) -> bool:  # evidence_resolver at 951a05415, verbatim
    title = " ".join(str(prod.get(key) or "") for key in ("product_name", "fullName", "brand_name", "brandName"))
    normalized_title = _canonical_text(title)
    child_population = re.compile(
        r"\b(?:baby|babies|infant|infants|child|children|kids?|toddler|toddlers|pediatric|junior|jr)\b"
    )
    target_groups = prod.get("targetGroups") or []
    if isinstance(target_groups, str):
        target_groups = [target_groups]
    target_text = _canonical_text(" ".join(
        str(group.get("text") or group.get("name") or "") if isinstance(group, Mapping) else str(group)
        for group in target_groups
    ))
    adult_target = bool(re.search(
        r"\b(?:adults?|seniors?|mature|men|women|pregnant|lactating|menopause|menopausal)\b", target_text,
    ))
    return bool(child_population.search(normalized_title)) or (
        bool(child_population.search(target_text)) and not adult_target
    )


def main() -> int:
    records = sorted(Path(sys.argv[1]).glob("*.json.gz"))
    mismatches, children, ages = [], 0, Counter()
    for path in records:
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            stages = json.load(handle)
        for stage in ("cleaned", "enriched"):
            product = stages[stage]
            if original_child_or_baby(product) != label_is_for_children(product):
                mismatches.append((path.stem, stage))
        if label_is_for_children(stages["enriched"]):
            children += 1
            ages[str(label_child_ul_ages(stages["enriched"]))] += 1
    print(json.dumps({"records": len(records), "stages_compared": 2 * len(records),
                      "mismatches": mismatches[:20], "mismatch_count": len(mismatches),
                      "childrens_products": children, "child_note_ages": ages.most_common()}, indent=1))
    return 1 if mismatches else 0


if __name__ == "__main__":
    raise SystemExit(main())
