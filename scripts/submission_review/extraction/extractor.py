"""The extractor boundary: one interface, provider-neutral, no network here.

An extractor turns one submission's evidence into a ``label_draft_v1`` envelope
or a typed failure. Everything provider-specific lives behind an adapter, so
the queue worker, the development harness and the reviewer console all drive
the same object and none of them learns a provider's shape.

Nothing in this module calls out. It exists so that the parts that do can be
written once, tested with a fake, and swapped without touching the caller.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Protocol

from .envelope import LabelDraftError, validate_label_draft_v1

FAILURE_SCHEMA = "extraction_failure_v1"

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

    def __init__(self, code: str, detail: str = "") -> None:
        if code not in FAILURE_CODES:
            raise ValueError(f"unknown extraction failure code {code!r}")
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail

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
    #: Local path to the fetched bytes. The worker fetches; the adapter reads.
    path: str | None = None
    categories: tuple[str, ...] = ()


@dataclass(frozen=True)
class EvidenceBundle:
    """Everything an extractor is allowed to see about one submission."""

    submission_id: str
    evidence_revision: int
    photos: tuple[EvidencePhoto, ...]

    @property
    def snapshot(self) -> dict[str, str]:
        """The manifest the draft must echo, built from the leased photos."""
        return {photo.photo_id: photo.sha256 for photo in self.photos}


@dataclass(frozen=True)
class ExtractionConfig:
    """The pinned configuration a run is attributable to."""

    provider: str
    model: str
    model_digest: str
    prompt_version: str
    prep_config_version: str = "prep_v1"
    #: An adapter refuses to run until the retention terms it operates under
    #: are stated. Free tiers that train on submissions are not an option, and
    #: silence is not consent.
    retention_policy_version: str | None = None


@dataclass
class Usage:
    """What one extraction cost, in integer micro-cents."""

    microcents: int = 0
    latency_seconds: float = 0.0
    cold_start: bool = False
    details: dict[str, Any] = field(default_factory=dict)

    def as_payload(self) -> dict[str, Any]:
        return {
            "cost_microcents": int(self.microcents),
            "latency_seconds": round(float(self.latency_seconds), 4),
            "cold_start": bool(self.cold_start),
            **self.details,
        }


@dataclass
class ExtractionResult:
    draft: dict[str, Any]
    usage: Usage


class LabelDraftAdapter(Protocol):
    """What a provider adapter must offer, and nothing more."""

    def extract(
        self, bundle: EvidenceBundle, config: ExtractionConfig
    ) -> dict[str, Any]:
        """Return a candidate ``label_draft_v1`` payload or raise."""


class LabelDraftExtractor:
    """Drives one adapter and refuses to hand back anything invalid.

    Validation lives here rather than in each adapter so a new provider cannot
    weaken it by forgetting. The draft must also describe the evidence it was
    actually given: a payload whose snapshot or revision disagrees with the
    lease is not a reading of these photos, whatever it contains.
    """

    def __init__(self, adapter: LabelDraftAdapter) -> None:
        self._adapter = adapter

    def extract(
        self, bundle: EvidenceBundle, config: ExtractionConfig
    ) -> ExtractionResult:
        if config.retention_policy_version is None:
            raise ExtractionError(
                "provider_unavailable",
                "an adapter must state the retention terms it runs under",
            )
        if not bundle.photos:
            raise ExtractionError("unsupported_evidence", "no photos were leased")
        started = time.monotonic()
        payload = self._adapter.extract(bundle, config)
        elapsed = time.monotonic() - started
        try:
            draft = validate_label_draft_v1(payload)
        except LabelDraftError as error:
            raise ExtractionError("model_failure", str(error)) from error
        if draft.get("evidence_snapshot") != bundle.snapshot:
            raise ExtractionError(
                "model_failure", "draft snapshot is not the leased evidence"
            )
        if draft.get("evidence_revision") != bundle.evidence_revision:
            raise ExtractionError(
                "model_failure", "draft revision is not the leased revision"
            )
        for key, expected in (
            ("provider", config.provider),
            ("model", config.model),
            ("prompt_version", config.prompt_version),
        ):
            if draft.get(key) != expected:
                raise ExtractionError(
                    "model_failure", f"draft {key} is not the configured one"
                )
        if draft.get("draft_origin") != "model":
            raise ExtractionError(
                "model_failure", "an extractor produces model drafts only"
            )
        usage = Usage(latency_seconds=elapsed)
        return ExtractionResult(draft=draft, usage=usage)
