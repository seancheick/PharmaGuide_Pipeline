"""Claimed certification signals and verified product certifications are two
dimensions with one owner (scoring_v4.cert_evidence).

A label claim ("USP Verified" printed on the label) is preserved as a claim.
Only a product-level registry match (sku / product_line, fresh, brand-matched)
is verified, and only verified programs light the quality flags, the
third-party badge, share copy or the transitional legacy program list that
installed apps render as "Third-party verified".
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))
TESTS_ROOT = Path(__file__).resolve().parent
if str(TESTS_ROOT) not in sys.path:
    sys.path.insert(0, str(TESTS_ROOT))

from cert_resolver import CertRegistry  # noqa: E402
from enrich_supplements_v3 import SupplementEnricherV3  # noqa: E402
from scoring_v4 import cert_evidence  # noqa: E402

RULES = json.loads((SCRIPTS_ROOT / "data" / "cert_claim_rules.json").read_text())
REGISTRY_PROGRAMS = {
    source["program"]
    for source in json.loads((SCRIPTS_ROOT / "data" / "cert_registry.json").read_text())["_metadata"][
        "registry_sources"
    ]
}
FLAGS = ("purity_verified", "heavy_metal_tested", "label_accuracy_verified")


def _verified_row(program, scope="sku", brand="Test Brand", **extra):
    return {
        "program": program,
        "scope": scope,
        "matched_brand": brand,
        "record_id": f"REC_{program.replace(' ', '_').upper()}",
        "source_url": "https://registry.example/listing",
        "snapshot_date": "2026-09-16",
        "recency_status": "fresh",
        **extra,
    }


def _product(claims=(), verified=()):
    return {
        "brandName": "Test Brand",
        "certification_data": {
            "third_party_programs": {"programs": [{"name": name, "source": "rules_db"} for name in claims]},
        },
        "verified_cert_programs": list(verified),
    }


# ── data-owned capability vocabulary ─────────────────────────────────────────

def test_capabilities_live_in_rules_data_for_registry_programs_only():
    programs = RULES["rules"]["third_party_programs"]
    with_caps = {
        key: rule["verified_capabilities"]
        for key, rule in programs.items()
        if not key.startswith("_") and isinstance(rule, dict) and "verified_capabilities" in rule
    }
    assert with_caps, "capabilities must be data-owned in cert_claim_rules.json"
    for key, caps in with_caps.items():
        assert caps["verified_program"] in REGISTRY_PROGRAMS, key
        assert set(caps["capabilities"]) <= set(FLAGS), key
        assert caps.get("source"), key
    for no_registry in ("labdoor", "goed", "clean_label_project"):
        assert "verified_capabilities" not in programs[no_registry]


def test_enricher_no_longer_owns_a_capability_table():
    assert not hasattr(SupplementEnricherV3, "QUALITY_CERT_CAPABILITIES")
    assert not hasattr(SupplementEnricherV3, "_quality_cert_capabilities")


# ── one interpreter ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("program, expected", [
    ("USP Verified", {"purity_verified", "heavy_metal_tested", "label_accuracy_verified"}),
    ("NSF Certified", {"purity_verified", "heavy_metal_tested", "label_accuracy_verified"}),
    ("NSF Sport", {"purity_verified", "heavy_metal_tested", "label_accuracy_verified"}),
    ("IFOS", {"purity_verified", "heavy_metal_tested"}),
    ("Informed Choice", {"purity_verified"}),
])
def test_verified_program_capabilities(program, expected):
    flags = cert_evidence.verified_quality_flags(_product(verified=[_verified_row(program)]))
    assert {flag for flag, value in flags.items() if value} == expected


@pytest.mark.parametrize("claims, verified", [
    (["USP Verified"], []),
    (["NSF Contents Certified"], [_verified_row("NSF Certified", scope="claimed_only")]),
    ([], [_verified_row("USP Verified", scope="brand_only")]),
    ([], [_verified_row("USP Verified", scope="needs_review")]),
    ([], [_verified_row("USP Verified", brand="Unrelated Megacorp")]),
    ([], [_verified_row("USP Verified", scoring_blocked_reason="snapshot stale")]),
    (["Labdoor Tested", "GOED Certified"], []),
])
def test_claims_and_unverified_rows_light_no_quality_flag(claims, verified):
    flags = cert_evidence.verified_quality_flags(_product(claims, verified))
    assert flags == {flag: False for flag in FLAGS}
    assert cert_evidence.verified_programs(_product(claims, verified)) == []


def test_claimed_programs_preserve_every_claim_even_when_verified():
    product = _product(["USP Verified", "Informed Choice"], [_verified_row("USP Verified")])
    assert cert_evidence.claimed_programs(product) == ["USP Verified", "Informed Choice"]


def test_verified_programs_keep_registry_provenance():
    row = _verified_row("NSF Sport", scope="product_line")
    [verified] = cert_evidence.verified_programs(_product(verified=[row]))
    assert verified == {
        "name": "NSF Sport",
        "program": "NSF Sport",
        "record_id": row["record_id"],
        "scope": "product_line",
        "source_url": row["source_url"],
        "snapshot_date": "2026-09-16",
        "recency_status": "fresh",
    }


# ── enricher keeps claims as claims ──────────────────────────────────────────

def _enricher():
    enricher = SupplementEnricherV3.__new__(SupplementEnricherV3)
    enricher.logger = MagicMock()
    enricher.databases = {"cert_claim_rules": RULES, "top_manufacturers_data": {"top_manufacturers": []}}
    enricher.reference_versions = {"cert_claim_rules": {"version": "test"}}
    enricher._cert_registry_cache = CertRegistry()
    enricher._compile_patterns()
    return enricher


def _certification(*notes):
    product = {
        "brandName": "Test Brand", "fullName": "Test Product",
        "statements": [{"type": "General Statements", "notes": note} for note in notes],
        "claims": [], "activeIngredients": [], "inactiveIngredients": [],
    }
    return _enricher()._collect_certification_data(product)


def test_enriched_claims_do_not_carry_a_verified_marker_or_quality_flags():
    certification = _certification("USP Verified")
    assert [p["name"] for p in certification["third_party_programs"]["programs"]] == ["USP Verified"]
    assert all("verified" not in p for p in certification["third_party_programs"]["programs"])
    for flag in FLAGS:
        assert flag not in certification
    assert "category_contamination_risk" in certification


@pytest.mark.parametrize("note, generic", [
    ("Third-party verified for purity.", True),
    ("Third-party inspected facility.", True),
    ("This product is not third-party tested.", False),
    ("Not third-party verified.", False),
])
def test_generic_third_party_wording_respects_negation(note, generic):
    assert _certification(note)["third_party_programs"]["has_generic_claim_only"] is generic


# ── export ──────────────────────────────────────────────────────────────────

def _export_enriched(claims, verified):
    from test_build_final_db import make_enriched

    enriched = make_enriched()
    enriched["named_cert_programs"] = list(claims)
    enriched["certification_data"]["third_party_programs"] = {
        "programs": [{"name": name, "source": "rules_db"} for name in claims]
    }
    enriched["verified_cert_programs"] = list(verified)
    return enriched


def test_export_separates_claimed_and_verified_and_legacy_list_is_verified_only():
    from build_final_db import build_detail_blob
    from test_build_final_db import make_scored

    enriched = _export_enriched(
        ["USP Verified", "Informed Choice"],
        [_verified_row("USP Verified"), _verified_row("NSF Sport", brand="Unrelated Megacorp")],
    )
    cert = build_detail_blob(enriched, make_scored())["certification_detail"]

    assert [p["name"] for p in cert["claimed_programs"]] == ["USP Verified", "Informed Choice"]
    assert [p["program"] for p in cert["verified_programs"]] == ["USP Verified"]
    assert cert["third_party_programs"]["programs"] == [{
        "name": "USP Verified", "verified": True, "source": "registry",
        "record_id": "REC_USP_VERIFIED",
    }]
    assert (cert["purity_verified"], cert["heavy_metal_tested"], cert["label_accuracy_verified"]) == (
        True, True, True,
    )


def test_exported_claims_carry_their_canonical_registry_program():
    """Label "NSF Contents Certified" is the registry's "NSF Certified" listing;
    consumers de-duplicate a claim against its verification by program."""
    from build_final_db import build_detail_blob
    from test_build_final_db import make_scored

    enriched = _export_enriched(["NSF Contents Certified"], [_verified_row("NSF Certified")])
    cert = build_detail_blob(enriched, make_scored())["certification_detail"]

    assert cert["claimed_programs"] == [{"name": "NSF Contents Certified", "program": "NSF Certified"}]
    assert [p["program"] for p in cert["verified_programs"]] == ["NSF Certified"]


def test_claim_only_export_has_no_verified_signal_anywhere():
    from build_final_db import build_decision_highlights, build_detail_blob, generate_share_metadata
    from test_build_final_db import make_scored

    enriched = _export_enriched(["USP Verified", "Labdoor Tested"], [])
    scored = make_scored()
    cert = build_detail_blob(enriched, scored)["certification_detail"]

    assert [p["name"] for p in cert["claimed_programs"]] == ["USP Verified", "Labdoor Tested"]
    assert cert["verified_programs"] == []
    assert cert["third_party_programs"]["programs"] == []
    assert not any(cert[flag] for flag in FLAGS)

    share = generate_share_metadata(enriched, scored)
    assert "third-party testing" not in share["share_description"]
    assert not any("USP Verified" in highlight for highlight in share["share_highlights"])

    trust = build_decision_highlights(enriched, scored, None)["trust"]
    assert "USP Verified" not in trust or "claimed on label" in trust.lower()


def test_core_third_party_columns_are_verified_only():
    import tempfile

    from test_build_final_db import _artifact_from_canned, _canned_v4, _core_rows, _run_build

    claim_only = _export_enriched(["USP Verified"], [])
    verified = _export_enriched([], [_verified_row("NSF Certified")])
    verified["dsld_id"] = "888"
    verified["upcSku"] = "0123456789888"
    verified["product_name"] = "Verified Product"
    scored = [_artifact_from_canned(d, _canned_v4()) for d in ("999", "888")]
    with tempfile.TemporaryDirectory() as tmp:
        _result, out = _run_build(tmp, [claim_only, verified], scored)
        rows = _core_rows(out, ["dsld_id", "has_third_party_testing", "cert_programs"])
    assert rows["999"]["has_third_party_testing"] == 0
    assert json.loads(rows["999"]["cert_programs"]) == []
    assert rows["888"]["has_third_party_testing"] == 1
    assert json.loads(rows["888"]["cert_programs"]) == ["NSF Certified"]
