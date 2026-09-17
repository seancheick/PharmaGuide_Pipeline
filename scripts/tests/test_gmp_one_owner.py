"""One GMP decision for every trust module, the pillar, the export and the app.

2026-09-16: the owner asked for "1 system, 1 brain, no drift, no duplicate
logic" after the GMP badge was moved onto the Verification pillar. Audit found
the decision still lived in three places that disagreed:
- generic_trust._score_b4b gave label GMP wording 4 points ("certified") and FDA
  facility registration 2;
- omega_trust._score_b4b gave a label "NSF GMP" mark 4 and FDA registration 2;
- the Verification pillar credited only a verified certification that audits
  GMP or a manufacturer facility record, discarding the rest.
The verified-cert lookup, GMP-program list and cert brand matcher were also
copied between generic_trust, omega_trust and confidence.

Now scoring_v4.cert_evidence owns them; both trust modules score B4b only from
its audited decision, and label wording is recorded but never scored.
"""

import pytest

from scoring_v4 import cert_evidence
from scoring_v4.modules import brand_testing_posture, generic_trust, omega_trust


def _product(**top):
    product = {
        "status": "active",
        "form_factor": "capsule",
        "supplement_type": {"type": "single_nutrient"},
        "brandName": "Thorne",
        "verified_cert_programs": [],
        "ingredient_quality_data": {"ingredients_scorable": [], "ingredients": []},
        "certification_data": {"gmp": {}, "batch_traceability": {}},
    }
    product.update(top)
    return product


def _generic_b4b(product):
    return generic_trust.score_trust(product)["components"]["B4b_gmp"]


def _omega_b4b(product):
    return omega_trust.score_trust(product)["components"].get("b4b_gmp", 0.0)


@pytest.mark.parametrize("gmp", [
    {"claimed": True, "gmp_certified_or_compliant": True, "text_matched": "GMP"},
    {"claimed": True, "nsf_gmp": True, "text_matched": "NSF GMP"},
    {"claimed": True, "fda_registered": True, "text_matched": "FDA Registered"},
])
def test_label_gmp_wording_scores_nothing_in_any_module(gmp):
    product = _product(certification_data={"gmp": gmp, "batch_traceability": {}})
    assert cert_evidence.audited_gmp_evidence(product) is None
    assert _generic_b4b(product) == 0.0
    assert _omega_b4b(product) == 0.0


def test_verified_gmp_auditing_certification_scores_in_both_modules():
    product = _product(verified_cert_programs=[
        {"program": "NSF Certified", "scope": "sku", "recency_status": "fresh",
         "record_id": "NSF_TEST", "source_url": "https://registry.example/nsf-test",
         "snapshot_date": "2026-09-16"}])
    assert cert_evidence.audited_gmp_evidence(product) == {
        "basis": "verified_certification", "detail": "NSF Certified"}
    assert _generic_b4b(product) == 4.0
    assert _omega_b4b(product) == 4.0


def test_manufacturer_listed_in_gmp_facility_registry_scores_in_both_modules(monkeypatch):
    _facility_registry(monkeypatch)
    _manufacturers(monkeypatch, facility_registrations=[_link()])
    product = _product(manufacturer_data=_exact_manufacturer())

    evidence = cert_evidence.audited_gmp_evidence(product)

    assert evidence["basis"] == "manufacturer_facility"
    assert "NSF/ANSI 455" in evidence["detail"] and "Thorne" in evidence["detail"]
    assert _generic_b4b(product) == 4.0
    assert _omega_b4b(product) == 4.0


def test_cross_brand_certification_never_implies_gmp():
    product = _product(verified_cert_programs=[
        {"program": "NSF Certified", "scope": "sku", "matched_brand": "Nature Made"}])
    assert cert_evidence.audited_gmp_evidence(product) is None


def test_named_certification_brand_fails_closed_when_product_brand_is_missing():
    """A registry row tied to a named brand cannot verify an unidentified
    product. Missing identity is not evidence of a match."""
    entry = {"program": "NSF Certified", "scope": "sku", "matched_brand": "Nature Made"}
    product = _product(brandName="")
    assert cert_evidence.cert_entry_brand_matches_product(product, entry) is False
    assert cert_evidence.verified_product_cert_entries({**product, "verified_cert_programs": [entry]}) == []


@pytest.mark.parametrize("module", [generic_trust, omega_trust])
@pytest.mark.parametrize("name", [
    "_gmp_implied_by_verified_cert", "_get_gmp_implying_programs",
    "_cert_entry_brand_matches_product", "_brand_key", "_brand_tokens",
])
def test_trust_modules_do_not_carry_their_own_copies(module, name):
    assert not hasattr(module, name)


# Audited GMP facility evidence comes only from a sourced facility-audit
# registry (cert_registry.json sources flagged audit_scope=gmp_facility),
# linked to the product's canonical manufacturer by an explicit, sourced
# facility_registrations entry. Free-text manufacturer summaries and brand-name
# similarity never attribute a facility (Codex plan audit 2026-09-16).


def _facility_registry(monkeypatch, *, recency="fresh", scope="facility", audit_scope="gmp_facility"):
    from cert_resolver import CertRegistry

    registry = CertRegistry(
        metadata={"registry_sources": [
            {"program": "NSF/ANSI 455", "url": "https://info.nsf.org/Certified/455GMP/", "audit_scope": audit_scope},
            {"program": "NSF Certified", "url": "https://info.nsf.org/Certified/Dietary/"},
        ]},
        records_by_program={"NSF/ANSI 455": [{
            "record_id": "NSF_ANSI_THORNE", "program": "NSF/ANSI 455", "brand": "Thorne®", "product": "",
            "scope": scope, "source_url": "https://info.nsf.org/Certified/455GMP/",
            "_snapshot_date": "2026-09-16", "_snapshot_age_days": 0, "_recency_status": recency,
        }]},
    )
    monkeypatch.setattr(cert_evidence, "_cert_registry", lambda: registry)
    return registry


def _link(**overrides):
    link = {"registry_record_id": "NSF_ANSI_THORNE", "program": "NSF/ANSI 455",
            "registered_company": "Thorne®", "relationship": "same_entity",
            "evidence_url": "https://info.nsf.org/Certified/455GMP/", "reviewed_at": "2026-09-16"}
    link.update(overrides)
    return link


def _manufacturers(monkeypatch, **entry):
    monkeypatch.setattr(
        brand_testing_posture, "_top_manufacturers_by_id",
        lambda: {"MANUF_THORNE": {"id": "MANUF_THORNE", "standard_name": "Thorne",
                                  "evidence": ["NSF GMP-registered facility"], **entry}},
    )


def _exact_manufacturer(match_type="exact"):
    return {"top_manufacturer": {"found": True, "match_type": match_type, "manufacturer_id": "MANUF_THORNE"}}


def test_free_text_manufacturer_evidence_never_counts(monkeypatch):
    _facility_registry(monkeypatch)
    _manufacturers(monkeypatch)  # evidence text says "NSF GMP-registered", no sourced link
    product = _product(manufacturer_data=_exact_manufacturer())

    assert cert_evidence.audited_gmp_evidence(product) is None
    assert cert_evidence.facility_audit_resolution(product)["state"] == "no_sourced_registration"


def test_brand_similarity_alone_never_attributes_a_facility(monkeypatch):
    _facility_registry(monkeypatch)  # registry lists "Thorne®"; product brand is Thorne
    _manufacturers(monkeypatch)
    assert cert_evidence.audited_gmp_evidence(_product()) is None
    assert cert_evidence.facility_audit_resolution(_product())["state"] == "no_canonical_manufacturer"


@pytest.mark.parametrize("registry_kwargs, link, state", [
    ({}, {"registry_record_id": "NSF_ANSI_MISSING"}, "registry_row_stale_or_missing"),
    ({"recency": "scoring_blocked"}, {}, "registry_row_stale_or_missing"),
    ({"scope": "sku"}, {}, "registry_row_stale_or_missing"),
    ({"audit_scope": None}, {}, "registry_row_stale_or_missing"),
])
def test_unusable_registry_rows_fail_closed(monkeypatch, registry_kwargs, link, state):
    _facility_registry(monkeypatch, **registry_kwargs)
    _manufacturers(monkeypatch, facility_registrations=[_link(**link)])
    product = _product(manufacturer_data=_exact_manufacturer())

    assert cert_evidence.audited_gmp_evidence(product) is None
    assert cert_evidence.facility_audit_resolution(product)["state"] == state


def test_fuzzy_manufacturer_match_is_not_canonical_identity(monkeypatch):
    _facility_registry(monkeypatch)
    _manufacturers(monkeypatch, facility_registrations=[_link()])
    product = _product(manufacturer_data=_exact_manufacturer(match_type="fuzzy"))

    assert cert_evidence.facility_audit_resolution(product)["state"] == "no_canonical_manufacturer"


def test_resolved_facility_audit_keeps_registry_provenance(monkeypatch):
    _facility_registry(monkeypatch)
    _manufacturers(monkeypatch, facility_registrations=[_link(relationship="dba")])
    product = _product(manufacturer_data=_exact_manufacturer())

    assert cert_evidence.facility_audit_resolution(product) == {
        "state": "resolved",
        "program": "NSF/ANSI 455",
        "registered_company": "Thorne®",
        "record_id": "NSF_ANSI_THORNE",
        "relationship": "dba",
        "evidence_url": "https://info.nsf.org/Certified/455GMP/",
        "source_url": "https://info.nsf.org/Certified/455GMP/",
        "snapshot_date": "2026-09-16",
        "recency_status": "fresh",
    }


def test_free_text_gmp_inference_is_deleted():
    for name in ("gmp_facility_evidence", "is_audited_gmp_facility_evidence", "AUDITED_GMP_FACILITY_RE"):
        assert not hasattr(brand_testing_posture, name), name


def test_registry_marks_nsf_455_as_a_gmp_facility_audit_source():
    import json
    from pathlib import Path

    registry = json.loads((Path(__file__).resolve().parents[1] / "data" / "cert_registry.json").read_text())
    sources = {s["program"]: s for s in registry["_metadata"]["registry_sources"]}
    assert sources["NSF/ANSI 455"].get("audit_scope") == "gmp_facility"
    assert all(s.get("audit_scope") in (None, "gmp_facility") for s in sources.values())


def test_facility_audit_rows_never_count_as_brand_only_certification(monkeypatch):
    _facility_registry(monkeypatch)
    product = _product(verified_cert_programs=[{"program": "NSF/ANSI 455", "scope": "brand_only"}])

    metadata = generic_trust.score_trust(product)["metadata"]

    assert "brand_only" not in metadata.get("verified_unscored_scope_counts", {})
    assert metadata.get("verified_brand_only_programs") == []


def test_manufacturer_gmp_evidence_does_not_leak_into_label_wording():
    """certification_data.gmp records label GMP wording only. Manufacturer GMP
    evidence is owned by cert_evidence.audited_gmp_evidence; the enricher used
    to copy it in as ``claimed=True, source=manufacturer_evidence``, so a label
    with no GMP text looked self-asserted (Life Extension probe, 2026-09-16)."""
    from enrich_supplements_v3 import SupplementEnricherV3

    product = {"brandName": "Life Extension", "fullName": "Magnesium", "statements": [],
               "contacts": [], "activeIngredients": [], "inactiveIngredients": []}
    gmp = SupplementEnricherV3()._collect_certification_data(product)["gmp"]
    assert gmp["claimed"] is False
    assert "source" not in gmp


def test_verified_product_cert_entries_is_the_one_filter():
    """Blocked, broader-scope and cross-brand registry rows never verify a
    product — the same filter for GMP inference, omega sourcing credit and the
    exported certification badges (omega formulation used to skip the blocked
    check and use its own substring brand matcher)."""
    product = _product(verified_cert_programs=[
        {"program": "IFOS", "scope": "sku", "record_id": "IFOS_TEST",
         "source_url": "https://registry.example/ifos-test", "snapshot_date": "2026-09-16",
         "recency_status": "fresh"},
        {"program": "IFOS", "scope": "sku", "scoring_blocked_reason": "stale_snapshot"},
        {"program": "USP Verified", "scope": "brand_only"},
        {"program": "NSF Certified", "scope": "product_line", "matched_brand": "Nature Made"},
    ])
    assert [e["program"] for e in cert_evidence.verified_product_cert_entries(product)] == ["IFOS"]


@pytest.mark.parametrize("name", ["_brand_key", "_verified_cert_brand_matches_product"])
def test_omega_formulation_does_not_carry_its_own_brand_matcher(name):
    from scoring_v4.modules import omega_formulation
    assert not hasattr(omega_formulation, name)
