"""Unreviewed clinical guidance must not reach a production artifact.

`medication_depletions.json` carries 31 verified / 29 needs_revision / 20
rejected records, and `timing_rules.json` carries 7 verified / 13
needs_revision. Both consumers in the app already fail closed on review status,
but both artifacts shipped every record and relied on the reader to hide them.
Defence in depth: an unverified clinical claim should not be inside the bundle
at all.

Exclusions are counted and listed in the artifact metadata rather than dropped
silently — the backlog stays visible as remediation work, which is the whole
reason those records exist.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for candidate in (ROOT, ROOT / "scripts"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from build_medication_depletions_artifact import (  # noqa: E402
    PUBLISHABLE_CITATION_REVIEW_STATES,
    TOP_LEVEL_KEY,
    build_artifact,
)
from sync_flutter_reference_data import (  # noqa: E402
    PUBLISHABLE_TIMING_REVIEW_STATES,
    publishable_timing_rules,
)

DEPLETIONS_SOURCE = ROOT / "scripts" / "data" / "medication_depletions.json"
TIMING_SOURCE = ROOT / "scripts" / "data" / "timing_rules.json"


def _source(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# medication_depletions
# --------------------------------------------------------------------------- #


def test_depletions_artifact_publishes_only_verified_records() -> None:
    artifact = build_artifact(_source(DEPLETIONS_SOURCE), content_version="test")
    statuses = {
        str(e.get("citation_review_status")) for e in artifact[TOP_LEVEL_KEY]
    }
    assert statuses <= PUBLISHABLE_CITATION_REVIEW_STATES, (
        f"artifact carries non-publishable citation states: "
        f"{sorted(statuses - PUBLISHABLE_CITATION_REVIEW_STATES)}"
    )


def test_depletions_exclusions_are_reported_not_silent() -> None:
    source = _source(DEPLETIONS_SOURCE)
    artifact = build_artifact(source, content_version="test")
    meta = artifact["_metadata"]

    withheld = [
        e for e in source[TOP_LEVEL_KEY]
        if str(e.get("citation_review_status") or "unverified").strip().lower()
        not in PUBLISHABLE_CITATION_REVIEW_STATES
    ]
    assert meta["withheld_entries"] == len(withheld)
    assert meta["total_entries"] == len(source[TOP_LEVEL_KEY]) - len(withheld)
    assert sorted(meta["withheld_entry_ids"]) == sorted(
        str(e["id"]) for e in withheld
    )
    assert meta["withheld_by_review_status"], (
        "the backlog must stay visible per status, not just as a count"
    )


def test_depletions_artifact_is_not_empty() -> None:
    """A filter that removed everything would pass the gate vacuously."""
    artifact = build_artifact(_source(DEPLETIONS_SOURCE), content_version="test")
    assert artifact["_metadata"]["total_entries"] > 0


@pytest.mark.parametrize(
    "status", ["needs_revision", "rejected", "unverified", None, "", "future_state"]
)
def test_a_non_verified_depletion_never_publishes(status) -> None:
    source = _source(DEPLETIONS_SOURCE)
    template = next(
        e for e in source[TOP_LEVEL_KEY]
        if str(e.get("citation_review_status")) == "verified"
    )
    probe = dict(template)
    probe["id"] = "PROBE_ENTRY"
    if status is None:
        probe.pop("citation_review_status", None)
    else:
        probe["citation_review_status"] = status
    probe.pop("watch_review_status", None)

    payload = {**source, TOP_LEVEL_KEY: [probe]}
    if status in {"", "future_state"}:
        with pytest.raises(ValueError):
            build_artifact(payload, content_version="test")
        return
    artifact = build_artifact(payload, content_version="test")
    assert artifact["_metadata"]["total_entries"] == 0
    assert artifact["_metadata"]["withheld_entry_ids"] == ["PROBE_ENTRY"]


# --------------------------------------------------------------------------- #
# timing_rules
# --------------------------------------------------------------------------- #


def test_timing_projection_publishes_only_verified_rules() -> None:
    projection = publishable_timing_rules(_source(TIMING_SOURCE))
    statuses = {str(r.get("review_status")) for r in projection["timing_rules"]}
    assert statuses <= PUBLISHABLE_TIMING_REVIEW_STATES, (
        f"projection carries non-publishable review states: "
        f"{sorted(statuses - PUBLISHABLE_TIMING_REVIEW_STATES)}"
    )


def test_timing_exclusions_are_reported_not_silent() -> None:
    source = _source(TIMING_SOURCE)
    projection = publishable_timing_rules(source)
    meta = projection["_metadata"]

    withheld = [
        r for r in source["timing_rules"]
        if str(r.get("review_status") or "").strip().lower()
        not in PUBLISHABLE_TIMING_REVIEW_STATES
    ]
    assert meta["withheld_entries"] == len(withheld)
    assert meta["total_entries"] == len(projection["timing_rules"])
    assert meta["total_entries"] == len(source["timing_rules"]) - len(withheld)
    assert sorted(meta["withheld_entry_ids"]) == sorted(
        str(r.get("id") or r.get("rule_id")) for r in withheld
    )


def test_timing_projection_is_not_empty() -> None:
    projection = publishable_timing_rules(_source(TIMING_SOURCE))
    assert projection["_metadata"]["total_entries"] > 0


def test_timing_projection_preserves_rule_content() -> None:
    """Filtering must not rewrite the rules it keeps."""
    source = _source(TIMING_SOURCE)
    projection = publishable_timing_rules(source)
    kept = {
        str(r.get("id") or r.get("rule_id")): r for r in projection["timing_rules"]
    }
    for rule in source["timing_rules"]:
        rid = str(rule.get("id") or rule.get("rule_id"))
        if rid in kept:
            assert kept[rid] == rule
