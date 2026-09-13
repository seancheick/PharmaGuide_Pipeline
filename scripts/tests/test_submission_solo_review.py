"""Solo results measure the untouched extraction against the reviewed label."""
import copy
import json
import threading
import urllib.request
import urllib.error
from http.server import ThreadingHTTPServer

import pytest

from submission_review.solo_review import summarize, save_review
from submission_review.extraction.bounded_http import Response


def authorized_record():
    from submission_review.extraction.to_manual_label import to_manual_label
    data = record()
    data.update(submission_id="11111111-1111-4111-8111-111111111111",
                reviewer="22222222-2222-4222-8222-222222222222",
                evidence_manifest_sha256="a" * 64)
    def field(value):
        return {"status": "read", "value": value}
    draft = {"schema_version": "label_draft_v1", "draft_origin": "model",
             "evidence_revision": 1,
             "identity": {"brand": field("Brand"), "product_name": field("D")},
             "ingredient_rows": [{"display_name": field("Vitamin D"),
                 "amount": field({"value": 50, "unit_text": "mcg"})}]}
    data["original_machine_draft"] = draft
    data["original_machine_payload"] = to_manual_label(draft).payload
    data["reviewed_payload"] = copy.deepcopy(data["original_machine_payload"])
    return data


def remote_transport(data, *, status=200):
    def request(method, url, **kwargs):
        if status != 200:
            return Response(status, b'{}')
        if url.endswith('/auth/v1/user'):
            result = {"id": data["reviewer"]}
        else:
            assert kwargs["body"]["submission_id"] == data["submission_id"]
            result = {"submissions": [{"id": data["submission_id"], "evidence_revision": 1,
                "evidence_manifest_sha256": data["evidence_manifest_sha256"],
                "extractions": [{"version": 1, "evidence_revision": 1,
                    "draft_payload": data["original_machine_draft"], "grounding": data["grounding"]}]}]}
        return Response(200, json.dumps(result).encode())
    return request


def record():
    row = {"name": "Vitamin D", "quantity": [{"quantity": 50, "unit": "mcg"}],
           "forms": [{"name": "cholecalciferol"}], "nestedRows": [], "order": 1}
    return {"schema_version": "solo_review_v1", "submission_id": "one", "evidence_revision": 1,
            "extraction_version": 1, "reviewer": "sean", "active_seconds": 12,
            "original_machine_draft": {"schema_version": "label_draft_v1"},
            "original_machine_payload": {"brandName": "Brand", "fullName": "D",
                "servingSizes": [{"minQuantity": 1, "unit": "capsule"}],
                "ingredientRows": [row]},
            "reviewed_payload": {"brandName": "Brand", "fullName": "D",
                "servingSizes": [{"minQuantity": 1, "unit": "capsule"}],
                "ingredientRows": [copy.deepcopy(row)]},
            "rows": [{"original_index": 0, "reviewed_index": 0, "confirmed": True}],
            "grounding": {"rows": [{"row_index": 0, "status": "supported"}]},
            "photo_causes": [], "review_complete": True}


def test_wrong_dose_is_not_hidden_by_supported_verification():
    data = record()
    data["reviewed_payload"]["ingredientRows"][0]["quantity"][0]["quantity"] = 120
    result = summarize([data])
    assert result["metrics"]["amount"] == {"correct": 0, "total": 1, "unknown": 0}
    assert result["verification"]["incorrect_supported"] == 1
    assert result["corrections"][0]["original_machine_value"]["amount"] == 50
    assert result["corrections"][0]["reviewed_value"]["amount"] == 120


def test_missing_rows_are_in_denominator_and_forms_only_when_printed():
    data = record()
    data["reviewed_payload"]["ingredientRows"].append({"name": "Zinc", "quantity": [{"quantity": 10, "unit": "mg"}], "forms": []})
    data["rows"].append({"original_index": None, "reviewed_index": 1, "confirmed": True})
    result = summarize([data])
    assert result["ingredient_rows_reviewed"] == 2
    assert result["metrics"]["amount"]["total"] == 2
    assert result["metrics"]["ingredient_form"]["total"] == 1
    assert result["missed_ingredients"] == 1


def test_reorder_does_not_manufacture_corrections():
    data = record()
    zinc = {"name": "Zinc", "quantity": [{"quantity": 10, "unit": "mg"}]}
    data["original_machine_payload"]["ingredientRows"].append(zinc)
    data["reviewed_payload"]["ingredientRows"].insert(0, copy.deepcopy(zinc))
    data["rows"] = [{"original_index": 0, "reviewed_index": 1, "confirmed": True},
                    {"original_index": 1, "reviewed_index": 0, "confirmed": True}]
    assert summarize([data])["products_corrected"] == 0


def test_removed_invention_retains_machine_value():
    data = record()
    data["reviewed_payload"]["ingredientRows"] = []
    data["rows"] = [{"original_index": 0, "reviewed_index": None, "confirmed": True, "reason": "not on label"}]
    result = summarize([data])
    assert result["invented_ingredients"] == 1
    assert result["corrections"][0]["reviewed_value"] is None


def test_incomplete_and_duplicate_correspondence_are_rejected():
    data = record()
    data["rows"].append(copy.deepcopy(data["rows"][0]))
    with pytest.raises(ValueError):
        summarize([data])


def test_multiple_serving_quantities_are_measured():
    data = record()
    original = data["original_machine_payload"]["ingredientRows"][0]
    reviewed = data["reviewed_payload"]["ingredientRows"][0]
    original["quantity"].append({"quantity": 100, "unit": "mcg", "servingSizeOrder": 2})
    reviewed["quantity"].append({"quantity": 200, "unit": "mcg", "servingSizeOrder": 2})
    summary = summarize([data])
    assert summary["metrics"]["amount"]["total"] == 1
    assert summary["metrics"]["amount"]["correct"] == 0
    assert summary["products_corrected"] == 1


def test_removing_invented_form_records_error_without_applicability():
    data = record()
    data["reviewed_payload"]["ingredientRows"][0]["forms"] = []
    summary = summarize([data])
    assert summary["metrics"]["ingredient_form"]["total"] == 0
    assert summary["products_corrected"] == 1
    assert summary["top_errors"]["WRONG_FORM"] == 1


def test_removing_invented_identity_and_serving_does_not_pass():
    data = record()
    data["reviewed_payload"]["brandName"] = ""
    data["reviewed_payload"]["servingSizes"] = []
    summary = summarize([data])
    assert summary["metrics"]["product_identity"]["correct"] == 0
    assert summary["metrics"]["serving_info"]["correct"] == 0


def test_csv_contains_aggregate_denominators(tmp_path):
    output = save_review(record(), tmp_path)
    assert "ingredient_rows_reviewed" in output["csv"]
    assert "ingredient_form" in output["csv"]


def test_bad_record_never_poisons_saved_results(tmp_path):
    bad = record()
    bad["photo_causes"] = None
    with pytest.raises(ValueError):
        save_review(bad, tmp_path)
    assert not list(tmp_path.glob("*.json"))
    assert save_review(record(), tmp_path)["summary"]["products_reviewed"] == 1
    data = record()
    data["rows"][0]["confirmed"] = False
    with pytest.raises(ValueError):
        summarize([data])


def test_one_person_one_product_saves_immutable_original_and_csv(tmp_path):
    data = record()
    saved = save_review(data, tmp_path)
    assert saved["summary"]["products_reviewed"] == 1
    assert "development" in saved["text"].lower()
    assert "original_machine_value" in saved["csv"]
    assert len(list(tmp_path.glob("*.json"))) == 1
    changed = copy.deepcopy(data)
    changed["original_machine_payload"]["fullName"] = "different"
    with pytest.raises(ValueError, match="original"):
        save_review(changed, tmp_path)
    assert json.loads(next(tmp_path.glob("*.json")).read_text())["original_machine_payload"]["fullName"] == "D"


def test_review_http_endpoint_persists_and_returns_report(tmp_path, monkeypatch):
    from submission_review import serve, solo_review
    from submission_review.extraction import bounded_http
    data = authorized_record()
    monkeypatch.setattr(bounded_http, "request", remote_transport(data))
    monkeypatch.setattr(solo_review, "ROOT", tmp_path)
    server = ThreadingHTTPServer(("127.0.0.1", 0), serve.ReviewerHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        request = urllib.request.Request(f"http://127.0.0.1:{server.server_port}/api/solo_review",
            data=json.dumps(data).encode(), headers={"Authorization": "Bearer fixture", "Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=5) as response:
            result = json.load(response)
        assert result["summary"]["products_reviewed"] == 1
        assert result["summary"]["metrics"]["amount"]["correct"] == 1
        assert "Vitamin D" in result["csv"]
        assert len(list(tmp_path.glob("*.json"))) == 1
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.mark.parametrize("status", [401, 403])
def test_report_endpoint_refuses_unverified_access(tmp_path, monkeypatch, status):
    from submission_review import serve, solo_review
    from submission_review.extraction import bounded_http
    data = authorized_record()
    monkeypatch.setattr(solo_review, "ROOT", tmp_path)
    monkeypatch.setattr(bounded_http, "request", remote_transport(data, status=status))
    server = ThreadingHTTPServer(("127.0.0.1", 0), serve.ReviewerHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{server.server_port}/api/solo_review",
            data=json.dumps(data).encode(), headers={"Authorization": "Bearer forged"})
        with pytest.raises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(req, timeout=5)
        assert error.value.code == status
        assert not list(tmp_path.glob("*.json"))
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=5)


def test_reports_do_not_include_another_reviewers_private_records(tmp_path):
    other = record()
    other.update(reviewer="other", submission_id="private-other")
    save_review(other, tmp_path)
    result = save_review(record(), tmp_path)
    assert result["summary"]["products_reviewed"] == 1
    assert "private-other" not in result["csv"]


def test_signed_in_non_reviewer_cannot_save_results(tmp_path, monkeypatch):
    from submission_review import solo_review
    from submission_review.extraction import bounded_http
    data = authorized_record()
    calls = []

    def transport(method, url, **kwargs):
        calls.append(url)
        if url.endswith("/auth/v1/user"):
            return Response(200, json.dumps({"id": data["reviewer"]}).encode())
        return Response(403, b'{}')

    monkeypatch.setattr(solo_review, "ROOT", tmp_path)
    monkeypatch.setattr(bounded_http, "request", transport)
    with pytest.raises(solo_review.SoloReviewError) as error:
        solo_review.save_authorized_review(data, "Bearer valid", "https://fixture", "public")
    assert error.value.status == 403
    assert len(calls) == 2
    assert not list(tmp_path.glob("*.json"))


@pytest.mark.parametrize("field", ["reviewer", "evidence_manifest_sha256", "original_machine_draft", "original_machine_payload"])
def test_authorized_report_refuses_forged_bindings(tmp_path, monkeypatch, field):
    from submission_review import solo_review
    from submission_review.extraction import bounded_http
    original = authorized_record()
    monkeypatch.setattr(solo_review, "ROOT", tmp_path)
    monkeypatch.setattr(bounded_http, "request", remote_transport(original))
    forged = copy.deepcopy(original)
    if isinstance(forged[field], dict):
        forged[field]["invented"] = True
    else:
        forged[field] = "b" * 64 if field.endswith("sha256") else "different-reviewer"
    with pytest.raises(solo_review.SoloReviewError) as error:
        solo_review.save_authorized_review(forged, "Bearer test", "https://fixture", "public")
    assert error.value.status in (403, 409)
    assert not list(tmp_path.glob("*.json"))


def test_stored_grounding_overrides_browser_claims_and_handles_old_rows(tmp_path, monkeypatch):
    from submission_review import solo_review
    from submission_review.extraction import bounded_http
    remote = authorized_record()
    remote["grounding"] = {"rows": None}
    monkeypatch.setattr(solo_review, "ROOT", tmp_path)
    monkeypatch.setattr(bounded_http, "request", remote_transport(remote))
    browser = authorized_record()  # falsely claims supported
    result = solo_review.save_authorized_review(browser, "Bearer test", "https://fixture", "public")
    assert result["summary"]["verification"]["not_checked"] == 1


@pytest.mark.parametrize("value", [None, {}, [None], ["bad"]])
def test_malformed_row_links_are_rejected_without_writing(tmp_path, value):
    data = record(); data["rows"] = value
    with pytest.raises(ValueError):
        save_review(data, tmp_path)
    assert not list(tmp_path.glob("*.json"))
