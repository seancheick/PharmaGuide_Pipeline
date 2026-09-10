"""The reviewer workstation over real HTTP: Edge Function, auth, RPCs, Storage.

Sandbox tests execute the shipped console and the SQL harness executes the real
migration chain, but neither crosses the Edge Function. This does: a real owner
creates a real submission with a real photo, a real reviewer signs in and works
it through the deployed function, and a batch approval is applied and then
replayed to prove it is not applied twice.

Requires a disposable local stack with the submission migration chain applied
and `supabase functions serve` running with PRODUCT_SUBMISSION_REVIEWER_IDS set
to the reviewer account this test signs in as. Opt in explicitly:

    export PG_RUN_LOCAL_REVIEW_TESTS=1
    export PG_REVIEW_URL=http://127.0.0.1:55531
    export PG_LOCAL_PUBLISHABLE_KEY=... PG_LOCAL_SECRET_KEY=...
    export PG_REVIEW_REVIEWER_EMAIL=... PG_REVIEW_REVIEWER_PASSWORD=...

Keys are never read from source: a key committed to a repository is a key
whatever it opens.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import uuid
from pathlib import Path

import pytest

pytest.importorskip("requests")
import requests  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

URL = os.environ.get("PG_REVIEW_URL", "http://127.0.0.1:55531")
CONSENT = "pharmaguide.submission_consent.2026-08-25.v1"
FUNCTION = f"{URL}/functions/v1/review-product-submissions"
REQUIRED_PATHS = [
    "identity.brand", "identity.product_name", "serving.size",
    "ingredient_rows", "other_ingredients",
]


class LocalSession(requests.Session):
    """Loopback only, no redirects, no ambient proxy."""

    def request(self, method, url, **kwargs):
        assert url.startswith(URL + "/"), url
        kwargs["allow_redirects"] = False
        return super().request(method, url, **kwargs)


http = LocalSession()
http.trust_env = False


def _label_payload(brand: str = "Northwind Labs") -> dict:
    """A payload the catalog importer accepts, as the console would send it."""
    return {
        "fullName": "Magnesium Glycinate",
        "brandName": brand,
        "ingredientRows": [{
            "name": "Magnesium", "ingredientGroup": "magnesium", "order": 1,
            "quantity": [], "forms": [], "nestedRows": [],
        }],
        "servingSizes": [{
            "minQuantity": 2.0, "maxQuantity": 2.0, "unit": "capsule", "order": 1,
        }],
        "otherIngredientsDisclosure": "declared_none",
    }


@pytest.fixture(scope="module")
def stack():
    if os.environ.get("PG_RUN_LOCAL_REVIEW_TESTS") != "1":
        pytest.skip("explicitly opt in with PG_RUN_LOCAL_REVIEW_TESTS=1")
    assert re.fullmatch(r"http://127\.0\.0\.1:[0-9]{1,5}", URL), "literal loopback only"
    publishable = os.environ.get("PG_LOCAL_PUBLISHABLE_KEY", "")
    secret = os.environ.get("PG_LOCAL_SECRET_KEY", "")
    email = os.environ.get("PG_REVIEW_REVIEWER_EMAIL", "")
    password = os.environ.get("PG_REVIEW_REVIEWER_PASSWORD", "")
    if not all([publishable, secret, email, password]):
        pytest.skip("set the local keys and the provisioned reviewer credentials")
    try:
        http.get(f"{URL}/rest/v1/", timeout=5)
    except Exception:
        pytest.skip("the local stack is not reachable")
    probe = http.post(
        FUNCTION, headers={"apikey": publishable, "Content-Type": "application/json"},
        json={"action": "list"}, timeout=15,
    )
    if probe.status_code != 401:
        pytest.skip("the reviewer Edge Function is not being served")
    return {
        "publishable": publishable, "secret": secret,
        "reviewer_email": email, "reviewer_password": password,
    }


def _sign_in(stack, email, password) -> str:
    response = http.post(
        f"{URL}/auth/v1/token?grant_type=password",
        headers={"apikey": stack["publishable"], "Content-Type": "application/json"},
        json={"email": email, "password": password}, timeout=30,
    )
    response.raise_for_status()
    return response.json()["access_token"]


def _call(stack, token, body, *, expect=200):
    response = http.post(
        FUNCTION,
        headers={"apikey": stack["publishable"], "Authorization": f"Bearer {token}",
                 "Content-Type": "application/json"},
        json=body, timeout=60,
    )
    assert response.status_code == expect, f"{response.status_code}: {response.text[:200]}"
    return response.json()


def _photo() -> bytes:
    image = Image.new("RGB", (640, 400), "white")
    draw = ImageDraw.Draw(image)
    draw.text((24, 30), "NORTHWIND LABS", fill="black")
    draw.text((24, 70), "Magnesium Glycinate", fill="black")
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=90)
    return buffer.getvalue()


@pytest.fixture
def submission(stack):
    """One real owner, one real finalized submission, one real photo."""
    suffix = uuid.uuid4().hex[:8]
    password = f"integration-only-{suffix}"
    admin = {"apikey": stack["secret"], "Authorization": f"Bearer {stack['secret']}",
             "Content-Type": "application/json"}
    created = http.post(
        f"{URL}/auth/v1/admin/users", headers=admin,
        json={"email": f"owner-{suffix}@example.test", "password": password,
              "email_confirm": True}, timeout=30,
    )
    created.raise_for_status()
    owner_id = created.json()["id"]
    owner_token = _sign_in(stack, f"owner-{suffix}@example.test", password)
    owner_headers = {"apikey": stack["publishable"],
                     "Authorization": f"Bearer {owner_token}",
                     "Content-Type": "application/json"}

    submission_id, photo_id = str(uuid.uuid4()), str(uuid.uuid4())
    image = _photo()
    digest = hashlib.sha256(image).hexdigest()
    response = http.post(
        f"{URL}/rest/v1/rpc/create_product_submission", headers=owner_headers,
        json={
            "p_submission_id": submission_id, "p_kind": "missing_product",
            "p_upc": "012345678905", "p_consent_version": CONSENT,
            "p_photos": [{
                "photo_id": photo_id, "seq": 1,
                "categories": ["front_identity", "supplement_facts",
                               "ingredient_disclosure", "barcode"],
                "content_type": "image/jpeg", "byte_size": len(image),
                "content_sha256": digest,
            }],
        }, timeout=30,
    )
    assert response.status_code == 200, response.text[:200]
    object_path = f"{owner_id}/{submission_id}/{photo_id}"
    upload = http.post(
        f"{URL}/storage/v1/object/product-submission-photos/{object_path}",
        headers={"apikey": stack["publishable"],
                 "Authorization": f"Bearer {owner_token}", "x-upsert": "false"},
        data={"metadata": json.dumps({"content_sha256": digest})},
        files={"file": ("label.jpg", image, "image/jpeg")}, timeout=60,
    )
    assert upload.status_code == 200, upload.text[:200]
    finalized = http.post(
        f"{URL}/rest/v1/rpc/finalize_product_submission", headers=owner_headers,
        json={"p_submission_id": submission_id}, timeout=30,
    )
    assert finalized.json() is True, finalized.text[:200]

    manifest = http.post(
        f"{URL}/rest/v1/rpc/product_submission_manifest_sha256", headers=admin,
        json={"p_manifest": {photo_id: digest}}, timeout=30,
    )
    yield {
        "submission_id": submission_id, "photo_id": photo_id,
        "owner_token": owner_token, "owner_id": owner_id,
        "manifest_sha256": manifest.json() if manifest.status_code == 200 else None,
    }
    http.delete(f"{URL}/storage/v1/object/product-submission-photos",
                headers=admin, json={"prefixes": [object_path]}, timeout=30)
    http.delete(f"{URL}/auth/v1/admin/users/{owner_id}", headers=admin, timeout=30)


@pytest.fixture
def reviewer(stack):
    return _sign_in(stack, stack["reviewer_email"], stack["reviewer_password"])


def _evidence(stack, reviewer, submission_id):
    """Revision and manifest as the server reports them, never as we guess."""
    state = _call(stack, reviewer,
                  {"action": "load_review", "submission_id": submission_id})["review"]
    return state["current_evidence_revision"], state["current_evidence_manifest_sha256"]


def _start_and_save(stack, reviewer, submission_id, brand="Northwind Labs"):
    revision, manifest = _evidence(stack, reviewer, submission_id)
    _call(stack, reviewer, {
        "action": "transition", "submission_id": submission_id,
        "to_status": "under_review", "expected_evidence_revision": revision,
        "evidence_manifest_sha256": manifest,
    })
    saved = _call(stack, reviewer, {
        "action": "save_review", "submission_id": submission_id,
        "payload": _label_payload(brand),
        "expected_evidence_revision": revision,
        "evidence_manifest_sha256": manifest,
    })["review"]
    return revision, manifest, saved["draft"]["payload_sha256"]


def test_a_reviewer_saves_reads_and_reloads_their_own_work(stack, reviewer, submission):
    submission_id = submission["submission_id"]
    revision, manifest, sha = _start_and_save(stack, reviewer, submission_id)

    for path in REQUIRED_PATHS:
        _call(stack, reviewer, {
            "action": "set_field_verification", "submission_id": submission_id,
            "field_path": path, "payload_sha256": sha, "verified": True,
            "photo_id": submission["photo_id"],
        })
    reloaded = _call(stack, reviewer,
                     {"action": "load_review", "submission_id": submission_id})["review"]

    assert reloaded["draft"]["payload"]["brandName"] == "Northwind Labs"
    assert reloaded["draft"]["superseded"] is False
    assert {entry["field_path"] for entry in reloaded["verifications"]} == set(REQUIRED_PATHS)
    assert all(entry["live"] for entry in reloaded["verifications"])
    assert all(entry["photo_id"] == submission["photo_id"]
               for entry in reloaded["verifications"])


def test_an_edit_withdraws_the_earlier_reading_over_http(stack, reviewer, submission):
    submission_id = submission["submission_id"]
    revision, manifest, sha = _start_and_save(stack, reviewer, submission_id)
    _call(stack, reviewer, {
        "action": "set_field_verification", "submission_id": submission_id,
        "field_path": "identity.brand", "payload_sha256": sha, "verified": True,
    })
    _call(stack, reviewer, {
        "action": "save_review", "submission_id": submission_id,
        "payload": _label_payload("Corrected Brand"),
        "expected_evidence_revision": revision, "evidence_manifest_sha256": manifest,
    })
    reloaded = _call(stack, reviewer,
                     {"action": "load_review", "submission_id": submission_id})["review"]

    # Kept as history, not counted as an attestation about the current text.
    assert len(reloaded["verifications"]) == 1
    assert reloaded["verifications"][0]["live"] is False


def test_a_non_reviewer_is_refused_by_the_function(stack, submission):
    _call(stack, submission["owner_token"],
          {"action": "load_review", "submission_id": submission["submission_id"]},
          expect=403)


def test_an_attestation_naming_other_text_is_refused(stack, reviewer, submission):
    submission_id = submission["submission_id"]
    _start_and_save(stack, reviewer, submission_id)

    _call(stack, reviewer, {
        "action": "set_field_verification", "submission_id": submission_id,
        "field_path": "identity.brand", "payload_sha256": "b" * 64, "verified": True,
    }, expect=400)


def test_a_stale_revision_cannot_save_corrections(stack, reviewer, submission):
    submission_id = submission["submission_id"]
    revision, manifest, _ = _start_and_save(stack, reviewer, submission_id)

    _call(stack, reviewer, {
        "action": "save_review", "submission_id": submission_id,
        "payload": _label_payload("Wrong Revision"),
        "expected_evidence_revision": revision + 1,
        "evidence_manifest_sha256": manifest,
    }, expect=400)


def test_batch_readiness_follows_the_reading(stack, reviewer, submission):
    submission_id = submission["submission_id"]
    _, _, sha = _start_and_save(stack, reviewer, submission_id)

    before = _call(stack, reviewer,
                   {"action": "review_states", "submission_ids": [submission_id]})["states"]
    assert before[0]["fully_verified"] is False

    for path in REQUIRED_PATHS:
        _call(stack, reviewer, {
            "action": "set_field_verification", "submission_id": submission_id,
            "field_path": path, "payload_sha256": sha, "verified": True,
        })
    after = _call(stack, reviewer,
                  {"action": "review_states", "submission_ids": [submission_id]})["states"]

    assert after[0]["fully_verified"] is True
    assert after[0]["payload_sha256"] == sha


def test_a_batch_refuses_an_item_nobody_finished_reading(stack, reviewer, submission):
    submission_id = submission["submission_id"]
    revision, manifest, sha = _start_and_save(stack, reviewer, submission_id)
    _call(stack, reviewer, {
        "action": "set_field_verification", "submission_id": submission_id,
        "field_path": "identity.brand", "payload_sha256": sha, "verified": True,
    })

    result = _call(stack, reviewer, {"action": "batch_transition", "items": [{
        "submission_id": submission_id, "to_status": "approved",
        "expected_evidence_revision": revision,
        "evidence_manifest_sha256": manifest,
        "product_image_photo_id": submission["photo_id"],
    }]})

    # Four of five fields unread. The database refuses, not the browser.
    assert result["applied"] == 0
    assert result["results"][0]["applied"] is False


def test_a_batch_approval_applies_once_and_is_not_replayed(stack, reviewer, submission):
    submission_id = submission["submission_id"]
    revision, manifest, sha = _start_and_save(stack, reviewer, submission_id)
    for path in REQUIRED_PATHS:
        _call(stack, reviewer, {
            "action": "set_field_verification", "submission_id": submission_id,
            "field_path": path, "payload_sha256": sha, "verified": True,
        })
    _call(stack, reviewer, {
        "action": "record_match", "submission_id": submission_id,
        "outcome": "no_match_verified", "canonical_gtin14": "00012345678905",
        "index_built_at": "2026-09-10T00:00:00Z", "candidate_dsld_ids": [],
        "expected_evidence_revision": revision,
        "evidence_manifest_sha256": manifest,
    })
    item = {
        "submission_id": submission_id, "to_status": "approved",
        "expected_evidence_revision": revision,
        "evidence_manifest_sha256": manifest,
        "product_image_photo_id": submission["photo_id"],
    }

    first = _call(stack, reviewer, {"action": "batch_transition", "items": [item]})
    assert first["applied"] == 1, first
    assert first["results"][0]["applied"] is True

    # The same request again is the lost-answer case. Approved is terminal, so
    # the transition refuses rather than approving a second time.
    second = _call(stack, reviewer, {"action": "batch_transition", "items": [item]})
    assert second["applied"] == 0
    assert second["results"][0]["applied"] is False

    final = _call(stack, reviewer,
                  {"action": "review_states", "submission_ids": [submission_id]})["states"]
    assert final[0]["review_status"] == "approved"
