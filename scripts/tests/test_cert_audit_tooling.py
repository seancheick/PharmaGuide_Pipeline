from __future__ import annotations

import sys


def test_cert_provenance_audit_uses_dynamic_registry_coverage() -> None:
    from scripts.api_audit import cert_claim_provenance_audit as audit

    summary = audit.summarize(
        [
            {
                "dsld_id": "1",
                "brand_name": "Example",
                "product_name": "Example Product",
                "provenance": {
                    "label_certifications": ["USP"],
                    "manufacturer_evidence": [],
                    "either_or_unknown": [],
                },
            }
        ],
        covered_programs={"USP Verified"},
    )

    assert summary["products_with_any_unsupported_program"] == 0
    assert summary["by_program"][0]["program"] == "USP Verified"
    assert summary["by_program"][0]["covered_by_live_registry"] is True


def test_cert_label_registry_audit_passes_dsld_id_to_resolver(monkeypatch, tmp_path) -> None:
    from scripts.api_audit import cert_label_registry_audit as audit

    class FakeRegistry:
        metadata = {"registry_sources": [{"program": "USP Verified"}]}
        records_by_program = {"USP Verified": [{"program": "USP Verified"}]}

    class FakeResolution:
        def to_dict(self) -> dict:
            return {"program": "USP Verified", "scope": "sku"}

    seen_dsld_ids: list[str | None] = []

    def fake_resolve(*, brand, product, claimed_programs, registry, dsld_id=None):
        seen_dsld_ids.append(dsld_id)
        return [FakeResolution()]

    monkeypatch.setattr(audit.CertRegistry, "load", staticmethod(lambda: FakeRegistry()))
    monkeypatch.setattr(
        audit,
        "load_catalog",
        lambda: [
            {
                "dsld_id": "12345",
                "brand_name": "Example",
                "product_name": "Example Product",
                "primary_category": "vitamin",
                "supplement_type": "vitamin",
                "verdict": "SAFE",
                "score_100_equivalent": 80.0,
            }
        ],
    )
    monkeypatch.setattr(
        audit,
        "load_blob",
        lambda _dsld_id: {
            "certification_detail": {
                "third_party_programs": {
                    "programs": [{"name": "USP Verified"}]
                }
            }
        },
    )
    monkeypatch.setattr(audit, "resolve", fake_resolve)
    monkeypatch.setattr(sys, "argv", ["cert_label_registry_audit.py", "--out-dir", str(tmp_path)])

    audit.main()

    assert seen_dsld_ids == ["12345"]
