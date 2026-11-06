"""Research clients must establish cache freshness before reusing a response."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from api_audit.discover_clinical_evidence import APIClient
from api_audit.enrich_chembl_bioactivity import ChEMBLClient
from api_audit.verify_clinical_trials import ClinicalTrialsClient
from api_audit.verify_comptox import CompToxClient
from api_audit.verify_cui import UMLSClient
from api_audit.verify_pubchem import PubChemClient
from api_audit.verify_unii import GSRSClient


@pytest.fixture(params=[
    ClinicalTrialsClient, ChEMBLClient, CompToxClient, PubChemClient,
    GSRSClient, APIClient, UMLSClient,
], ids=lambda cls: cls.__name__)
def client(request):
    if request.param is UMLSClient:
        return request.param("", emit_errors=False)
    return request.param()


@pytest.mark.parametrize("entry", [
    {"payload": {"stale": True}},
    {"payload": {"stale": True}, "expires_at": None},
    {"payload": {"stale": True}, "expires_at": 0},
    {"payload": {"stale": True}, "expires_at": True},
    {"payload": {"stale": True}, "expires_at": "not-a-date"},
    {"payload": {"stale": True}, "expires_at": "2000-01-01T00:00:00"},
    {"payload": {"stale": True}, "expires_at": "2999-01-01T00:00:00"},
    {"payload": {"stale": True}, "expires_at": "2000-01-01T00:00:00+00:00"},
    {"result": {"legacy_undated": True}},
], ids=["missing", "null", "numeric", "boolean", "malformed", "naive-past",
        "naive-future", "expired", "legacy-undated"])
def test_unproven_or_expired_response_is_evicted(client, entry):
    client._cache = {"query": entry, "unrelated": {"preserved": True}}

    assert client._cache_get("query") is None
    assert client._cache == {"unrelated": {"preserved": True}}


@pytest.mark.parametrize("offset", [-7, 0, 5.5])
def test_future_aware_response_reused_without_restamping(client, offset):
    payload = {"result": ["source response"]}
    expiry = (datetime.now(timezone(timedelta(hours=offset))) + timedelta(days=1)).isoformat()
    entry = {"payload": payload, "expires_at": expiry}
    client._cache = {"query": entry}

    assert client._cache_get("query") is payload
    assert client._cache["query"] is entry
    assert entry["expires_at"] == expiry


def test_current_writer_envelope_remains_readable(client):
    payload = {"result": "current response"}
    client._cache_set("query", payload)

    assert client._cache_get("query") == payload


def test_dated_disk_cache_remains_readable(client, tmp_path):
    client.cache_path = tmp_path / "responses.json"
    client._cache_set("query", {"result": "current response"})
    if isinstance(client, UMLSClient):
        # UMLS persists when setting a response; the other clients save explicitly.
        reloaded = UMLSClient("", cache_path=client.cache_path, emit_errors=False)
    else:
        client.save_cache()
        reloaded = type(client)(cache_path=client.cache_path)

    assert reloaded._cache_get("query") == {"result": "current response"}


def test_zero_ttl_never_reuses_response(client, monkeypatch):
    # Discovery has a fixed module TTL; the other clients expose it per instance.
    monkeypatch.setattr("api_audit.discover_clinical_evidence.DEFAULT_CACHE_TTL_SECONDS", 0)
    client.cache_ttl_seconds = 0
    client._cache_set("query", {"stale": True})

    assert client._cache_get("query") is None


def test_umls_undated_cache_cannot_supply_offline_verification(monkeypatch):
    client = UMLSClient("", emit_errors=False)
    client._cache = {
        "https://uts-ws.nlm.nih.gov/rest/content/current/CUI/C0000001?": {
            "result": {"ui": "C0000001", "name": "Unverified legacy response"},
        },
    }
    monkeypatch.setattr("api_audit.verify_cui.urllib.request.urlopen",
                        lambda *args, **kwargs: pytest.fail("No API key: do not call network"))

    assert client.lookup_cui("C0000001") is None


def test_comptox_list_payload_is_preserved():
    client = CompToxClient()
    payload = [{"dtxsid": "DTXSID0000000"}]
    client._cache_set("query", payload)

    assert client._cache_get("query") is payload


def test_malformed_expiry_fetches_fresh_response_once(monkeypatch):
    client = ClinicalTrialsClient()
    url = "https://clinicaltrials.gov/api/v2/studies/NCT00000001"
    client._cache[url] = {"payload": {"stale": True}, "expires_at": "2999-01-01"}
    calls = []
    payload = {"protocolSection": {"identificationModule": {"nctId": "NCT00000001"}}}

    def fetch(request_url, **kwargs):
        calls.append(request_url)
        return SimpleNamespace(status_code=200, json=lambda: payload)

    monkeypatch.setattr("api_audit.verify_clinical_trials.requests.get", fetch)
    monkeypatch.setattr("api_audit.verify_clinical_trials.time.sleep", lambda _: None)

    assert client._get(url) == payload
    expiry = client._cache[url]["expires_at"]
    assert datetime.fromisoformat(expiry).utcoffset() is not None
    assert client._get(url) == payload
    assert client._cache[url]["expires_at"] == expiry
    assert calls == [url]
