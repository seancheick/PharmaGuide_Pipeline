#!/usr/bin/env python3
"""Regenerate scripts/tests/shard_plan.json from a CI run's junit reports.

The fast rung is split across CI jobs by scripts/test_profiles.py::iter_profile_paths,
which balances the shards by the measured per-file duration recorded here (greedy
longest-first) and round-robins any file the plan does not know. Regenerate the plan
when the shard times drift apart again:

    gh run download <run-id> -n junit-fast-0 -D /tmp/j0   # ... one per shard
    scripts/test_shard_plan.py --run-id <run-id> /tmp/j*/ci-junit.xml

Durations are the sum of pytest testcase times per test file, so collection and
fixture setup outside a testcase are not counted; that is enough to balance on.
"""

from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ci_skip_guard import test_file_from_classname  # noqa: E402

PLAN_PATH = Path(__file__).resolve().parent / "tests" / "shard_plan.json"


def file_durations(junit_paths: list[Path]) -> dict[str, float]:
    """Seconds of testcase time per test file across every junit report."""
    seconds: dict[str, float] = defaultdict(float)
    for path in junit_paths:
        for case in ET.parse(path).getroot().iter("testcase"):
            seconds[test_file_from_classname(case.get("classname", ""))] += float(case.get("time") or 0)
    return {name: round(total, 3) for name, total in sorted(seconds.items())}


def build_plan(junit_paths: list[Path], run_id: str) -> dict:
    durations = file_durations(junit_paths)
    return {
        "_metadata": {
            "description": "Per-file fast-rung durations that scripts/test_profiles.py uses to "
                           "balance CI shards (greedy longest-first); files absent here are "
                           "round-robined. Regenerate with scripts/test_shard_plan.py.",
            "source_run_id": run_id,
            "generated_on": date.today().isoformat(),
            "unit": "seconds of pytest testcase time per file",
            "files": len(durations),
            "total_seconds": round(sum(durations.values()), 1),
        },
        "durations": durations,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("junit", nargs="+", type=Path, help="junit xml files, one per shard")
    parser.add_argument("--run-id", required=True, help="GitHub Actions run id the reports came from")
    parser.add_argument("--out", type=Path, default=PLAN_PATH)
    args = parser.parse_args(argv)
    plan = build_plan(args.junit, args.run_id)
    if not plan["durations"]:
        parser.error("no testcases found in the junit reports")
    args.out.write_text(json.dumps(plan, indent=1) + "\n")
    print(f"{args.out}: {plan['_metadata']['files']} files, {plan['_metadata']['total_seconds']} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
