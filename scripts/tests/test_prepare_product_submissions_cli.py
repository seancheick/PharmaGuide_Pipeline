"""The runner: bounded, honest about outcomes, and silent about people.

One command serves manual and scheduled use, so what runs unattended is what
was tested. These cover the parts a scheduler and an operator depend on.
"""
from __future__ import annotations

import json

import pytest

import prepare_product_submissions as runner
from submission_review.extraction.queue_client import QueueConfigurationError
from submission_review.extraction.worker import DrainReport


class _Queue:
    def __init__(self, remaining: int = 100):
        self.remaining = remaining
        self.closed = False

    def remaining_microcents(self) -> int:
        return self.remaining

    def close(self) -> None:
        self.closed = True


def _args(argv):
    return runner.build_parser().parse_args(argv)


def test_status_reports_the_allowance_and_releases_evidence(monkeypatch, capsys) -> None:
    queue = _Queue(remaining=4200)
    monkeypatch.setattr(runner, "_queue", lambda args: queue)

    assert runner.main(["status"]) == 0

    assert json.loads(capsys.readouterr().out)["remaining_microcents"] == 4200
    assert queue.closed


def test_a_run_returns_nonzero_when_it_stopped_on_a_limit(monkeypatch, capsys) -> None:
    queue = _Queue()
    monkeypatch.setattr(runner, "_queue", lambda args: queue)
    monkeypatch.setattr(
        runner,
        "drain",
        lambda *a, **k: DrainReport(claimed=1, stopped_because="budget_exhausted"),
    )

    # A scheduler must be able to see an unclean run without parsing prose.
    assert runner.main(["run"]) == 2
    assert queue.closed


def test_a_clean_run_returns_zero(monkeypatch) -> None:
    monkeypatch.setattr(runner, "_queue", lambda args: _Queue())
    monkeypatch.setattr(
        runner, "drain", lambda *a, **k: DrainReport(drafted=2, stopped_because="queue_empty")
    )

    assert runner.main(["run"]) == 0


def test_evidence_is_released_even_when_a_run_raises(monkeypatch) -> None:
    queue = _Queue()
    monkeypatch.setattr(runner, "_queue", lambda args: queue)

    def explode(*a, **k):
        raise RuntimeError("drain blew up")

    monkeypatch.setattr(runner, "drain", explode)

    with pytest.raises(RuntimeError):
        runner.main(["run"])

    # Another person's photographs must not outlive the run that fetched them.
    assert queue.closed


def test_the_run_summary_carries_no_identifiers(monkeypatch, capsys) -> None:
    monkeypatch.setattr(runner, "_queue", lambda args: _Queue())
    monkeypatch.setattr(
        runner,
        "drain",
        lambda *a, **k: DrainReport(
            claimed=3, drafted=1, failed=2, failure_codes={"model_failure": 2}
        ),
    )

    runner.main(["run"])

    printed = json.loads(capsys.readouterr().out)
    assert set(printed) == {
        "claimed",
        "drafted",
        "failed",
        "retryable",
        "spent_microcents",
        "failure_codes",
        "stopped_because",
    }


def test_missing_worker_credentials_fail_before_any_work(monkeypatch, capsys) -> None:
    def refuse(args):
        raise QueueConfigurationError("missing EXTRACTION_WORKER_EMAIL")

    monkeypatch.setattr(runner, "_queue", refuse)

    assert runner.main(["run"]) == 1
    assert "EXTRACTION_WORKER_EMAIL" in capsys.readouterr().err


def test_timeouts_must_be_positive() -> None:
    assert runner.main(["--call-timeout", "0", "status"]) == 2
    assert runner.main(["--request-timeout", "-1", "status"]) == 2


def test_the_default_mode_calls_no_model() -> None:
    args = _args(["run"])

    adapter = runner._adapter(args)

    assert args.mode == "fake"
    assert adapter.__class__.__name__ == "FakeAdapter"


def test_local_mode_carries_a_real_per_call_deadline() -> None:
    args = _args(["--mode", "local", "--call-timeout", "45", "run"])

    adapter = runner._adapter(args)

    # The drain's own budget is an admission window; only the transport can
    # interrupt a call already in flight.
    assert adapter._timeout == 45
    assert adapter._endpoint.startswith("http://127.0.0.1")


def test_max_seconds_is_documented_as_an_admission_window() -> None:
    # The distinction matters operationally, so it belongs in --help rather
    # than in folklore: this window stops new jobs starting, it cannot cancel
    # a model call already in flight.
    import contextlib
    import io

    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer), pytest.raises(SystemExit):
        runner.main(["run", "--help"])

    assert "admission window" in buffer.getvalue()
