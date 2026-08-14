#!/usr/bin/env python3
"""Validate and atomically apply structured evidence to IQM forms.

The ingredient quality map remains the scoring source of truth. This module
adds a narrow evidence contract around a form's existing ``bio_score``; it does
not calculate, infer, or change that score.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import sys
import tempfile
import unicodedata
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Iterator


EXCELLENT_BIO_SCORE = 12
SUPPORTED_SCHEMA_VERSIONS = {"1.0.0"}
SUPPORTED_BACKLOG_SCHEMA_VERSIONS = {"5.0.0"}
SUPPORTED_AXES = {
    "systemic_bioavailability",
    "delivery_to_site",
    "form_quality_confidence",
    "organism_survivability",
    "class_equivalence",
}
SUPPORTED_EVIDENCE_LEVELS = {
    "strong",
    "moderate",
    "limited",
    "mechanistic_only",
    "none",
}
EXCELLENT_EVIDENCE_LEVELS = {"strong", "moderate"}
SUPPORTED_REVIEW_STATUSES = {"source_verified", "clinician_approved"}
SUPPORTED_REFERENCE_TYPES = {"pubmed", "authoritative_guidance"}
INTERNAL_EVIDENCE_FIELDS = {
    "axis",
    "rationale",
    "review",
    "schema_version",
    "score_supported",
}


class ManifestError(ValueError):
    """A migration manifest cannot be applied exactly as authored."""


def evidence_key(ingredient_key: str, form_key: str) -> str:
    return f"{ingredient_key}::{form_key}"


def form_digest(form: dict[str, Any]) -> str:
    payload = json.dumps(
        form,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def backlog_initial_digest(keys: Iterable[str]) -> str:
    canonical = "\n".join(sorted(str(key).strip() for key in keys if str(key).strip()))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _is_iso_date(value: Any) -> bool:
    try:
        date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return False
    return True


def _non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _validate_reference(reference: Any, label: str) -> list[str]:
    if not isinstance(reference, dict):
        return [f"{label}: reference must be an object"]

    problems: list[str] = []
    reference_type = reference.get("type")
    if reference_type not in SUPPORTED_REFERENCE_TYPES:
        problems.append(
            f"{label}: unsupported reference type {reference_type!r}"
        )
    for field in ("authority", "title", "url", "verification_source"):
        if not _non_empty_string(reference.get(field)):
            problems.append(f"{label}: {field} must be non-empty")
    url = reference.get("url")
    if _non_empty_string(url) and not str(url).startswith("https://"):
        problems.append(f"{label}: url must use https")

    supports = reference.get("supports_claims")
    if not isinstance(supports, list) or not supports or not all(
        _non_empty_string(item) for item in supports
    ):
        problems.append(f"{label}: supports_claims must be non-empty")

    if not _is_iso_date(reference.get("verified_on")):
        problems.append(f"{label}: verified_on must be an ISO date")

    if reference_type == "pubmed":
        pmid = str(reference.get("pmid") or "").strip()
        if not pmid.isdigit() or not 5 <= len(pmid) <= 9:
            problems.append(f"{label}: pubmed reference requires a valid PMID")
        if reference.get("retracted") is not False:
            problems.append(f"{label}: pubmed reference must explicitly be non-retracted")

    return problems


def validate_form_evidence(
    form_evidence: Any,
    *,
    label: str,
    excellent: bool,
) -> list[str]:
    if not isinstance(form_evidence, dict):
        return [f"{label}: form_evidence must be an object"]

    problems: list[str] = []
    if form_evidence.get("schema_version") not in SUPPORTED_SCHEMA_VERSIONS:
        problems.append(f"{label}: unsupported form_evidence schema_version")
    if form_evidence.get("axis") not in SUPPORTED_AXES:
        problems.append(f"{label}: unsupported evidence axis")

    evidence_level = form_evidence.get("evidence_level")
    if evidence_level not in SUPPORTED_EVIDENCE_LEVELS:
        problems.append(f"{label}: unsupported evidence_level")
    if excellent and evidence_level not in EXCELLENT_EVIDENCE_LEVELS:
        problems.append(
            f"{label}: Excellent form requires strong or moderate evidence"
        )
    if excellent and form_evidence.get("score_supported") is not True:
        problems.append(f"{label}: Excellent form must explicitly support its score")

    rationale = form_evidence.get("rationale")
    if not _non_empty_string(rationale) or len(str(rationale).strip()) < 20:
        problems.append(f"{label}: rationale must be at least 20 characters")

    review = form_evidence.get("review")
    if not isinstance(review, dict):
        problems.append(f"{label}: review must be an object")
    else:
        if review.get("status") not in SUPPORTED_REVIEW_STATUSES:
            problems.append(f"{label}: unsupported review.status")
        if not _non_empty_string(review.get("by")):
            problems.append(f"{label}: review.by must be non-empty")
        if not _is_iso_date(review.get("date")):
            problems.append(f"{label}: review.date must be an ISO date")

    references = form_evidence.get("references_structured")
    if not isinstance(references, list) or not references:
        problems.append(f"{label}: references_structured must be non-empty")
    else:
        for index, reference in enumerate(references):
            problems.extend(
                _validate_reference(reference, f"{label}.references_structured[{index}]")
            )
    return problems


def validate_exported_form_evidence(form_evidence: Any, *, label: str) -> list[str]:
    """Validate the consumer-safe projection without requiring audit fields."""
    if not isinstance(form_evidence, dict):
        return [f"{label}: form_evidence must be an object"]
    problems: list[str] = []
    for field in sorted(INTERNAL_EVIDENCE_FIELDS & set(form_evidence)):
        problems.append(f"{label}: internal field {field} must not be exported")
    if form_evidence.get("evidence_level") not in EXCELLENT_EVIDENCE_LEVELS:
        problems.append(f"{label}: unsupported exported evidence_level")
    references = form_evidence.get("references_structured")
    if not isinstance(references, list) or not references:
        problems.append(f"{label}: references_structured must be non-empty")
    else:
        for index, reference in enumerate(references):
            problems.extend(
                _validate_reference(reference, f"{label}.references_structured[{index}]")
            )
    return problems


def _iter_forms(iqm: dict[str, Any]) -> Iterable[tuple[str, str, dict[str, Any]]]:
    for ingredient_key, ingredient in iqm.items():
        if ingredient_key == "_metadata" or not isinstance(ingredient, dict):
            continue
        forms = ingredient.get("forms")
        if not isinstance(forms, dict):
            continue
        for form_key, form in forms.items():
            if isinstance(form, dict):
                yield ingredient_key, form_key, form


def validate_iqm_form_evidence(
    iqm: dict[str, Any],
    *,
    backlog: set[str],
) -> list[str]:
    problems: list[str] = []
    seen_keys: set[str] = set()

    for ingredient_key, form_key, form in _iter_forms(iqm):
        key = evidence_key(ingredient_key, form_key)
        seen_keys.add(key)
        bio_score = form.get("bio_score")
        excellent = isinstance(bio_score, (int, float)) and bio_score >= EXCELLENT_BIO_SCORE
        form_evidence = form.get("form_evidence")

        if form_evidence is None:
            if excellent and key not in backlog:
                problems.append(
                    f"{key}: Excellent bio_score {bio_score:g} lacks approved form_evidence"
                )
            elif not excellent and key in backlog:
                problems.append(
                    f"{key}: non-Excellent form is still listed in the backlog"
                )
            continue

        evidence_problems = validate_form_evidence(
            form_evidence,
            label=key,
            excellent=excellent,
        )
        problems.extend(evidence_problems)
        if key in backlog and not evidence_problems:
            problems.append(f"{key}: approved evidence is still listed in the backlog")

    for key in sorted(backlog - seen_keys):
        problems.append(f"{key}: backlog entry does not resolve to an IQM form")
    return problems


def build_initial_backlog(
    iqm: dict[str, Any], *, created_on: str
) -> dict[str, Any]:
    if not _is_iso_date(created_on):
        raise ManifestError("created_on must be an ISO date")
    keys: list[str] = []
    for ingredient_key, form_key, form in _iter_forms(iqm):
        bio_score = form.get("bio_score")
        if not isinstance(bio_score, (int, float)) or bio_score < EXCELLENT_BIO_SCORE:
            continue
        key = evidence_key(ingredient_key, form_key)
        evidence = form.get("form_evidence")
        if evidence is None or validate_form_evidence(
            evidence,
            label=key,
            excellent=True,
        ):
            keys.append(key)
    keys.sort()
    return {
        "_metadata": {
            "schema_version": "5.0.0",
            "created_on": created_on,
            "last_updated": created_on,
            "description": (
                "Frozen migration ledger for legacy Excellent IQM forms that "
                "still require approved structured evidence."
            ),
            "purpose": "form_evidence_release_governance",
            "total_entries": len(keys),
            "policy": (
                "Frozen legacy backlog. remaining_forms may only shrink; new "
                "Excellent forms require approved structured evidence."
            ),
            "initial_forms_sha256": backlog_initial_digest(keys),
        },
        "initial_forms": keys,
        "remaining_forms": list(keys),
    }


def load_backlog_file(path: Path) -> set[str]:
    payload = _load_json_object(path, label="backlog")
    metadata = payload.get("_metadata")
    if (
        not isinstance(metadata, dict)
        or metadata.get("schema_version") not in SUPPORTED_BACKLOG_SCHEMA_VERSIONS
    ):
        raise ManifestError("backlog schema_version must be 5.0.0")
    initial = payload.get("initial_forms")
    remaining = payload.get("remaining_forms")
    if not isinstance(initial, list) or not all(_non_empty_string(key) for key in initial):
        raise ManifestError("backlog initial_forms must be a string list")
    if not isinstance(remaining, list) or not all(_non_empty_string(key) for key in remaining):
        raise ManifestError("backlog remaining_forms must be a string list")
    if len(initial) != len(set(initial)) or len(remaining) != len(set(remaining)):
        raise ManifestError("backlog form lists must not contain duplicates")
    expected_digest = str(metadata.get("initial_forms_sha256") or "")
    if backlog_initial_digest(initial) != expected_digest:
        raise ManifestError("backlog initial_forms_sha256 does not match initial_forms")
    unexpected = sorted(set(remaining) - set(initial))
    if unexpected:
        raise ManifestError(
            f"{unexpected[0]} is not in the frozen initial set"
        )
    return set(remaining)


def _iter_json_array(path: Path, *, chunk_size: int = 1024 * 1024) -> Iterator[Any]:
    """Yield values from a top-level JSON array without loading the file."""
    decoder = json.JSONDecoder()
    with path.open("r", encoding="utf-8") as handle:
        buffer = ""
        position = 0
        eof = False

        def refill() -> None:
            nonlocal buffer, position, eof
            if position:
                buffer = buffer[position:]
                position = 0
            chunk = handle.read(chunk_size)
            if chunk:
                buffer += chunk
            else:
                eof = True

        refill()
        while not eof and not buffer.strip():
            refill()
        position = len(buffer) - len(buffer.lstrip())
        if position >= len(buffer) or buffer[position] != "[":
            raise ManifestError(f"enriched batch must be a top-level array: {path}")
        position += 1

        while True:
            while True:
                while position < len(buffer) and (
                    buffer[position].isspace() or buffer[position] == ","
                ):
                    position += 1
                if position < len(buffer):
                    break
                if eof:
                    raise ManifestError(f"unterminated JSON array: {path}")
                refill()

            if buffer[position] == "]":
                return

            try:
                value, end = decoder.raw_decode(buffer, position)
            except json.JSONDecodeError as exc:
                if eof:
                    raise ManifestError(f"invalid enriched JSON {path}: {exc}") from exc
                refill()
                continue
            position = end
            yield value


def _quality_form_occurrences(product: dict[str, Any]) -> list[str]:
    quality = product.get("ingredient_quality_data")
    rows = quality.get("ingredients") if isinstance(quality, dict) else None
    if not isinstance(rows, list):
        return []
    occurrences: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        row_keys: set[str] = set()
        parent = str(row.get("canonical_id") or "").strip()
        primary_form = str(row.get("matched_form") or "").strip()
        if parent and primary_form:
            row_keys.add(evidence_key(parent, primary_form))
        matched_forms = row.get("matched_forms")
        if isinstance(matched_forms, list):
            for matched in matched_forms:
                if not isinstance(matched, dict):
                    continue
                matched_parent = str(matched.get("canonical_id") or parent).strip()
                matched_form = str(matched.get("form_key") or "").strip()
                if matched_parent and matched_form:
                    row_keys.add(evidence_key(matched_parent, matched_form))
        occurrences.extend(sorted(row_keys))
    return occurrences


def catalog_form_usage(products_dir: Path) -> dict[str, dict[str, int]]:
    """Count IQM forms in saved enriched outputs without loading the corpus at once."""
    row_counts: dict[str, int] = {}
    product_counts: dict[str, int] = {}
    paths = sorted(products_dir.glob("*_enriched/enriched/*.json"))
    for path in paths:
        if path.name.startswith("."):
            continue
        for product in _iter_json_array(path):
            if not isinstance(product, dict):
                raise ManifestError(f"enriched batch contains a non-object product: {path}")
            occurrences = _quality_form_occurrences(product)
            for key in occurrences:
                row_counts[key] = row_counts.get(key, 0) + 1
            for key in set(occurrences):
                product_counts[key] = product_counts.get(key, 0) + 1
    return {
        key: {
            "ingredient_rows": row_counts[key],
            "products": product_counts[key],
        }
        for key in sorted(row_counts)
    }


def _form_by_evidence_key(
    iqm: dict[str, Any], key: str
) -> dict[str, Any] | None:
    ingredient_key, separator, form_key = key.partition("::")
    if not separator:
        return None
    ingredient = iqm.get(ingredient_key)
    forms = ingredient.get("forms") if isinstance(ingredient, dict) else None
    form = forms.get(form_key) if isinstance(forms, dict) else None
    return form if isinstance(form, dict) else None


def catalog_evidence_gaps(
    iqm: dict[str, Any], usage: dict[str, dict[str, int]]
) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []
    for key, counts in usage.items():
        form = _form_by_evidence_key(iqm, key)
        if form is None:
            continue
        bio_score = form.get("bio_score")
        if not isinstance(bio_score, (int, float)) or bio_score < EXCELLENT_BIO_SCORE:
            continue
        evidence = form.get("form_evidence")
        if evidence is None:
            issues = [
                f"{key}: Excellent bio_score {bio_score:g} lacks approved form_evidence"
            ]
        else:
            issues = validate_form_evidence(evidence, label=key, excellent=True)
        if issues:
            gaps.append(
                {
                    "key": key,
                    "bio_score": bio_score,
                    "ingredient_rows": int(counts.get("ingredient_rows") or 0),
                    "products": int(counts.get("products") or 0),
                    "issues": issues,
                }
            )
    gaps.sort(key=lambda item: (-item["products"], -item["ingredient_rows"], item["key"]))
    return gaps


def _normalized_bibliographic_text(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).casefold()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def verify_pubmed_content(
    iqm: dict[str, Any], articles_by_pmid: dict[str, dict[str, Any]]
) -> list[str]:
    """Compare stored citation identity with freshly fetched PubMed content."""
    problems: list[str] = []
    for ingredient_key, form_key, form in _iter_forms(iqm):
        evidence = form.get("form_evidence")
        if not isinstance(evidence, dict):
            continue
        references = evidence.get("references_structured")
        if not isinstance(references, list):
            continue
        key = evidence_key(ingredient_key, form_key)
        for index, reference in enumerate(references):
            if not isinstance(reference, dict) or reference.get("type") != "pubmed":
                continue
            pmid = str(reference.get("pmid") or "").strip()
            label = f"{key}.references_structured[{index}] PMID {pmid}"
            article = articles_by_pmid.get(pmid)
            if not isinstance(article, dict):
                problems.append(f"{label}: does not resolve in live PubMed")
                continue
            if _normalized_bibliographic_text(reference.get("title")) != (
                _normalized_bibliographic_text(article.get("title"))
            ):
                problems.append(f"{label}: title does not match live PubMed")
            stored_doi = _normalized_bibliographic_text(reference.get("doi"))
            live_doi = _normalized_bibliographic_text(article.get("doi"))
            if stored_doi and stored_doi != live_doi:
                problems.append(f"{label}: DOI does not match live PubMed")
            if article.get("retracted") is True:
                problems.append(f"{label}: live PubMed record is retracted")
    return problems


def collect_pubmed_pmids(iqm: dict[str, Any]) -> list[str]:
    pmids: set[str] = set()
    for _, _, form in _iter_forms(iqm):
        evidence = form.get("form_evidence")
        references = (
            evidence.get("references_structured")
            if isinstance(evidence, dict)
            else None
        )
        if not isinstance(references, list):
            continue
        for reference in references:
            if not isinstance(reference, dict) or reference.get("type") != "pubmed":
                continue
            pmid = str(reference.get("pmid") or "").strip()
            if pmid.isdigit():
                pmids.add(pmid)
    return sorted(pmids, key=int)


def _load_json_object(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManifestError(f"Cannot read {label} {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ManifestError(f"{label} must contain a JSON object: {path}")
    return value


def _resolve_manifest_form(
    iqm: dict[str, Any], ingredient_key: str, form_key: str
) -> dict[str, Any]:
    ingredient = iqm.get(ingredient_key)
    forms = ingredient.get("forms") if isinstance(ingredient, dict) else None
    form = forms.get(form_key) if isinstance(forms, dict) else None
    if not isinstance(form, dict):
        raise ManifestError(f"{evidence_key(ingredient_key, form_key)}: form not found")
    return form


def apply_manifest_file(iqm_path: Path, manifest_path: Path) -> dict[str, int]:
    """Apply a complete manifest or leave the IQM byte-for-byte untouched."""
    iqm = _load_json_object(iqm_path, label="IQM")
    manifest = _load_json_object(manifest_path, label="manifest")
    if manifest.get("schema_version") != "1.0.0":
        raise ManifestError("manifest schema_version must be 1.0.0")
    changes = manifest.get("changes")
    if not isinstance(changes, list) or not changes:
        raise ManifestError("manifest changes must be a non-empty list")

    # Validate every precondition before mutating the in-memory candidate.
    resolved: list[tuple[dict[str, Any], dict[str, Any], str]] = []
    seen: set[str] = set()
    for index, change in enumerate(changes):
        if not isinstance(change, dict):
            raise ManifestError(f"changes[{index}] must be an object")
        ingredient_key = str(change.get("ingredient_key") or "").strip()
        form_key = str(change.get("form_key") or "").strip()
        key = evidence_key(ingredient_key, form_key)
        if key in seen:
            raise ManifestError(f"{key}: duplicate manifest change")
        seen.add(key)
        form = _resolve_manifest_form(iqm, ingredient_key, form_key)
        expected_digest = str(change.get("expected_form_sha256") or "").strip()
        if form_digest(form) != expected_digest:
            raise ManifestError(f"{key}: form precondition digest is stale")
        set_values = change.get("set")
        if not isinstance(set_values, dict) or not set_values:
            raise ManifestError(f"{key}: set must be a non-empty object")
        resolved.append((form, set_values, key))

    candidate = copy.deepcopy(iqm)
    applied = 0
    unchanged = 0
    for change, (_, set_values, _) in zip(changes, resolved, strict=True):
        form = _resolve_manifest_form(
            candidate,
            str(change["ingredient_key"]),
            str(change["form_key"]),
        )
        if all(form.get(field) == value for field, value in set_values.items()):
            unchanged += 1
            continue
        form.update(copy.deepcopy(set_values))
        applied += 1

    # Validate evidence entries touched by the manifest before any write.
    for change in changes:
        key = evidence_key(str(change["ingredient_key"]), str(change["form_key"]))
        form = _resolve_manifest_form(
            candidate,
            str(change["ingredient_key"]),
            str(change["form_key"]),
        )
        bio_score = form.get("bio_score")
        excellent = isinstance(bio_score, (int, float)) and bio_score >= EXCELLENT_BIO_SCORE
        evidence = form.get("form_evidence")
        if evidence is not None:
            issues = validate_form_evidence(evidence, label=key, excellent=excellent)
            if issues:
                raise ManifestError("\n".join(issues))

    # Preserve the IQM's human-readable Unicode audit prose. Escaping every
    # dash, arrow, and symbol would turn a targeted evidence migration into a
    # repository-wide formatting diff.
    payload = json.dumps(candidate, indent=2, ensure_ascii=False) + "\n"
    iqm_path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{iqm_path.name}.",
        suffix=".tmp",
        dir=iqm_path.parent,
        text=True,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, iqm_path)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise

    return {"expected": len(changes), "applied": applied, "unchanged": unchanged}


def main(argv: list[str] | None = None) -> int:
    scripts_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=("audit", "verify-live", "apply"),
    )
    parser.add_argument(
        "--iqm",
        type=Path,
        default=scripts_dir / "data" / "ingredient_quality_map.json",
    )
    parser.add_argument(
        "--backlog",
        type=Path,
        default=scripts_dir / "data" / "iqm_excellent_evidence_backlog.json",
    )
    parser.add_argument("--products", type=Path)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args(argv)

    try:
        if args.command == "apply":
            if args.manifest is None:
                parser.error("apply requires --manifest")
            print(json.dumps(apply_manifest_file(args.iqm, args.manifest), indent=2))
            return 0

        iqm = _load_json_object(args.iqm, label="IQM")
        if args.command == "audit":
            backlog = load_backlog_file(args.backlog)
            problems = validate_iqm_form_evidence(iqm, backlog=backlog)
            if args.products is not None:
                usage = catalog_form_usage(args.products)
                for gap in catalog_evidence_gaps(iqm, usage):
                    problems.extend(gap["issues"])
            if problems:
                print("\n".join(problems), file=sys.stderr)
                return 1
            print("IQM form-evidence audit passed")
            return 0

        from api_audit.normalize_clinical_pubmed import fetch_articles_for_pmids
        from api_audit.pubmed_client import PubMedClient

        pmids = collect_pubmed_pmids(iqm)
        articles = fetch_articles_for_pmids(PubMedClient(), pmids, batch_size=100)
        problems = verify_pubmed_content(
            iqm,
            {
                str(article.get("pmid")): article
                for article in articles
                if article.get("pmid")
            },
        )
        if problems:
            print("\n".join(problems), file=sys.stderr)
            return 1
        print(f"Live PubMed verification passed for {len(pmids)} PMID(s)")
        return 0
    except ManifestError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


__all__ = [
    "ManifestError",
    "apply_manifest_file",
    "backlog_initial_digest",
    "build_initial_backlog",
    "catalog_evidence_gaps",
    "catalog_form_usage",
    "collect_pubmed_pmids",
    "evidence_key",
    "form_digest",
    "load_backlog_file",
    "validate_exported_form_evidence",
    "validate_form_evidence",
    "validate_iqm_form_evidence",
    "verify_pubmed_content",
]


if __name__ == "__main__":
    raise SystemExit(main())
