"""Contract for the versioned medication-depletions runtime artifact (B1.2).

The pipeline generates the app-bound artifact: it validates referenced ids
(rejecting a malformed asset — the primary gate), injects citation-review
defaults so every entry carries a review status, and stamps versioned metadata
(schema_version / content_version / content_hash / minimum_runtime_contract).
The content_hash covers the clinical entries, not the release version stamp, so
the app can tell "the content changed" from "a new release was cut".
"""

import pytest

from build_medication_depletions_artifact import (
    ARTIFACT_SCHEMA_VERSION,
    CITATION_REVIEW_STATES,
    MINIMUM_RUNTIME_CONTRACT,
    build_artifact,
)


def _entry(**over):
    e = {
        "id": "DEP_STATINS_COQ10",
        "drug_ref": {
            "type": "class",
            "id": "class:statins",
            "display_name": "Statins",
        },
        "depleted_nutrient": {
            "standard_name": "CoQ10",
            "canonical_id": "coenzyme_q10",
        },
        "depletion_type": "depletion",
        "severity": "significant",
    }
    e.update(over)
    return e


def _source(entries):
    return {"_metadata": {"schema_version": "5.3.0"}, "depletions": entries}


def test_metadata_is_stamped():
    art = build_artifact(_source([_entry()]), content_version="2026.07.23")
    m = art["_metadata"]
    assert m["schema_version"] == ARTIFACT_SCHEMA_VERSION
    assert m["content_version"] == "2026.07.23"
    assert m["content_hash"].startswith("sha256:")
    assert m["minimum_runtime_contract"] == MINIMUM_RUNTIME_CONTRACT
    assert m["total_entries"] == 1


def test_all_states_are_the_locked_enum():
    assert CITATION_REVIEW_STATES == {
        "unverified",
        "verified",
        "needs_revision",
        "rejected",
    }


def test_review_status_defaults_to_unverified():
    art = build_artifact(_source([_entry()]), content_version="v")
    e = art["depletions"][0]
    assert e["citation_review_status"] == "unverified"
    assert e["reviewed_at"] is None
    assert e["reviewer"] is None


def test_authored_review_status_preserved():
    art = build_artifact(
        _source(
            [
                _entry(
                    citation_review_status="verified",
                    reviewed_at="2026-07-23T00:00:00Z",
                    reviewer="lead_clinician",
                )
            ]
        ),
        content_version="v",
    )
    e = art["depletions"][0]
    assert e["citation_review_status"] == "verified"
    assert e["reviewed_at"] == "2026-07-23T00:00:00Z"
    assert e["reviewer"] == "lead_clinician"


def test_invalid_authored_review_status_rejected():
    with pytest.raises(ValueError):
        build_artifact(
            _source([_entry(citation_review_status="bogus")]), content_version="v"
        )


def test_valid_proposed_watch_threshold_is_preserved_but_not_promoted():
    entry = _entry(
        citation_review_status="verified",
        watch_threshold_days=730,
        watch_basis="The entry source stratified exposure at two years.",
        watch_review_status="proposed",
        watch_approver=None,
    )
    art = build_artifact(_source([entry]), content_version="v")
    emitted = art["depletions"][0]
    assert emitted["watch_threshold_days"] == 730
    assert emitted["watch_review_status"] == "proposed"
    assert emitted["watch_approver"] is None


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"watch_threshold_days": "730"}, "positive whole number"),
        ({"watch_threshold_days": 0}, "positive whole number"),
        ({"watch_basis": ""}, "watch_basis"),
        ({"watch_review_status": "draft"}, "watch_review_status"),
    ],
)
def test_malformed_watch_threshold_is_rejected(override, message):
    entry = _entry(
        citation_review_status="verified",
        watch_threshold_days=730,
        watch_basis="Cited basis.",
        watch_review_status="proposed",
    )
    entry.update(override)
    with pytest.raises(ValueError, match=message):
        build_artifact(_source([entry]), content_version="v")


def test_approved_watch_threshold_requires_attributable_reviewer():
    entry = _entry(
        citation_review_status="verified",
        watch_threshold_days=730,
        watch_basis="Cited basis.",
        watch_review_status="approved",
        watch_approver=None,
    )
    with pytest.raises(ValueError, match="watch_approver"):
        build_artifact(_source([entry]), content_version="v")


def test_proposed_watch_threshold_can_await_citation_revision_but_stays_inert():
    entry = _entry(
        citation_review_status="needs_revision",
        watch_threshold_days=730,
        watch_basis="Cited basis.",
        watch_review_status="proposed",
    )
    art = build_artifact(_source([entry]), content_version="v")
    assert art["depletions"][0]["watch_review_status"] == "proposed"


def test_approved_watch_threshold_requires_verified_citation_content():
    entry = _entry(
        citation_review_status="needs_revision",
        watch_threshold_days=730,
        watch_basis="Cited basis.",
        watch_review_status="approved",
        watch_approver="PharmaGuide Clinical Team",
    )
    with pytest.raises(ValueError, match="verified citation"):
        build_artifact(_source([entry]), content_version="v")


def test_missing_id_rejected():
    e = _entry()
    del e["id"]
    with pytest.raises(ValueError):
        build_artifact(_source([e]), content_version="v")


def test_missing_nutrient_canonical_id_rejected():
    e = _entry()
    e["depleted_nutrient"] = {"standard_name": "CoQ10"}
    with pytest.raises(ValueError):
        build_artifact(_source([e]), content_version="v")


def test_missing_drug_subject_rejected():
    e = _entry()
    e["drug_ref"] = {"type": "class"}  # no id, no display_name
    with pytest.raises(ValueError):
        build_artifact(_source([e]), content_version="v")


def test_duplicate_ids_rejected():
    dup = _entry(
        depleted_nutrient={"standard_name": "B12", "canonical_id": "vitamin_b12"}
    )
    with pytest.raises(ValueError):
        build_artifact(_source([_entry(), dup]), content_version="v")


def test_content_hash_is_deterministic():
    a = build_artifact(_source([_entry()]), content_version="v")
    b = build_artifact(_source([_entry()]), content_version="v")
    assert a["_metadata"]["content_hash"] == b["_metadata"]["content_hash"]


def test_content_hash_is_content_sensitive():
    a = build_artifact(_source([_entry()]), content_version="v")
    c = build_artifact(_source([_entry(severity="mild")]), content_version="v")
    assert c["_metadata"]["content_hash"] != a["_metadata"]["content_hash"]


def test_content_hash_ignores_release_version():
    a = build_artifact(_source([_entry()]), content_version="2026.07.23")
    b = build_artifact(_source([_entry()]), content_version="2026.08.01")
    assert a["_metadata"]["content_hash"] == b["_metadata"]["content_hash"]


def test_real_source_content_hash_is_pinned():
    """Cross-repo parity pin (B1.2 #3): the content_hash of the generated
    artifact over the REAL canonical source must equal the value the app also
    pins (test/services/stack/med_nutrient_bundled_parity_test.dart). Two
    identical pins = the parity contract — a drifted source or a stale app asset
    fails a pin. Update BOTH when the source legitimately changes."""
    import json
    import os

    source_path = os.path.join(
        os.path.dirname(__file__), os.pardir, "data", "medication_depletions.json"
    )
    with open(source_path, encoding="utf-8") as f:
        source = json.load(f)
    art = build_artifact(source, content_version="pin")
    # Repinned 2026-07-27: the final B1 clinical-content sign-off narrows
    # warfarin and prednisone scopes, suppresses the overbroad OCP-B6 record,
    # rejects the pregnancy-only antiseizure-vitamin-K warning, and records
    # evidence-aligned consumer wording plus immutable review dispositions.
    # Repinned again 2026-07-27 (B1 release correction): the metformin/B12
    # record's consumer "From food" copy no longer implies universal
    # supplementation — it names food sources and routes to testing, matching
    # the same record's risk-based recommendation. Its dormant monitoring_note
    # also drops the unverified "every 2-3 years in all patients" interval.
    # Repinned for the fail-closed B1.1 candidate delta: four suppressed records
    # received evidence-aligned proposed copy and current sources, but remain
    # hidden pending a separate licensed-pharmacist review.
    # Repinned for the B1 closure correction: eleven active records now require
    # exact-copy delta review (including the furosemide/thiamine monitoring
    # tip), and record provenance distinguishes the AI evidence audit from the
    # PharmaGuide Clinical Team's exact-fingerprint approval.
    # Repinned 2026-07-30 after the Clinical Team's bounded delta response:
    # exact levothyroxine/calcium and orlistat/vitamin-A wording was applied,
    # and the acid-suppression/iron plus SSRI/sodium evidence gaps were closed
    # with reviewed primary guidance/label sources. Final presentation review
    # remains separately fail-closed in the delta ledger.
    assert (
        art["_metadata"]["content_hash"]
        == "sha256:ed274d0b7828e3b0d511e56137cb832a417a8148b21cc4545f8d8357851a4651"
    )
