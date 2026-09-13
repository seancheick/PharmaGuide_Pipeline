#!/usr/bin/env python3
"""Read saved DSLD renders through the production extractor, without qualifying.

This is experiment orchestration, not another extractor or gold importer.
Catalog discrepancies use catalog_gold; original DSLD records are preserved
separately, since agreement with our own export cannot prove source fidelity.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import sys
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

import env_loader  # noqa: F401 - load optional provider keys without printing them
from submission_review.extraction.adapters.hosted_adapter import (
    DEFAULT_GEMINI_MODEL,
    DEFAULT_GROQ_MODEL,
    DEFAULT_TIMEOUT_SECONDS,
    GEMINI_FREE_RETENTION_POLICY,
    GROQ_DEFAULT_RETENTION_POLICY,
    HOSTED_PROMPT_VERSION,
    GeminiAdapter,
    GroqAdapter,
)
from submission_review.extraction.adapters.ocr_adapter import (
    PROVIDER, RULES_VERSION, OcrLabelAdapter,
)
from submission_review.extraction.adapters.rapidocr_reader import RapidOcrReader
from submission_review.extraction.catalog_gold import disagreements, verify_fingerprint
from submission_review.extraction.development import _write
from submission_review.extraction.extractor import (
    EvidenceBundle, EvidencePhoto, ExtractionConfig, ExtractionError, LabelDraftExtractor,
)
from submission_review.extraction.photo_prep import prepare_bundle


def selected_images(manifest_path: Path) -> tuple[dict, list[tuple[dict, bytes]]]:
    """Validate every selected byte before creating an experiment directory."""
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("schema_version") != "dsld_image_diagnostic_v1":
        raise ValueError("expected a DSLD diagnostic image manifest")
    products = manifest.get("products")
    if not isinstance(products, list) or not 1 <= len(products) <= 200:
        raise ValueError("expected between 1 and 200 selected products")
    seen: set[str] = set()
    selected = []
    root = manifest_path.parent.resolve()
    for entry in products:
        key = entry.get("dsld_id")
        if not isinstance(key, str) or not key.isascii() or not key.isdecimal() or key in seen:
            raise ValueError("invalid or duplicate DSLD id")
        seen.add(key)
        if entry.get("status") != "ok":
            raise ValueError(f"image {key} was not successfully downloaded")
        relative = entry.get("path")
        if not isinstance(relative, str) or Path(relative).is_absolute():
            raise ValueError("image path must be relative")
        path = (root / relative).resolve()
        if not path.is_relative_to(root):
            raise ValueError("image path escapes the manifest directory")
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != entry.get("sha256"):
            raise ValueError(f"image {key} differs from its manifest")
        if len(data) != entry.get("size_bytes"):
            raise ValueError(f"image {key} size differs from its manifest")
        selected.append((entry, data))
    return manifest, selected


def run_diagnostic(
    manifest_path: Path, output: Path, blobs: Path, raw_root: Path,
    extractor: LabelDraftExtractor, config: ExtractionConfig,
    *, runtime: dict[str, Any] | None = None,
    limit: int | None = None,
    crop_region: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Preserve selected sources and record one extraction outcome per product."""
    manifest, selected = selected_images(manifest_path)
    if limit is not None:
        if type(limit) is not int or limit < 1:
            raise ValueError("limit must be a positive integer")
        selected = selected[:limit]
        manifest = {**manifest, "products": [entry for entry, _ in selected]}
    if crop_region is not None and len(selected) != 1:
        raise ValueError("a close-up requires exactly one selected product")
    # Refuse replacement, including a previous interrupted experiment.
    output.mkdir(parents=True, exist_ok=False)
    for folder in ("images", "raw", "catalog", "runs"):
        (output / folder).mkdir()
    preserved = json.loads(json.dumps(manifest))
    for target, (entry, data) in zip(preserved["products"], selected):
        target["path"] = f"images/{entry['dsld_id']}.webp"
        with (output / target["path"]).open("xb") as stream:
            stream.write(data)
    _write(output / "diagnostic_manifest.json", preserved)
    _write(output / "configuration.json", {
        "mode": "diagnostic_only", "qualification": False,
        "configuration": asdict(config), "prompt_sha256": extractor.prompt_sha256,
        "runtime": runtime or {},
        "crop_region": crop_region,
        "limitations": [
            "DSLD PDF page-one renders, not real phone captures or a frozen holdout",
            "Catalog comparison is not independent raw-source gold",
            "No production writes, approvals, scoring changes or qualification",
        ],
    })
    counts: Counter = Counter()
    codes: Counter = Counter()
    outcomes = []
    for entry, _data in selected:
        key = entry["dsld_id"]
        receipt: dict[str, Any] = {"dsld_id": key, "reference_status": "unavailable"}
        # A missing or ambiguous reference is reported, never guessed.
        sources = sorted(raw_root.glob(f"*/{key}.json"))
        if len(sources) == 1:
            raw_bytes = sources[0].read_bytes()
            raw = json.loads(raw_bytes)
            if str(raw.get("id")) == key:
                with (output / "raw" / f"{key}.json").open("xb") as stream:
                    stream.write(raw_bytes)
                receipt["raw_source"] = {
                    "path": str(sources[0]), "sha256": hashlib.sha256(raw_bytes).hexdigest(),
                }
        receipt["raw_status"] = "preserved" if "raw_source" in receipt else "missing_or_ambiguous"
        blob = None
        path = blobs / f"{key}.json"
        if path.is_file():
            blob_bytes = path.read_bytes()
            candidate = json.loads(blob_bytes)
            try:
                if str(candidate.get("dsld_id")) != key:
                    raise ValueError("catalog identity mismatch")
                receipt["formula_fingerprint"] = verify_fingerprint(candidate)
            except ValueError as error:
                receipt["reference_status"] = "invalid"
                receipt["reference_error"] = str(error)
            else:
                blob = candidate
                with (output / "catalog" / f"{key}.json").open("xb") as stream:
                    stream.write(blob_bytes)
                receipt["catalog_sha256"] = hashlib.sha256(blob_bytes).hexdigest()
                receipt["reference_status"] = "catalog_only"
        photo = EvidencePhoto(
            str(uuid5(NAMESPACE_URL, f"dsld-diagnostic/{key}/{entry['sha256']}")),
            entry["sha256"], str(output / "images" / f"{key}.webp"),
        )
        try:
            prepared = prepare_bundle(EvidenceBundle(key, 1, (photo,)),
                                      crops={photo.photo_id: crop_region} if crop_region is not None else None)
            result = extractor.extract(prepared, config)
        except ExtractionError as error:
            receipt["outcome"] = "failed"
            receipt["failure"] = error.as_envelope()
            codes[error.code] += 1
        else:
            receipt["outcome"] = "abstained" if result.draft.get("abstained") else "drafted"
            receipt["usage"] = result.usage.as_payload()
            receipt["sent_inputs"] = [p.as_sent_input() for p in prepared.photos]
            for index, prepared_photo in enumerate(prepared.photos):
                with (output / "runs" / f"{key}-input-{index}.jpg").open("xb") as stream:
                    stream.write(prepared_photo.data)
            _write(output / "runs" / f"{key}.draft.json", result.draft)
            if blob is not None:
                found = disagreements(blob, result.draft)
                receipt["catalog_disagreements"] = [asdict(item) for item in found]
                codes.update(f"catalog:{item.kind}" for item in found)
        counts[receipt["outcome"]] += 1
        outcomes.append(receipt)
        _write(output / "runs" / f"{key}.receipt.json", receipt)
        print(f"{len(outcomes)}/{len(selected)}: {key} {receipt['outcome']}", file=sys.stderr, flush=True)
    summary = {
        "mode": "diagnostic_only", "qualification": False,
        "products": len(selected), "outcomes": dict(counts),
        "finding_counts": dict(codes), "results": outcomes,
    }
    _write(output / "summary.json", summary)
    return summary


def hosted_candidate(
    provider: str,
    *,
    model: str | None,
    model_digest: str | None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> tuple[LabelDraftExtractor, ExtractionConfig, dict[str, Any]]:
    """Build and pin one hosted diagnostic before any image is opened."""
    if provider == "gemini":
        adapter = GeminiAdapter(timeout=timeout)
        selected_model = model or DEFAULT_GEMINI_MODEL
        retention = GEMINI_FREE_RETENTION_POLICY
    elif provider == "groq":
        adapter = GroqAdapter(timeout=timeout)
        selected_model = model or DEFAULT_GROQ_MODEL
        retention = GROQ_DEFAULT_RETENTION_POLICY
    else:
        raise ValueError("unsupported hosted provider")
    selected_digest = model_digest or adapter.current_model_digest(selected_model)
    config = ExtractionConfig(
        provider=provider,
        model=selected_model,
        model_digest=selected_digest,
        prompt_version=HOSTED_PROMPT_VERSION,
        retention_policy_version=retention,
    )
    adapter.verify_model(config)
    return LabelDraftExtractor(adapter), config, {
        "hosted": True,
        "retention_policy_version": retention,
        "model_descriptor_sha256": selected_digest,
    }


def main() -> int:
    """Run an installed local candidate without connecting to a queue."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--blobs", type=Path, default=Path("scripts/dist/detail_blobs"))
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument(
        "--provider", choices=("ocr", "ollama", "gemini", "groq"), default="ocr"
    )
    parser.add_argument("--model")
    parser.add_argument("--model-digest")
    parser.add_argument("--endpoint", default="http://127.0.0.1:11434")
    parser.add_argument("--call-timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--crop", type=float, nargs=4, metavar=('X', 'Y', 'W', 'H'),
                        help="normalized close-up in the oriented image; exactly one selected product")
    args = parser.parse_args()
    runtime = {"python": sys.version,
               "packages": {"Pillow": importlib.metadata.version("Pillow")}}
    scripts_root = Path(__file__).resolve().parent
    code_paths = [Path(__file__).resolve(), *sorted(
        (scripts_root / "submission_review" / "extraction").rglob("*.py"))]
    runtime["code_sha256"] = {
        str(path.relative_to(scripts_root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in code_paths
    }
    if args.call_timeout <= 0:
        parser.error("call timeout must be positive")
    if args.provider == "ollama":
        from submission_review.extraction.adapters.ollama_adapter import OllamaAdapter, PROMPT_VERSION
        from submission_review.extraction.bounded_http import request
        if not args.model or not args.model_digest:
            parser.error("Ollama requires an installed model and its exact digest")
        adapter = OllamaAdapter(
            endpoint=args.endpoint, timeout=args.call_timeout
        )  # validates loopback first
        response = request("GET", args.endpoint.rstrip("/") + "/api/status",
                           timeout=5, max_bytes=65536)
        if response.status_code != 200 or json.loads(response.content).get("cloud", {}).get("disabled") is not True:
            parser.error("diagnostics require an Ollama daemon with cloud disabled")
        runtime["cloud_disabled"] = True
        config = ExtractionConfig(
            provider="ollama", model=args.model, model_digest=args.model_digest,
            prompt_version=PROMPT_VERSION, retention_policy_version="local-only-v1",
        )
        extractor = LabelDraftExtractor(adapter)
    elif args.provider in {"gemini", "groq"}:
        extractor, config, hosted_runtime = hosted_candidate(
            args.provider,
            model=args.model,
            model_digest=args.model_digest,
            timeout=args.call_timeout,
        )
        runtime.update(hosted_runtime)
    else:
        if args.model or args.model_digest:
            parser.error("OCR model identity is derived from installed model files")
        package = importlib.metadata.distribution("rapidocr-onnxruntime")
        models = {str(p): hashlib.sha256(Path(package.locate_file(p)).read_bytes()).hexdigest()
                  for p in package.files or () if str(p).endswith(".onnx")}
        if not models:
            raise ValueError("installed OCR model files must be fingerprinted")
        runtime["models"] = models
        runtime["packages"].update({name: importlib.metadata.version(name) for name in
                                   ("rapidocr-onnxruntime", "onnxruntime", "numpy")})
        config = ExtractionConfig(
            provider=PROVIDER, model=f"rapidocr-{package.version}",
            model_digest=hashlib.sha256(json.dumps(models, sort_keys=True).encode()).hexdigest(),
            prompt_version=RULES_VERSION, retention_policy_version="local-only-v1",
        )
        extractor = LabelDraftExtractor(OcrLabelAdapter(RapidOcrReader()))
    result = run_diagnostic(args.manifest, args.output, args.blobs, args.raw_root,
                            extractor, config, runtime=runtime, limit=args.limit,
                            crop_region=dict(zip(('x', 'y', 'w', 'h'), args.crop)) if args.crop else None)
    print(json.dumps({k: v for k, v in result.items() if k != "results"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
