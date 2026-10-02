#!/usr/bin/env python3
"""Reject skips whose reason is not declared for the execution profile.

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
import re
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_profiles import CI_SKIP_ALLOWED_REASONS, LOCAL_ONLY_TEST_FILES  # noqa: E402


def _test_file(classname: str) -> str:
    for part in classname.split("."):
        if part.startswith("test_"):
            return f"{part}.py"
    return classname


def undeclared_skips(junit_xml: Path, profile: str = "ci") -> list[str]:
    if profile not in {"ci", "local"}:
        raise ValueError("expected ci or local skip policy")
    found = []
    cases = list(ET.parse(junit_xml).getroot().iter("testcase"))
    if not cases:
        return ["JUnit report contains no executed test cases"]
    for case in cases:
        skipped = case.find("skipped")
        if skipped is None:
            continue
        test_file = _test_file(case.get("classname", ""))
        if skipped.get("type") == "pytest.xfail":
            found.append(f"{test_file}::{case.get('name')} — expected failure requires explicit review")
            continue
        reason = (skipped.get("message") or "").strip()
        # pytest prefixes skip messages with "Skipped: "; unittest may not.
        reason = reason.removeprefix("Skipped: ")
        expected = CI_SKIP_ALLOWED_REASONS.get(test_file, ())
        local_opt_in = test_file.startswith("test_submission_")
        permitted = any(re.fullmatch(pattern, reason) for pattern in expected)
        if profile == "local" and test_file in LOCAL_ONLY_TEST_FILES and not local_opt_in:
            permitted = False
        if not permitted:
            found.append(f"{test_file}::{case.get('name')} — {reason}")
    return found


def main(argv: list[str]) -> int:
    if len(argv) not in (1, 2):
        print(__doc__, file=sys.stderr)
        return 2
    found = undeclared_skips(Path(argv[0]), argv[1] if len(argv) == 2 else "ci")
    if found:
        print(f"{len(found)} test(s) have undeclared or disallowed skip reasons:")
        for line in found:
            print(f"  {line}")
        print(
            "Declare a file in scripts/test_profiles.py LOCAL_ONLY_TEST_FILES only if it "
            "needs local corpus/build data; otherwise make the test run in CI."
        )
        return 1
    print("ci_skip_guard: every skip matches its declared reason and execution profile")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
