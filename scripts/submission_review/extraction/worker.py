"""Drain the extraction queue: claim, prepare, extract, record, complete.

The worker is deliberately small and deliberately dumb about authority. It
cannot approve, reject, publish or mint anything; the database decides what it
may claim and the reviewer decides what any of it means. Its whole job is to
turn leased evidence into a draft or a typed failure, inside limits it is told.

Budgets and the on/off switch live in the database, not here. A runner that
forgets a flag must not be able to start spending.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Protocol

from .extractor import (
    EvidenceBundle,
    ExtractionConfig,
    ExtractionError,
    LabelDraftExtractor,
)
from .photo_prep import prepare_bundle

#: Failures worth another attempt versus ones that will fail again identically.
RETRYABLE_CODES = frozenset({"provider_unavailable", "budget_exhausted"})


@dataclass(frozen=True)
class LeasedJob:
    job_id: str
    fencing_token: int
    bundle: EvidenceBundle


@dataclass
class DrainLimits:
    """What a single run is allowed to consume."""

    max_jobs: int = 10
    max_seconds: float = 600.0
    max_microcents: int = 0  # 0 means "whatever the database still allows"


@dataclass
class DrainReport:
    claimed: int = 0
    drafted: int = 0
    failed: int = 0
    retryable: int = 0
    spent_microcents: int = 0
    #: Failure codes and how often each occurred. No submission ids, no photo
    #: paths, no user ids: a runner's output is read in a terminal and pasted
    #: into chat, and none of that is anyone else's business.
    failure_codes: dict[str, int] = field(default_factory=dict)
    stopped_because: str = "queue_empty"

    def as_summary(self) -> dict[str, Any]:
        return {
            "claimed": self.claimed,
            "drafted": self.drafted,
            "failed": self.failed,
            "retryable": self.retryable,
            "spent_microcents": self.spent_microcents,
            "failure_codes": dict(sorted(self.failure_codes.items())),
            "stopped_because": self.stopped_because,
        }


class ExtractionQueue(Protocol):
    """The database operations a worker is allowed to perform."""

    def claim(self, limit: int) -> list[LeasedJob]: ...

    def heartbeat(self, job_id: str, fencing_token: int) -> None: ...

    def complete(
        self,
        job_id: str,
        fencing_token: int,
        outcome: str,
        *,
        draft: dict[str, Any] | None = None,
        usage: dict[str, Any] | None = None,
        error_code: str | None = None,
        cost_microcents: int = 0,
    ) -> None: ...

    def remaining_microcents(self) -> int: ...


def drain(
    queue: ExtractionQueue,
    extractor: LabelDraftExtractor,
    config: ExtractionConfig,
    limits: DrainLimits | None = None,
    *,
    reader=None,
    clock=time.monotonic,
) -> DrainReport:
    """Work the queue until a limit is reached or nothing is left."""
    limits = limits or DrainLimits()
    report = DrainReport()
    started = clock()

    while report.claimed < limits.max_jobs:
        if clock() - started >= limits.max_seconds:
            report.stopped_because = "time_limit"
            break
        remaining = queue.remaining_microcents()
        if remaining <= 0:
            # Stop before claiming, so a job is not leased only to be failed.
            report.stopped_because = "budget_exhausted"
            break
        if limits.max_microcents and report.spent_microcents >= limits.max_microcents:
            report.stopped_because = "run_budget_reached"
            break

        jobs = queue.claim(1)
        if not jobs:
            report.stopped_because = "queue_empty"
            break
        job = jobs[0]
        report.claimed += 1
        _work_one(queue, extractor, config, job, report, reader=reader)

    else:
        report.stopped_because = "job_limit"
    return report


def _work_one(
    queue: ExtractionQueue,
    extractor: LabelDraftExtractor,
    config: ExtractionConfig,
    job: LeasedJob,
    report: DrainReport,
    *,
    reader=None,
) -> None:
    try:
        prepared = prepare_bundle(job.bundle, reader=reader)
        # Preparation can take a while on a slow disk or a large set; tell the
        # database the lease is still wanted before the provider call.
        queue.heartbeat(job.job_id, job.fencing_token)
        result = extractor.extract(job.bundle, config)
    except ExtractionError as error:
        _record_failure(queue, job, error, report)
        return
    except Exception:  # noqa: BLE001 - a worker never dies on one job
        _record_failure(
            queue,
            job,
            ExtractionError("model_failure", "extraction failed unexpectedly"),
            report,
        )
        return

    draft = dict(result.draft)
    # The draft names exactly what was transmitted, which is not always what
    # was stored: preparation re-encodes.
    draft["sent_inputs"] = [entry.as_sent_input() for entry in prepared]
    usage = result.usage.as_payload()
    cost = int(usage.get("cost_microcents") or 0)
    try:
        queue.complete(
            job.job_id,
            job.fencing_token,
            "review_ready",
            draft=draft,
            usage=usage,
            cost_microcents=cost,
        )
    except Exception:  # noqa: BLE001
        # A lost lease is not a drafting failure. Leave the job to whoever
        # holds it now rather than overwriting their result.
        report.failure_codes["lease_lost"] = report.failure_codes.get("lease_lost", 0) + 1
        return
    report.drafted += 1
    report.spent_microcents += cost


def _record_failure(
    queue: ExtractionQueue,
    job: LeasedJob,
    error: ExtractionError,
    report: DrainReport,
) -> None:
    retryable = error.code in RETRYABLE_CODES
    outcome = "retryable_error" if retryable else "failed"
    report.failure_codes[error.code] = report.failure_codes.get(error.code, 0) + 1
    if retryable:
        report.retryable += 1
    else:
        report.failed += 1
    try:
        queue.complete(job.job_id, job.fencing_token, outcome, error_code=error.code)
    except Exception:  # noqa: BLE001
        report.failure_codes["lease_lost"] = report.failure_codes.get("lease_lost", 0) + 1
