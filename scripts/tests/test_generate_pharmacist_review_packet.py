from generate_pharmacist_review_packet import (
    CONSUMER_VISIBLE_FIELDS,
    build_packet,
)


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


def test_signed_packet_records_licensed_pharmacist_approval():
    artifact = {
        "_metadata": {
            "schema_version": "5.4.0",
            "content_version": "v",
            "content_hash": "sha256:abc",
        },
        "depletions": [_row("APPROVED", "verified")],
    }
    ledger = {
        "_metadata": {
            "review_scope_count": 1,
            "active_record_count": 1,
            "reviewed_at": "2026-07-27",
            "reviewer": "Dr. Pham, PharmaGuide Clinical Team",
            "reviewer_type": "Licensed pharmacist clinical review",
            "licensed_pharmacist_signoff": True,
            "release_disposition": "approved_for_controlled_beta",
        },
        "records": {
            "APPROVED": {
                "disposition": "approved",
                "note": "Claim aligns.",
            },
        },
    }

    packet = build_packet(
        artifact,
        ledger=ledger,
        verified_screenshot="verified.png",
        unavailable_screenshot="unavailable.png",
    )

    assert "licensed pharmacist clinical review complete" in packet
    assert "Dr. Pham, PharmaGuide Clinical Team" in packet
    assert "Licensed pharmacist sign-off: **confirmed**" in packet
    assert (
        "records licensed-pharmacist approval of the bounded "
        "controlled-beta corpus"
    ) in packet
    assert "does not claim professional licensure" not in packet


def test_delta_packet_uses_ledger_title_status_and_scope_overrides():
    artifact = {
        "_metadata": {
            "schema_version": "5.4.0",
            "content_version": "v",
            "content_hash": "sha256:abc",
        },
        "depletions": [_row("CANDIDATE", "needs_revision")],
    }
    ledger = {
        "_metadata": {
            "packet_title": "B1.1 pharmacist delta review packet",
            "packet_status": (
                "evidence revision complete; licensed pharmacist sign-off requested"
            ),
            "packet_scope": (
                "4 suppressed candidates; none are consumer-visible until approved."
            ),
            "reviewed_at": "2026-07-27",
            "reviewer": "openai_codex_ai_clinical_audit",
            "reviewer_type": "AI clinical-content audit",
            "licensed_pharmacist_signoff": False,
            "release_disposition": "pending_licensed_pharmacist_delta_review",
        },
        "records": {
            "CANDIDATE": {
                "disposition": "pending_licensed_pharmacist_review",
                "note": "Evidence-ready candidate.",
            },
        },
    }

    packet = build_packet(
        artifact,
        ledger=ledger,
        verified_screenshot="verified.png",
        unavailable_screenshot="unavailable.png",
    )

    assert packet.startswith("# B1.1 pharmacist delta review packet")
    assert (
        "Status: **evidence revision complete; licensed pharmacist sign-off requested**"
        in packet
    )
    assert "Scope: **4 suppressed candidates; none are consumer-visible until approved.**" in packet


def test_packet_renders_every_consumer_visible_field():
    """Every field the card shows a user must appear in the review packet.

    Regression for the 2026-07-27 B1 defect: `food_sources_short` reached
    consumers while being absent from the packet, the ledger fingerprint, and
    the reviewer golden — so a reviewer could sign "Approved" without ever
    having seen the copy. If a new consumer-visible field is added to the
    card, add it to CONSUMER_VISIBLE_FIELDS and this test keeps it in review.
    """
    row = _row("FULLCOPY", "verified")
    # Distinct sentinel per field so a dropped field cannot be masked by
    # another field's text happening to appear in the packet.
    sentinels = {
        field: f"SENTINEL-{field.upper().replace('_', '-')}"
        for field, _ in CONSUMER_VISIBLE_FIELDS
    }
    row.update(sentinels)
    artifact = {
        "_metadata": {
            "schema_version": "5.4.0",
            "content_version": "v",
            "content_hash": "sha256:abc",
        },
        "depletions": [row],
    }

    packet = build_packet(
        artifact,
        ledger=None,
        verified_screenshot="verified.png",
        unavailable_screenshot="unavailable.png",
    )

    missing = [
        field
        for field, sentinel in sentinels.items()
        if sentinel not in packet
    ]
    assert not missing, f"consumer-visible fields missing from packet: {missing}"
    # The on-screen label is what tells the reviewer where the copy appears.
    for _, label in CONSUMER_VISIBLE_FIELDS:
        assert label in packet


def test_packet_does_not_present_goldens_as_clinical_evidence():
    """The goldens are box-glyph, collapsed-card layout artifacts.

    They must never be offered to a clinician as evidence of consumer copy.
    """
    artifact = {
        "_metadata": {
            "schema_version": "5.4.0",
            "content_version": "v",
            "content_hash": "sha256:abc",
        },
        "depletions": [_row("APPROVED", "verified")],
    }

    packet = build_packet(
        artifact,
        ledger=None,
        verified_screenshot="verified.png",
        unavailable_screenshot="unavailable.png",
    )

    assert "layout-regression artifacts, not clinical-review evidence" in packet
    assert "Do not base an approval on these screenshots." in packet
