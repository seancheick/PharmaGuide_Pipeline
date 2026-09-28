"""The agent reader's two guarantees, tested without a network.

1. What the agent writes is label content only; provenance comes from the
   runtime, so a reading cannot claim evidence it was not given.
2. label.json may only add what a draft cannot carry. A changed reading value
   has to go back through the draft, or the reviewer's draft and label differ.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from submission_review.extraction.agent_reader import (  # noqa: E402
    AgentError, _bundle as bundle_from_fetch, build_draft, reading_changes, save_refusal,
)
from submission_review.extraction.extractor import (  # noqa: E402
    PreparedBundle, PreparedInput,
)

PHOTO = "11111111-1111-4111-8111-111111111111"


def _bundle() -> PreparedBundle:
    data = b"prepared"
    import hashlib
    return PreparedBundle("s", 3, (PreparedInput(
        input_id="i0", photo_id=PHOTO, original_sha256="a" * 64,
        sent_sha256=hashlib.sha256(data).hexdigest(), content_type="image/jpeg",
        byte_size=len(data), data=data),))


def _source_field(value):
    return {"value": value, "status": "read", "confidence": None,
            "sources": [{"photo_id": PHOTO, "supporting_text": value}]}


def test_provenance_is_the_runtime_s_and_sources_get_their_input() -> None:
    draft = build_draft({"identity": {"brand": _source_field("Acme")}}, _bundle(), "m1")

    assert draft["provider"] == "agent" and draft["model"] == "m1"
    assert draft["evidence_revision"] == 3
    assert draft["evidence_snapshot"] == {PHOTO: "a" * 64}
    assert draft["identity"]["brand"]["sources"][0]["input_id"] == "i0"


def test_a_reading_cannot_carry_provenance_or_cite_a_foreign_photo() -> None:
    with pytest.raises(AgentError):
        build_draft({"provider": "human"}, _bundle(), "m1")
    foreign = _source_field("Acme")
    foreign["sources"][0]["photo_id"] = "22222222-2222-4222-8222-222222222222"
    with pytest.raises(AgentError):
        build_draft({"identity": {"brand": foreign}}, _bundle(), "m1")


def test_label_json_may_add_but_not_change_the_reading() -> None:
    skeleton = {
        "brandName": "Acme",
        "ingredientRows": [{"name": "Vitamin C (as ascorbic acid)", "forms": [{"name": "ascorbic acid"}],
                            "quantity": [{"quantity": 1000.0, "unit": "mg"}], "nestedRows": []}],
        "statements": [{"type": "Label statement", "notes": "Vegan."}],
    }
    completed = {
        "brandName": "Acme", "physicalState": {"name": "Tablet(s)"},
        "ingredientRows": [{**skeleton["ingredientRows"][0], "ingredientGroup": "Vitamin C"}],
        "statements": [{"type": "Formulation re: Vegetarian/Vegan", "notes": "Vegan."}],
    }
    assert reading_changes(skeleton, completed) == []

    altered = {**completed, "ingredientRows": [
        {**completed["ingredientRows"][0], "quantity": [{"quantity": 100.0, "unit": "mg"}]}]}
    assert reading_changes(skeleton, altered) == ["$.ingredientRows[0].quantity[0].quantity"]
    assert reading_changes(skeleton, {**completed, "statements": []}) == ["$.statements"]


def _saveable():
    draft = build_draft({"identity": {"brand": _source_field("Acme")}}, _bundle(), "m1")
    return draft, {"brandName": "Acme"}, {"evidence_revision": 3}


def test_save_refuses_a_reading_of_photos_that_changed_since_record() -> None:
    draft, label, submission = _saveable()
    assert save_refusal(draft, label, submission, {}) is None
    assert "photos changed" in save_refusal(draft, label, {"evidence_revision": 4}, {})


def test_save_never_writes_over_a_review_the_reviewer_has_started() -> None:
    draft, label, submission = _saveable()
    ticked = {"verifications": [{"field": "brand", "live": True}]}
    assert "ticked" in save_refusal(draft, label, submission, ticked)
    edited = {"draft": {"payload": {"brandName": "Acme Labs"}}}
    assert "edited" in save_refusal(draft, label, submission, edited)
    # The agent's own earlier save of the same label is not the reviewer's edit.
    assert save_refusal(draft, label, submission, {"draft": {"payload": label}}) is None


def test_a_photo_added_after_fetch_asks_for_fetch_not_a_traceback(tmp_path) -> None:
    import json
    (tmp_path / "photos.json").write_text(json.dumps([{"photo_id": PHOTO, "file": "a.jpg"}]))
    submission = {"id": "s", "evidence_revision": 2, "photos": [
        {"photo_id": PHOTO, "content_sha256": "a" * 64},
        {"photo_id": "22222222-2222-4222-8222-222222222222", "content_sha256": "b" * 64}]}
    with pytest.raises(AgentError, match="fetch"):
        bundle_from_fetch(submission, tmp_path)
