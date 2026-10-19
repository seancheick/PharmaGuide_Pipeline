"""Shared reference loaders used by Clean and Enrich fail closed.

2026-10-19 (independent audit of PR #176): `UnitConverter._load_database`
logged a missing or corrupt unit_conversions.json and left empty rule tables,
so every later conversion silently returned "no rule"; the cleaner loaded the
converter lazily, so only folate products would have errored. The UNII
exoneration allowlist loader also returned {} for a missing or corrupt file.
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import enhanced_normalizer
import unit_converter
from dosage_normalizer import DosageNormalizer
from enhanced_normalizer import EnhancedDSLDNormalizer
from enrich_supplements_v3 import SupplementEnricherV3
from unit_converter import UnitConverter


@pytest.fixture
def missing_path(tmp_path):
    return tmp_path / "missing.json"


@pytest.fixture
def corrupt_path(tmp_path):
    path = tmp_path / "corrupt.json"
    path.write_text('{"vitamin_conversions": {', encoding="utf-8")
    return path


@pytest.fixture
def empty_rules_path(tmp_path):
    path = tmp_path / "empty_rules.json"
    path.write_text(json.dumps({"_metadata": {"version": "x"}}), encoding="utf-8")
    return path


@pytest.mark.parametrize("fixture", ["missing_path", "corrupt_path", "empty_rules_path"])
def test_unit_converter_raises_on_unusable_database(fixture, request):
    with pytest.raises(RuntimeError, match="unit conversions"):
        UnitConverter(db_path=request.getfixturevalue(fixture))


def _partial_db(tmp_path, mutate):
    """The shipped database with one section removed or reshaped."""
    from constants import UNIT_CONVERSIONS_DB
    data = json.loads(UNIT_CONVERSIONS_DB.read_text(encoding="utf-8"))
    data = mutate(data)
    path = tmp_path / "partial.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


PARTIAL_DATABASES = {
    # Vitamin E 400 IU d-alpha stayed 400 IU (vitamin_e_unknown) and vitamin A
    # 10,000 IU retinyl palmitate stayed IU (audit of PR #183, 2026-10-19).
    "no_form_patterns": lambda d: {k: v for k, v in d.items() if k != "form_detection_patterns"},
    "no_vitamin_a_retinol_patterns": lambda d: (
        d["form_detection_patterns"]["vitamin_a"].pop("retinol_patterns"), d)[1],
    "no_vitamin_e_patterns": lambda d: (d["form_detection_patterns"].pop("vitamin_e"), d)[1],
    # Vitamin D3 returned success=False instead of stopping the run.
    "no_vitamin_d3_rule": lambda d: (d["vitamin_conversions"].pop("vitamin_d3"), d)[1],
    # Loaded, then every conversion raised AttributeError.
    "vitamin_conversions_list": lambda d: {**d, "vitamin_conversions": ["vitamin_d3"]},
    "top_level_list": lambda d: [d],
    "rule_without_conversions": lambda d: (
        d["vitamin_conversions"]["vitamin_d3"].pop("conversions"), d)[1],
}


@pytest.mark.parametrize("case", sorted(PARTIAL_DATABASES))
def test_unit_converter_raises_on_partial_database(tmp_path, case):
    with pytest.raises(RuntimeError, match="unit conversions"):
        UnitConverter(db_path=_partial_db(tmp_path, PARTIAL_DATABASES[case]))


def test_required_rule_ids_cover_every_rule_the_converter_names():
    """A rule id written in unit_converter.py must be in REQUIRED_VITAMIN_RULES."""
    import re
    from constants import UNIT_CONVERSIONS_DB
    rule_ids = json.loads(UNIT_CONVERSIONS_DB.read_text(encoding="utf-8"))["vitamin_conversions"]
    source = open(unit_converter.__file__, encoding="utf-8").read()
    named = {rule for rule in rule_ids if re.search(rf"['\"]{re.escape(rule)}['\"]", source)}
    assert named <= unit_converter.REQUIRED_VITAMIN_RULES
    assert unit_converter.REQUIRED_VITAMIN_RULES <= set(rule_ids)


@pytest.fixture
def default_unit_db(monkeypatch):
    """Point the converter's default path at a test file and drop the singleton."""
    def point_at(path):
        monkeypatch.setattr(unit_converter, "UNIT_CONVERSIONS_DB", path)
        monkeypatch.setattr(unit_converter, "_converter_instance", None)
    return point_at


@pytest.mark.parametrize("fixture", ["missing_path", "corrupt_path"])
def test_cleaner_init_stops_on_unusable_unit_database(fixture, request, default_unit_db):
    default_unit_db(request.getfixturevalue(fixture))
    with pytest.raises(RuntimeError, match="unit conversions"):
        EnhancedDSLDNormalizer()


@pytest.mark.parametrize("fixture", ["missing_path", "corrupt_path"])
def test_enricher_init_stops_on_unusable_unit_database(fixture, request, default_unit_db):
    default_unit_db(request.getfixturevalue(fixture))
    with pytest.raises(RuntimeError, match="unit conversions"):
        DosageNormalizer()
    with pytest.raises(RuntimeError, match="unit conversions"):
        SupplementEnricherV3()


@pytest.fixture
def unii_allowlist_path(tmp_path):
    enhanced_normalizer._load_unii_exoneration_label_tokens.cache_clear()
    yield tmp_path / "unii_exoneration_allowlist.json"
    enhanced_normalizer._load_unii_exoneration_label_tokens.cache_clear()


def test_unii_exoneration_allowlist_missing_raises(unii_allowlist_path):
    with pytest.raises(RuntimeError, match="unii_exoneration_allowlist"):
        enhanced_normalizer._load_unii_exoneration_label_tokens(unii_allowlist_path)


def test_unii_exoneration_allowlist_corrupt_raises(unii_allowlist_path):
    unii_allowlist_path.write_text('{"exonerations": [', encoding="utf-8")
    with pytest.raises(RuntimeError, match="unii_exoneration_allowlist"):
        enhanced_normalizer._load_unii_exoneration_label_tokens(unii_allowlist_path)


def test_unii_exoneration_allowlist_without_exonerations_raises(unii_allowlist_path):
    unii_allowlist_path.write_text(json.dumps({"_metadata": {}}), encoding="utf-8")
    with pytest.raises(RuntimeError, match="unii_exoneration_allowlist"):
        enhanced_normalizer._load_unii_exoneration_label_tokens(unii_allowlist_path)


def test_shipped_unii_exoneration_allowlist_loads(unii_allowlist_path):
    assert enhanced_normalizer._load_unii_exoneration_label_tokens()


def test_shipped_unit_database_passes_the_structure_check():
    converter = UnitConverter()
    assert converter.convert_nutrient(
        "Vitamin E", 400, "IU", ingredient_name="d-alpha tocopherol"
    ).converted_value == pytest.approx(268.0)


def test_pool_run_with_unusable_unit_database_stops_without_cleaned_output(
    tmp_path, monkeypatch, missing_path, default_unit_db,
):
    """Worker pool path: a failed initializer breaks the pool, each file is
    quarantined as BrokenProcessPool, and the main process's own normalizer
    (built for the unmapped report) raises, so no stage manifest is written and
    clean_dsld_data exits 1. Spawned workers cannot see a monkeypatch, so the
    pool is replaced by one whose futures fail the way a broken pool does."""
    import concurrent.futures
    from concurrent.futures.process import BrokenProcessPool
    import batch_processor

    class BrokenPool:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def submit(self, *args, **kwargs):
            future = concurrent.futures.Future()
            future.set_exception(BrokenProcessPool("A process in the process pool was terminated"))
            return future

    fixture = os.path.join(os.path.dirname(__file__), "fixtures", "bcaa_1063_raw.json")
    label = json.load(open(fixture, encoding="utf-8"))
    files = []
    for offset in range(2):
        label["id"] = 900000 + offset
        path = tmp_path / f"{label['id']}.json"
        path.write_text(json.dumps(label), encoding="utf-8")
        files.append(path)

    default_unit_db(missing_path)
    monkeypatch.setattr(batch_processor, "ProcessPoolExecutor", BrokenPool)
    processor = batch_processor.BatchProcessor({
        "processing": {"batch_size": 10, "max_workers": 2, "min_files_per_worker": 0},
        "paths": {"output_directory": str(tmp_path / "out"), "log_directory": str(tmp_path / "logs")},
        "validation": {"verify_output": False, "check_input_integrity": False},
        "output_format": {},
        "ui": {"show_progress_bar": False},
    })

    with pytest.raises(RuntimeError, match="unit conversions"):
        processor.process_all_files(files, resume=False)

    records = sorted((processor.output_dir / "errors").glob("*_error.json"))
    assert len(records) == 2
    assert all("BrokenProcessPool" in r.read_text(encoding="utf-8") for r in records)
    cleaned = processor.output_dir / "cleaned"
    for batch in cleaned.glob("cleaned_batch_*.json"):
        assert json.loads(batch.read_text(encoding="utf-8")) in ([], None)
    assert not (cleaned / ".stage_manifest.json").exists()


@pytest.mark.parametrize("exonerations", [
    "not-a-list",
    [1],
    [{"unii": None, "entries": [{"entry_id": "x"}]}],
])
def test_unii_exoneration_allowlist_malformed_raises(unii_allowlist_path, exonerations):
    unii_allowlist_path.write_text(json.dumps({"exonerations": exonerations}), encoding="utf-8")
    with pytest.raises(RuntimeError, match="unii_exoneration_allowlist"):
        enhanced_normalizer._load_unii_exoneration_label_tokens(unii_allowlist_path)
