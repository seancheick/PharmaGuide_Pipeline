"""A deterministic adapter for tests and for exercising the worker path.

It reads nothing and invents nothing: it echoes the evidence it was given into
a minimal abstaining draft. That makes it useless for measuring a model and
exactly right for proving that queueing, leasing, validation, recording and
scoring all work before any provider is chosen or paid.
"""

from __future__ import annotations

from typing import Any

from ..extractor import EvidenceBundle, ExtractionConfig, ExtractionError


class FakeAdapter:
    """Returns a valid, abstaining draft over whatever was leased."""

    def __init__(self, *, fail_with: str | None = None) -> None:
        self._fail_with = fail_with

    def extract(
        self, bundle: EvidenceBundle, config: ExtractionConfig
    ) -> dict[str, Any]:
        if self._fail_with is not None:
            raise ExtractionError(self._fail_with, "fake adapter was told to fail")
        snapshot = bundle.snapshot
        return {
            "schema_version": "label_draft_v1",
            "draft_origin": "model",
            "provider": config.provider,
            "model": config.model,
            "prompt_version": config.prompt_version,
            "evidence_revision": bundle.evidence_revision,
            "evidence_snapshot": snapshot,
            # Provenance the writer checks: a model draft must name what it was
            # actually sent, and the sent bytes must be the leased bytes.
            "sent_inputs": [
                {
                    "input_id": f"i{index}",
                    "photo_id": photo.photo_id,
                    "original_sha256": photo.sha256,
                    "sent_sha256": photo.sha256,
                }
                for index, photo in enumerate(bundle.photos)
            ],
            "photo_roles": [],
            "identity": {
                "brand": _unknown(),
                "product_name": _unknown(),
                "barcode_digits_seen": None,
            },
            "serving": {
                "size": _unknown(),
                "servings_per_container": _unknown(),
                "basis_text": _unknown(),
                "amount": None,
            },
            "ingredient_rows": [],
            "other_ingredients": {"text": None, "disclosure_hint": "unknown"},
            "statements": [],
            "discrepancies": [],
            # Abstaining is the honest answer from an adapter that cannot read.
            "abstained": True,
            "abstain_reason": "fake adapter does not read labels",
            "overall_confidence": None,
        }


def _unknown() -> dict[str, Any]:
    return {"value": None, "status": "unreadable", "confidence": None, "sources": []}
