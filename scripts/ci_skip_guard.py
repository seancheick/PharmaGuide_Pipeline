#!/usr/bin/env python3
"""Fail CI when a test skips outside the declared local-only files.

CI runs a clean checkout without the 11 GB product corpus or built exports,
so the tests that need them skip there. Those files are declared in
scripts/test_profiles.py (LOCAL_ONLY_TEST_FILES, run locally by
`scripts/test.sh local`). Any other skip is either a new local-only test that
must be declared, or a test silently not running; both fail here instead of
reading as a pass.

    ci_skip_guard.py <pytest junit xml>
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_profiles import CI_SKIP_ALLOWED_FILES, LOCAL_ONLY_TEST_FILES  # noqa: E402


def _test_file(classname: str) -> str:
    for part in classname.split("."):
        if part.startswith("test_"):
            return f"{part}.py"
    return classname


def undeclared_skips(junit_xml: Path) -> list[str]:
    allowed = LOCAL_ONLY_TEST_FILES | CI_SKIP_ALLOWED_FILES
    found = []
    for case in ET.parse(junit_xml).getroot().iter("testcase"):
        skipped = case.find("skipped")
        if skipped is None:
            continue
        test_file = _test_file(case.get("classname", ""))
        if test_file not in allowed:
            reason = (skipped.get("message") or "").strip()
            found.append(f"{test_file}::{case.get('name')} — {reason}")
    return found


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(__doc__, file=sys.stderr)
        return 2
    found = undeclared_skips(Path(argv[0]))
    if found:
        print(f"{len(found)} test(s) skipped outside the declared local-only files:")
        for line in found:
            print(f"  {line}")
        print(
            "Declare a file in scripts/test_profiles.py LOCAL_ONLY_TEST_FILES only if it "
            "needs local corpus/build data; otherwise make the test run in CI."
        )
        return 1
    print("ci_skip_guard: every skip is in a declared local-only file")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
