"""Drain the extraction queue: claim, prepare, extract, record, complete.

The worker is deliberately small and deliberately dumb about authority. It
cannot approve, reject, publish or mint anything; the database decides what it
may claim and the reviewer decides what any of it means. Its whole job is to
turn leased evidence into a draft or a typed failure, inside limits it is told.

Budgets and the on/off switch live in the database, not here. A runner that
forgets a flag must not be able to start spending.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

from .extractor import (
    EvidenceBundle,
    ExtractionConfig,
    ExtractionError,
    LabelDraftExtractor,
    PREPARATION_VERSION,
)
from .photo_prep import prepare_bundle

#: Failures worth another attempt versus ones that will fail again identically.
RETRYABLE_CODES = frozenset({"provider_unavailable", "budget_exhausted"})


@dataclass(frozen=True)
class LeasedJob:
    job_id: str
    fencing_token: int
    bundle: EvidenceBundle
    configuration: ExtractionConfig
    heartbeat_seconds: float = 30.0


class LeaseLostError(RuntimeError):
    """The queue confirmed this token no longer owns its lease."""


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

    def reserve(self, job_id: str, fencing_token: int) -> bool: ...

    def complete(
        self,
        job_id: str,
        fencing_token: int,
        outcome: str,
        *,
        draft: dict[str, Any] | None = None,
        usage: dict[str, Any] | None = None,
        error_code: str | None = None,
        cost_microcents: int | None = None,
    ) -> None: ...

    def remaining_microcents(self) -> int: ...


def drain(
    queue: ExtractionQueue,
    extractor: LabelDraftExtractor,
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
        try:
            remaining = queue.remaining_microcents()
        except Exception:
            report.stopped_because = "queue_unavailable"
            break
        if remaining <= 0:
            # Stop before claiming, so a job is not leased only to be failed.
            report.stopped_because = "budget_exhausted"
            break
        if limits.max_microcents and report.spent_microcents >= limits.max_microcents:
            report.stopped_because = "run_budget_reached"
            break

        try:
            jobs = queue.claim(1)
        except Exception:
            report.stopped_because = "queue_unavailable"
            break
        if not jobs:
            report.stopped_because = "queue_empty"
            break
        job = jobs[0]
        report.claimed += 1
        if limits.max_microcents and job.configuration.max_cost_microcents > limits.max_microcents - report.spent_microcents:
            _record_failure(queue, job, ExtractionError("budget_exhausted"), report, cost=0, admission_hold=True)
            if report.stopped_because == "queue_empty":
                report.stopped_because = "run_budget_reached"
            break
        _work_one(queue, extractor, job, report, reader=reader)
        if report.stopped_because in {"completion_unknown", "queue_unavailable", "budget_exhausted", "cost_unknown"}:
            break

    else:
        report.stopped_because = "job_limit"
    return report


def _work_one(
    queue: ExtractionQueue,
    extractor: LabelDraftExtractor,
    job: LeasedJob,
    report: DrainReport,
    *,
    reader=None,
) -> None:
    config = job.configuration
    called = False
    result = None
    try:
        if config.prep_config_version != PREPARATION_VERSION:
            raise ExtractionError("preparation_failed", "unsupported preparation version")
        queue.heartbeat(job.job_id, job.fencing_token)
        with _LeaseHeartbeat(queue, job) as heartbeat:
            prepared = prepare_bundle(
                job.bundle, reader=reader or getattr(queue, "read_evidence", None))
            if heartbeat.error is not None:
                raise heartbeat.error
            if not queue.reserve(job.job_id, job.fencing_token):
                _record_failure(queue, job, ExtractionError("budget_exhausted"), report, cost=0, admission_hold=True)
                if report.stopped_because == "queue_empty":
                    report.stopped_because = "budget_exhausted"
                return
            called = True
            result = extractor.extract(
                prepared,
                config,
                submission_gtin=job.bundle.submission_gtin,
                catalog_match=job.bundle.catalog_match,
            )
        if heartbeat.error is not None:
            raise heartbeat.error
        queue.heartbeat(job.job_id, job.fencing_token)
    except LeaseLostError:
        if result is not None:
            report.spent_microcents += result.usage.microcents
        report.failure_codes["lease_lost"] = report.failure_codes.get("lease_lost", 0) + 1
        return
    except ExtractionError as error:
        cost = error.usage.microcents if error.usage is not None else (None if called else 0)
        _record_failure(queue, job, error, report, cost=cost)
        if cost is None and report.stopped_because == "queue_empty":
            # The DB retains this attempt's reservation. Stop this run too:
            # unknown spend cannot be treated as zero against a run cap.
            report.stopped_because = "cost_unknown"
        return
    except Exception:  # noqa: BLE001 - a worker never dies on one job
        if result is not None:
            report.spent_microcents += result.usage.microcents
        report.stopped_because = "queue_unavailable"
        return

    draft = dict(result.draft)
    usage = result.usage.as_payload()
    cost = int(usage.get("cost_microcents") or 0)
    report.spent_microcents += cost
    try:
        queue.complete(
            job.job_id,
            job.fencing_token,
            "review_ready",
            draft=draft,
            usage=usage,
            cost_microcents=cost,
        )
    except LeaseLostError:
        # A lost lease is not a drafting failure. Leave the job to whoever
        # holds it now rather than overwriting their result.
        report.failure_codes["lease_lost"] = report.failure_codes.get("lease_lost", 0) + 1
        return
    except Exception:
        # A timeout may mean the transaction committed. Never issue a second,
        # contradictory failure completion or spend on more jobs until checked.
        report.failure_codes["completion_unknown"] = report.failure_codes.get("completion_unknown", 0) + 1
        report.stopped_because = "completion_unknown"
        return
    report.drafted += 1


def _record_failure(
    queue: ExtractionQueue,
    job: LeasedJob,
    error: ExtractionError,
    report: DrainReport,
    *,
    cost: int | None = None,
    admission_hold: bool = False,
) -> None:
    retryable = error.code in RETRYABLE_CODES
    outcome = "retryable_error" if retryable else "failed"
    if admission_hold:
        outcome = "budget_hold"
    elif error.code in {"unreadable_evidence", "unsupported_evidence"}:
        outcome = "needs_evidence"
    report.failure_codes[error.code] = report.failure_codes.get(error.code, 0) + 1
    report.spent_microcents += cost or 0
    try:
        queue.complete(job.job_id, job.fencing_token, outcome, error_code=error.code, cost_microcents=cost)
    except LeaseLostError:
        report.failure_codes["lease_lost"] = report.failure_codes.get("lease_lost", 0) + 1
        return
    except Exception:
        report.stopped_because = "completion_unknown"
        report.failure_codes["completion_unknown"] = report.failure_codes.get("completion_unknown", 0) + 1
        return
    if retryable:
        report.retryable += 1
    else:
        report.failed += 1


class _LeaseHeartbeat:
    """Renew during a blocking model call; surface loss before completion."""

    def __init__(self, queue: ExtractionQueue, job: LeasedJob):
        self.queue, self.job = queue, job
        self.stop = threading.Event()
        self.error: Exception | None = None

    def __enter__(self):
        if self.job.heartbeat_seconds <= 0:
            raise ValueError("heartbeat interval must be positive")
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        return self

    def _run(self):
        while not self.stop.wait(self.job.heartbeat_seconds):
            try:
                self.queue.heartbeat(self.job.job_id, self.job.fencing_token)
            except Exception as error:
                self.error = error
                return

    def __exit__(self, *_):
        self.stop.set()
        self.thread.join(timeout=1.0)
        if self.thread.is_alive():
            self.error = RuntimeError("heartbeat acknowledgement unknown")
