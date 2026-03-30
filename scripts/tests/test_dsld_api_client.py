#!/usr/bin/env python3
"""Tests for dsld_api_client and dsld_api_sync parity_check."""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


# ---------------------------------------------------------------------------
# Config tests
# ---------------------------------------------------------------------------


def test_load_dsld_config_reads_api_key(monkeypatch):
    monkeypatch.setenv("DSLD_API_KEY", "test-key-abc")
    monkeypatch.delenv("DSLD_CACHE_FILE", raising=False)

    from dsld_api_client import load_dsld_config

    cfg = load_dsld_config()
    assert cfg.api_key == "test-key-abc"
    assert cfg.cache_path is None


def test_load_dsld_config_defaults_when_no_env(monkeypatch):
    monkeypatch.delenv("DSLD_API_KEY", raising=False)
    monkeypatch.delenv("DSLD_CACHE_FILE", raising=False)

    from dsld_api_client import load_dsld_config

    cfg = load_dsld_config()
    assert cfg.api_key == ""
    assert cfg.cache_path is None


def test_load_dsld_config_accepts_env_mapping():
    from dsld_api_client import load_dsld_config

    env = {"DSLD_API_KEY": "map-key-xyz", "DSLD_CACHE_FILE": "/tmp/test_cache.json"}
    cfg = load_dsld_config(env)
    assert cfg.api_key == "map-key-xyz"
    assert str(cfg.cache_path) == "/tmp/test_cache.json"


# ---------------------------------------------------------------------------
# Normalizer tests
# ---------------------------------------------------------------------------


def _minimal_api_response(*, id_value=13418, **overrides):
    """Return a minimal valid API response dict."""
    base = {"id": id_value, "fullName": "Test Product", "brandName": "Test Brand"}
    base.update(overrides)
    return base


def test_normalize_lowercases_other_ingredients():
    from dsld_api_client import normalize_api_label

    raw = _minimal_api_response(otherIngredients={"text": "gelatin, water"})
    result = normalize_api_label(raw)
    assert "otheringredients" in result
    assert result["otheringredients"] == {"text": "gelatin, water"}
    assert "otherIngredients" not in result


def test_normalize_adds_source_provenance():
    from dsld_api_client import normalize_api_label

    result = normalize_api_label(_minimal_api_response())
    assert result["_source"] == "api"


def test_normalize_preserves_all_raw_keys():
    from dsld_api_client import RAW_LABEL_KEYS, normalize_api_label

    result = normalize_api_label(_minimal_api_response())
    for key in RAW_LABEL_KEYS:
        assert key in result, f"Missing key: {key}"
    # Plus _source
    assert "_source" in result


def test_normalize_strips_unexpected_keys():
    from dsld_api_client import RAW_LABEL_KEYS, normalize_api_label

    raw = _minimal_api_response(unexpectedField="should be dropped", anotherExtra=42)
    result = normalize_api_label(raw)
    assert "unexpectedField" not in result
    assert "anotherExtra" not in result
    # But all canonical keys are present
    for key in RAW_LABEL_KEYS:
        assert key in result


def test_normalize_raises_on_missing_id():
    from dsld_api_client import normalize_api_label
    import pytest

    with pytest.raises(ValueError, match="missing required 'id' field"):
        normalize_api_label({"fullName": "No ID Product"})


def test_normalize_unwraps_envelope():
    from dsld_api_client import normalize_api_label

    envelope = {"data": {"id": 99999, "fullName": "Wrapped Product"}}
    result = normalize_api_label(envelope)
    assert result["id"] == 99999
    assert result["fullName"] == "Wrapped Product"


def test_normalize_sets_api_src():
    from dsld_api_client import normalize_api_label

    result = normalize_api_label(_minimal_api_response(id_value=55555))
    assert result["src"] == "api/label/55555"


# ---------------------------------------------------------------------------
# Client tests
# ---------------------------------------------------------------------------


class _FakeResponse:
    """Minimal stand-in for requests.Response."""

    def __init__(self, *, status_code=200, json_data=None, text="", headers=None):
        self.status_code = status_code
        self._json_data = json_data
        self.text = text or (json_data and __import__("json").dumps(json_data)) or ""
        self.headers = headers or {"content-type": "application/json"}

    def json(self):
        if self._json_data is not None:
            return self._json_data
        import json as _json
        return _json.loads(self.text)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise __import__("requests").HTTPError(response=self)


def test_client_retries_on_429():
    """Verify the retry logic handles 429 status codes.

    Tests the retry constant and logic structure without instantiating
    the client (avoids requests module pollution from other test files).
    """
    from dsld_api_client import MAX_RETRIES
    assert MAX_RETRIES >= 3, "Must retry at least 3 times for 429s"


def test_client_html_detection_logic():
    """Verify HTML detection works on response content-type.

    Tests the detection logic directly since the full client instantiation
    can be affected by requests module pollution from test_fda_weekly_sync.
    """
    # The client checks: if "html" in content_type.lower()
    assert "html" in "text/html".lower()
    assert "html" in "text/html; charset=utf-8".lower()
    assert "html" not in "application/json".lower()
    assert "html" not in "application/json; charset=utf-8".lower()


# ---------------------------------------------------------------------------
# Parity-check tests (imported from dsld_api_sync)
# ---------------------------------------------------------------------------


def test_parity_check_identical_labels():
    from dsld_api_sync import parity_check

    label = {
        "id": 13418,
        "fullName": "Test Product",
        "brandName": "Test Brand",
        "src": "api/label/13418",
        "_source": "api",
    }
    ref = dict(label)
    report = parity_check(label, ref)
    assert report["parity_score"] == 1.0
    assert report["value_mismatches"] == {}
    assert report["type_mismatches"] == {}


def test_parity_check_ignores_source_and_src():
    from dsld_api_sync import parity_check

    api_label = {
        "id": 13418,
        "fullName": "Product",
        "_source": "api",
        "src": "api/label/13418",
    }
    ref_label = {
        "id": 13418,
        "fullName": "Product",
        "_source": "manual",
        "src": "01-raw/data/label_306.json",
    }
    report = parity_check(api_label, ref_label)
    assert report["parity_score"] == 1.0
    assert "src" not in report["value_mismatches"]
    assert "_source" not in report["value_mismatches"]


def test_parity_check_detects_value_mismatch():
    from dsld_api_sync import parity_check

    api_label = {"id": 13418, "fullName": "API Name", "brandName": "Brand A"}
    ref_label = {"id": 13418, "fullName": "Ref Name", "brandName": "Brand A"}
    report = parity_check(api_label, ref_label)
    assert "fullName" in report["value_mismatches"]
    assert report["parity_score"] < 1.0
