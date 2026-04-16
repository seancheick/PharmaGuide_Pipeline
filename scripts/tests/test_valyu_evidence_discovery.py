import os
import sys
import importlib
import json
from pathlib import Path

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api_audit.valyu_query_planner import build_search_plan


def test_clinical_refresh_uses_clinical_sources_and_date_window():
    plan = build_search_plan(
        domain="clinical_refresh",
        entity_name="Meriva Curcumin Phytosome",
        months_back=24,
    )

    assert "pubmed" in " ".join(plan["included_sources"]).lower()
    assert plan["start_date"]
    assert plan["end_date"]


def test_harmful_refresh_does_not_reuse_clinical_sources():
    plan = build_search_plan(
        domain="harmful_refresh",
        entity_name="Titanium Dioxide",
        months_back=24,
    )

    joined = " ".join(plan["included_sources"]).lower()
    assert "pubmed" not in joined


def test_cli_module_is_importable_without_valyu_sdk(monkeypatch):
    monkeypatch.delenv("VALYU_API_KEY", raising=False)
    sys.modules.pop("api_audit.valyu_evidence_discovery", None)
    module = importlib.import_module("api_audit.valyu_evidence_discovery")
    assert hasattr(module, "main")


def test_main_rejects_unknown_mode(monkeypatch):
    monkeypatch.delenv("VALYU_API_KEY", raising=False)
    sys.modules.pop("api_audit.valyu_evidence_discovery", None)
    module = importlib.import_module("api_audit.valyu_evidence_discovery")

    with pytest.raises(SystemExit):
        module.main(["unknown-mode"])


def test_main_requires_api_key_for_real_run(monkeypatch):
    monkeypatch.delenv("VALYU_API_KEY", raising=False)
    sys.modules.pop("api_audit.valyu_evidence_discovery", None)
    module = importlib.import_module("api_audit.valyu_evidence_discovery")

    with pytest.raises(SystemExit):
        module.main(["clinical-refresh"])


def test_main_does_not_accept_apply_flag(monkeypatch):
    monkeypatch.delenv("VALYU_API_KEY", raising=False)
    sys.modules.pop("api_audit.valyu_evidence_discovery", None)
    module = importlib.import_module("api_audit.valyu_evidence_discovery")

    with pytest.raises(SystemExit):
        module.main(["clinical-refresh", "--apply"])


class _FakeSearchResponse:
    def __init__(self, rows):
        self.results = rows
        self.success = True


class _FakeValyuClient:
    def __init__(self, rows):
        self._rows = rows

    def search(self, **kwargs):
        return _FakeSearchResponse(self._rows)


def test_execute_search_reads_sdk_results_field():
    sys.modules.pop("api_audit.valyu_evidence_discovery", None)
    module = importlib.import_module("api_audit.valyu_evidence_discovery")

    payload = module.execute_search(
        _FakeValyuClient([{"title": "Result", "url": "https://example.com", "source": "pubmed"}]),
        {
            "query_used": "query",
            "included_sources": ["valyu/valyu-pubmed"],
            "start_date": "2024-01-01",
            "end_date": "2026-01-01",
        },
    )

    assert len(payload["search_results"]) == 1
    assert payload["search_results"][0]["title"] == "Result"


def test_classify_signal_uses_domain_specific_signal_types(monkeypatch):
    sys.modules.pop("api_audit.valyu_evidence_discovery", None)
    module = importlib.import_module("api_audit.valyu_evidence_discovery")

    row = module.classify_signal(
        {
            "domain": "harmful-refresh",
            "entity_type": "harmful_additive",
            "entity_id": "ADD_TEST",
            "entity_name": "Titanium Dioxide",
            "target_file": "harmful_additives.json",
            "query_used": "query",
            "start_date": "2024-01-01",
            "end_date": "2026-01-01",
        },
        {"search_results": [{"title": "FDA update", "url": "https://fda.gov/test", "source": "fda.gov"}]},
    )

    assert row["signal_type"] == "possible_safety_change"


def test_classify_signal_dedupes_repeated_references():
    sys.modules.pop("api_audit.valyu_evidence_discovery", None)
    module = importlib.import_module("api_audit.valyu_evidence_discovery")

    row = module.classify_signal(
        {
            "domain": "clinical-refresh",
            "entity_type": "clinical_entry",
            "entity_id": "BRAND_MERIVA",
            "entity_name": "Meriva Curcumin Phytosome",
            "target_file": "backed_clinical_studies.json",
            "query_used": "query",
            "start_date": "2024-01-01",
            "end_date": "2026-01-01",
        },
        {
            "search_results": [
                {"title": "A", "url": "https://example.com/a", "published_date": "2025-01-01", "source": "valyu/valyu-pubmed"},
                {"title": "A", "url": "https://example.com/a", "published_date": "2025-01-01", "source": "valyu/valyu-pubmed"},
                {"title": "B", "url": "https://example.com/b", "published_date": "2025-02-01", "source": "valyu/valyu-pubmed"},
            ]
        },
    )

    assert len(row["candidate_references"]) == 2
    assert len(row["candidate_sources"]) == 1


def test_classify_signal_returns_none_for_empty_results(monkeypatch):
    sys.modules.pop("api_audit.valyu_evidence_discovery", None)
    module = importlib.import_module("api_audit.valyu_evidence_discovery")

    row = module.classify_signal(
        {
            "domain": "clinical-refresh",
            "entity_type": "clinical_entry",
            "entity_id": "CLINICAL_1",
            "entity_name": "Meriva Curcumin Phytosome",
            "target_file": "backed_clinical_studies.json",
        },
        {"search_results": []},
    )

    assert row is None


def test_run_mode_and_main_do_not_mutate_canonical_files(monkeypatch, tmp_path):
    sys.modules.pop("api_audit.valyu_evidence_discovery", None)
    module = importlib.import_module("api_audit.valyu_evidence_discovery")

    # Resolve canonical files relative to the repo root so this test
    # works regardless of pytest's CWD (previously hardcoded a path
    # that only resolved when run from the repo root).
    repo_root = Path(__file__).resolve().parents[2]
    before = {}
    canonical_files = [
        repo_root / "scripts/data/backed_clinical_studies.json",
        repo_root / "scripts/data/ingredient_quality_map.json",
        repo_root / "scripts/data/harmful_additives.json",
        repo_root / "scripts/data/banned_recalled_ingredients.json",
    ]
    for path in canonical_files:
        before[str(path)] = path.read_text(encoding="utf-8")

    monkeypatch.setattr(
        module,
        "create_valyu_client",
        lambda: _FakeValyuClient(
            [{"title": "Result", "url": "https://example.com", "published_date": "2026-04-01", "source": "fda.gov"}]
        ),
    )

    rc = module.main(["harmful-refresh", "--limit", "1", "--output-dir", str(tmp_path)])
    assert rc == 0

    for path in canonical_files:
        after = path.read_text(encoding="utf-8")
        assert after == before[str(path)]

    queue_files = list(tmp_path.glob("*-review-queue.json"))
    assert queue_files, "expected a review queue report"
    saved_rows = json.loads(queue_files[0].read_text())
    assert saved_rows[0]["auto_apply_allowed"] is False
