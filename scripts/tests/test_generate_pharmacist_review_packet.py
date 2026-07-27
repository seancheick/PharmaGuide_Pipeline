from generate_pharmacist_review_packet import build_packet


def _row(record_id, status):
    return {
        "id": record_id,
        "drug_ref": {
            "type": "drug",
            "id": "123",
            "display_name": f"Drug {record_id}",
        },
        "depleted_nutrient": {
            "standard_name": "Nutrient",
            "canonical_id": "nutrient",
        },
        "depletion_type": "monitoring_stability",
        "severity": "mild",
        "onset_timeline": "months",
        "mechanism": "Bounded mechanism.",
        "clinical_impact": "Bounded impact.",
        "recommendation": "Discuss individualized care.",
        "sources": [{"label": "Evidence", "url": "https://example.test"}],
        "citation_review_status": status,
    }


def test_signed_packet_includes_all_dispositions_without_claiming_licensure():
    artifact = {
        "_metadata": {
            "schema_version": "5.4.0",
            "content_version": "v",
            "content_hash": "sha256:abc",
        },
        "depletions": [
            _row("APPROVED", "verified"),
            _row("REMOVED", "rejected"),
        ],
    }
    ledger = {
        "_metadata": {
            "review_scope_count": 2,
            "active_record_count": 1,
            "reviewed_at": "2026-07-27",
            "reviewer": "openai_codex_ai_clinical_audit",
            "reviewer_type": "AI clinical-content audit",
            "licensed_pharmacist_signoff": False,
            "release_disposition": "approved_for_controlled_beta",
        },
        "records": {
            "APPROVED": {
                "disposition": "approved",
                "note": "Claim aligns.",
            },
            "REMOVED": {
                "disposition": "remove_from_release",
                "note": "Scope cannot be represented safely.",
            },
        },
    }

    packet = build_packet(
        artifact,
        ledger=ledger,
        verified_screenshot="verified.png",
        unavailable_screenshot="unavailable.png",
    )

    assert "AI clinical-content review complete" in packet
    assert "**1 consumer-visible records**" in packet
    assert "**2 reviewed records**" in packet
    assert "`approved`" in packet
    assert "`remove_from_release`" in packet
    assert "Scope cannot be represented safely." in packet
    assert "Licensed pharmacist sign-off: **not represented by this packet**" in packet
