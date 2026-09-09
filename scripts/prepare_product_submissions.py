#!/usr/bin/env python3
"""Run the local extraction worker over the submission queue.

One runner, used both by hand and by any later schedule. There is deliberately
no second scheduled implementation: a cron entry calls this with the same flags
a person would type, so what runs unattended is what was tested.

    scripts/prepare_product_submissions.py preflight --mode local
    scripts/prepare_product_submissions.py status
    scripts/prepare_product_submissions.py run --mode local --max-jobs 5

What this program will not do, by construction: pull a model, fall back to a
remote or paid provider, upload a photograph anywhere, approve or reject a
submission, or print a submission id, photo path or account. Extraction is
enabled in the database, not here; a runner that forgets a flag cannot start
spending.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from submission_review.extraction.adapters.fake_adapter import FakeAdapter  # noqa: E402
from submission_review.extraction.adapters.ollama_adapter import (  # noqa: E402
    DEFAULT_ENDPOINT,
    DEFAULT_TIMEOUT_SECONDS,
    OllamaAdapter,
)
from submission_review.extraction.extractor import (  # noqa: E402
    ExtractionError,
    LabelDraftExtractor,
)
from submission_review.extraction.queue_client import (  # noqa: E402
    QueueConfigurationError,
    SupabaseExtractionQueue,
    WorkerCredentials,
)
from submission_review.extraction.worker import DrainLimits, drain  # noqa: E402

MODES = ("fake", "local")


def _queue(args) -> SupabaseExtractionQueue:
    return SupabaseExtractionQueue(
        WorkerCredentials.from_environment(), timeout=args.request_timeout
    )


def _adapter(args):
    if args.mode == "local":
        # The per-call deadline lives on the transport, which is the only thing
        # that can actually interrupt a blocked read. The drain's own budget is
        # an admission window and cannot cancel a call already in flight.
        return OllamaAdapter(
            endpoint=args.endpoint, timeout=args.call_timeout
        )
    return FakeAdapter()


def command_preflight(args) -> int:
    """Check everything a run needs, and write nothing."""
    checks: list[tuple[str, bool, str]] = []
    try:
        WorkerCredentials.from_environment()
        checks.append(("worker account configured", True, ""))
    except QueueConfigurationError as error:
        checks.append(("worker account configured", False, str(error)))

    if args.mode == "local":
        try:
            _probe_local_model(args)
            checks.append(("pinned local model installed and vision-capable", True, ""))
        except ExtractionError as error:
            checks.append(
                ("pinned local model installed and vision-capable", False, error.detail)
            )
    else:
        checks.append(("fake adapter selected; no model needed", True, ""))

    ok = all(passed for _, passed, _ in checks)
    for name, passed, detail in checks:
        marker = "ok  " if passed else "FAIL"
        print(f"{marker} {name}" + (f" — {detail}" if detail else ""))
    print("\npreflight wrote nothing and called no provider.")
    return 0 if ok else 1


def _probe_local_model(args) -> None:
    from submission_review.extraction.extractor import ExtractionConfig

    if not args.model or not args.model_digest:
        raise ExtractionError(
            "provider_unavailable",
            "--model and --model-digest are required to check a local pin",
        )
    adapter = OllamaAdapter(endpoint=args.endpoint, timeout=args.call_timeout)
    adapter._verify_model(  # noqa: SLF001 - the check is the point of preflight
        ExtractionConfig(
            provider="ollama",
            model=args.model,
            model_digest=args.model_digest,
            prompt_version="preflight",
            retention_policy_version="local-only",
        )
    )


def command_status(args) -> int:
    """Report what the queue would allow, without claiming anything."""
    queue = _queue(args)
    try:
        remaining = queue.remaining_microcents()
    except Exception:
        print("the queue could not be reached", file=sys.stderr)
        return 1
    finally:
        queue.close()
    print(json.dumps({"remaining_microcents": remaining}, indent=2))
    return 0


def command_run(args) -> int:
    queue = _queue(args)
    extractor = LabelDraftExtractor(_adapter(args))
    limits = DrainLimits(
        max_jobs=args.max_jobs,
        max_seconds=args.max_seconds,
        max_microcents=args.max_microcents,
    )
    try:
        report = drain(queue, extractor, limits)
    finally:
        # Another person's photographs never outlive the run that fetched them.
        queue.close()
    print(json.dumps(report.as_summary(), indent=2))
    # A run that stopped on a limit or an unknown outcome is not a clean run,
    # and a scheduler should be able to see that without parsing prose.
    return 0 if report.stopped_because in {"queue_empty", "job_limit"} else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=MODES, default="fake")
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--model", default=None)
    parser.add_argument("--model-digest", default=None)
    parser.add_argument(
        "--call-timeout",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="hard deadline for one model call",
    )
    parser.add_argument("--request-timeout", type=float, default=20.0)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("preflight")
    sub.add_parser("status")
    run = sub.add_parser("run")
    run.add_argument("--max-jobs", type=int, default=5)
    run.add_argument(
        "--max-seconds",
        type=float,
        default=600.0,
        help="admission window: stops starting new jobs, never interrupts one",
    )
    run.add_argument("--max-microcents", type=int, default=0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.call_timeout <= 0 or args.request_timeout <= 0:
        print("timeouts must be positive", file=sys.stderr)
        return 2
    try:
        return {
            "preflight": command_preflight,
            "status": command_status,
            "run": command_run,
        }[args.command](args)
    except QueueConfigurationError as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
