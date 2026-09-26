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
from api_audit import verify_cui as verify_cui_impl
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


def test_verify_cui_for_entry_uses_curated_none_override_for_iqm_pqq_entry():
    report = verify_cui_for_entry(
        AliasAwareClient(),
        "IQM_PQQ",
        "PQQ (Pyrroloquinoline Quinone)",
        None,
        ["pyrroloquinoline quinone"],
        cui_status="no_confirmed_umls_match",
    )

    assert report["status"] == "ANNOTATED_NULL"
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


def test_verify_cui_for_entry_rejects_measurement_cui_even_when_name_overlaps():
    class MeasurementClient:
        def lookup_cui(self, cui):
            assert cui == "C0202469"
            return {
                "cui": "C0202469",
                "name": "Silica measurement",
                "semantic_types": ["Laboratory Procedure"],
            }

        def search_exact(self, term):
            return None

        def search(self, term, max_results=3):
            assert term == "Silica"
            return [{"cui": "C0037098", "name": "silicon dioxide", "source": "TEST"}]

    report = verify_cui_for_entry(
        MeasurementClient(),
        "IQM_SILICA",
        "Silica",
        "C0202469",
        ["silicon dioxide"],
    )

    assert report["status"] == "MISMATCH"
    assert report["umls_name"] == "Silica measurement"
    assert report["suggested_cui"] == "C0037098"
    assert report["suggested_name"] == "silicon dioxide"
    assert report["match_source"] == "search"


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


def test_verify_cui_for_product_entry_keeps_annotated_null_even_with_exact_alias_match():
    class ProductClient(AliasAwareClient):
        def search_exact(self, term):
            if term == "hydroxycut":
                return {"cui": "C1723542", "name": "hydroxycut", "source": "TEST"}
            return super().search_exact(term)

    report = verify_cui_for_entry(
        ProductClient(),
        "RECALLED_HYDROXYCUT",
        "Hydroxycut (Multiple Formulations)",
        None,
        ["hydroxycut"],
        cui_status="no_single_umls_concept",
        entity_type="product",
    )

    assert report["status"] == "ANNOTATED_NULL"
    assert report["suggested_cui"] == "C1723542"
    assert report["match_source"] == "exact_alias"
    assert report["action"] is None


def test_should_apply_cui_fix_is_safe_by_default():
    exact_missing = {"status": "MISSING_CUI", "match_source": "exact_standard", "suggested_cui": "C1"}
    fuzzy_missing = {"status": "MISSING_CUI", "match_source": "search", "suggested_cui": "C2"}
    mismatch = {"status": "MISMATCH", "match_source": "exact_standard", "suggested_cui": "C3"}

    assert should_apply_cui_fix(exact_missing, allow_mismatch_overwrite=False) is True
    assert should_apply_cui_fix(fuzzy_missing, allow_mismatch_overwrite=False) is False
    assert should_apply_cui_fix(mismatch, allow_mismatch_overwrite=False) is False
    assert should_apply_cui_fix(mismatch, allow_mismatch_overwrite=True) is True


def test_verify_cui_for_botanical_prefers_latin_name_over_extract_alias():
    class BotanicalClient:
        def lookup_cui(self, cui):
            return None

        def search_exact(self, term):
            if term == "Acai Berry":
                return None
            if term == "acai berry extract":
                return {"cui": "C2368977", "name": "acai extract", "source": "TEST"}
            if term == "Euterpe oleracea":
                return {"cui": "C1054955", "name": "Euterpe oleracea", "source": "TEST"}
            return None

        def search(self, term, max_results=3):
            return []

    report = verify_cui_for_entry(
        BotanicalClient(),
        "BOT_ACAI",
        "Acai Berry",
        None,
        ["acai berry extract", "Euterpe oleracea"],
        latin_name="Euterpe oleracea",
    )

    assert report["status"] == "MISSING_CUI"
    assert report["suggested_cui"] == "C1054955"
    assert report["suggested_name"] == "Euterpe oleracea"


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


def test_load_entries_supports_iqm_map_and_skips_metadata(tmp_path):
    payload = {
        "_metadata": {"version": "test"},
        "ingredient_alpha": {
            "standard_name": "Ingredient Alpha",
            "cui": "C123",
            "aliases": ["alpha"],
            "cui_status": None,
            "cui_note": "ok",
        },
        "ingredient_beta": {
            "standard_name": "Ingredient Beta",
            "cui": None,
            "aliases": ["beta"],
            "cui_status": "no_confirmed_umls_match",
            "cui_note": "none",
        },
    }
    path = tmp_path / "iqm.json"
    path.write_text(json.dumps(payload))

    entries = verify_cui.load_entries(path, "ingredient_quality_map", "id", "cui", mode="iqm")

    assert [entry["id"] for entry in entries] == ["ingredient_alpha", "ingredient_beta"]
    assert entries[0]["standard_name"] == "Ingredient Alpha"
    assert entries[1]["cui_status"] == "no_confirmed_umls_match"


def test_verify_cui_for_entry_bridges_roman_and_arabic_numerals():
    """BANNED_IGF1 regression: UMLS renders the concept with a Roman numeral
    ("Insulin-Like Growth Factor I") while the curated entry uses the Arabic
    form ("...Growth Factor 1"). Substring containment cannot bridge the two,
    so the entry was reported as MISMATCH and the auditor proposed swapping to
    C3712803 ("IGF1 protein, human") — a narrower, species-specific concept.
    C0021665 is the correct broad substance and is pinned by
    test_banned_recalled_identifier_integrity.py; the comparison is what was
    wrong, not the data.
    """

    class RomanNumeralClient:
        def lookup_cui(self, cui):
            assert cui == "C0021665"
            return {
                "cui": "C0021665",
                "name": "Insulin-Like Growth Factor I",
                "semantic_types": [
                    "Amino Acid, Peptide, or Protein",
                    "Biologically Active Substance",
                ],
            }

        def search_exact(self, term):
            return None

        def search(self, term, max_results=3):
            return []

    report = verify_cui_for_entry(
        RomanNumeralClient(),
        "BANNED_IGF1",
        "IGF-1 (Insulin-like Growth Factor 1)",
        "C0021665",
        ["igf-1", "igf1", "insulin-like growth factor 1", "somatomedin c"],
    )

    assert report["status"] == "VERIFIED", (
        "C0021665 is the correct broad IGF-1 substance concept; a Roman/Arabic "
        "numeral difference must not be reported as a CUI mismatch"
    )
    assert report["match_source"] == "numeral_equivalent", (
        "the numeral rescue must be visible in the report, not silently "
        "indistinguishable from a plain name match"
    )


class PreparationFormClient:
    """UMLS shapes seen live on 2026-09-26 for tansy and phlorizin."""

    CONCEPTS = {
        "C1256219": ("Tanacetum vulgare, flower essence", ["Pharmacologic Substance"]),
        "C0331409": ("Tanacetum vulgare", ["Plant"]),
        "C0885670": (
            "Phlorizinum, trituration of a substance discovered in the fresh bark "
            "of trees, phlorizin, Homeopathic preparation",
            ["Pharmacologic Substance"],
        ),
        "C0613707": ("Ashwagandha preparation", ["Organic Chemical", "Pharmacologic Substance"]),
        "C_ESSENCE": ("Rescue Remedy flower essence", ["Pharmacologic Substance"]),
    }
    EXACT = {
        "tansy": "C1256219",
        "tanacetum vulgare": "C0331409",
    }

    def lookup_cui(self, cui):
        name, types = self.CONCEPTS[cui]
        return {"cui": cui, "name": name, "semantic_types": types}

    def search_exact(self, term):
        cui = self.EXACT.get(term.lower())
        if not cui:
            return None
        return {"cui": cui, "name": self.CONCEPTS[cui][0], "source": "TEST"}

    def search(self, term, max_results=3):
        return []


def test_verify_cui_for_entry_rejects_flower_essence_cui_for_a_herb_entry():
    """BANNED_TANSY carried C1256219 "Tanacetum vulgare, flower essence", a
    flower-remedy preparation. Its alias "tanacetum vulgare" is a substring of
    that name, so substring containment reported VERIFIED."""
    report = verify_cui_for_entry(
        PreparationFormClient(),
        "BANNED_TANSY",
        "Tansy",
        "C1256219",
        ["tansy", "tanacetum vulgare", "tansy oil"],
    )

    assert report["status"] == "MISMATCH"
    assert "flower essence" in report["action"]
    # The replacement suggestion must not be the same preparation concept,
    # which an exact search for "Tansy" returns first.
    assert report["suggested_cui"] == "C0331409"
    assert report["match_source"] == "exact_alias"


def test_verify_cui_for_entry_rejects_homeopathic_cui_for_a_compound_entry():
    report = verify_cui_for_entry(
        PreparationFormClient(),
        "phlorizin",
        "Phlorizin",
        "C0885670",
        ["phloridzin"],
    )

    assert report["status"] == "MISMATCH"
    assert "homeopathic" in report["action"]


def test_verify_cui_for_entry_keeps_plain_preparation_concepts_verified():
    """UMLS names ordinary herbal-ingredient concepts "X preparation"
    (VANDF/NDDF), e.g. ashwagandha, kava, ephedra. Bare "preparation" is not
    a product-form qualifier."""
    report = verify_cui_for_entry(
        PreparationFormClient(),
        "ashwagandha",
        "Ashwagandha",
        "C0613707",
        ["withania somnifera"],
    )

    assert report["status"] == "VERIFIED"


def test_curated_cui_overrides_are_exactly_the_json_file():
    """cui_overrides.json is the one owner. A hard-coded fallback copy used to
    load whenever the JSON was missing, corrupt or empty, and it had drifted
    (nitrites, rhaponticin, PHO keys, e153, 5a-hydroxy laxogenin)."""
    path = Path(verify_cui_impl.SCRIPTS_ROOT) / "data" / "curated_overrides" / "cui_overrides.json"
    assert verify_cui_impl.CURATED_CUI_OVERRIDES == json.loads(path.read_text())


def test_curated_cui_overrides_missing_file_fails_loudly(monkeypatch, tmp_path):
    monkeypatch.setattr(verify_cui_impl, "SCRIPTS_ROOT", tmp_path)
    with pytest.raises(FileNotFoundError):
        verify_cui_impl._load_curated_cui_overrides()


def test_curated_cui_overrides_corrupt_file_fails_loudly(monkeypatch, tmp_path):
    overrides = tmp_path / "data" / "curated_overrides" / "cui_overrides.json"
    overrides.parent.mkdir(parents=True)
    overrides.write_text("{not json")
    monkeypatch.setattr(verify_cui_impl, "SCRIPTS_ROOT", tmp_path)
    with pytest.raises(json.JSONDecodeError):
        verify_cui_impl._load_curated_cui_overrides()


def test_verify_cui_for_entry_accepts_qualifier_the_entry_itself_names():
    report = verify_cui_for_entry(
        PreparationFormClient(),
        "RESCUE_REMEDY",
        "Rescue Remedy flower essence",
        "C_ESSENCE",
        [],
    )

    assert report["status"] == "VERIFIED"
