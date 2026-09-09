"""Run the same extractor over the development split and write scorable output.

This is how a configuration is examined before anyone talks about qualifying
it. It reuses the frozen holdout layout, the same preparation, the same
extractor and the same envelope the queue worker uses, so what is measured is
the thing that would actually run.

Two boundaries are deliberate. It refuses the held-out split outright: that
split is evaluated once per candidate configuration, through `benchmark.py`,
which keeps the ledger. And it writes drafts and typed failures only; it never
writes gold, because a gold answer produced from a model is not gold.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

from .benchmark import load_manifest
from .extractor import (
    PREPARATION_VERSION,
    EvidenceBundle,
    EvidencePhoto,
    ExtractionConfig,
    ExtractionError,
    LabelDraftExtractor,
)
from .photo_prep import prepare_bundle

DEVELOPMENT_SPLIT = "development"


class DevelopmentRunError(RuntimeError):
    """The development run was asked to do something it must not."""


def run_development_split(
    holdout_dir: Path,
    run_dir: Path,
    extractor: LabelDraftExtractor,
    config: ExtractionConfig,
    *,
    split: str = DEVELOPMENT_SPLIT,
    limit: int | None = None,
    clock=time.monotonic,
) -> dict[str, Any]:
    """Extract each product of the split and write one file per product."""
    if split != DEVELOPMENT_SPLIT:
        # The held-out split is evaluated once per configuration, through the
        # benchmark's ledger. A tuning loop must not be able to consume it.
        raise DevelopmentRunError(
            "only the development split may be run here; use benchmark.py "
            "--split holdout for a single ledgered evaluation"
        )
    products = load_manifest(holdout_dir, split)
    if limit is not None:
        products = products[:limit]
    run_dir.mkdir(parents=True, exist_ok=True)
    summary = {"products": 0, "drafted": 0, "failed": 0, "failure_codes": {}}

    for entry in products:
        summary["products"] += 1
        key = entry["product_key"]
        started = clock()
        try:
            if config.prep_config_version != PREPARATION_VERSION:
                raise ExtractionError(
                    "preparation_failed", "unsupported preparation version"
                )
            # The same preparation the queue worker runs, so what is measured
            # is the bytes a provider would actually have been sent.
            prepared = prepare_bundle(_bundle_for(holdout_dir, entry))
            result = extractor.extract(prepared, config)
        except ExtractionError as error:
            summary["failed"] += 1
            summary["failure_codes"][error.code] = (
                summary["failure_codes"].get(error.code, 0) + 1
            )
            _write(run_dir / f"{key}.json", error.as_envelope())
            _write(
                run_dir / f"{key}.meta.json",
                {"latency_seconds": round(clock() - started, 4), "sent_inputs": []},
            )
            continue
        summary["drafted"] += 1
        _write(run_dir / f"{key}.json", result.draft)
        _write(
            run_dir / f"{key}.meta.json",
            {
                "latency_seconds": round(clock() - started, 4),
                "cost_microcents": result.usage.microcents,
                "cold_start": result.usage.cold_start,
                "sent_inputs": [
                    {"input_id": sent["input_id"], "path": f"{key}-{sent['input_id']}.jpg"}
                    for sent in result.draft.get("sent_inputs", [])
                ],
            },
        )
    _write(run_dir / "configuration.json", {"configuration": _config_payload(config)})
    return summary


def _bundle_for(holdout_dir: Path, entry: dict[str, Any]) -> EvidenceBundle:
    photos = []
    for photo in entry.get("photos", []):
        path = holdout_dir / photo["path"]
        if not path.exists():
            raise ExtractionError("preparation_failed", "a set photo is missing")
        photos.append(
            EvidencePhoto(
                photo_id=photo["photo_id"], sha256=photo["sha256"], path=str(path)
            )
        )
    if not photos:
        raise ExtractionError("unsupported_evidence", "the product has no photos")
    return EvidenceBundle(
        submission_id=entry["product_key"], evidence_revision=1, photos=tuple(photos)
    )


def _config_payload(config: ExtractionConfig) -> dict[str, Any]:
    return {
        "provider": config.provider,
        "model": config.model,
        "model_digest": config.model_digest,
        "prompt_version": config.prompt_version,
        "prep_config_version": config.prep_config_version,
        "preparation": {"version": config.prep_config_version},
    }


def _write(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def gold_template(product_key: str) -> dict[str, Any]:
    """A blank two-checker gold record, for a person to fill in.

    Deliberately empty. Every value here has to come off the photograph by eye,
    twice, by two people who have not seen a model's answer. A prefilled
    template is the fastest way to turn a check into a rubber stamp.
    """
    return {
        "schema_version": "gold_label_v1",
        "product_key": product_key,
        "checked_by": [
            {
                "checker": "<initials of first checker>",
                "checked_at": "<UTC timestamp>",
                "human": True,
                "independent": True,
                "model_output_seen": False,
            },
            {
                "checker": "<initials of second checker>",
                "checked_at": "<UTC timestamp>",
                "human": True,
                "independent": True,
                "model_output_seen": False,
            },
        ],
        "expected": "draft",
        "identity": {"brand": "", "product_name": "", "barcode_digits_seen": ""},
        "serving": {
            "size": "",
            "servings_per_container": "",
            "basis_text": "",
            "amount": None,
        },
        "other_ingredients": {"text": "", "disclosure_hint": "present"},
        "rows": [
            {
                "display_name": "",
                "amount": {"value": 0, "unit_text": ""},
                "owner": None,
                "parent_index": None,
                "is_blend_header": False,
                "percent_dv": None,
                "form_text": None,
                "readable": True,
            }
        ],
    }


def intake_manifest_entry(product_key: str, family: str, split: str, photo_paths: list[Path], root: Path) -> dict[str, Any]:
    """One manifest row for a real product, hashed from the bytes on disk."""
    if split not in (DEVELOPMENT_SPLIT, "holdout"):
        raise DevelopmentRunError("split must be development or holdout")
    photos = []
    for index, path in enumerate(photo_paths):
        data = path.read_bytes()
        photos.append(
            {
                "photo_id": _photo_id(product_key, index),
                "path": str(path.relative_to(root)),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )
    return {
        "product_key": product_key,
        "brand": family.split("/")[0],
        "family": family,
        "split": split,
        "gold": f"gold/{product_key}.json",
        "cases": [],
        "photos": photos,
    }


def _photo_id(product_key: str, index: int) -> str:
    token = hashlib.md5(f"{product_key}/{index}".encode()).hexdigest()  # noqa: S324
    return f"{token[:8]}-{token[8:12]}-{token[12:16]}-{token[16:20]}-{token[20:]}"
