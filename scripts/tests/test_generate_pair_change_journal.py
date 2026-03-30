"""Tests for generate_pair_change_journal.py."""

import json
import os
import sys

_scripts_dir = os.path.join(os.path.dirname(__file__), "..")
if _scripts_dir not in sys.path:
    sys.path.insert(0, os.path.abspath(_scripts_dir))


def _make_pair(scan_dir, prefix, enriched_payload, scored_payload):
    enriched_dir = scan_dir / f"output_{prefix}_enriched" / "enriched"
    scored_dir = scan_dir / f"output_{prefix}_scored" / "scored"
    enriched_dir.mkdir(parents=True, exist_ok=True)
    scored_dir.mkdir(parents=True, exist_ok=True)
    (enriched_dir / "a.json").write_text(json.dumps(enriched_payload), encoding="utf-8")
    (scored_dir / "a.json").write_text(json.dumps(scored_payload), encoding="utf-8")


def test_build_journal_entries_detects_new_changed_and_removed_pairs():
    from generate_pair_change_journal import build_journal_entries

    current_state = {
        "Nordic-2026": {
            "enriched_dir": "/tmp/nordic-enriched",
            "scored_dir": "/tmp/nordic-scored",
            "combined_fingerprint": "new",
        },
        "Pure-2026": {
            "enriched_dir": "/tmp/pure-enriched",
            "scored_dir": "/tmp/pure-scored",
            "combined_fingerprint": "same",
        },
    }
    previous_state = {
        "Pure-2026": {
            "enriched_dir": "/tmp/pure-enriched",
            "scored_dir": "/tmp/pure-scored",
            "combined_fingerprint": "old",
        },
        "Olly-2026": {
            "enriched_dir": "/tmp/olly-enriched",
            "scored_dir": "/tmp/olly-scored",
            "combined_fingerprint": "gone",
        },
    }

    entries = build_journal_entries(
        current_state,
        previous_state,
        changed_at="2026-03-29T20:45:00Z",
    )

    assert entries == [
        {
            "prefix": "Nordic-2026",
            "change_type": "new",
            "changed_at": "2026-03-29T20:45:00Z",
            "enriched_dir": "/tmp/nordic-enriched",
            "scored_dir": "/tmp/nordic-scored",
            "combined_fingerprint": "new",
        },
        {
            "prefix": "Olly-2026",
            "change_type": "removed",
            "changed_at": "2026-03-29T20:45:00Z",
            "enriched_dir": "/tmp/olly-enriched",
            "scored_dir": "/tmp/olly-scored",
            "combined_fingerprint": "gone",
        },
        {
            "prefix": "Pure-2026",
            "change_type": "changed",
            "changed_at": "2026-03-29T20:45:00Z",
            "enriched_dir": "/tmp/pure-enriched",
            "scored_dir": "/tmp/pure-scored",
            "combined_fingerprint": "same",
        },
    ]


def test_write_change_journal_and_state_persists_outputs(tmp_path):
    from generate_pair_change_journal import write_change_journal_and_state

    journal_path = tmp_path / "pair_change_journal.json"
    state_path = tmp_path / "pair_source_state.json"
    current_state = {
        "Nordic-2026": {
            "enriched_dir": "/tmp/nordic-enriched",
            "scored_dir": "/tmp/nordic-scored",
            "combined_fingerprint": "abc",
        }
    }
    entries = [
        {
            "prefix": "Nordic-2026",
            "change_type": "new",
            "changed_at": "2026-03-29T20:45:00Z",
            "enriched_dir": "/tmp/nordic-enriched",
            "scored_dir": "/tmp/nordic-scored",
            "combined_fingerprint": "abc",
        }
    ]

    write_change_journal_and_state(
        str(journal_path),
        str(state_path),
        entries,
        current_state,
        scan_dir="/tmp/scan",
    )

    journal = json.loads(journal_path.read_text(encoding="utf-8"))
    state = json.loads(state_path.read_text(encoding="utf-8"))

    assert journal["scan_dir"] == "/tmp/scan"
    assert journal["entries"] == entries
    assert state["pairs"]["Nordic-2026"]["combined_fingerprint"] == "abc"


def test_main_generates_journal_from_discovered_pairs(tmp_path):
    from generate_pair_change_journal import main

    scan_dir = tmp_path / "scan"
    scan_dir.mkdir()
    _make_pair(scan_dir, "Nordic-2026", {"id": 1}, {"id": 1})
    _make_pair(scan_dir, "Pure-2026", {"id": 2}, {"id": 2})

    journal_path = tmp_path / "pair_change_journal.json"
    state_path = tmp_path / "pair_source_state.json"

    exit_code = main(
        [
            "--scan-dir",
            str(scan_dir),
            "--journal-path",
            str(journal_path),
            "--state-file",
            str(state_path),
        ]
    )

    assert exit_code == 0
    journal = json.loads(journal_path.read_text(encoding="utf-8"))
    assert sorted(entry["prefix"] for entry in journal["entries"]) == ["Nordic-2026", "Pure-2026"]
    assert {entry["change_type"] for entry in journal["entries"]} == {"new"}
