"""Advisory photo sections: evidence-based hints, never approval or identity."""
from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from submission_review.extraction.adapters.ocr_adapter import OcrLine, OcrPage


def page(*texts):
    return OcrPage(photo_id="photo", input_id="i0", lines=tuple(
        OcrLine(text=text, left=10, top=i * 20, right=300, bottom=i * 20 + 18)
        for i, text in enumerate(texts)
    ))


def suggestions(*texts):
    from submission_review.extraction.photo_guidance import suggest_photo_roles
    return suggest_photo_roles(page(*texts))


def test_sections_are_multi_role_and_include_located_support():
    result = suggestions("Supplement Facts", "Serving Size: 1 capsule",
                         "Other ingredients: rice flour", "Warnings: Keep out of reach of children")
    assert [item["role"] for item in result] == [
        "supplement_facts", "ingredient_disclosure", "directions_warnings"]
    assert result[0]["text"] == "Supplement Facts"
    assert result[0]["box"] == {"left": 10, "top": 0, "right": 300, "bottom": 18}
    assert all("confidence" not in item for item in result)


@pytest.mark.parametrize("text", ["SupplementFacts", "SUPPLEMENT FACTS", "Supplement Facts:"])
def test_collapsed_heading_is_supported(text):
    assert suggestions(text)[0]["role"] == "supplement_facts"


@pytest.mark.parametrize("text", ["Allergens & warnings", "Product Warning: Keep out of reach of children"])
def test_retailer_warning_headings_are_supported(text):
    assert suggestions(text)[0]["role"] == "directions_warnings"


@pytest.mark.parametrize("text", [
    "Read the Supplement Facts panel before use", "Our ingredients are the best",
    "Vitamin C 500 mg", "Organic brand name", "Directions for a healthier life",
    "Données nutritionnelles", "Serving Size: 1 capsule", "",
])
def test_missing_or_ambiguous_headings_do_not_invent_front_or_facts(text):
    assert suggestions(text) == []


@pytest.mark.parametrize("text", ["UPC: 030772032565", "UPC: 0  30772  03256  5"])
def test_printed_upc_uses_existing_gtin_owner(text):
    assert suggestions(text)[0]["role"] == "barcode"


@pytest.mark.parametrize("text", ["TCIN: 93215054", "UPC: 030772032564", "Lot 0370001\n23453 ct"])
def test_unrelated_or_invalid_numbers_are_not_barcode_evidence(text):
    assert suggestions(text) == []


def test_advice_distinguishes_unknown_unreadable_and_possible_mismatch():
    from submission_review.extraction.photo_guidance import guidance_for_page
    source = page("Supplement Facts")
    original = copy.deepcopy(source)
    report = guidance_for_page(source, declared=("front_identity",))
    assert report["possible_role_mismatch"] is True
    assert report["status"] == "suggestions"
    assert report["declared"] == ["front_identity"]
    assert source == original
    assert guidance_for_page(page(), declared=())["status"] == "unreadable"
    assert guidance_for_page(page("Brand"), declared=())["status"] == "unknown"
    assert not guidance_for_page(source, declared=("front_identity", "supplement_facts"))["possible_role_mismatch"]


def test_adapter_uses_the_same_role_suggestions_without_claiming_probability():
    from test_submission_ocr_adapter import _extract, _line
    draft = _extract([_line("Supplement Facts", 0), _line("Vitamin C", 40, width=120),
                      _line("500 mg", 40, left=300, width=70)])
    assert draft["photo_roles"][0]["inferred"] == [
        {"role": "supplement_facts", "confidence": None}]


SUBMISSION = "11111111-1111-4111-8111-111111111111"
PHOTO = "22222222-2222-4222-8222-222222222222"
PROJECT = "https://project.supabase.co"
REQUEST = {"submission_id": SUBMISSION, "photo_id": PHOTO,
           "evidence_revision": 1, "evidence_manifest_sha256": "c" * 64}
RAW = b"controlled stored photo"
ROW = {"id": SUBMISSION, "evidence_revision": 1,
       "evidence_manifest_sha256": "c" * 64,
       "photos": [{"photo_id": PHOTO, "content_sha256": hashlib.sha256(RAW).hexdigest(),
                   "categories": ["front_identity"],
                   "signed_url": PROJECT + "/storage/v1/object/sign/product-submission-photos/u/s/p?token=signed"}]}


def boundary(*, rows=None, upstream_status=200, request=None, raw=RAW):
    from submission_review.photo_guidance_service import review_photo_guidance
    from submission_review.extraction.bounded_http import Response
    from submission_review.serve import validate_submission_photo_url
    calls = []
    snapshots = iter(rows or [copy.deepcopy(ROW), copy.deepcopy(ROW)])

    def transport(method, url, **kwargs):
        calls.append((method, url, kwargs))
        if method == "POST":
            assert kwargs["body"] == {"action": "list", "submission_id": SUBMISSION, "limit": 1}
            return Response(upstream_status, json.dumps({"submissions": [next(snapshots)]}).encode())
        assert "authorization" not in kwargs.get("headers", {})  # signed URL only
        return Response(200, raw)

    def runner(photo, data):
        calls.append(("OCR", photo, data))
        return {"rules_version": "photo-sections-v1", "status": "suggestions",
                "suggestions": [{"role": "supplement_facts", "text": "Supplement Facts"}],
                "declared": list(photo.categories), "possible_role_mismatch": True}

    result = review_photo_guidance(request or REQUEST, "Bearer reviewer", PROJECT, "anon",
                                  validate_submission_photo_url, transport=transport, runner=runner)
    return result, calls


def test_authorized_guidance_binds_report_to_unchanged_server_evidence():
    report, calls = boundary()
    assert report["photo_id"] == PHOTO
    assert report["evidence_manifest_sha256"] == REQUEST["evidence_manifest_sha256"]
    assert report["photo_sha256"] == ROW["photos"][0]["content_sha256"]
    assert [call[0] for call in calls] == ["POST", "GET", "OCR", "POST"]


@pytest.mark.parametrize("status", [401, 403, 500])
def test_reviewer_authorization_must_succeed_before_ocr(status):
    from submission_review.photo_guidance_service import GuidanceError
    with pytest.raises(GuidanceError) as error:
        boundary(upstream_status=status)
    assert error.value.status == (status if status in (401, 403) else 503)


def test_photo_removed_or_revision_changed_while_reading_refuses_result():
    from submission_review.photo_guidance_service import GuidanceError
    newer = {**ROW, "evidence_revision": 2}
    with pytest.raises(GuidanceError) as error:
        boundary(rows=[ROW, newer])
    assert error.value.status == 409


def test_manifest_digest_is_verified_before_ocr_even_for_signed_photos():
    from submission_review.photo_guidance_service import GuidanceError
    with pytest.raises(GuidanceError):
        boundary(raw=b"different photo")


@pytest.mark.parametrize("changes", [
    {"signed_url": "https://attacker.example/photo"}, {"photo_id": "not-a-uuid"},
    {"evidence_revision": True}, {"evidence_manifest_sha256": "invalid"},
])
def test_client_cannot_supply_sources_or_invalid_bindings(changes):
    from submission_review.photo_guidance_service import GuidanceError
    with pytest.raises(GuidanceError) as error:
        boundary(request={**REQUEST, **changes})
    assert error.value.status == 400


def test_server_returned_photo_url_still_cannot_redirect_to_another_host():
    from submission_review.photo_guidance_service import GuidanceError
    bad = copy.deepcopy(ROW)
    bad["photos"][0]["signed_url"] = "https://attacker.example/photo"
    with pytest.raises(GuidanceError):
        boundary(rows=[bad])


@pytest.fixture
def guidance_http():
    from submission_review.serve import ReviewerHandler
    server = ThreadingHTTPServer(("127.0.0.1", 0), ReviewerHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}/api/photo_guidance"
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


def test_guidance_http_requires_session_before_work(guidance_http):
    request = urllib.request.Request(guidance_http, data=json.dumps(REQUEST).encode())
    with pytest.raises(urllib.error.HTTPError) as error:
        urllib.request.urlopen(request)
    assert error.value.code == 401


def test_guidance_http_uses_authorized_service_and_does_not_enqueue(monkeypatch, guidance_http):
    from submission_review import photo_guidance_service as service
    calls = []

    def check(payload, authorization, project, key):
        calls.append((payload, authorization))
        return {**REQUEST, "status": "unknown"}

    monkeypatch.setattr(service, "execute_photo_guidance", check)
    request = urllib.request.Request(guidance_http, data=json.dumps(REQUEST).encode(),
                                     headers={"Authorization": "Bearer reviewer"})
    with urllib.request.urlopen(request) as response:
        assert response.headers["Cache-Control"] == "no-store"
        assert json.load(response)["status"] == "unknown"
    assert calls == [(REQUEST, "Bearer reviewer")]


def test_ocr_timeout_has_a_hard_deadline_and_no_inherited_api_credentials(monkeypatch):
    from submission_review import photo_guidance_service as service
    from submission_review.extraction.extractor import EvidencePhoto
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "must-not-travel")

    def hang(command, **kwargs):
        assert kwargs["timeout"] == service.OCR_TIMEOUT_SECONDS
        assert kwargs["stderr"] == subprocess.DEVNULL
        assert "SUPABASE_SERVICE_ROLE_KEY" not in kwargs["env"]
        assert kwargs["input"] == RAW
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    monkeypatch.setattr(service.subprocess, "run", hang)
    with pytest.raises(subprocess.TimeoutExpired):
        service.run_photo_guidance(EvidencePhoto(PHOTO, "a" * 64), RAW)


def test_oversized_download_is_refused_even_with_an_injected_transport():
    from submission_review.photo_guidance_service import GuidanceError
    from submission_review.extraction.photo_prep import MAX_SOURCE_BYTES
    with pytest.raises(GuidanceError):
        boundary(raw=b"x" * (MAX_SOURCE_BYTES + 1))


def test_entire_guidance_has_a_deadline_including_dns_and_releases_its_slot(monkeypatch):
    from submission_review import photo_guidance_service as service
    calls = []

    def hang(command, **kwargs):
        calls.append(command)
        assert "Bearer reviewer" not in " ".join(command)
        assert json.loads(kwargs["input"])["authorization"] == "Bearer reviewer"
        assert kwargs["timeout"] == service.GUIDANCE_TIMEOUT_SECONDS
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    monkeypatch.setattr(service.subprocess, "run", hang)
    for _ in range(2):
        with pytest.raises(service.GuidanceError) as error:
            service.execute_photo_guidance(REQUEST, "Bearer reviewer", PROJECT, "anon")
        assert error.value.status == 503
    assert len(calls) == 2
