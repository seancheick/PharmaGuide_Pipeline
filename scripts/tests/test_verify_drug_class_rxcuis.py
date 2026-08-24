"""RxNorm release diagnostics separate registry data from transport state."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
API_AUDIT = ROOT / "scripts" / "api_audit"
if str(API_AUDIT) not in sys.path:
    sys.path.insert(0, str(API_AUDIT))

from verify_drug_class_rxcuis import audit  # noqa: E402


CLASSES = {
    "class:test": {
        "member_rxcuis": ["11289"],
        "member_names": ["warfarin"],
    }
}


def test_transport_failure_is_not_reported_as_retired_identifier() -> None:
    problems, checked = audit(
        CLASSES,
        name_fn=lambda _rxcui: "ERR:<urlopen error TLS failed>",
        request_delay=0,
    )

    assert checked == 1
    assert "registry transport failure" in problems[0]
    assert "retired" not in problems[0]


def test_empty_successful_response_is_reported_as_retired_identifier() -> None:
    problems, checked = audit(
        CLASSES,
        name_fn=lambda _rxcui: "",
        request_delay=0,
    )

    assert checked == 1
    assert "no current RxNorm name (retired?)" in problems[0]
