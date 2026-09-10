"""The authenticated queue client: what a worker may reach, and how it fails.

No network. A fake transport stands in for the database so the client's own
rules can be examined: it signs in as itself, refuses the service key, reads
only the photos its lease named, bounds what it accepts, and removes another
person's photographs from disk whatever the outcome.
"""
from __future__ import annotations

import hashlib
import io
from pathlib import Path

import pytest
from PIL import Image

from submission_review.extraction.extractor import ExtractionError
from submission_review.extraction.queue_client import (
    QueueConfigurationError,
    SupabaseExtractionQueue,
    WorkerCredentials,
)
from submission_review.extraction.worker import LeaseLostError

_PHOTO = "10000000-0000-0000-0000-000000000001"
_OTHER = "10000000-0000-0000-0000-000000000002"
_SUBMISSION = "018f4c79-7c7e-4c70-9d62-7fc3b9ce6a11"


def _jpeg() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (32, 24), (10, 90, 160)).save(buffer, format="JPEG")
    return buffer.getvalue()


_IMAGE = _jpeg()
_DIGEST = hashlib.sha256(_IMAGE).hexdigest()

_ENV = {
    "SUPABASE_URL": "https://example.test",
    "SUPABASE_PUBLISHABLE_KEY": "sb_publishable_fixture",
    "EXTRACTION_WORKER_EMAIL": "worker@example.test",
    "EXTRACTION_WORKER_PASSWORD": "worker-secret",
}

_CONFIG = {
    "provider": "ollama",
    "model": "gemma4",
    "model_digest": "d" * 64,
    "prompt_version": "p1",
    "prep_config_version": "prep_v1",
    "retention_policy_version": "local-only-v1",
    "max_cost_microcents": 0,
}


def _claim_row(**overrides):
    row = {
        "job_id": "018f4c79-7c7e-4c70-9d62-7fc3b9ce6a20",
        "submission_id": _SUBMISSION,
        "evidence_revision": 1,
        "job_key": "f" * 64,
        "fencing_token": 3,
        "attempts": 1,
        "leased_until": "2026-09-09T12:00:00Z",
        "evidence_manifest": {_PHOTO: _DIGEST},
        "evidence_object_paths": {_PHOTO: f"owner/{_SUBMISSION}/{_PHOTO}"},
        "configuration": dict(_CONFIG),
    }
    row.update(overrides)
    return row


class _Transport:
    def __init__(self, *, claim_rows=None, photo_bytes=_IMAGE):
        self.claim_rows = claim_rows if claim_rows is not None else [_claim_row()]
        self.photo_bytes = photo_bytes
        self.calls: list[str] = []
        self.fetched: list[str] = []
        self.rejections: dict[str, Exception] = {}

    def post_json(self, url, *, headers, body, timeout):
        name = url.rsplit("/", 1)[-1].split("?")[0]
        self.calls.append(name)
        assert timeout > 0, "every request must carry a deadline"
        if name == "token":
            return {"access_token": "worker-session-token"}
        assert headers["Authorization"] == "Bearer worker-session-token"
        if name in self.rejections:
            raise self.rejections[name]
        if name == "claim_product_submission_extraction_jobs":
            return self.claim_rows
        if name == "product_submission_extraction_budget_state":
            # The worker-facing shape, as the granted function returns it.
            return [{
                "month_key": "2026-09",
                "spent_microcents": 0,
                "monthly_cap_microcents": 100000,
                "remaining_microcents": 5000,
            }]
        if name == "reserve_product_submission_extraction_budget":
            return True
        return None

    def get_bytes(self, url, *, headers, timeout, max_bytes):
        self.fetched.append(url)
        assert timeout > 0
        assert max_bytes > 0
        return self.photo_bytes


def _queue(tmp_path: Path, transport: _Transport) -> SupabaseExtractionQueue:
    return SupabaseExtractionQueue(
        WorkerCredentials.from_environment(_ENV),
        transport=transport,
        workspace=tmp_path,
    )


def test_the_worker_signs_in_as_itself() -> None:
    credentials = WorkerCredentials.from_environment(_ENV)

    assert credentials.email == "worker@example.test"
    assert credentials.anon_key == "sb_publishable_fixture"


def test_a_service_key_in_the_environment_is_refused() -> None:
    # A runner that can reach the service role is one edit away from using it,
    # and the service role can read every user's photos.
    for key in ("SUPABASE_SECRET_KEY", "SUPABASE_SERVICE_ROLE_KEY"):
        with pytest.raises(QueueConfigurationError) as error:
            WorkerCredentials.from_environment({**_ENV, key: "sb_secret_value"})
        assert key in str(error.value)


def test_admin_key_cannot_hide_in_public_slot_or_opt_out():
    with pytest.raises(QueueConfigurationError):
        WorkerCredentials.from_environment({**_ENV, "SUPABASE_PUBLISHABLE_KEY": "sb_secret_value"})
    with pytest.raises(QueueConfigurationError):
        WorkerCredentials.from_environment({**_ENV, "SUPABASE_SERVICE_ROLE_KEY": "secret",
                                            "EXTRACTION_WORKER_ALLOW_ADMIN_ENV": "1"})


@pytest.mark.parametrize("url", ["http://remote.test", "https://user:pass@example.test", "https://example.test/private"])
def test_worker_credentials_are_not_sent_to_unsafe_endpoints(url):
    with pytest.raises(QueueConfigurationError):
        WorkerCredentials.from_environment({**_ENV, "SUPABASE_URL": url})


def test_photo_id_is_validated_before_any_fetch_or_write(tmp_path):
    row = _claim_row(evidence_manifest={"../../escaped": _DIGEST},
                     evidence_object_paths={"../../escaped": "owner/photo"})
    transport = _Transport(claim_rows=[row])
    with pytest.raises(ExtractionError):
        _queue(tmp_path, transport).claim(1)
    assert transport.fetched == []


def test_non_boolean_budget_ack_is_not_permission(tmp_path):
    class Bad(_Transport):
        def post_json(self, url, **kwargs):
            if url.endswith("reserve_product_submission_extraction_budget"):
                return "false"
            return super().post_json(url, **kwargs)
    with pytest.raises(Exception):
        _queue(tmp_path, Bad()).reserve("job", 1)


def test_missing_worker_credentials_name_what_is_missing() -> None:
    with pytest.raises(QueueConfigurationError) as error:
        WorkerCredentials.from_environment({"SUPABASE_URL": "https://example.test"})

    assert "EXTRACTION_WORKER_EMAIL" in str(error.value)


def test_a_claim_builds_the_job_from_the_queue_alone(tmp_path: Path) -> None:
    transport = _Transport()
    queue = _queue(tmp_path, transport)

    jobs = queue.claim(1)

    assert len(jobs) == 1
    job = jobs[0]
    assert job.fencing_token == 3
    assert job.bundle.snapshot == {_PHOTO: _DIGEST}
    # The configuration is the one pinned at enqueue, never a local default.
    assert job.configuration.model == "gemma4"
    assert job.configuration.retention_policy_version == "local-only-v1"
    assert transport.fetched == []  # claim never downloads outside the heartbeat
    queue.read_evidence(job.bundle.photos[0])
    assert transport.fetched == [
        f"https://example.test/storage/v1/object/product-submission-photos/owner/{_SUBMISSION}/{_PHOTO}"
    ]
    queue.close()


def test_a_lease_whose_hashes_and_paths_disagree_is_refused(tmp_path: Path) -> None:
    row = _claim_row(evidence_object_paths={_OTHER: f"owner/{_SUBMISSION}/{_OTHER}"})
    queue = _queue(tmp_path, _Transport(claim_rows=[row]))

    with pytest.raises(ExtractionError) as error:
        queue.claim(1)

    assert error.value.code == "unsupported_evidence"


def test_a_traversing_evidence_path_is_never_fetched(tmp_path: Path) -> None:
    row = _claim_row(evidence_object_paths={_PHOTO: "../../etc/passwd"})
    transport = _Transport(claim_rows=[row])
    queue = _queue(tmp_path, transport)

    with pytest.raises(ExtractionError):
        job = queue.claim(1)[0]
        queue.read_evidence(job.bundle.photos[0])

    assert transport.fetched == []


def test_leased_photos_land_in_a_private_directory_and_are_removed(tmp_path: Path) -> None:
    transport = _Transport()
    queue = _queue(tmp_path, transport)
    job = queue.claim(1)[0]
    queue.read_evidence(job.bundle.photos[0])
    stored = Path(job.bundle.photos[0].path)

    assert stored.exists()
    assert stored.read_bytes() == _IMAGE
    # Another person's photographs, so owner-only on disk.
    assert oct(stored.stat().st_mode)[-3:] == "600"
    assert oct(stored.parent.stat().st_mode)[-3:] == "700"

    queue.complete(job.job_id, job.fencing_token, "failed", error_code="model_failure")

    assert not stored.exists()
    assert not stored.parent.exists()


def test_evidence_is_removed_even_when_completion_fails(tmp_path: Path) -> None:
    transport = _Transport()
    queue = _queue(tmp_path, transport)
    job = queue.claim(1)[0]
    queue.read_evidence(job.bundle.photos[0])
    stored = Path(job.bundle.photos[0].path)
    transport.rejections["complete_product_submission_extraction_job"] = RuntimeError(
        "network gone"
    )

    with pytest.raises(RuntimeError):
        queue.complete(job.job_id, job.fencing_token, "failed", error_code="x")

    assert not stored.exists()


def test_lost_completion_ack_is_reconciled_without_second_write(tmp_path):
    class LostAck(_Transport):
        def post_json(self, url, **kwargs):
            if url.endswith("complete_product_submission_extraction_job"):
                self.calls.append("complete_product_submission_extraction_job")
                raise TimeoutError()
            if url.endswith("product_submission_extraction_attempt_outcome"):
                return [{"attempt_is_current": True, "job_state": "review_ready",
                         "draft_recorded": True, "result_extraction_version": 2,
                         "reservation_open": False, "reserved_microcents": 1,
                         "settled_microcents": 0}]
            return super().post_json(url, **kwargs)
    transport = LostAck()
    queue = _queue(tmp_path, transport)
    queue.complete(_claim_row()["job_id"], 3, "review_ready", cost_microcents=0)
    assert transport.calls.count("complete_product_submission_extraction_job") == 1


def test_live_attempt_is_not_proof_of_completion(tmp_path):
    transport = _Transport()
    transport.rejections["complete_product_submission_extraction_job"] = TimeoutError()
    with pytest.raises(Exception):
        _queue(tmp_path, transport).complete(_claim_row()["job_id"], 3, "review_ready")


def test_uncertain_completion_leaves_a_private_reconciliation_receipt(tmp_path):
    journal = tmp_path / "attempts.jsonl"
    transport = _Transport()
    transport.rejections["complete_product_submission_extraction_job"] = TimeoutError()
    queue = SupabaseExtractionQueue(WorkerCredentials.from_environment(_ENV),
                                    transport=transport, workspace=tmp_path,
                                    attempt_journal=journal)
    with pytest.raises(Exception):
        queue.complete(_claim_row()["job_id"], 3, "review_ready")
    import json
    record = json.loads(journal.read_text().splitlines()[0])
    assert record["job_id"] == _claim_row()["job_id"] and record["fencing_token"] == 3
    assert set(record) == {"job_id", "fencing_token", "outcome", "cost_microcents", "event"}
    assert oct(journal.stat().st_mode)[-3:] == "600"


def test_a_lost_lease_is_reported_as_such(tmp_path: Path) -> None:
    from submission_review.extraction.queue_client import _RpcRejected

    transport = _Transport()
    queue = _queue(tmp_path, transport)
    job = queue.claim(1)[0]
    transport.rejections["heartbeat_product_submission_extraction_job"] = _RpcRejected(
        "rejected", code="lease_lost"
    )

    with pytest.raises(LeaseLostError):
        queue.heartbeat(job.job_id, job.fencing_token)
    queue.close()


def test_the_allowance_is_read_from_the_database(tmp_path: Path) -> None:
    queue = _queue(tmp_path, _Transport())

    assert queue.remaining_microcents() == 5000


def test_a_database_error_message_is_never_passed_outward(tmp_path: Path) -> None:
    from submission_review.extraction.queue_client import _decode

    class _Response:
        status_code = 400
        content = b'{"code":"22023","message":"row (secret@example.com) violated"}'

    with pytest.raises(Exception) as error:
        _decode(_Response())

    assert "secret@example.com" not in str(error.value)
    assert error.value.code == "22023"


def test_an_oversized_response_is_refused(tmp_path: Path) -> None:
    from submission_review.extraction.queue_client import MAX_RESPONSE_BYTES, _decode

    class _Response:
        status_code = 200
        content = b"x" * (MAX_RESPONSE_BYTES + 1)

    with pytest.raises(Exception):
        _decode(_Response())


def _reading_adapter(barcode: str | None):
    """A fake that reports reading a barcode, so the checks have something to
    compare. The shared FakeAdapter deliberately reads nothing."""
    from submission_review.extraction.adapters.fake_adapter import FakeAdapter

    class ReadingAdapter(FakeAdapter):
        def extract(self, bundle, config):
            result = super().extract(bundle, config)
            if barcode is not None:
                photo = bundle.photos[0]
                result.draft["identity"]["barcode_digits_seen"] = {
                    "value": barcode, "status": "read", "confidence": 0.9,
                    # A read field must name the image it was read off; the
                    # envelope refuses a reading with no source.
                    "sources": [{
                        "input_id": photo.input_id,
                        "photo_id": photo.photo_id,
                        "supporting_text": barcode,
                    }],
                }
            return result

    return ReadingAdapter()


_FAKE_CONFIG = {**_CONFIG, "provider": "fake", "model": "fake-1"}


def _extract_from_claim(tmp_path, row, adapter):
    """Drive the production path: claim, prepare, extract."""
    from submission_review.extraction.extractor import LabelDraftExtractor
    from submission_review.extraction.photo_prep import prepare_bundle

    queue = _queue(tmp_path, _Transport(claim_rows=[row]))
    job = queue.claim(1)[0]
    prepared = prepare_bundle(job.bundle, reader=queue.read_evidence)
    return job, LabelDraftExtractor(adapter).extract(
        prepared,
        job.configuration,
        submission_gtin=job.bundle.submission_gtin,
        catalog_match=job.bundle.catalog_match,
    )


def test_a_claim_carries_the_identity_context_onto_the_bundle(tmp_path) -> None:
    queue = _queue(tmp_path, _Transport(claim_rows=[_claim_row(
        submission_gtin="00012345678905",
        catalog_match={"outcome": "catalog_match", "matched_dsld_id": "12345"},
    )]))

    job = queue.claim(1)[0]

    # The worker reads nothing but its lease, so this is the only route in.
    assert job.bundle.submission_gtin == "00012345678905"
    assert job.bundle.catalog_match["matched_dsld_id"] == "12345"


def test_a_barcode_mismatch_is_found_from_a_real_claim(tmp_path) -> None:
    _, result = _extract_from_claim(
        tmp_path,
        _claim_row(submission_gtin="00012345678905", configuration=_FAKE_CONFIG),
        _reading_adapter("012345678929"),
    )

    codes = {finding["code"] for finding in result.draft["discrepancies"]}
    assert "barcode_mismatch" in codes


def test_the_same_barcode_in_another_width_is_not_a_mismatch(tmp_path) -> None:
    _, result = _extract_from_claim(
        tmp_path,
        _claim_row(submission_gtin="00012345678905", configuration=_FAKE_CONFIG),
        _reading_adapter("012345678905"),
    )

    codes = {finding["code"] for finding in result.draft["discrepancies"]}
    # GTIN-12 and GTIN-14 are widths of one identity; the claim hands over the
    # canonical form precisely so the worker never has to decide that itself.
    assert "barcode_mismatch" not in codes


def test_a_recorded_catalog_hit_reaches_the_findings_from_a_real_claim(tmp_path) -> None:
    _, result = _extract_from_claim(
        tmp_path,
        _claim_row(
            submission_gtin="00012345678905",
            catalog_match={"outcome": "catalog_match", "matched_dsld_id": "12345"},
            configuration=_FAKE_CONFIG,
        ),
        _reading_adapter(None),
    )

    findings = [f for f in result.draft["discrepancies"] if f["code"] == "catalog_candidate"]
    assert findings, "a recorded catalog hit produced no candidate finding"
    # Still a candidate to compare against, never a disposition, and the
    # catalog identity is not named in what the reviewer is shown.
    assert findings[0]["severity"] == "info"
    assert "12345" not in findings[0]["detail"]


def test_a_claim_without_context_still_extracts(tmp_path) -> None:
    _, result = _extract_from_claim(
        tmp_path, _claim_row(configuration=_FAKE_CONFIG),
        _reading_adapter("012345678929"),
    )

    codes = {finding["code"] for finding in result.draft["discrepancies"]}
    # Nothing to compare against is not a finding. An older database that does
    # not return the context must not make every submission look wrong.
    assert "barcode_mismatch" not in codes
