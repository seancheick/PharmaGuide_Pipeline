"""data_batch: canonical save, _metadata recount and the landed check.

A curated-data batch edits several entries at once; every entry is verified on
its own, and data_batch proves the mechanical part: each intended entry
changed, nothing else did, the counts match, and the file stays canonical JSON.
"""

import json
import subprocess
from datetime import date
from pathlib import Path

import pytest

import data_batch as db
from run_artifacts import json_text

DATA = Path(__file__).parent.parent / "data"


def _tracked_data_files() -> list[Path]:
    """Tracked JSON only: a checkout also holds ignored downloads and caches
    (fda_drug_labels/, fda_unii_cache.json) that no one curates."""
    proc = subprocess.run(["git", "ls-files", "-z", "--", "*.json"], cwd=DATA,
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    return sorted(DATA / name for name in proc.stdout.split("\0") if name)


DATA_FILES = _tracked_data_files()

# Byte-pinned elsewhere, so their bytes are the contract and they keep their
# format: reformatting one is a cross-repo change.
BYTE_PINNED = {
    "profile_gate_test_cases.json": "vendored byte-identical by the Flutter app; "
    "test_profile_gate_fixture_sync.py and the app's profile_gate_fixture_sync_test.dart "
    "pin its sha256",
}

# Formatted in their own commit once the lane editing them has landed. The test
# below fails as soon as a listed file is canonical, so the list only shrinks.
NOT_YET_CANONICAL = {
    "ingredient_quality_map.json",
    "ingredient_interaction_rules.json",
    "standardized_botanicals.json",
}


@pytest.mark.parametrize("path", DATA_FILES, ids=lambda p: str(p.relative_to(DATA)))
def test_data_file_is_canonical_json_without_duplicate_keys(path):
    text = path.read_text(encoding="utf-8")
    blob = db.loads(text)  # raises on a duplicate key, which json would drop silently
    canonical = text == json_text(blob)
    if path.name in BYTE_PINNED:
        return
    if path.name in NOT_YET_CANONICAL:
        assert not canonical, f"{path.name} is canonical now: remove it from NOT_YET_CANONICAL"
        assert json.loads(json_text(blob)) == blob
    else:
        assert canonical, f"{path.name} is not canonical JSON: run scripts/data_batch.py format {path}"


@pytest.mark.parametrize("path", DATA_FILES, ids=lambda p: str(p.relative_to(DATA)))
def test_recount_agrees_with_every_data_file(path):
    blob = db.load(path)
    if isinstance(blob, dict):
        assert db.recount(path.name, blob) == {}


def test_entries_keys_each_shape():
    listed = {"_metadata": {}, "items": [{"id": "A"}, {"id": "A"}, {"name": "no id"}]}
    assert list(db.entries(listed)) == ["items/A", "items/A#2", "items[2]"]
    wrapped = {"_metadata": {}, "aliases": {"x": ["a"], "y": ["b"]}}
    assert list(db.entries(wrapped)) == ["aliases/x", "aliases/y"]
    iqm_like = {"_metadata": {}, "zinc": {"forms": {}}, "iron": {"forms": {}}}
    assert list(db.entries(iqm_like)) == ["zinc", "iron"]


def test_changed_keys_reports_added_removed_and_modified():
    before = {"a": 1, "b": {"x": 1}, "c": 3}
    after = {"b": {"x": 2}, "c": 3, "d": 4}
    assert db.changed_keys(before, after) == (["d"], ["a"], ["b"])


def test_recount_writes_only_existing_fields_and_skips_exceptions():
    blob = {"_metadata": {"total_entries": 1}, "items": [{"id": 1}, {"id": 2}]}
    assert db.recount("x.json", blob) == {"total_entries": (1, 2)}
    assert blob["_metadata"]["total_entries"] == 2
    no_field = {"_metadata": {}, "items": [{"id": 1}]}
    assert db.recount("x.json", no_field) == {} and "total_entries" not in no_field["_metadata"]
    exception = {"_metadata": {"total_entries": 4}, "a": [1], "b": [2]}
    assert db.recount("ingredient_weights.json", exception) == {}


def test_recount_iqm_statistics():
    blob = {
        "_metadata": {"total_entries": 0, "statistics": {"total_forms": 0, "total_form_aliases": 0}},
        "zinc": {"aliases": ["zn"], "forms": {"zinc picolinate": {"aliases": ["a", "b"]}}},
        "iron": {"forms": {"ferrous bisglycinate": {"aliases": []}}},
    }
    changes = db.recount(db.IQM_FILE, blob)
    assert changes == {"total_entries": (0, 2), "statistics.total_forms": (0, 2),
                       "statistics.total_form_aliases": (0, 2)}
    assert set(blob["_metadata"]["statistics"]) == {"total_forms", "total_form_aliases"}


def test_duplicate_keys_are_refused():
    with pytest.raises(ValueError, match="duplicate JSON keys"):
        db.loads('{"a": 1, "a": 2}')


def test_save_bumps_date_only_when_an_entry_changed(tmp_path):
    path = tmp_path / "x.json"
    blob = {"_metadata": {"last_updated": "2000-01-01", "total_entries": 1}, "items": [{"id": 1}]}
    path.write_text(json_text(blob), encoding="utf-8")
    db.save(path, db.load(path))
    assert db.load(path)["_metadata"]["last_updated"] == "2000-01-01"
    edited = db.load(path)
    edited["items"].append({"id": 2})
    assert db.save(path, edited) == {"total_entries": (1, 2)}
    saved = path.read_text(encoding="utf-8")
    assert saved == json_text(db.loads(saved)) and saved.endswith("}\n")
    assert json.loads(saved)["_metadata"]["last_updated"] == date.today().isoformat()


def test_save_refuses_a_file_that_is_not_canonical(tmp_path):
    path = tmp_path / "x.json"
    path.write_text('{"_metadata": {}, "items": []}', encoding="utf-8")
    with pytest.raises(ValueError, match="not canonical"):
        db.save(path, {"_metadata": {}, "items": [{"id": 1}]})


def test_format_file_keeps_content(tmp_path):
    path = tmp_path / "x.json"
    path.write_text('{"note": "a \\u2014 b", "n": 1.50}', encoding="utf-8")
    assert db.format_file(path) is True
    assert path.read_text(encoding="utf-8") == '{\n  "note": "a — b",\n  "n": 1.5\n}\n'
    assert db.format_file(path) is False


def test_landed_flags_missing_unexpected_and_count_drift():
    before = {"_metadata": {"total_entries": 2}, "items": [{"id": "A", "v": 1}, {"id": "B", "v": 1}]}
    after = {"_metadata": {"total_entries": 2},
             "items": [{"id": "A", "v": 2}, {"id": "B", "v": 2}, {"id": "C", "v": 1}]}
    lines, problems = db.landed("x.json", before, after, {"items/A", "items/C", "items/D"})
    assert problems == 3  # B unexpected, D missing, total_entries 2 -> 3
    assert "changed  items/B  UNEXPECTED" in lines
    assert "MISSING  items/D  (expected to change)" in lines
    assert "METADATA total_entries is 2, entries give 3" in lines
    lines, problems = db.landed("x.json", None, after, None)
    assert problems == 1 and lines[0] == "added    items/A"


def test_at_ref_distinguishes_a_missing_file_from_a_bad_ref():
    missing = db.REPO / "scripts" / "data" / "__not_a_data_file__.json"
    assert db.at_ref("HEAD", missing) is None
    assert db.at_ref("HEAD", DATA / "daily_values.json")["_metadata"]
    with pytest.raises(ValueError, match="failed"):
        db.at_ref("no-such-ref-7f3a", DATA / "daily_values.json")
