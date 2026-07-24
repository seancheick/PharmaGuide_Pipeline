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
    assert (
        art["_metadata"]["content_hash"]
        == "sha256:2f869d42ac017dd235688f510c2047855def2e06481052aa1d80b105fd31670e"
    )
