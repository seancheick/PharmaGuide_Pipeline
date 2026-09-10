from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest


FIXTURE_PATH = (
    Path(__file__).parents[1]
    / "submission_review"
    / "fixtures"
    / "manual_label_v1_cases.json"
)
FIXTURE_SHA256 = "3498b58d19399f187aa6d71d78f5bf1aa6583f21ff2479190956cf07fa7bd0de"


def test_manual_label_v1_fixture_contract_stays_checksum_pinned() -> None:
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    canonical = json.dumps(
        fixture,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    assert hashlib.sha256(canonical).hexdigest() == FIXTURE_SHA256


APP_FIXTURE_PATH = Path(
    "/Users/seancheick/PharmaGuide ai/supabase/functions/"
    "review-product-submissions/fixtures/manual_label_v1_cases.json"
)


def test_manual_label_v1_accepts_and_rejects_shared_contract_cases() -> None:
    from product_submission_import import (
        SubmissionImportError,
        _validate_label_payload,
    )

    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    for case in fixture["cases"]:
        if case["valid"]:
            _validate_label_payload(case["payload"])
            continue
        with pytest.raises(SubmissionImportError) as raised:
            _validate_label_payload(case["payload"])
        # Both the location and the exact wording are pinned. manual_label_v1
        # is implemented twice — here for the catalog gate and in TypeScript
        # for the approval gate — so the only defence against the two drifting
        # apart is that neither can change what it says without this failing.
        assert str(raised.value) == case["python_message"], case["name"]
        assert _rejected_path(str(raised.value)) == case["path"], case["name"]


def _rejected_path(message: str) -> str:
    """The JSON location a rejection names: structure, not prose."""
    head = message.split(" ")[0]
    return head if ("[" in head or "." in head) else "$"


def test_the_two_repositories_hold_the_same_contract_bytes() -> None:
    if not APP_FIXTURE_PATH.exists():
        pytest.skip("the app repository is not checked out beside this one")

    # Each side pins a checksum of its own copy, which proves neither drifted
    # by accident but not that they are still the same contract. This does.
    assert APP_FIXTURE_PATH.read_bytes() == FIXTURE_PATH.read_bytes()
