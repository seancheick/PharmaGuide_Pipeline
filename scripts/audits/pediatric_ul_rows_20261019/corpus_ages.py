#!/usr/bin/env python3
"""Child-age reading of every distinct DSLD targetGroups combination in the frozen raw corpus.

Writes one JSON object {combination: ages} to stdout, so two source revisions can be compared:
a reader change that leaves this output identical cannot change any corpus label's UL screen.

    $PG_PYTHON scripts/audits/pediatric_ul_rows_20261019/corpus_ages.py FROZEN_RAW_ROOT > ages.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from rda_ul_calculator import label_pediatric_age_ranges  # noqa: E402


def main() -> int:
    combos = {}
    for path in sorted(Path(sys.argv[1]).rglob("*.json")):
        payload = json.loads(path.read_text())
        for label in payload if isinstance(payload, list) else [payload]:
            groups = label.get("targetGroups") or []
            combos.setdefault(json.dumps(groups, sort_keys=True), groups)
    out = {key: label_pediatric_age_ranges({"targetGroups": groups}) for key, groups in combos.items()}
    print(json.dumps(out, sort_keys=True, indent=0))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
