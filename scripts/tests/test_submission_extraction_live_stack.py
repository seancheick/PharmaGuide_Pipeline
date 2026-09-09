"""Real authenticated integration: PostgREST, Storage, worker JWT, real photo.

This is the proof that SQL function tests and fake transports cannot stand in
for. It uses a pre-provisioned disposable local stack, creates a real submission
through the production RPCs, uploads a real image, and drives the actual queue
client over HTTP as a real worker account.

Requires PG_RUN_LOCAL_EXTRACTION_TESTS=1, the dedicated pg-workstation-audit
stack with the migration chain applied, and runtime local keys. It refuses
an existing job queue. URLs are literal loopback, with no proxy or redirect.
"""
from __future__ import annotations

import contextlib
import fcntl
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import re
import uuid
from pathlib import Path

import pytest

pytest.importorskip("requests")
import requests  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

SCRIPTS = Path(__file__).parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

LOCAL_URL = os.environ.get("PG_LOCAL_EXTRACTION_URL", "http://127.0.0.1:55431")
DB_CONTAINER = "supabase_db_pg-workstation-audit"
DOCKER = "/Applications/Docker.app/Contents/Resources/bin/docker"
CONSENT = "pharmaguide.submission_consent.2026-08-25.v1"

# Never follow a local endpoint's redirect or pick up an ambient HTTP proxy.
class LocalSession(requests.Session):
    def request(self, method, url, **kwargs):
        assert url.startswith(LOCAL_URL + "/")
        kwargs["allow_redirects"] = False
        return super().request(method, url, **kwargs)


http = LocalSession()
http.trust_env = False

# These tests share one local stack and mutate stack-wide settings: the enabled
# switch and the consent registry are single rows, so two workers running them
# at once corrupt each other. They did, the first time this file met the
# parallel runner. A worker group is not enough because it needs a particular
# dist mode, so serialize with a real cross-process lock.
_STACK_LOCK = Path(tempfile.gettempdir()) / "pg-live-supabase-stack.lock"


@contextlib.contextmanager
def _exclusive_stack():
    with open(_STACK_LOCK, "w") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def _keys() -> tuple[str, str]:
    """Local stack keys, read from the environment and never from source.

    They are only the CLI's local development values, but a key committed to a
    repository is a key regardless of what it opens, and secret scanning is
    right to refuse it. `supabase status -o env` prints the current pair:

        export PG_LOCAL_PUBLISHABLE_KEY=... PG_LOCAL_SECRET_KEY=...
    """
    publishable = os.environ.get("PG_LOCAL_PUBLISHABLE_KEY", "")
    secret = os.environ.get("PG_LOCAL_SECRET_KEY", "")
    if not publishable or not secret:
        pytest.skip(
            "set PG_LOCAL_PUBLISHABLE_KEY and PG_LOCAL_SECRET_KEY from "
            "`supabase status -o env` to run the live stack test"
        )
    return publishable, secret


def _sql(statement: str) -> str:
    result = subprocess.run(
        [DOCKER, "exec", "-i", DB_CONTAINER, "psql", "-U", "postgres", "-d",
         "postgres", "-v", "ON_ERROR_STOP=1", "-tAc", statement],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip()[:400])
    return result.stdout.strip()


@pytest.fixture(scope="module")
def stack():
    if os.environ.get("PG_RUN_LOCAL_EXTRACTION_TESTS") != "1":
        pytest.skip("explicitly opt in with PG_RUN_LOCAL_EXTRACTION_TESTS=1")
    assert re.fullmatch(r"http://127\.0\.0\.1:[0-9]{1,5}", LOCAL_URL), "literal loopback only"
    if not Path(DOCKER).exists():
        pytest.skip("docker is required for the live stack test")
    try:
        ready = _sql(
            "SELECT count(*) FROM pg_proc WHERE proname = "
            "'claim_product_submission_extraction_jobs'"
        )
    except Exception:
        pytest.skip("local Supabase stack is not running")
    if ready != "1":
        pytest.skip("the extraction migration chain is not applied locally")
    try:
        http.get(f"{LOCAL_URL}/rest/v1/", timeout=5)
    except Exception:
        pytest.skip("the local PostgREST endpoint is not reachable")
    return _keys()


def _label_jpeg() -> bytes:
    image = Image.new("RGB", (640, 400), "white")
    draw = ImageDraw.Draw(image)
    for index, line in enumerate(
        ["NORTHWIND LABS", "Magnesium Glycinate", "Serving Size: 2 capsules"]
    ):
        draw.text((24, 30 + index * 40), line, fill="black")
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=90)
    return buffer.getvalue()


@pytest.fixture
def provisioned(stack):
    """One owner, one worker, one finalized submission with a real photo."""
    publishable, secret = stack
    with _exclusive_stack(), contextlib.ExitStack() as cleanup:
        # Do not drain another developer's work or silently rewrite their config.
        assert _sql("SELECT count(*) FROM product_submission_extraction_jobs") == "0", "use an empty disposable audit stack"
        settings = json.loads(_sql("SELECT row_to_json(s) FROM product_submission_extraction_settings s WHERE id"))
        columns = ','.join('"' + key + '"' for key in settings)
        encoded = json.dumps(settings).replace("'", "''")
        cleanup.callback(_sql, f"UPDATE product_submission_extraction_settings SET ({columns}) = "
                         f"(SELECT {columns} FROM json_populate_record(NULL::product_submission_extraction_settings, '{encoded}')) WHERE id")
        yield from _provision(publishable, secret, cleanup)


def _provision(publishable, secret, cleanup):
    suffix = uuid.uuid4().hex[:8]
    password = f"integration-only-{suffix}"
    admin = {"apikey": secret, "Authorization": f"Bearer {secret}",
             "Content-Type": "application/json"}

    def create_user(email: str) -> str:
        response = http.post(
            f"{LOCAL_URL}/auth/v1/admin/users", headers=admin,
            json={"email": email, "password": password, "email_confirm": True},
            timeout=30,
        )
        response.raise_for_status()
        user_id = response.json()["id"]
        def remove_user():
            http.delete(f"{LOCAL_URL}/auth/v1/admin/users/{user_id}", headers=admin, timeout=30).raise_for_status()
        cleanup.callback(remove_user)
        return user_id

    def sign_in(email: str) -> str:
        response = http.post(
            f"{LOCAL_URL}/auth/v1/token?grant_type=password",
            headers={"apikey": publishable, "Content-Type": "application/json"},
            json={"email": email, "password": password}, timeout=30,
        )
        response.raise_for_status()
        return response.json()["access_token"]

    worker_email = f"worker-{suffix}@example.test"
    owner_email = f"owner-{suffix}@example.test"
    worker_id = create_user(worker_email)
    owner_id = create_user(owner_email)
    cleanup.callback(_sql, f"DELETE FROM product_submission_extraction_workers WHERE user_id='{worker_id}'")
    _sql(
        "INSERT INTO product_submission_extraction_workers(user_id,label) "
        f"VALUES ('{worker_id}','integration')"
    )

    submission_id, photo_id = str(uuid.uuid4()), str(uuid.uuid4())
    cleanup.callback(_sql, f"DELETE FROM product_submissions WHERE id='{submission_id}'")
    # Enable before finalize, so the production intake trigger owns enqueueing.
    _sql(
        "UPDATE product_submission_extraction_settings SET enabled=true, "
        "provider='fake', model='fake-1', model_digest=repeat('c',64), "
        "prompt_version='p1', retention_policy_version='local-only-v1', "
        "monthly_cap_microcents=1000000, pilot_cap_microcents=100000 WHERE id"
    )
    image = _label_jpeg()
    digest = hashlib.sha256(image).hexdigest()
    owner_token = sign_in(owner_email)
    owner_headers = {"apikey": publishable, "Authorization": f"Bearer {owner_token}",
                     "Content-Type": "application/json"}
    created = http.post(
        f"{LOCAL_URL}/rest/v1/rpc/create_product_submission", headers=owner_headers,
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
    assert created.status_code == 200, created.text[:200]

    object_path = f"{owner_id}/{submission_id}/{photo_id}"
    def remove_photo():
        http.delete(f"{LOCAL_URL}/storage/v1/object/product-submission-photos", headers=admin,
                    json={"prefixes": [object_path]}, timeout=30).raise_for_status()
    cleanup.callback(remove_photo)
    upload = http.post(
        f"{LOCAL_URL}/storage/v1/object/product-submission-photos/{object_path}",
        headers={"apikey": publishable, "Authorization": f"Bearer {owner_token}", "x-upsert": "false"},
        data={"metadata": json.dumps({"content_sha256": digest})},
        files={"file": ("label.jpg", image, "image/jpeg")}, timeout=60,
    )
    assert upload.status_code == 200, upload.text[:200]
    finalized = http.post(
        f"{LOCAL_URL}/rest/v1/rpc/finalize_product_submission",
        headers=owner_headers, json={"p_submission_id": submission_id}, timeout=30,
    )
    assert finalized.json() is True, finalized.text[:200]

    context = {
        "publishable": publishable, "worker_email": worker_email,
        "owner_email": owner_email, "password": password,
        "submission_id": submission_id, "object_path": object_path,
        "owner_token": owner_token, "owner_id": owner_id, "worker_id": worker_id,
        "sign_in": sign_in,
    }
    yield context


@contextlib.contextmanager
def _queue(context):
    from submission_review.extraction.queue_client import (
        SupabaseExtractionQueue, WorkerCredentials,
    )

    environment = {
        "SUPABASE_URL": LOCAL_URL,
        "SUPABASE_PUBLISHABLE_KEY": context["publishable"],
        "EXTRACTION_WORKER_EMAIL": context["worker_email"],
        "EXTRACTION_WORKER_PASSWORD": context["password"],
    }
    queue = SupabaseExtractionQueue(WorkerCredentials.from_environment(environment))
    try:
        yield queue
    finally:
        queue.close()


def _drain(context, *, max_jobs: int = 2):
    from submission_review.extraction.adapters.fake_adapter import FakeAdapter
    from submission_review.extraction.extractor import LabelDraftExtractor
    from submission_review.extraction.worker import DrainLimits, drain

    with _queue(context) as queue:
        return drain(queue, LabelDraftExtractor(FakeAdapter()), DrainLimits(max_jobs=max_jobs))


def test_a_real_worker_claims_downloads_extracts_and_completes(provisioned) -> None:
    report = _drain(provisioned)

    # Asserted on this submission rather than the drain total: a shared local
    # stack may hold other work, and a test that only counts is not isolated.
    assert report.drafted >= 1, report.as_summary()
    assert report.failure_codes == {}
    recorded = _sql(
        "SELECT actor_kind || '|' || (draft_payload->>'draft_origin') || '|' || "
        "jsonb_array_length(draft_payload->'sent_inputs')::text "
        "FROM product_submission_extractions WHERE submission_id = "
        f"'{provisioned['submission_id']}'"
    )
    # The draft is attributed to the machine and names what it was sent.
    assert recorded == "worker|model|1"
    job = _sql(
        "SELECT state || '|' || coalesce(result_extraction_version::text,'none') "
        f"FROM product_submission_extraction_jobs WHERE submission_id='{provisioned['submission_id']}'"
    )
    assert job == "review_ready|1"


def test_the_photo_is_readable_only_under_a_live_lease(provisioned) -> None:
    publishable = provisioned["publishable"]
    worker_token = provisioned["sign_in"](provisioned["worker_email"])
    url = (
        f"{LOCAL_URL}/storage/v1/object/product-submission-photos/"
        f"{provisioned['object_path']}"
    )

    def read(token: str) -> int:
        return http.get(
            url, headers={"apikey": publishable, "Authorization": f"Bearer {token}"},
            timeout=30,
        ).status_code

    # No lease yet: the machine account cannot read another person's photograph.
    assert read(worker_token) >= 400
    # The owner always can.
    assert read(provisioned["owner_token"]) == 200

    _drain(provisioned)
    # And after the job completes, the lease is gone and so is the access.
    assert read(worker_token) >= 400


def test_only_an_allowlisted_worker_may_claim(provisioned) -> None:
    publishable = provisioned["publishable"]

    def claim(token: str | None):
        headers = {"apikey": publishable, "Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return http.post(
            f"{LOCAL_URL}/rest/v1/rpc/claim_product_submission_extraction_jobs",
            headers=headers, json={"p_limit": 1}, timeout=30,
        )

    signed_in_but_not_a_worker = claim(provisioned["owner_token"])
    assert signed_in_but_not_a_worker.status_code == 403
    assert "extraction worker access required" in signed_in_but_not_a_worker.text

    anonymous = claim(None)
    assert anonymous.status_code == 401


def test_turning_extraction_off_stops_the_queue_over_http(provisioned) -> None:
    _sql("UPDATE product_submission_extraction_settings SET enabled=false WHERE id")
    worker_token = provisioned["sign_in"](provisioned["worker_email"])

    response = http.post(
        f"{LOCAL_URL}/rest/v1/rpc/claim_product_submission_extraction_jobs",
        headers={"apikey": provisioned["publishable"],
                 "Authorization": f"Bearer {worker_token}",
                 "Content-Type": "application/json"},
        json={"p_limit": 1}, timeout=30,
    )

    assert response.status_code == 500
    assert "extraction is disabled" in response.text


def test_retiring_ai_consent_stops_new_work_being_leased(provisioned) -> None:
    _sql(
        f"UPDATE product_submission_consent_versions SET retired_at=now() "
        f"WHERE version='{CONSENT}'"
    )
    try:
        report = _drain(provisioned)
        # Nothing is leased, so nothing is read: consent is checked at the
        # queue, not left to the worker's good manners.
        assert report.claimed == 0
        assert report.drafted == 0
    finally:
        _sql(
            f"UPDATE product_submission_consent_versions SET retired_at=NULL "
            f"WHERE version='{CONSENT}'"
        )


def test_a_completed_job_is_not_handed_out_twice(provisioned) -> None:
    first = _drain(provisioned)
    second = _drain(provisioned)

    assert first.drafted == 1
    # A second run finds nothing: the job is finished, not merely unlocked.
    assert second.claimed == 0 and second.stopped_because == "queue_empty"
    count = _sql(
        "SELECT count(*)::text FROM product_submission_extractions "
        f"WHERE submission_id='{provisioned['submission_id']}'"
    )
    assert count == "1"


@pytest.mark.parametrize("revocation", ["disabled", "consent", "expired", "retake"])
def test_existing_lease_loses_photo_access_when_authority_changes(provisioned, revocation):
    with _queue(provisioned) as queue:
        job, = queue.claim(1)
        assert queue.read_evidence(job.bundle.photos[0]) == _label_jpeg()
        retired_before = _sql(f"SELECT coalesce(retired_at::text,'') FROM product_submission_consent_versions WHERE version='{CONSENT}' AND kind='missing_product'")
        try:
            if revocation == 'disabled':
                _sql("UPDATE product_submission_extraction_settings SET enabled=false WHERE id")
            elif revocation == 'consent':
                _sql(f"UPDATE product_submission_consent_versions SET retired_at=now() WHERE version='{CONSENT}' AND kind='missing_product'")
            elif revocation == 'expired':
                _sql(f"UPDATE product_submission_extraction_jobs SET leased_until=now()-interval '1 second' WHERE id='{job.job_id}'")
            else:
                response = http.post(f"{LOCAL_URL}/rest/v1/rpc/open_product_submission_evidence_revision",
                    headers={'apikey': provisioned['publishable'], 'Authorization': f"Bearer {provisioned['owner_token']}"},
                    json={'p_submission_id': provisioned['submission_id'], 'p_expected_revision': 1,
                          'p_request_key': str(uuid.uuid4()), 'p_keep_photo_ids': [], 'p_consent_version': CONSENT}, timeout=30)
                assert response.status_code == 200 and response.json() == 2
            # Real Storage HTTP must refuse the already-issued worker JWT.
            token = provisioned['sign_in'](provisioned['worker_email'])
            response = http.get(f"{LOCAL_URL}/storage/v1/object/product-submission-photos/{provisioned['object_path']}",
                headers={'apikey': provisioned['publishable'], 'Authorization': f'Bearer {token}'}, timeout=30)
            assert response.status_code in (400, 403, 404)
            assert response.content != _label_jpeg()
        finally:
            restored = "NULL" if not retired_before else "'" + retired_before.replace("'", "''") + "'::timestamptz"
            _sql(f"UPDATE product_submission_consent_versions SET retired_at={restored} WHERE version='{CONSENT}' AND kind='missing_product'")


def test_another_allowlisted_worker_cannot_read_attempt_receipts(provisioned):
    with _queue(provisioned) as queue:
        job, = queue.claim(1)
        assert queue.attempt_outcome(job.job_id, job.fencing_token)['job_state'] == 'leased'
        _sql(f"INSERT INTO product_submission_extraction_workers(user_id,label) VALUES ('{provisioned['owner_id']}','other-test-worker')")
        try:
            response = http.post(f"{LOCAL_URL}/rest/v1/rpc/product_submission_extraction_attempt_outcome",
                headers={'apikey': provisioned['publishable'], 'Authorization': f"Bearer {provisioned['owner_token']}"},
                json={'p_job_id': job.job_id, 'p_fencing_token': job.fencing_token}, timeout=30)
            assert response.status_code == 403
            assert 'extraction attempt access required' in response.text
        finally:
            _sql(f"DELETE FROM product_submission_extraction_workers WHERE user_id='{provisioned['owner_id']}'")


def test_lost_completion_response_reconciles_without_a_second_write(provisioned, monkeypatch):
    from submission_review.extraction.adapters.fake_adapter import FakeAdapter
    from submission_review.extraction.extractor import LabelDraftExtractor
    from submission_review.extraction.worker import DrainLimits, drain

    with _queue(provisioned) as queue:
        send = queue._transport.post_json
        completions = []
        def lose_ack(url, **kwargs):
            result = send(url, **kwargs)  # the real HTTP request commits
            if url.endswith('/complete_product_submission_extraction_job'):
                completions.append(kwargs['body'])
                raise TimeoutError('simulated dropped acknowledgement after COMMIT')
            return result
        monkeypatch.setattr(queue._transport, 'post_json', lose_ack)
        report = drain(queue, LabelDraftExtractor(FakeAdapter()), DrainLimits(max_jobs=1))
        assert report.drafted == 1 and report.failure_codes == {}
        assert len(completions) == 1
        attempt = completions[0]
        # A restarted client independently sees the same recorded result.
    with _queue(provisioned) as restarted:
        receipt = restarted.attempt_outcome(attempt['p_job_id'], attempt['p_fencing_token'])
        assert receipt['draft_recorded'] and not receipt['reservation_open']
        assert restarted.claim(1) == []
