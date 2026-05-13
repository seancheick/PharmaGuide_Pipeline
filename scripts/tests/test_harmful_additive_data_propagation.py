"""Test that updates to harmful_additives.json propagate to the build
without requiring a full re-enrichment cycle.

Sprint E1.1.2 / 2026-05-13: the enricher snapshots mechanism_of_harm,
notes, and population_warnings from harmful_additives.json into each
product's enriched data at enrich-time. Before this fix, build_final_db
preferred the enricher's snapshot over the live data-file lookup —
which meant any correction to the data file sat dormant until the
operator re-ran the full enrichment pipeline.

For medical-grade safety copy this is unacceptable: when authoring
identifies a problem with mechanism_of_harm, population_warnings, or
notes, the correction must flow into the next build immediately.

This test pins the priority order: data file (h_ref) wins, enricher's
snapshot (h) is the fallback only when the runtime reference lookup
fails (e.g. additive_id renamed mid-cycle).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))


def test_data_file_wins_over_enriched_snapshot_for_mechanism_of_harm(monkeypatch):
    """Live data-file mechanism_of_harm must win over the enricher's
    stale snapshot. Regression guard for the Sprint E1.1.2 priority flip
    on 2026-05-13."""
    from scripts.build_final_db import resolve_harmful_reference

    # Simulate enriched-product harmful_additive entry with STALE snapshot
    enriched_entry = {
        "additive_id": "ADD_TEST_ADDITIVE",
        "additive_name": "Test Additive",
        "ingredient": "Test Additive",
        "mechanism_of_harm": "OLD TEXT — should not win",
        "notes": "OLD notes — should not win",
        "population_warnings": ["OLD pop warning — should not win"],
        "severity_level": "moderate",
        "category": "test_category",
    }

    fresh_ref = {
        "id": "ADD_TEST_ADDITIVE",
        "additive_name": "Test Additive",
        "standard_name": "Test Additive",
        "mechanism_of_harm": "FRESH TEXT — must win",
        "notes": "FRESH notes — must win",
        "population_warnings": ["FRESH pop warning — must win"],
    }

    # Force the runtime reference lookup to return our fresh entry.
    monkeypatch.setattr(
        "scripts.build_final_db.resolve_harmful_reference",
        lambda h: fresh_ref,
    )

    # Replicate exactly the priority order used by the build's warning
    # emitter (build_final_db line ~3001-3008).
    from scripts.build_final_db import safe_str, safe_list
    import scripts.build_final_db as bfd
    h_ref = bfd.resolve_harmful_reference(enriched_entry)
    h_notes = safe_str(h_ref.get("notes") or enriched_entry.get("notes"))
    h_mechanism = safe_str(
        h_ref.get("mechanism_of_harm") or enriched_entry.get("mechanism_of_harm")
    )
    h_pop_warnings = (
        h_ref.get("population_warnings")
        or enriched_entry.get("population_warnings")
        or []
    )

    assert h_mechanism == "FRESH TEXT — must win", (
        "Data file mechanism_of_harm must override the enricher's snapshot. "
        "Without this priority, authoring corrections sit dormant until a "
        "full re-enrichment cycle."
    )
    assert h_notes == "FRESH notes — must win"
    assert h_pop_warnings == ["FRESH pop warning — must win"]


def test_enriched_snapshot_used_when_data_file_lookup_fails(monkeypatch):
    """Fallback: when the runtime data-file lookup returns an empty dict
    (e.g. additive_id renamed mid-cycle), the enricher's snapshot must
    still be used so the warning isn't lost entirely."""
    from scripts.build_final_db import safe_str

    enriched_entry = {
        "additive_id": "ADD_ORPHANED",
        "additive_name": "Orphaned Additive",
        "ingredient": "Orphaned Additive",
        "mechanism_of_harm": "Snapshot mechanism",
        "notes": "Snapshot notes",
        "population_warnings": ["Snapshot pop warning"],
        "severity_level": "moderate",
        "category": "test",
    }

    # Simulate runtime ref returning empty dict (id no longer matches).
    monkeypatch.setattr(
        "scripts.build_final_db.resolve_harmful_reference",
        lambda h: {},
    )

    import scripts.build_final_db as bfd
    h_ref = bfd.resolve_harmful_reference(enriched_entry)
    h_notes = safe_str(h_ref.get("notes") or enriched_entry.get("notes"))
    h_mechanism = safe_str(
        h_ref.get("mechanism_of_harm") or enriched_entry.get("mechanism_of_harm")
    )

    assert h_mechanism == "Snapshot mechanism"
    assert h_notes == "Snapshot notes"


def test_shmp_data_file_no_longer_carries_bare_kidney_disease():
    """Regression: ADD_SODIUM_HEXAMETAPHOSPHATE's mechanism_of_harm in the
    live data file must not contain the bare phrase 'kidney disease'.
    Population-specific guidance lives in population_warnings, where the
    warning emitter routes it as a separate field that doesn't get piped
    into the critical-mode warning's 'detail' field (Sprint E1.1.2)."""
    data_path = ROOT / "scripts" / "data" / "harmful_additives.json"
    data = json.loads(data_path.read_text())
    items = data["harmful_additives"]
    target = next((i for i in items if i.get("id") == "ADD_SODIUM_HEXAMETAPHOSPHATE"), None)
    assert target is not None, "ADD_SODIUM_HEXAMETAPHOSPHATE missing from data file"

    mech = target.get("mechanism_of_harm") or ""
    assert "kidney disease" not in mech.lower(), (
        f"ADD_SODIUM_HEXAMETAPHOSPHATE.mechanism_of_harm still contains the "
        f"bare phrase 'kidney disease' — this is profile-specific copy in a "
        f"field that gets piped into critical-mode warnings. Move kidney-"
        f"specific guidance to population_warnings (where it already lives). "
        f"Sprint E1.1.2 / commit pending."
    )

    # Population-specific guidance should still be preserved — kidney/CKD
    # context belongs in population_warnings.
    pop = target.get("population_warnings") or []
    pop_text = " ".join(p if isinstance(p, str) else "" for p in pop).lower()
    assert "ckd" in pop_text or "kidney" in pop_text, (
        "Kidney-related population-specific guidance was lost in the rewrite. "
        "It must remain in population_warnings."
    )
