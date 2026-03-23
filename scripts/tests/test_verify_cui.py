#!/usr/bin/env python3
"""Tests for verify_cui.py safety, runbook text, and performance guardrails."""

import io
import json
import os
import sys
from pathlib import Path
from urllib.error import URLError

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import verify_cui
from verify_cui import UMLSClient, should_apply_cui_fix, verify_cui_for_entry


class AliasAwareClient:
    def lookup_cui(self, cui):
        if cui == "C_EXIST":
            return {"cui": "C_EXIST", "name": "Example Variant Expanded"}
        return None

    def search_exact(self, term):
        if term == "beta-methylphenyl-ethylamine":
            return {"cui": "C4041589", "name": "beta-methylphenyl-ethylamine", "source": "RXNORM"}
        if term == "XV":
            return {"cui": "C_EXIST", "name": "Example Variant Expanded", "source": "TEST"}
        if term == "Example Variant Expanded":
            return {"cui": "C_EXIST", "name": "Example Variant Expanded", "source": "TEST"}
        return None

    def search(self, term, max_results=3):
        return [{"cui": "C_FALLBACK", "name": f"{term} fallback", "source": "TEST"}]


def test_verify_cui_for_entry_uses_exact_alias_before_word_search():
    report = verify_cui_for_entry(
        AliasAwareClient(),
        "BANNED_BMPEA",
        "BMPEA",
        None,
        ["beta-methylphenyl-ethylamine"],
    )

    assert report["status"] == "MISSING_CUI"
    assert report["suggested_cui"] == "C4041589"
    assert report["suggested_name"] == "beta-methylphenyl-ethylamine"
    assert report["match_source"] == "curated_override"


def test_verify_cui_for_entry_uses_curated_none_override_for_policy_entries():
    report = verify_cui_for_entry(
        AliasAwareClient(),
        "BANNED_ADD_SYNTHETIC_FOOD_ACIDS",
        "Policy Watchlist: Synthetic Food Acids",
        None,
        ["synthetic food acids", "fumaric acid"],
    )

    assert report["status"] == "NOT_FOUND"
    assert report["suggested_cui"] is None
    assert report["match_source"] == "curated_override_none"


def test_verify_cui_for_entry_accepts_existing_cui_when_exact_standard_resolves_same_concept():
    report = verify_cui_for_entry(
        AliasAwareClient(),
        "VARIANT_EV",
        "XV",
        "C_EXIST",
        [],
    )

    assert report["status"] == "VERIFIED"
    assert report["suggested_cui"] == "C_EXIST"
    assert report["match_source"] == "exact_standard"


def test_verify_cui_for_entry_suppresses_broad_search_for_annotated_null():
    report = verify_cui_for_entry(
        AliasAwareClient(),
        "ADD_UNSPECIFIED_COLORS",
        "Unspecified Colors",
        None,
        ["color"],
        cui_status="no_single_umls_concept",
    )

    assert report["status"] == "ANNOTATED_NULL"
    assert report["action"] is None
    assert report["suggested_cui"] is None
    assert report["match_source"] == "curated_override_none"


def test_verify_cui_for_entry_flags_exact_match_for_annotated_null_review():
    report = verify_cui_for_entry(
        AliasAwareClient(),
        "ADD_VARIANT",
        "Unmapped Variant",
        None,
        ["XV"],
        cui_status="no_confirmed_umls_match",
    )

    assert report["status"] == "ANNOTATED_NULL_REVIEW"
    assert report["suggested_cui"] == "C_EXIST"
    assert report["match_source"] == "exact_alias"
    assert "Annotated null should be reviewed" in report["action"]


def test_should_apply_cui_fix_is_safe_by_default():
    exact_missing = {"status": "MISSING_CUI", "match_source": "exact_standard", "suggested_cui": "C1"}
    fuzzy_missing = {"status": "MISSING_CUI", "match_source": "search", "suggested_cui": "C2"}
    mismatch = {"status": "MISMATCH", "match_source": "exact_standard", "suggested_cui": "C3"}

    assert should_apply_cui_fix(exact_missing, allow_mismatch_overwrite=False) is True
    assert should_apply_cui_fix(fuzzy_missing, allow_mismatch_overwrite=False) is False
    assert should_apply_cui_fix(mismatch, allow_mismatch_overwrite=False) is False
    assert should_apply_cui_fix(mismatch, allow_mismatch_overwrite=True) is True


def test_umls_client_reuses_disk_cache(tmp_path, monkeypatch):
    calls = {"count": 0}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            payload = {
                "result": {
                    "results": [{"ui": "C0529793", "name": "Sildenafil", "rootSource": "RXNORM"}]
                }
            }
            return json.dumps(payload).encode()

    def fake_urlopen(req, timeout, context):
        calls["count"] += 1
        return FakeResponse()

    monkeypatch.setattr("verify_cui.urllib.request.urlopen", fake_urlopen)

    cache_path = tmp_path / "umls_cache.json"
    client = UMLSClient("api-key", cache_path=cache_path)

    first = client.search_exact("Sildenafil")
    second = client.search_exact("Sildenafil")

    assert first["cui"] == "C0529793"
    assert second["cui"] == "C0529793"
    assert calls["count"] == 1
    assert cache_path.exists()
    cache_data = json.loads(cache_path.read_text())
    cached_value = next(iter(cache_data.values()))
    assert "stored_at" in cached_value
    assert "expires_at" in cached_value
    assert "payload" in cached_value


def test_umls_client_can_read_warm_cache_without_api_key(tmp_path, monkeypatch):
    monkeypatch.setattr("verify_cui.urllib.request.urlopen", lambda *args, **kwargs: pytest.fail("network should not be called"))

    cache_path = tmp_path / "umls_cache.json"
    cached_url = (
        "https://uts-ws.nlm.nih.gov/rest/search/current"
        "?string=Sildenafil&pageSize=1&searchType=exact"
    )
    cache_path.write_text(
        json.dumps(
            {
                cached_url: {
                    "result": {
                        "results": [{"ui": "C0529793", "name": "Sildenafil", "rootSource": "RXNORM"}]
                    }
                }
            }
        )
    )

    offline_client = UMLSClient("", cache_path=cache_path)
    cached = offline_client.search_exact("Sildenafil")

    assert cached["cui"] == "C0529793"


def test_umls_client_opens_circuit_after_repeated_transport_failures(monkeypatch):
    calls = {"count": 0}

    def failing_urlopen(req, timeout, context):
        calls["count"] += 1
        raise URLError("offline")

    monkeypatch.setattr("verify_cui.urllib.request.urlopen", failing_urlopen)

    client = UMLSClient("api-key", timeout_seconds=0.01, failure_limit=2)

    assert client.search_exact("Sildenafil") is None
    assert client.search_exact("Tadalafil") is None
    assert client.search_exact("Meloxicam") is None

    assert client.circuit_open is True
    assert calls["count"] == 2


def test_verify_cui_module_docstring_includes_operator_runbook():
    doc = verify_cui.__doc__ or ""

    assert "--apply-mismatches" in doc
    assert "leave cui null" in doc.lower()
    assert "exact alias" in doc.lower()
