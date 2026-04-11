"""Unit tests for scripts/api_audit/verify_interactions.py.

All tests are offline — network clients are injected via stubs. Live
integration tests live in test_verify_interactions_live.py and are gated
by PHARMAGUIDE_LIVE_TESTS=1.

Covers every pure-function check defined in INTERACTION_DB_SPEC v2.2.0 §6.2.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Make scripts/api_audit importable
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api_audit"))

import verify_interactions as vi  # noqa: E402


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture
def iqm_index() -> dict[str, str]:
    # Realistic sample: vitamin K → vitamin_k, calcium → calcium, etc.
    return {
        "C0042839": "vitamin_k",
        "C0006675": "calcium",
        "C0020961": "iron",
        "C0025527": "magnesium",
    }


@pytest.fixture
def drug_classes() -> dict:
    return {
        "_metadata": {"schema_version": "1.0.0"},
        "classes": {
            "class:statins": {
                "display_name": "Statins",
                "member_rxcuis": ["83367", "36567", "42463"],
                "member_names": ["atorvastatin", "simvastatin", "rosuvastatin"],
                "rxclass_id": "C10AA",
            },
            "class:ssris": {
                "display_name": "SSRIs",
                "member_rxcuis": ["36437", "37418"],
                "member_names": ["sertraline", "fluoxetine"],
                "rxclass_id": "N06AB",
            },
        },
    }


@pytest.fixture
def ctx_offline(iqm_index, drug_classes):
    return vi.VerifyContext(
        iqm_cui_index=iqm_index,
        drug_classes=drug_classes,
        rxnorm=None,
        umls=None,
    )


@pytest.fixture
def warfarin_vitk_entry() -> dict:
    return {
        "id": "DDI_WAR_VITK",
        "type": "Med-Sup",
        "agent1_name": "Warfarin",
        "agent1_id": "11289",
        "agent2_name": "Vitamin K",
        "agent2_id": "C0042839",
        "severity": "Major",
        "interaction_effect_type": "Inhibitor",
        "mechanism": "Affects INR/clotting time",
        "management": "Monitor INR closely. Maintain consistent vitamin K intake.",
        "source_urls": ["https://pubmed.ncbi.nlm.nih.gov/28458697/"],
    }


# --------------------------------------------------------------------------- #
# Check 1: schema validation
# --------------------------------------------------------------------------- #


def test_schema_valid_entry_passes(warfarin_vitk_entry):
    assert vi.validate_schema(warfarin_vitk_entry) == []


def test_schema_missing_required_field_fails(warfarin_vitk_entry):
    del warfarin_vitk_entry["mechanism"]
    errors = vi.validate_schema(warfarin_vitk_entry)
    assert any("mechanism" in e for e in errors)


def test_schema_empty_required_field_fails(warfarin_vitk_entry):
    warfarin_vitk_entry["management"] = "   "
    errors = vi.validate_schema(warfarin_vitk_entry)
    assert any("management" in e for e in errors)


def test_schema_invalid_type_fails(warfarin_vitk_entry):
    warfarin_vitk_entry["type"] = "Drug-Thing"
    errors = vi.validate_schema(warfarin_vitk_entry)
    assert any("invalid type" in e for e in errors)


def test_schema_invalid_severity_fails(warfarin_vitk_entry):
    warfarin_vitk_entry["severity"] = "Critical"
    errors = vi.validate_schema(warfarin_vitk_entry)
    assert any("invalid severity" in e for e in errors)


def test_schema_invalid_effect_type_fails(warfarin_vitk_entry):
    warfarin_vitk_entry["interaction_effect_type"] = "Blocker"
    errors = vi.validate_schema(warfarin_vitk_entry)
    assert any("invalid interaction_effect_type" in e for e in errors)


def test_schema_invalid_agent_id_fails(warfarin_vitk_entry):
    warfarin_vitk_entry["agent2_id"] = "not-a-real-id"
    errors = vi.validate_schema(warfarin_vitk_entry)
    assert any("invalid agent2_id" in e for e in errors)


def test_schema_allows_class_agent_id(warfarin_vitk_entry):
    warfarin_vitk_entry["agent1_id"] = "class:statins"
    assert vi.validate_schema(warfarin_vitk_entry) == []


def test_schema_source_urls_must_be_list(warfarin_vitk_entry):
    warfarin_vitk_entry["source_urls"] = "not a list"
    errors = vi.validate_schema(warfarin_vitk_entry)
    assert any("source_urls" in e for e in errors)


def test_schema_source_pmids_must_be_digit_strings(warfarin_vitk_entry):
    warfarin_vitk_entry["source_pmids"] = ["abc"]
    errors = vi.validate_schema(warfarin_vitk_entry)
    assert any("source_pmids" in e for e in errors)


# --------------------------------------------------------------------------- #
# Check 2: duplicate detection
# --------------------------------------------------------------------------- #


def test_detect_duplicates_finds_repeats():
    entries = [{"id": "A"}, {"id": "B"}, {"id": "A"}]
    dupes = vi.detect_duplicates(entries)
    assert "A" in dupes
    assert dupes["A"] == [0, 2]
    assert "B" not in dupes


def test_detect_duplicates_empty_when_unique():
    entries = [{"id": "A"}, {"id": "B"}]
    assert vi.detect_duplicates(entries) == {}


# --------------------------------------------------------------------------- #
# Agent classification
# --------------------------------------------------------------------------- #


def test_classify_agent_rxcui():
    assert vi.classify_agent("11289") == "drug"


def test_classify_agent_cui():
    assert vi.classify_agent("C0042839") == "supplement"


def test_classify_agent_class():
    assert vi.classify_agent("class:statins") == "class"


def test_classify_agent_unknown():
    assert vi.classify_agent("random-thing") == "unknown"
    assert vi.classify_agent("") == "unknown"


# --------------------------------------------------------------------------- #
# Check 8: severity normalization
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "draft,expected",
    [
        ("Contraindicated", "contraindicated"),
        ("Major", "avoid"),
        ("Moderate", "caution"),
        ("Minor", "monitor"),
        ("MAJOR", "avoid"),  # case-insensitive
        ("major", "avoid"),
    ],
)
def test_normalize_severity_happy_path(draft, expected):
    assert vi.normalize_severity(draft) == expected


def test_normalize_severity_unknown_returns_none():
    assert vi.normalize_severity("Whatever") is None
    assert vi.normalize_severity("") is None


# --------------------------------------------------------------------------- #
# Check 7: direction normalization
# --------------------------------------------------------------------------- #


def test_normalize_direction_preserves_drug_first(warfarin_vitk_entry):
    norm = vi.normalize_direction(warfarin_vitk_entry)
    # warfarin (drug, rxcui) already first — no swap
    assert norm["agent1_name"] == "Warfarin"
    assert norm["agent2_name"] == "Vitamin K"
    assert norm["agent1_type"] == "drug"
    assert norm["agent2_type"] == "supplement"
    assert norm["type_authored"] == "Med-Sup"


def test_normalize_direction_swaps_supplement_first():
    entry = {
        "id": "X",
        "type": "Sup-Med",
        "agent1_name": "Vitamin K",
        "agent1_id": "C0042839",
        "agent2_name": "Warfarin",
        "agent2_id": "11289",
        "severity": "Major",
        "mechanism": "m",
        "management": "m",
    }
    norm = vi.normalize_direction(entry)
    assert norm["agent1_name"] == "Warfarin"
    assert norm["agent2_name"] == "Vitamin K"
    assert norm["agent1_type"] == "drug"
    assert norm["agent2_type"] == "supplement"
    assert norm["type_authored"] == "Sup-Med"


def test_normalize_direction_stable_sup_sup_order():
    entry = {
        "id": "X",
        "type": "Sup-Sup",
        "agent1_name": "Iron",
        "agent1_id": "C0020961",
        "agent2_name": "Calcium",
        "agent2_id": "C0006675",
        "severity": "Moderate",
        "mechanism": "m",
        "management": "m",
    }
    norm = vi.normalize_direction(entry)
    # Lower CUI string sorts first
    assert norm["agent1_id"] == "C0006675"
    assert norm["agent1_name"] == "Calcium"


# --------------------------------------------------------------------------- #
# Check 10: PMID extraction
# --------------------------------------------------------------------------- #


def test_extract_pmids_from_pubmed_urls():
    urls = [
        "https://pubmed.ncbi.nlm.nih.gov/28458697/",
        "https://www.ncbi.nlm.nih.gov/pubmed/12345678",
        "https://example.com/not-a-pmid",
    ]
    assert vi.extract_pmids_from_urls(urls) == ["28458697", "12345678"]


def test_extract_pmids_skips_bookshelf_urls():
    urls = ["https://www.ncbi.nlm.nih.gov/books/NBK501808/"]
    assert vi.extract_pmids_from_urls(urls) == []


def test_extract_pmids_dedupe():
    urls = [
        "https://pubmed.ncbi.nlm.nih.gov/28458697/",
        "https://pubmed.ncbi.nlm.nih.gov/28458697",
    ]
    assert vi.extract_pmids_from_urls(urls) == ["28458697"]


def test_extract_pmids_handles_none():
    assert vi.extract_pmids_from_urls(None) == []
    assert vi.extract_pmids_from_urls([]) == []


# --------------------------------------------------------------------------- #
# Check 9: Major+ source gate
# --------------------------------------------------------------------------- #


def test_major_source_gate_passes_with_url(warfarin_vitk_entry):
    assert vi.check_major_source_gate(warfarin_vitk_entry) is True


def test_major_source_gate_passes_with_pmid_only():
    entry = {"severity": "Contraindicated", "source_pmids": ["12345678"]}
    assert vi.check_major_source_gate(entry) is True


def test_major_source_gate_blocks_empty_major():
    entry = {"severity": "Major", "source_urls": []}
    assert vi.check_major_source_gate(entry) is False


def test_major_source_gate_blocks_empty_contraindicated():
    entry = {"severity": "Contraindicated"}
    assert vi.check_major_source_gate(entry) is False


def test_major_source_gate_always_passes_minor():
    entry = {"severity": "Minor"}
    assert vi.check_major_source_gate(entry) is True


def test_major_source_gate_always_passes_moderate():
    entry = {"severity": "Moderate", "source_urls": []}
    assert vi.check_major_source_gate(entry) is True


# --------------------------------------------------------------------------- #
# Check 5: canonical_id mapping
# --------------------------------------------------------------------------- #


def test_map_canonical_id_hit(iqm_index):
    assert vi.map_canonical_id("C0042839", "supplement", iqm_index) == "vitamin_k"


def test_map_canonical_id_miss(iqm_index):
    assert vi.map_canonical_id("C9999999", "supplement", iqm_index) is None


def test_map_canonical_id_ignores_drug(iqm_index):
    assert vi.map_canonical_id("11289", "drug", iqm_index) is None


def test_build_iqm_cui_index_skips_metadata_and_missing_cui():
    iqm = {
        "_metadata": {"schema_version": "5.1.0"},
        "vitamin_k": {"cui": "C0042839", "standard_name": "Vitamin K"},
        "mystery": {"standard_name": "Mystery"},  # no cui
        "duplicate_cui": {"cui": "C0042839", "standard_name": "Dup"},
    }
    idx = vi.build_iqm_cui_index(iqm)
    # First-wins semantics
    assert idx == {"C0042839": "vitamin_k"}


# --------------------------------------------------------------------------- #
# Check 6: drug class expansion
# --------------------------------------------------------------------------- #


def test_expand_drug_class_known(drug_classes):
    rxcuis = vi.expand_drug_class("class:statins", drug_classes)
    assert "83367" in rxcuis
    assert len(rxcuis) == 3


def test_expand_drug_class_unknown(drug_classes):
    assert vi.expand_drug_class("class:does_not_exist", drug_classes) is None


# --------------------------------------------------------------------------- #
# End-to-end verify_entry / verify_all — pure (no network)
# --------------------------------------------------------------------------- #


def test_verify_entry_happy_path(warfarin_vitk_entry, ctx_offline):
    report = vi.VerificationReport(total_entries=1)
    normalized = vi.verify_entry(warfarin_vitk_entry, ctx_offline, report)
    assert normalized is not None
    assert normalized["severity"] == "avoid"
    assert normalized["agent2_canonical_id"] == "vitamin_k"
    assert "28458697" in normalized["source_pmids"]
    assert report.errors == 0


def test_verify_entry_blocks_empty_major(ctx_offline):
    entry = {
        "id": "BAD",
        "type": "Med-Sup",
        "agent1_name": "Drug",
        "agent1_id": "11289",
        "agent2_name": "Thing",
        "agent2_id": "C0042839",
        "severity": "Major",
        "mechanism": "m",
        "management": "m",
        "source_urls": [],
    }
    report = vi.VerificationReport(total_entries=1)
    result = vi.verify_entry(entry, ctx_offline, report)
    assert result is None
    assert report.errors == 1
    assert report.blocked_by[0]["id"] == "BAD"


def test_verify_entry_warns_unmapped_supplement(ctx_offline):
    entry = {
        "id": "ORPHAN",
        "type": "Med-Sup",
        "agent1_name": "Warfarin",
        "agent1_id": "11289",
        "agent2_name": "Unknown Herb",
        "agent2_id": "C9999999",
        "severity": "Moderate",
        "mechanism": "m",
        "management": "m",
    }
    report = vi.VerificationReport(total_entries=1)
    result = vi.verify_entry(entry, ctx_offline, report)
    assert result is not None
    assert result["agent2_canonical_id"] is None
    assert report.warnings >= 1
    assert any(u["cui"] == "C9999999" for u in report.unmapped_supplements)


def test_verify_entry_blocks_unknown_class(ctx_offline):
    entry = {
        "id": "BADCLS",
        "type": "Med-Sup",
        "agent1_name": "Some class",
        "agent1_id": "class:bogus",
        "agent2_name": "Vitamin K",
        "agent2_id": "C0042839",
        "severity": "Major",
        "mechanism": "m",
        "management": "m",
        "source_urls": ["https://pubmed.ncbi.nlm.nih.gov/1/"],
    }
    report = vi.VerificationReport(total_entries=1)
    result = vi.verify_entry(entry, ctx_offline, report)
    assert result is None
    assert any(c["class_id"] == "class:bogus" for c in report.unknown_classes)


def test_verify_all_detects_duplicates(ctx_offline, warfarin_vitk_entry):
    dup = dict(warfarin_vitk_entry)
    report, normalized = vi.verify_all([warfarin_vitk_entry, dup], ctx_offline)
    assert report.errors >= 1
    # Only one copy survives
    assert len(normalized) == 1


# --------------------------------------------------------------------------- #
# Network-dependent paths with injected stubs
# --------------------------------------------------------------------------- #


class FakeRxNorm:
    def __init__(self, data: dict[str, dict | None]):
        self.data = data

    def properties(self, rxcui: str):
        return self.data.get(rxcui)


class FakeUMLS:
    def __init__(self, exact: dict[str, dict | None]):
        self.exact = exact

    def search_exact(self, term: str):
        return self.exact.get(term.lower())

    def lookup_cui(self, cui: str):
        return None


def test_verify_entry_rxcui_mismatch_warning(iqm_index, drug_classes, warfarin_vitk_entry):
    ctx = vi.VerifyContext(
        iqm_cui_index=iqm_index,
        drug_classes=drug_classes,
        rxnorm=FakeRxNorm({"11289": {"name": "tylenol", "synonym": "", "tty": "IN"}}),
    )
    report = vi.VerificationReport(total_entries=1)
    result = vi.verify_entry(warfarin_vitk_entry, ctx, report)
    assert result is not None  # warning, not error
    assert report.warnings >= 1
    assert len(report.rxcui_mismatches) == 1


def test_verify_entry_rxcui_not_found_is_error(iqm_index, drug_classes, warfarin_vitk_entry):
    ctx = vi.VerifyContext(
        iqm_cui_index=iqm_index,
        drug_classes=drug_classes,
        rxnorm=FakeRxNorm({"11289": None}),
    )
    report = vi.VerificationReport(total_entries=1)
    result = vi.verify_entry(warfarin_vitk_entry, ctx, report)
    assert result is None
    assert report.errors >= 1


def test_verify_entry_cui_mismatch_autocorrects(iqm_index, drug_classes):
    entry = {
        "id": "WRONG_CUI",
        "type": "Med-Sup",
        "agent1_name": "Warfarin",
        "agent1_id": "11289",
        "agent2_name": "Vitamin K",
        "agent2_id": "C0042810",  # wrong — real is C0042839
        "severity": "Major",
        "mechanism": "m",
        "management": "m",
        "source_urls": ["https://pubmed.ncbi.nlm.nih.gov/28458697/"],
    }
    ctx = vi.VerifyContext(
        iqm_cui_index=iqm_index,
        drug_classes=drug_classes,
        umls=FakeUMLS({"vitamin k": {"cui": "C0042839", "name": "Vitamin K"}}),
    )
    report = vi.VerificationReport(total_entries=1)
    result = vi.verify_entry(entry, ctx, report)
    assert result is not None
    assert result["agent2_id"] == "C0042839"  # corrected
    assert result["agent2_canonical_id"] == "vitamin_k"  # re-mapped
    assert len(report.cui_corrections) == 1


# --------------------------------------------------------------------------- #
# load_drafts
# --------------------------------------------------------------------------- #


def test_load_drafts_reads_flat_list(tmp_path):
    shard = tmp_path / "a.json"
    shard.write_text(json.dumps([{"id": "A"}, {"id": "B"}]))
    entries = vi.load_drafts(tmp_path)
    assert len(entries) == 2


def test_load_drafts_reads_interactions_key(tmp_path):
    shard = tmp_path / "b.json"
    shard.write_text(json.dumps({"interactions": [{"id": "X"}]}))
    entries = vi.load_drafts(tmp_path)
    assert entries == [{"id": "X"}]


def test_load_drafts_merges_multiple_shards(tmp_path):
    (tmp_path / "1.json").write_text(json.dumps([{"id": "A"}]))
    (tmp_path / "2.json").write_text(json.dumps([{"id": "B"}]))
    entries = vi.load_drafts(tmp_path)
    ids = {e["id"] for e in entries}
    assert ids == {"A", "B"}


def test_load_drafts_single_file(tmp_path):
    shard = tmp_path / "one.json"
    shard.write_text(json.dumps([{"id": "Z"}]))
    entries = vi.load_drafts(shard)
    assert entries == [{"id": "Z"}]


def test_load_drafts_missing_path_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        vi.load_drafts(tmp_path / "nope")


# --------------------------------------------------------------------------- #
# CLI smoke test (uses tmp_path and offline mode)
# --------------------------------------------------------------------------- #


def test_cli_offline_happy_path(tmp_path, monkeypatch, warfarin_vitk_entry):
    drafts = tmp_path / "drafts"
    drafts.mkdir()
    (drafts / "d.json").write_text(json.dumps([warfarin_vitk_entry]))

    # Minimal IQM + drug_classes stubs
    iqm = tmp_path / "iqm.json"
    iqm.write_text(json.dumps({"vitamin_k": {"cui": "C0042839", "standard_name": "Vitamin K"}}))
    dc = tmp_path / "dc.json"
    dc.write_text(json.dumps({"_metadata": {"schema_version": "1.0.0"}, "classes": {}}))

    report_path = tmp_path / "report.json"
    normalized_path = tmp_path / "normalized.json"

    rc = vi.main(
        [
            "--drafts",
            str(drafts),
            "--iqm",
            str(iqm),
            "--drug-classes",
            str(dc),
            "--report",
            str(report_path),
            "--normalized-out",
            str(normalized_path),
            "--offline",
        ]
    )
    assert rc == 0
    report = json.loads(report_path.read_text())
    assert report["total_entries"] == 1
    assert report["valid"] == 1
    assert report["errors"] == 0

    normalized = json.loads(normalized_path.read_text())
    assert len(normalized["interactions"]) == 1
    assert normalized["interactions"][0]["severity"] == "avoid"


def test_cli_exits_1_on_errors(tmp_path):
    drafts = tmp_path / "drafts"
    drafts.mkdir()
    # Major severity with no sources → blocked
    bad = {
        "id": "BAD",
        "type": "Med-Sup",
        "agent1_name": "Drug",
        "agent1_id": "11289",
        "agent2_name": "Thing",
        "agent2_id": "C0042839",
        "severity": "Major",
        "mechanism": "m",
        "management": "m",
        "source_urls": [],
    }
    (drafts / "d.json").write_text(json.dumps([bad]))
    iqm = tmp_path / "iqm.json"
    iqm.write_text(json.dumps({}))
    dc = tmp_path / "dc.json"
    dc.write_text(json.dumps({"classes": {}}))

    rc = vi.main(
        [
            "--drafts",
            str(drafts),
            "--iqm",
            str(iqm),
            "--drug-classes",
            str(dc),
            "--offline",
        ]
    )
    assert rc == 1
