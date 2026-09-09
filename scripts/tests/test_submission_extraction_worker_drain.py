"""Draining the extraction queue, with a fake queue and the fake adapter.

No provider, no database, no photos on disk. What is being proven is that the
worker stays inside its limits, never dies on one job, never overwrites a lease
it has lost, and never puts a user's identifiers in its output.
"""
from __future__ import annotations

import hashlib
import io

import pytest
from PIL import Image

from submission_review.extraction.adapters.fake_adapter import FakeAdapter
from submission_review.extraction.extractor import (
    EvidenceBundle,
    EvidencePhoto,
    ExtractionConfig,
    LabelDraftExtractor,
)
from submission_review.extraction.worker import DrainLimits, LeasedJob, drain

_SUBMISSION = "018f4c79-7c7e-4c70-9d62-7fc3b9ce6a11"
_PHOTO = "10000000-0000-0000-0000-000000000001"


def _jpeg() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (48, 32), (90, 140, 190)).save(buffer, format="JPEG")
    return buffer.getvalue()


_IMAGE = _jpeg()
_DIGEST = hashlib.sha256(_IMAGE).hexdigest()


def _job(index: int) -> LeasedJob:
    return LeasedJob(
        job_id=f"job-{index}",
        fencing_token=index + 1,
        bundle=EvidenceBundle(
            submission_id=_SUBMISSION,
            evidence_revision=1,
            photos=(EvidencePhoto(photo_id=_PHOTO, sha256=_DIGEST),),
        ),
    )


def _config(**overrides) -> ExtractionConfig:
    base = {
        "provider": "fake",
        "model": "fake-1",
        "model_digest": "c" * 64,
        "prompt_version": "p1",
        "retention_policy_version": "local-only-v1",
    }
    base.update(overrides)
    return ExtractionConfig(**base)


def _reader(photo):
    return _IMAGE


class _Queue:
    def __init__(self, jobs: int = 1, remaining: int = 1_000, cost: int = 0):
        self._pending = [_job(i) for i in range(jobs)]
        self.remaining = remaining
        self.cost = cost
        self.completed: list[dict] = []
        self.heartbeats: list[str] = []
        self.complete_raises = False

    def claim(self, limit: int):
        return [self._pending.pop(0)] if self._pending else []

    def heartbeat(self, job_id, fencing_token):
        self.heartbeats.append(job_id)

    def complete(self, job_id, fencing_token, outcome, *, draft=None, usage=None,
                 error_code=None, cost_microcents=0):
        if self.complete_raises:
            raise RuntimeError("lease is not held")
        self.completed.append(
            {
                "job_id": job_id,
                "outcome": outcome,
                "error_code": error_code,
                "cost": cost_microcents,
                "draft": draft,
            }
        )

    def remaining_microcents(self) -> int:
        return self.remaining


def _extractor(**kwargs) -> LabelDraftExtractor:
    return LabelDraftExtractor(FakeAdapter(**kwargs))


def test_a_drafted_job_is_completed_review_ready_with_what_was_sent() -> None:
    queue = _Queue(jobs=1)

    report = drain(queue, _extractor(), _config(), reader=_reader)

    assert report.drafted == 1 and report.failed == 0
    done = queue.completed[0]
    assert done["outcome"] == "review_ready"
    # The recorded sent_inputs describe the prepared bytes, not the stored
    # ones, because preparation re-encodes.
    sent = done["draft"]["sent_inputs"][0]
    assert sent["original_sha256"] == _DIGEST
    assert sent["sent_sha256"] != _DIGEST
    assert queue.heartbeats == ["job-0"]


def test_the_worker_stops_before_claiming_when_the_budget_is_gone() -> None:
    queue = _Queue(jobs=3, remaining=0)

    report = drain(queue, _extractor(), _config(), reader=_reader)

    # Not "claim then fail": a job must not be leased only to be abandoned.
    assert report.claimed == 0
    assert report.stopped_because == "budget_exhausted"
    assert queue.completed == []


def test_the_job_limit_is_respected() -> None:
    queue = _Queue(jobs=5)

    report = drain(
        queue, _extractor(), _config(), DrainLimits(max_jobs=2), reader=_reader
    )

    assert report.claimed == 2 and report.stopped_because == "job_limit"


def test_the_time_limit_stops_the_run() -> None:
    queue = _Queue(jobs=5)
    ticks = iter([0.0, 0.0, 99.0, 99.0, 99.0])

    report = drain(
        queue,
        _extractor(),
        _config(),
        DrainLimits(max_jobs=5, max_seconds=10),
        reader=_reader,
        clock=lambda: next(ticks),
    )

    assert report.stopped_because == "time_limit"
    assert report.claimed <= 1


def test_a_provider_outage_is_retryable_and_a_bad_draft_is_not() -> None:
    queue = _Queue(jobs=1)
    report = drain(
        queue, _extractor(fail_with="provider_unavailable"), _config(), reader=_reader
    )
    assert report.retryable == 1 and report.failed == 0
    assert queue.completed[0]["outcome"] == "retryable_error"

    queue = _Queue(jobs=1)
    report = drain(
        queue, _extractor(fail_with="unreadable_evidence"), _config(), reader=_reader
    )
    assert report.failed == 1 and report.retryable == 0
    assert queue.completed[0]["outcome"] == "failed"


def test_one_bad_job_never_stops_the_run() -> None:
    queue = _Queue(jobs=2)

    def explode(photo):
        raise MemoryError("boom")

    report = drain(queue, _extractor(), _config(), reader=explode)

    assert report.claimed == 2 and report.drafted == 0
    assert report.failure_codes.get("preparation_failed") == 2


def test_a_lost_lease_is_not_reported_as_a_draft() -> None:
    queue = _Queue(jobs=1)
    queue.complete_raises = True

    report = drain(queue, _extractor(), _config(), reader=_reader)

    # Losing the lease means another worker owns the answer now. Do not claim
    # a draft that was never recorded.
    assert report.drafted == 0
    assert report.failure_codes.get("lease_lost") == 1


def test_the_summary_never_carries_a_submission_or_photo_identifier() -> None:
    queue = _Queue(jobs=1)

    summary = drain(queue, _extractor(), _config(), reader=_reader).as_summary()

    rendered = repr(summary)
    assert _SUBMISSION not in rendered
    assert _PHOTO not in rendered
    assert set(summary) == {
        "claimed",
        "drafted",
        "failed",
        "retryable",
        "spent_microcents",
        "failure_codes",
        "stopped_because",
    }


def test_an_adapter_without_retention_terms_never_reaches_the_queue_work() -> None:
    queue = _Queue(jobs=1)

    report = drain(
        queue, _extractor(), _config(retention_policy_version=None), reader=_reader
    )

    assert report.drafted == 0
    assert report.failure_codes.get("provider_unavailable") == 1
