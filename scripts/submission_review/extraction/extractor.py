"""The extractor boundary: one interface, provider-neutral, no network here.

An extractor turns one submission's evidence into a ``label_draft_v1`` envelope
or a typed failure. Everything provider-specific lives behind an adapter, so
the queue worker, the development harness and the reviewer console all drive
the same object and none of them learns a provider's shape.

Nothing in this module calls out. It exists so that the parts that do can be
written once, tested with a fake, and swapped without touching the caller.
"""

from __future__ import annotations

import hashlib
import math
import time
from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol

from .checks import run_checks
from .grounding import verify_grounding
from .envelope import MAX_DISCREPANCIES, LabelDraftError, validate_label_draft_v1

FAILURE_SCHEMA = "extraction_failure_v1"
PREPARATION_VERSION = "prep_v1"

#: Typed failures. A model that fell over is not the same thing as evidence a
#: careful reader cannot use, and a reviewer needs to see which happened.
FAILURE_CODES = frozenset(
    {
        "model_failure",
        "unreadable_evidence",
        "unsupported_evidence",
        "budget_exhausted",
        "provider_unavailable",
        "preparation_failed",
    }
)


class ExtractionError(RuntimeError):
    """The extractor could not produce a draft, and says why in one code."""

    def __init__(self, code: str, detail: str = "", *, usage: Usage | None = None) -> None:
        if code not in FAILURE_CODES:
            raise ValueError(f"unknown extraction failure code {code!r}")
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail
        self.usage = usage

    def as_envelope(self) -> dict[str, Any]:
        return {
            "schema_version": FAILURE_SCHEMA,
            "code": self.code,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class EvidencePhoto:
    """One photo as the queue leased it, identified by content."""

    photo_id: str
    sha256: str
    #: Local path consumed only by preparation, never exposed to an adapter.
    path: str | None = None
    categories: tuple[str, ...] = ()


@dataclass(frozen=True)
class EvidenceBundle:
    """Original evidence leased to the worker for preparation."""

    submission_id: str
    evidence_revision: int
    photos: tuple[EvidencePhoto, ...]
    # Optional context is supplied by the identity owner at the queue
    # boundary.  It is deliberately not inferred from model output.
    submission_gtin: str | None = None
    catalog_match: Mapping[str, Any] | None = None

    @property
    def snapshot(self) -> dict[str, str]:
        """The manifest the draft must echo, built from the leased photos."""
        return {photo.photo_id: photo.sha256 for photo in self.photos}


@dataclass(frozen=True)
class PreparedInput:
    """The exact sanitized bytes an adapter receives, with original lineage."""

    input_id: str
    photo_id: str
    original_sha256: str
    sent_sha256: str
    content_type: str
    byte_size: int
    data: bytes
    categories: tuple[str, ...] = ()
    #: Optional normalized x/y/w/h in the orientation-corrected original.
    crop: tuple[float, float, float, float] | None = None

    # Geometry retained internally; the draft input contract stays unchanged.
    original_size: tuple[int, int] | None = None
    prepared_size: tuple[int, int] | None = None
    pixel_crop: tuple[int, int, int, int] | None = None

    def as_sent_input(self) -> dict[str, object]:
        result: dict[str, object] = {"input_id": self.input_id, "photo_id": self.photo_id,
                                    "original_sha256": self.original_sha256, "sent_sha256": self.sent_sha256}
        if self.crop is not None:
            result["crop"] = dict(zip(("x", "y", "w", "h"), self.crop))
        return result


@dataclass(frozen=True)
class PreparedBundle:
    """Provider input; intentionally contains no original paths or raw bytes."""

    submission_id: str
    evidence_revision: int
    photos: tuple[PreparedInput, ...]

    @property
    def snapshot(self) -> dict[str, str]:
        return {photo.photo_id: photo.original_sha256 for photo in self.photos}


@dataclass(frozen=True)
class ExtractionConfig:
    """The pinned configuration a run is attributable to."""

    provider: str
    model: str
    model_digest: str
    prompt_version: str
    prep_config_version: str = PREPARATION_VERSION
    #: An adapter refuses to run until the retention terms it operates under
    #: are stated. Free tiers that train on submissions are not an option, and
    #: silence is not consent.
    retention_policy_version: str | None = None
    max_cost_microcents: int = 0


@dataclass
class Usage:
    """What one extraction cost, in integer micro-cents."""

    microcents: int = 0
    latency_seconds: float = 0.0
    cold_start: bool = False
    details: dict[str, Any] = field(default_factory=dict)

    def as_payload(self) -> dict[str, Any]:
        if type(self.microcents) is not int or self.microcents < 0:
            raise ValueError("invalid extraction cost")
        if not math.isfinite(self.latency_seconds) or self.latency_seconds < 0:
            raise ValueError("invalid extraction latency")
        return {
            **self.details,
            "cost_microcents": int(self.microcents),
            "latency_seconds": round(float(self.latency_seconds), 4),
            "cold_start": bool(self.cold_start),
        }


@dataclass
class ExtractionResult:
    draft: dict[str, Any]
    usage: Usage


class LabelDraftAdapter(Protocol):
    """What a provider adapter must offer, and nothing more."""

    def extract(self, bundle: PreparedBundle, config: ExtractionConfig) -> ExtractionResult:
        """Return a candidate draft and authoritative adapter usage, or raise."""


class LabelDraftExtractor:
    """Drives one adapter and refuses to hand back anything invalid.

    Validation lives here rather than in each adapter so a new provider cannot
    weaken it by forgetting. The draft must also describe the evidence it was
    actually given: a payload whose snapshot or revision disagrees with the
    lease is not a reading of these photos, whatever it contains.
    """

    def __init__(
        self,
        adapter: LabelDraftAdapter,
        *,
        grounding_reader: Any | None = None,
    ) -> None:
        self._adapter = adapter
        # An optional second reader that looks at the same prepared bytes and
        # answers one question: is each value the producer claims actually
        # printed where it says it is. It grants nothing and blocks nothing.
        self._grounding_reader = grounding_reader

    @property
    def prompt_sha256(self) -> str:
        """Adapter-owned immutable instructions, required before a benchmark."""
        value = getattr(self._adapter, "prompt_sha256", None)
        if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            raise ValueError("adapter has no immutable prompt digest")
        return value

    def extract(
        self,
        bundle: PreparedBundle,
        config: ExtractionConfig,
        *,
        submission_gtin: str | None = None,
        catalog_match: Mapping[str, Any] | None = None,
    ) -> ExtractionResult:
        if not isinstance(config.retention_policy_version, str) or not config.retention_policy_version.strip():
            raise ExtractionError(
                "provider_unavailable",
                "an adapter must state the retention terms it runs under",
                usage=Usage(),
            )
        if not isinstance(bundle, PreparedBundle):
            raise ExtractionError("preparation_failed", "prepared evidence required", usage=Usage())
        if not bundle.photos:
            raise ExtractionError("unsupported_evidence", "no photos were leased", usage=Usage())
        if len(bundle.snapshot) != len(bundle.photos) or len({p.input_id for p in bundle.photos}) != len(bundle.photos):
            raise ExtractionError("preparation_failed", "duplicate evidence identity")
        for photo in bundle.photos:
            if len(photo.data) != photo.byte_size or hashlib.sha256(photo.data).hexdigest() != photo.sent_sha256:
                raise ExtractionError("preparation_failed", "prepared bytes do not match provenance")
        started = time.monotonic()
        try:
            result = self._adapter.extract(bundle, config)
        except ExtractionError as error:
            # A typed adapter exception still crosses the untrusted boundary.
            # Invalid usage means unknown cost, never an invented zero charge.
            error.usage = _checked_usage(error.usage)
            raise
        except LabelDraftError as error:
            # Some adapters validate before returning. This is the same bad
            # draft as a validation failure below, not an unavailable engine.
            # No usage was returned, so do not invent a zero-cost receipt.
            raise ExtractionError("model_failure", "invalid provider draft") from error
        except Exception as error:
            # Adapters are provider boundaries. An unexpected SDK/network
            # exception must become a retryable typed failure rather than
            # escaping the worker and leaving the lease to expire. Do not
            # expose provider exception text: it can contain request data or
            # credentials.
            raise ExtractionError(
                "provider_unavailable", "provider adapter failed"
            ) from error
        elapsed = time.monotonic() - started
        usage = _checked_usage(getattr(result, "usage", None))
        try:
            if not isinstance(result, ExtractionResult):
                raise LabelDraftError("$", "adapter result must include usage")
            if usage is None:
                raise LabelDraftError("$", "adapter usage must be valid")
            draft = validate_label_draft_v1(result.draft)
        except (LabelDraftError, ValueError, TypeError, AttributeError) as error:
            raise ExtractionError("model_failure", "invalid provider draft", usage=usage) from error
        if draft.get("evidence_snapshot") != bundle.snapshot:
            raise ExtractionError(
                "model_failure", "draft snapshot is not the leased evidence", usage=result.usage
            )
        if draft.get("evidence_revision") != bundle.evidence_revision:
            raise ExtractionError(
                "model_failure", "draft revision is not the leased revision", usage=result.usage
            )
        for key, expected in (
            ("provider", config.provider),
            ("model", config.model),
            ("prompt_version", config.prompt_version),
        ):
            if draft.get(key) != expected:
                raise ExtractionError(
                    "model_failure", f"draft {key} is not the configured one", usage=result.usage
                )
        if draft.get("draft_origin") != "model":
            raise ExtractionError(
                "model_failure", "an extractor produces model drafts only", usage=result.usage
            )
        if draft["sent_inputs"] != [photo.as_sent_input() for photo in bundle.photos]:
            raise ExtractionError("model_failure", "draft inputs are not the prepared evidence", usage=result.usage)
        # These are deterministic findings, not model claims.  Attach them at
        # the one extractor boundary so every worker/development caller gets
        # the same checks and no caller can forget to run them.
        derived = run_checks(
            draft,
            submission_gtin=submission_gtin,
            catalog_match=catalog_match,
        )
        if derived:
            existing = draft.get("discrepancies") or []
            merged = list(existing)
            seen = {
                (
                    item.get("code"), item.get("severity"), item.get("detail"),
                    tuple(item.get("photo_ids") or ()),
                )
                for item in existing
                if isinstance(item, dict)
            }
            for finding in derived:
                key = (
                    finding["code"], finding["severity"], finding["detail"],
                    tuple(finding.get("photo_ids") or ()),
                )
                if key not in seen:
                    merged.append(finding)
                    seen.add(key)
            if len(merged) > MAX_DISCREPANCIES:
                raise ExtractionError(
                    "model_failure",
                    "draft discrepancy limit exceeded after deterministic checks",
                    usage=result.usage,
                )
            draft = dict(draft)
            draft["discrepancies"] = merged
            try:
                draft = validate_label_draft_v1(draft)
            except (LabelDraftError, ValueError, TypeError, AttributeError) as error:
                raise ExtractionError(
                    "model_failure", "deterministic findings were invalid", usage=result.usage
                ) from error
        self._attach_grounding(draft, bundle, config, result.usage)
        result.usage.latency_seconds = elapsed
        return ExtractionResult(draft=draft, usage=result.usage)

    def _attach_grounding(
        self,
        draft: dict[str, Any],
        bundle: PreparedBundle,
        config: ExtractionConfig,
        usage: Usage,
    ) -> None:
        """Record whether the reading can be located in the photographs.

        A safety report, not a gate. Nothing here refuses a draft, changes a
        disposition or reaches approval: it writes what an independent reader
        could and could not find, so a reviewer sees it and the benchmark can
        measure it per field.

        Grounding a draft against the very reader that produced it is
        circular — it can only catch an assembly bug, never an invented value —
        so whether the check was independent of the producer is recorded
        alongside the result rather than left for someone to assume.
        """
        if self._grounding_reader is None:
            return
        try:
            pages = [
                self._grounding_reader.read(
                    photo.data, photo_id=photo.photo_id, input_id=photo.input_id)
                for photo in bundle.photos
            ]
            report = verify_grounding(draft, pages, prepared_inputs=bundle.photos)
        except Exception as error:  # noqa: BLE001 - a report must never fail a run
            # A broken verifier is not a broken reading. Say the check did not
            # run rather than let it decide anything by its absence.
            usage.details["grounding"] = {
                "schema_version": "grounding_report_v1",
                "status": "unavailable",
                "reason": type(error).__name__,
            }
            return
        payload = report.as_payload()
        payload["status"] = "ok"
        payload["independent_of_producer"] = config.provider != "ocr"
        payload["independence_note"] = ("Legacy provider-name heuristic only; reader identity and independence are not verified.")
        usage.details["grounding"] = payload


def _checked_usage(value: object) -> Usage | None:
    if not isinstance(value, Usage):
        return None
    try:
        value.as_payload()
    except (ValueError, TypeError, AttributeError, OverflowError):
        return None
    return value
