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
        {"program": "NSF Certified", "scope": "sku", "recency_status": "fresh"}])
    assert cert_evidence.audited_gmp_evidence(product) == {
        "basis": "verified_certification", "detail": "NSF Certified"}
    assert _generic_b4b(product) == 4.0
    assert _omega_b4b(product) == 4.0


def test_manufacturer_facility_record_scores_in_both_modules(monkeypatch):
    monkeypatch.setattr(
        brand_testing_posture, "_top_manufacturers_by_id",
        lambda: {"MANUF_THORNE": {"id": "MANUF_THORNE",
                                  "evidence": ["NSF GMP-registered facility"]}},
    )
    product = _product(manufacturer_data={"top_manufacturer": {
        "found": True, "match_type": "exact", "manufacturer_id": "MANUF_THORNE"}})
    assert cert_evidence.audited_gmp_evidence(product)["basis"] == "manufacturer_facility"
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


# Manufacturer evidence strings from data/top_manufacturers_data.json
# (2026-09-16 Codex audit): the audit/certification wording must attach to the
# GMP program or the facility itself. Compliance statements, product-level
# certifications and FDA facility registration are not audited GMP.
@pytest.mark.parametrize("evidence", [
    "NSF GMP-registered, third-party tested",
    "ISO, GMP certifications",
    "GMP certs, clinical distribution",
    "NSF, cGMP certifications",
    "GMP and NSF registered facilities",
    "GMP certified",
    "cGMP and HACCP certified",
    "Non-GMO and GMP certified",
    "GMP certified production",
    "GMP and ISO certified",
    "NSF GMP certified",
    "UL Solutions-certified facility, cGMP-compliant",
    "cGMP, ISO certified manufacturing",
    "cGMP-compliant and Natural Products Association certified",
    "Brand states manufacturing in NSF-GMP registered facility",
    "Brand states manufacturing in TGA-registered GMP facility",
    "Brand references Health Canada GMP licensing and quality-control framework",
])
def test_audited_facility_wording_counts(evidence):
    assert brand_testing_posture.is_audited_gmp_facility_evidence(evidence)


@pytest.mark.parametrize("evidence", [
    "cGMP-compliant with third-party testing",
    "cGMP compliant facilities",
    "cGMP compliant manufacturing",
    "cGMP compliant",
    "cGMP-compliant with USDA Organic certifications",
    "IFOS-certified fish oil, cGMP-compliant",
    "cGMP-compliant with NSF certification",
    "NSF Certified, cGMP compliant",
    "GMP, NSF certification",
    "GMP, multiple third-party certifications",
    "GMP, third-party certified",
    "GMP and USP certifications",
    "cGMP and FDA registered facilities",
    "cGMP and NSF certifications on many products",
    "cGMP and Informed-Sport certified for select products",
    "NSF GMP compliant; transparent ingredient sourcing",
])
def test_compliance_or_other_certification_wording_does_not_count(evidence):
    assert not brand_testing_posture.is_audited_gmp_facility_evidence(evidence)


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
        {"program": "IFOS", "scope": "sku"},
        {"program": "IFOS", "scope": "sku", "scoring_blocked_reason": "stale_snapshot"},
        {"program": "USP Verified", "scope": "brand_only"},
        {"program": "NSF Certified", "scope": "product_line", "matched_brand": "Nature Made"},
    ])
    assert [e["program"] for e in cert_evidence.verified_product_cert_entries(product)] == ["IFOS"]


@pytest.mark.parametrize("name", ["_brand_key", "_verified_cert_brand_matches_product"])
def test_omega_formulation_does_not_carry_its_own_brand_matcher(name):
    from scoring_v4.modules import omega_formulation
    assert not hasattr(omega_formulation, name)
