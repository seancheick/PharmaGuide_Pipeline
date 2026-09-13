#!/usr/bin/env python3
"""Run the local extraction worker over the submission queue.

One runner, used both by hand and by any later schedule. There is deliberately
no second scheduled implementation: a cron entry calls this with the same flags
a person would type, so what runs unattended is what was tested.

    scripts/prepare_product_submissions.py --mode local preflight
    scripts/prepare_product_submissions.py --mode gemini --model gemini-2.5-flash model-pin
    scripts/prepare_product_submissions.py status
    scripts/prepare_product_submissions.py --mode local run --max-jobs 5

What this program will not do, by construction: pull a model, fall back to a
different provider, approve or reject a submission, or print a submission id,
photo path or account. A hosted provider is used only when named explicitly.
Extraction is enabled in the database, not here; a runner that forgets a flag
cannot start spending.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import env_loader  # noqa: E402,F401 - load local secrets without printing them
from submission_review.extraction.adapters.fake_adapter import FakeAdapter  # noqa: E402
from submission_review.extraction.adapters.hosted_adapter import (  # noqa: E402
    DEFAULT_GEMINI_MODEL,
    DEFAULT_GROQ_MODEL,
    GEMINI_FREE_RETENTION_POLICY,
    GROQ_DEFAULT_RETENTION_POLICY,
    HOSTED_PROMPT_VERSION,
    GeminiAdapter,
    GroqAdapter,
)
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

MODES = ("fake", "local", "gemini", "groq")


def _queue(args) -> SupabaseExtractionQueue:
    return SupabaseExtractionQueue(
        WorkerCredentials.from_environment(), timeout=args.request_timeout,
        attempt_journal=args.attempt_journal if args.command == "run" else None,
    )


def _adapter(args):
    if args.mode == "local":
        # The per-call deadline lives on the transport, which is the only thing
        # that can actually interrupt a blocked read. The drain's own budget is
        # an admission window and cannot cancel a call already in flight.
        return OllamaAdapter(
            endpoint=args.endpoint, timeout=args.call_timeout
        )
    if args.mode == "gemini":
        return GeminiAdapter(timeout=args.call_timeout)
    if args.mode == "groq":
        return GroqAdapter(timeout=args.call_timeout)
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
    elif args.mode in {"gemini", "groq"}:
        try:
            _probe_hosted_model(args)
            checks.append((f"pinned {args.mode} vision model available", True, ""))
        except ExtractionError as error:
            checks.append((f"pinned {args.mode} vision model available", False, error.detail))
    else:
        checks.append(("fake adapter selected; no model needed", True, ""))

    ok = all(passed for _, passed, _ in checks)
    for name, passed, detail in checks:
        marker = "ok  " if passed else "FAIL"
        print(f"{marker} {name}" + (f" — {detail}" if detail else ""))
    print("\npreflight wrote nothing and sent no photograph.")
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


def _probe_hosted_model(args) -> None:
    from submission_review.extraction.extractor import ExtractionConfig

    if not args.model or not args.model_digest:
        raise ExtractionError(
            "provider_unavailable",
            "--model and --model-digest are required to check a hosted pin",
        )
    _adapter(args).verify_model(
        ExtractionConfig(
            provider=args.mode,
            model=args.model,
            model_digest=args.model_digest,
            prompt_version=HOSTED_PROMPT_VERSION,
            retention_policy_version=_default_retention_policy(args.mode),
        )
    )


def _default_retention_policy(mode: str) -> str:
    return (
        GEMINI_FREE_RETENTION_POLICY if mode == "gemini"
        else GROQ_DEFAULT_RETENTION_POLICY
    )


def command_model_pin(args) -> int:
    """Print a hosted service descriptor pin without opening any photograph."""
    if args.mode not in {"gemini", "groq"}:
        print("model-pin requires --mode gemini or --mode groq", file=sys.stderr)
        return 2
    model = args.model or (
        DEFAULT_GEMINI_MODEL if args.mode == "gemini" else DEFAULT_GROQ_MODEL
    )
    adapter = _adapter(args)
    print(json.dumps({
        "provider": args.mode,
        "model": model,
        "model_digest": adapter.current_model_digest(model),
        "prompt_version": HOSTED_PROMPT_VERSION,
        "prompt_sha256": adapter.prompt_sha256,
        "retention_policy_version": _default_retention_policy(args.mode),
    }, indent=2, sort_keys=True))
    return 0


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


def command_reconcile(args) -> int:
    """Say what one uncertain attempt actually did, and what is owed.

    Used after a completion whose answer was lost. It states facts and stops:
    age is not evidence that a call cost nothing, so nothing is settled here on
    a guess.
    """
    queue = _queue(args)
    try:
        outcome = queue.attempt_outcome(args.job_id, args.fencing_token)
    except Exception:
        print("the attempt could not be checked", file=sys.stderr)
        return 1
    finally:
        queue.close()

    if outcome["draft_recorded"]:
        verdict = "the draft was recorded; do not retry this attempt"
    elif not outcome["attempt_is_current"]:
        verdict = "another attempt owns this job; this one is finished"
    else:
        verdict = "no draft is confirmed; do not rerun inference or completion blindly; inspect the lease and usage"
    if outcome["reservation_open"]:
        verdict += (
            "; a reservation is still outstanding and needs verified usage "
            "or proof the call never ran before it is settled"
        )
    print(json.dumps({**outcome, "verdict": verdict}, indent=2))
    return 0


def _grounding_reader(args):
    """The independent reader that checks a draft against the photographs.

    Optional on purpose: a missing engine must not stop the queue being
    worked. It is never silently absent, though — a run says whether the
    check was in place, because "no report" and "nothing wrong" look identical
    in a record and must not be confused later.
    """
    if getattr(args, "no_grounding", False):
        return None, "disabled"
    try:
        from submission_review.extraction.adapters.rapidocr_reader import (
            RapidOcrReader,
        )
        return RapidOcrReader(), "enabled"
    except Exception as error:  # noqa: BLE001 - an optional engine
        return None, f"unavailable: {type(error).__name__}"


def command_run(args) -> int:
    queue = _queue(args)
    reader, grounding_status = _grounding_reader(args)
    extractor = LabelDraftExtractor(_adapter(args), grounding_reader=reader)
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
    print(json.dumps(
        {**report.as_summary(), "grounding": grounding_status}, indent=2))
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
    parser.add_argument("--attempt-journal", type=Path,
                        default=SCRIPTS_DIR.parent / "reports/submission_extraction/attempts.jsonl",
                        help="private local attempt references for uncertain-completion reconciliation")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("preflight")
    sub.add_parser("model-pin")
    sub.add_parser("status")
    reconcile = sub.add_parser("reconcile")
    reconcile.add_argument("--job-id", required=True)
    reconcile.add_argument("--fencing-token", type=int, required=True)
    run = sub.add_parser("run")
    run.add_argument("--max-jobs", type=int, default=5)
    run.add_argument(
        "--max-seconds",
        type=float,
        default=600.0,
        help="admission window: stops starting new jobs, never interrupts one",
    )
    run.add_argument("--max-microcents", type=int, default=0)
    run.add_argument(
        "--no-grounding",
        action="store_true",
        help="skip the independent check that each reading is printed where "
             "the draft says it is; the report is recorded, never enforced",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.call_timeout <= 0 or args.request_timeout <= 0:
        print("timeouts must be positive", file=sys.stderr)
        return 2
    try:
        return {
            "preflight": command_preflight,
            "model-pin": command_model_pin,
            "status": command_status,
            "reconcile": command_reconcile,
            "run": command_run,
        }[args.command](args)
    except (QueueConfigurationError, ExtractionError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
