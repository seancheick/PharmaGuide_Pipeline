#!/usr/bin/env python3
"""Locked analysis for the PharmaGuide V4 blinded reviewer benchmark.

The development path refuses a sealed holdout filename before reading it.
Reviewer identity, responses, and the analysis implementation are content
locked before the development baseline may be opened.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import re
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import urlsplit


PILLAR_REVIEW_FIELDS = (
    "formulation_0_20",
    "dose_0_20",
    "evidence_0_20",
    "transparency_0_15",
    "verification_0_15",
    "formula_quality_checks_0_10",
)
PILLAR_ENGINE_FIELDS = (
    "pillar_formulation_v4",
    "pillar_dose_v4",
    "pillar_evidence_v4",
    "pillar_transparency_v4",
    "pillar_verification_v4",
    "pillar_safety_hygiene_v4",
)
RESPONSE_CONTRACT_VERSION = "2.0.0"
ATTESTATION_FIELDS = (
    "ai_assistance_used",
    "prior_ai_review_seen",
    "engine_output_seen",
)
# One ordered schema for the freeze, document parser, and response validator.
# Its implementation stays here, inside the manifest's analysis-script hash.
RESPONSE_FIELDS = (
    "benchmark_id",
    "review_sequence",
    "reviewer_slot",
    "reviewer_id",
    "reviewer_order",
    "review_round",
    "correction_reason",
    *ATTESTATION_FIELDS,
    *PILLAR_REVIEW_FIELDS,
    "overall_0_100",
    "product_safety_status",
    "safety_concern_driver",
    "assessment_confidence",
    "label_facts_sufficient",
    "source_citations_json",
    "rationale",
    "protocol_deviation",
)
RESPONSE_REQUIRED_FIELDS = frozenset(RESPONSE_FIELDS)
REGISTRY_REQUIRED_FIELDS = frozenset({
    "reviewer_slot",
    "reviewer_id",
    "panel_role",
    "credential_type",
    "credential_detail",
    "license_jurisdiction",
    "license_status",
    "license_verification_source",
    "supplement_experience_years",
    "evidence_appraisal_experience_years",
    "conflicts_json",
    "training_completed_on",
    "training_assessment_score",
    "protocol_version",
    "independence_attested_on",
    "data_use_attested_on",
    "registered_on",
})


class AnalysisContractError(ValueError):
    """Raised when a frozen benchmark contract would be violated."""


def _as_float(value: Any, *, field: str) -> float:
    if isinstance(value, bool):
        raise AnalysisContractError(f"{field} must be numeric, not bool")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise AnalysisContractError(f"{field} must be numeric") from exc
    if not math.isfinite(number):
        raise AnalysisContractError(f"{field} must be finite")
    return number


def _as_int(value: Any, *, field: str) -> int:
    number = _as_float(value, field=field)
    if not number.is_integer():
        raise AnalysisContractError(f"{field} must be an integer")
    return int(number)


def _nonempty(value: Any, *, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise AnalysisContractError(f"{field} is required")
    return text


def _json_list(value: Any, *, field: str) -> list[Any]:
    if isinstance(value, list):
        parsed = value
    else:
        try:
            parsed = json.loads(str(value or ""))
        except json.JSONDecodeError as exc:
            raise AnalysisContractError(f"{field} must be valid JSON") from exc
    if not isinstance(parsed, list):
        raise AnalysisContractError(f"{field} must be a JSON list")
    return parsed


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise AnalysisContractError(f"{path} must contain a JSON object")
    return payload


def _load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def validate_response_contract(spec: Mapping[str, Any]) -> dict[str, Any]:
    """Reject legacy contracts; never infer a new contract for old answers."""
    if spec.get("response_contract_version") != RESPONSE_CONTRACT_VERSION:
        raise AnalysisContractError(
            "legacy or missing response contract; a new versioned freeze is required"
        )
    contract = dict(spec.get("rating_contract") or {})
    limits = contract.get("pillar_limits") or {}
    if set(limits) != set(PILLAR_REVIEW_FIELDS):
        raise AnalysisContractError("rating contract requires all six pillar_limits")
    if any(_as_float(value, field="pillar limit") <= 0 for value in limits.values()):
        raise AnalysisContractError("pillar limits must be positive")
    if _as_float(contract.get("increment"), field="rating increment") <= 0:
        raise AnalysisContractError("rating increment must be positive")
    if _as_float(contract.get("arithmetic_tolerance"), field="arithmetic tolerance") < 0:
        raise AnalysisContractError("arithmetic tolerance cannot be negative")
    for field in ("confidence_values", "label_sufficiency_values", "attestation_values"):
        if not isinstance(contract.get(field), list) or not contract[field]:
            raise AnalysisContractError(f"rating contract requires {field}")
    if set(contract["attestation_values"]) != {"yes", "no", "unknown"}:
        raise AnalysisContractError("attestation values must be yes/no/unknown")
    return contract


def validate_packet_sequences(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    """Validate the full blinded packet's canonical sequence, not rater order."""
    sequences: dict[str, int] = {}
    for row in rows:
        bid = _nonempty(row.get("benchmark_id"), field="packet benchmark_id")
        if bid in sequences:
            raise AnalysisContractError("duplicate packet benchmark_id")
        sequences[bid] = _as_int(row.get("review_sequence"), field="packet review_sequence")
    if not sequences or set(sequences.values()) != set(range(1, len(sequences) + 1)):
        raise AnalysisContractError("packet review_sequence must be a complete 1-N permutation")
    return sequences


def validate_template_orders(
    rows: Iterable[Mapping[str, Any]],
    sequences: Mapping[str, int],
    spec: Mapping[str, Any],
) -> dict[int, dict[str, int]]:
    """Read frozen randomized assignments without deriving them from sequence."""
    validate_response_contract(spec)
    panel_size = _as_int((spec.get("primary_design") or {}).get("panel_size"), field="panel_size")
    if panel_size != 3:
        raise AnalysisContractError("primary design requires exactly three fixed reviewers")
    orders: dict[int, dict[str, int]] = {slot: {} for slot in range(1, panel_size + 1)}
    for row in rows:
        missing = RESPONSE_REQUIRED_FIELDS - set(row)
        if missing:
            raise AnalysisContractError(f"response template missing fields: {sorted(missing)}")
        bid = str(row.get("benchmark_id") or "")
        slot = _as_int(row.get("reviewer_slot"), field="template reviewer_slot")
        if bid not in sequences or slot not in orders:
            raise AnalysisContractError("response template has unknown product or reviewer slot")
        if bid in orders[slot]:
            raise AnalysisContractError("duplicate response template assignment")
        if _as_int(row.get("review_sequence"), field="template review_sequence") != sequences[bid]:
            raise AnalysisContractError("response template review_sequence does not match packet")
        orders[slot][bid] = _as_int(row.get("reviewer_order"), field="template reviewer_order")
    for slot, assigned in orders.items():
        if set(assigned) != set(sequences) or set(assigned.values()) != set(range(1, len(sequences) + 1)):
            raise AnalysisContractError(f"template slot {slot} reviewer_order must be a complete 1-N permutation")
    return orders


def load_frozen_response_inputs(
    *, manifest_path: Path, analysis_spec_path: Path, analysis_script_path: Path,
    reviewer_packet_path: Path, reviewer_template_path: Path,
) -> dict[str, Any]:
    """Load only blinded inputs and verify their freeze provenance."""
    manifest, spec = _load_json(manifest_path), _load_json(analysis_spec_path)
    validate_response_contract(spec)
    if not spec.get("freeze_id") or manifest.get("freeze_id") != spec["freeze_id"]:
        raise AnalysisContractError("analysis spec freeze_id does not match benchmark manifest")
    contract = dict(manifest.get("analysis_contract") or {})
    if contract.get("response_contract_version") != RESPONSE_CONTRACT_VERSION:
        raise AnalysisContractError("legacy manifest; a new response-contract freeze is required")
    hashes = {
        "manifest_sha256": _sha256(manifest_path),
        "analysis_spec_sha256": _sha256(analysis_spec_path),
        "analysis_script_sha256": _sha256(analysis_script_path),
        "reviewer_packet_sha256": _sha256(reviewer_packet_path),
        "reviewer_template_sha256": _sha256(reviewer_template_path),
    }
    for field in ("analysis_spec_sha256", "analysis_script_sha256"):
        if contract.get(field) != hashes[field]:
            raise AnalysisContractError(f"{field} does not match benchmark manifest")
    for name, field in (("reviewer_packet.csv", "reviewer_packet_sha256"),
                        ("reviewer_response_template.csv", "reviewer_template_sha256")):
        if ((manifest.get("artifacts") or {}).get(name) or {}).get("sha256") != hashes[field]:
            raise AnalysisContractError(f"{field} does not match benchmark manifest")
    packet = _load_csv(reviewer_packet_path)
    sequences = validate_packet_sequences(packet)
    orders = validate_template_orders(_load_csv(reviewer_template_path), sequences, spec)
    expected_ratings = _as_int((spec.get("primary_design") or {}).get("required_ratings"), field="required_ratings")
    if expected_ratings != len(sequences) * len(orders):
        raise AnalysisContractError("full packet rating count does not match analysis spec")
    return {"manifest": manifest, "spec": spec, "packet": packet,
            "sequences": sequences, "orders": orders, "hashes": hashes}


def validate_reviewer_registry(
    rows: Iterable[Mapping[str, Any]],
    spec: Mapping[str, Any],
) -> dict[int, dict[str, Any]]:
    """Validate and return the fixed primary panel keyed by reviewer slot."""
    source_rows = [dict(row) for row in rows]
    if not source_rows:
        raise AnalysisContractError("reviewer registry is empty")
    for index, row in enumerate(source_rows, start=1):
        missing = REGISTRY_REQUIRED_FIELDS - set(row)
        if missing:
            raise AnalysisContractError(
                f"registry row {index} missing fields: {sorted(missing)}"
            )

    reviewer_ids = [
        _nonempty(row.get("reviewer_id"), field="reviewer_id")
        for row in source_rows
    ]
    if len(set(reviewer_ids)) != len(reviewer_ids):
        raise AnalysisContractError("reviewer IDs must be unique")

    design = dict(spec.get("primary_design") or {})
    panel_size = _as_int(
        design.get("panel_size"),
        field="primary_design.panel_size",
    )
    if panel_size != 3:
        raise AnalysisContractError("primary design requires exactly three fixed reviewers")
    primary_rows = [
        row for row in source_rows
        if str(row.get("panel_role") or "").strip().lower() == "primary"
    ]
    if len(primary_rows) != panel_size:
        raise AnalysisContractError(
            f"primary panel requires exactly {panel_size} reviewers"
        )

    panel: dict[int, dict[str, Any]] = {}
    clinical_credentials = {
        str(value).strip().lower()
        for value in design.get("licensed_clinical_credentials") or []
    }
    licensed_count = 0
    expected_protocol = str(spec.get("protocol_version") or "")
    for row in primary_rows:
        slot = _as_int(row.get("reviewer_slot"), field="reviewer_slot")
        if slot in panel:
            raise AnalysisContractError("primary reviewer slots must be unique")
        reviewer_id = _nonempty(row.get("reviewer_id"), field="reviewer_id")
        credential = _nonempty(
            row.get("credential_type"),
            field=f"{reviewer_id}.credential_type",
        ).lower()
        _nonempty(
            row.get("credential_detail"),
            field=f"{reviewer_id}.credential_detail",
        )
        conflicts = _json_list(
            row.get("conflicts_json"),
            field=f"{reviewer_id}.conflicts_json",
        )
        if conflicts:
            raise AnalysisContractError(
                "primary panel must be conflict-free across the frozen sample"
            )

        supplement_years = _as_float(
            row.get("supplement_experience_years"),
            field=f"{reviewer_id}.supplement_experience_years",
        )
        evidence_years = _as_float(
            row.get("evidence_appraisal_experience_years"),
            field=f"{reviewer_id}.evidence_appraisal_experience_years",
        )
        if supplement_years < 0 or evidence_years < 0:
            raise AnalysisContractError("experience years cannot be negative")
        if supplement_years == 0 and evidence_years == 0:
            raise AnalysisContractError(
                f"{reviewer_id} has no relevant recorded experience"
            )

        if credential in clinical_credentials:
            if str(row.get("license_status") or "").strip().lower() != (
                "active_verified"
            ):
                raise AnalysisContractError(
                    f"{reviewer_id} clinical license is not active_verified"
                )
            _nonempty(
                row.get("license_jurisdiction"),
                field=f"{reviewer_id}.license_jurisdiction",
            )
            _nonempty(
                row.get("license_verification_source"),
                field=f"{reviewer_id}.license_verification_source",
            )
            licensed_count += 1

        training_score = _as_float(
            row.get("training_assessment_score"),
            field=f"{reviewer_id}.training_assessment_score",
        )
        if not 0 <= training_score <= 100:
            raise AnalysisContractError(
                f"{reviewer_id} training score must be 0-100"
            )
        for field in (
            "training_completed_on",
            "independence_attested_on",
            "data_use_attested_on",
            "registered_on",
        ):
            _nonempty(row.get(field), field=f"{reviewer_id}.{field}")
        if str(row.get("protocol_version") or "") != expected_protocol:
            raise AnalysisContractError(
                f"{reviewer_id} trained on the wrong protocol version"
            )
        normalized = dict(row)
        normalized["reviewer_slot"] = slot
        normalized["reviewer_id"] = reviewer_id
        normalized["credential_type"] = credential
        panel[slot] = normalized

    expected_slots = set(range(1, panel_size + 1))
    if set(panel) != expected_slots:
        raise AnalysisContractError(
            f"primary reviewer slots must be {sorted(expected_slots)}"
        )
    required_licensed = _as_int(
        design.get("licensed_clinical_reviewers_required"),
        field="licensed_clinical_reviewers_required",
    )
    if licensed_count < required_licensed:
        raise AnalysisContractError(
            f"primary panel requires {required_licensed} licensed clinical "
            "reviewers"
        )
    return dict(sorted(panel.items()))


def _validate_source_citations(
    value: Any,
    *,
    benchmark_id: str,
    reviewer_id: str,
) -> list[Any]:
    citations = _json_list(
        value,
        field=f"{benchmark_id}/{reviewer_id}.source_citations_json",
    )
    if not citations:
        raise AnalysisContractError(
            f"{benchmark_id}/{reviewer_id} requires a source citation"
        )
    for citation in citations:
        if isinstance(citation, str):
            if not citation.strip():
                raise AnalysisContractError("source citation cannot be blank")
            text = citation.strip()
            url = urlsplit(text)
            valid_url = url.scheme in {"https", "http"} and bool(url.hostname) and not re.search(r"\s", text)
            valid_id = re.fullmatch(r"(?:PMID\s*:?\s*)?[1-9][0-9]*|(?:DOI\s*:?\s*)?10\.[0-9]{4,9}/\S+", text, re.I)
            if not valid_url and not valid_id:
                raise AnalysisContractError("source citation must be a PMID, DOI, or HTTP(S) URL")
            continue
        if not isinstance(citation, dict):
            raise AnalysisContractError(
                "each source citation must be a string or object"
            )
        identity = (
            citation.get("id")
            or citation.get("pmid")
            or citation.get("doi")
            or citation.get("url")
        )
        if not str(identity or "").strip():
            raise AnalysisContractError(
                "source citation object needs PMID, DOI, ID, or URL"
            )
        if not str(citation.get("supports") or "").strip():
            raise AnalysisContractError(
                "source citation object needs a supports statement"
            )
    return citations


def validate_and_select_responses(
    rows: Iterable[Mapping[str, Any]],
    panel: Mapping[int, Mapping[str, Any]],
    benchmark_sequences: Mapping[str, int],
    spec: Mapping[str, Any],
    *,
    reviewer_orders: Mapping[int, Mapping[str, int]] | None = None,
) -> list[dict[str, Any]]:
    """Validate append-only responses and select each latest review round."""
    source_rows = [dict(row) for row in rows]
    contract = validate_response_contract(spec)
    increment = _as_float(contract.get("increment"), field="rating increment")
    tolerance = _as_float(
        contract.get("arithmetic_tolerance"),
        field="arithmetic tolerance",
    )
    safety_values = {
        str(value)
        for value in spec.get("safety_severity_low_to_high") or []
    }
    safety_values.add(str(spec.get("safety_not_assessed_value") or ""))
    grouped: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)

    for row_number, original in enumerate(source_rows, start=2):
        missing = RESPONSE_REQUIRED_FIELDS - set(original)
        if missing:
            raise AnalysisContractError(
                f"response row {row_number} missing fields: {sorted(missing)}"
            )
        benchmark_id = _nonempty(
            original.get("benchmark_id"),
            field=f"row {row_number}.benchmark_id",
        )
        if benchmark_id not in benchmark_sequences:
            raise AnalysisContractError(
                f"unknown benchmark_id {benchmark_id}"
            )
        sequence = _as_int(
            original.get("review_sequence"),
            field=f"{benchmark_id}.review_sequence",
        )
        if sequence != int(benchmark_sequences[benchmark_id]):
            raise AnalysisContractError(
                f"{benchmark_id} review sequence does not match packet"
            )
        slot = _as_int(
            original.get("reviewer_slot"),
            field=f"{benchmark_id}.reviewer_slot",
        )
        if slot not in panel:
            raise AnalysisContractError(
                f"{benchmark_id} uses unregistered reviewer slot {slot}"
            )
        reviewer_id = _nonempty(
            original.get("reviewer_id"),
            field=f"{benchmark_id}.reviewer_id",
        )
        if reviewer_id != panel[slot]["reviewer_id"]:
            raise AnalysisContractError(
                f"{benchmark_id} reviewer does not match fixed slot {slot}"
            )
        reviewer_order = _as_int(
            original.get("reviewer_order"),
            field=f"{benchmark_id}/{reviewer_id}.reviewer_order",
        )
        if reviewer_order < 1:
            raise AnalysisContractError("reviewer_order must be positive")
        if reviewer_orders is not None and reviewer_order != reviewer_orders.get(slot, {}).get(benchmark_id):
            raise AnalysisContractError(f"{benchmark_id}/{reviewer_id}.reviewer_order does not match frozen template")
        review_round = _as_int(
            original.get("review_round"),
            field=f"{benchmark_id}/{reviewer_id}.review_round",
        )
        if review_round < 1:
            raise AnalysisContractError("review_round must be positive")
        correction_reason = str(
            original.get("correction_reason") or ""
        ).strip()
        if review_round > 1 and not correction_reason:
            raise AnalysisContractError(
                f"{benchmark_id}/{reviewer_id} round {review_round} "
                "requires correction_reason"
            )

        numeric: dict[str, float] = {}
        for field in PILLAR_REVIEW_FIELDS:
            maximum = _as_float(contract["pillar_limits"][field], field="pillar limit")
            value = _as_float(
                original.get(field),
                field=f"{benchmark_id}/{reviewer_id}.{field}",
            )
            if not 0 <= value <= maximum:
                raise AnalysisContractError(
                    f"{benchmark_id}/{reviewer_id}.{field} outside 0-{maximum:g}"
                )
            if abs((value / increment) - round(value / increment)) > tolerance:
                raise AnalysisContractError(
                    f"{benchmark_id}/{reviewer_id}.{field} must use "
                    f"{increment:g}-point increments"
                )
            numeric[field] = value
        overall = _as_float(
            original.get("overall_0_100"),
            field=f"{benchmark_id}/{reviewer_id}.overall_0_100",
        )
        expected_overall = sum(numeric.values())
        if abs(overall - expected_overall) > tolerance:
            raise AnalysisContractError(
                f"{benchmark_id}/{reviewer_id} overall does not equal "
                "pillar sum"
            )
        safety = str(original.get("product_safety_status") or "").strip()
        if safety not in safety_values:
            raise AnalysisContractError(
                f"{benchmark_id}/{reviewer_id} invalid safety status"
            )
        safety_driver = str(
            original.get("safety_concern_driver") or ""
        ).strip()
        if safety in {"caution", "unsafe", "blocked"} and not safety_driver:
            raise AnalysisContractError(
                f"{benchmark_id}/{reviewer_id} safety_concern_driver "
                "is required"
            )
        confidence = str(
            original.get("assessment_confidence") or ""
        ).strip()
        if confidence not in contract["confidence_values"]:
            raise AnalysisContractError(
                f"{benchmark_id}/{reviewer_id} invalid confidence"
            )
        sufficient = str(
            original.get("label_facts_sufficient") or ""
        ).strip().lower()
        if sufficient not in contract["label_sufficiency_values"]:
            raise AnalysisContractError(
                f"{benchmark_id}/{reviewer_id} invalid label sufficiency"
            )
        citations = _validate_source_citations(
            original.get("source_citations_json"),
            benchmark_id=benchmark_id,
            reviewer_id=reviewer_id,
        )
        _nonempty(
            original.get("rationale"),
            field=f"{benchmark_id}/{reviewer_id}.rationale",
        )
        deviation = str(original.get("protocol_deviation") or "").strip()
        if deviation.lower() == "none":
            deviation = ""
        attestations = {}
        for field in ATTESTATION_FIELDS:
            value = str(original.get(field) or "").strip()
            if value not in contract["attestation_values"]:
                raise AnalysisContractError(f"{benchmark_id}/{reviewer_id}.{field} must be yes/no/unknown")
            attestations[field] = value
        normalized = dict(original)
        normalized.update(numeric)
        normalized.update(attestations)
        normalized.update({
            "benchmark_id": benchmark_id,
            "review_sequence": sequence,
            "reviewer_slot": slot,
            "reviewer_id": reviewer_id,
            "reviewer_order": reviewer_order,
            "review_round": review_round,
            "overall_0_100": overall,
            "product_safety_status": safety,
            "safety_concern_driver": safety_driver,
            "assessment_confidence": confidence,
            "label_facts_sufficient": sufficient,
            "source_citations_json": citations,
            "correction_reason": correction_reason,
            "protocol_deviation": deviation,
        })
        grouped[(benchmark_id, slot)].append(normalized)

    expected_keys = {
        (benchmark_id, slot)
        for benchmark_id in benchmark_sequences
        for slot in panel
    }
    if set(grouped) != expected_keys:
        missing = sorted(expected_keys - set(grouped))
        extra = sorted(set(grouped) - expected_keys)
        raise AnalysisContractError(
            f"responses do not cover the fixed panel; missing={missing}, "
            f"extra={extra}"
        )

    selected: list[dict[str, Any]] = []
    for key in sorted(grouped):
        rounds = sorted(
            row["review_round"] for row in grouped[key]
        )
        if len(rounds) != len(set(rounds)):
            raise AnalysisContractError(
                f"{key} contains duplicate review_round values"
            )
        if rounds != list(range(1, max(rounds) + 1)):
            raise AnalysisContractError(
                f"{key} review rounds must be append-only and contiguous"
            )
        reviewer_orders = {
            row["reviewer_order"] for row in grouped[key]
        }
        if len(reviewer_orders) != 1:
            raise AnalysisContractError(
                f"{key} reviewer_order changed across review rounds"
            )
        latest = dict(max(
            grouped[key],
            key=lambda row: row["review_round"],
        ))
        # A correction cannot erase earlier exposure or compromised review.
        exclusions: set[str] = set()
        for previous in grouped[key]:
            for field in ATTESTATION_FIELDS:
                if previous[field] != "no":
                    exclusions.add(f"{field}={previous[field]}")
            if previous["protocol_deviation"]:
                exclusions.add(f"protocol_deviation: {previous['protocol_deviation']}")
        latest["primary_exclusion_reasons"] = sorted(exclusions)
        selected.append(latest)

    product_count = len(benchmark_sequences)
    expected_order = set(range(1, product_count + 1))
    for slot in panel:
        actual_order = {
            row["reviewer_order"]
            for row in selected
            if row["reviewer_slot"] == slot
        }
        if actual_order != expected_order:
            raise AnalysisContractError(
                f"reviewer slot {slot} reviewer_order must be a complete "
                f"1-{product_count} permutation"
            )

    required_ratings = len(benchmark_sequences) * len(panel)
    if len(selected) != required_ratings:
        raise AnalysisContractError(
            f"expected {required_ratings} selected ratings, got {len(selected)}"
        )
    return selected


def icc_absolute_agreement(
    matrix: Sequence[Sequence[float]],
) -> dict[str, float]:
    """Return ICC(A,1) and ICC(A,k) for a complete target-by-rater matrix."""
    rows = [list(map(float, row)) for row in matrix]
    if len(rows) < 2:
        raise AnalysisContractError("ICC requires at least two products")
    rater_count = len(rows[0])
    if rater_count < 2 or any(len(row) != rater_count for row in rows):
        raise AnalysisContractError(
            "ICC requires a complete rectangular reviewer matrix"
        )
    target_count = len(rows)
    grand = mean(value for row in rows for value in row)
    target_means = [mean(row) for row in rows]
    rater_means = [
        mean(row[index] for row in rows)
        for index in range(rater_count)
    ]
    ss_target = rater_count * sum(
        (value - grand) ** 2 for value in target_means
    )
    ss_rater = target_count * sum(
        (value - grand) ** 2 for value in rater_means
    )
    ss_total = sum(
        (value - grand) ** 2 for row in rows for value in row
    )
    ss_error = ss_total - ss_target - ss_rater
    ms_target = ss_target / (target_count - 1)
    ms_rater = ss_rater / (rater_count - 1)
    ms_error = ss_error / (
        (target_count - 1) * (rater_count - 1)
    )
    numerator = ms_target - ms_error
    denominator_single = (
        ms_target
        + (rater_count - 1) * ms_error
        + (rater_count * (ms_rater - ms_error) / target_count)
    )
    denominator_mean = (
        ms_target + ((ms_rater - ms_error) / target_count)
    )
    if denominator_single == 0 or denominator_mean == 0:
        raise AnalysisContractError("ICC is undefined for constant ratings")
    return {
        "icc_a1": numerator / denominator_single,
        "icc_ak": numerator / denominator_mean,
    }


def _percentile(values: Sequence[float], probability: float) -> float:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        raise AnalysisContractError("cannot take percentile of empty values")
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] + (
        (ordered[upper] - ordered[lower]) * fraction
    )


def _bootstrap_ci(
    values: Sequence[float],
    *,
    iterations: int,
    confidence_level: float,
    seed: str,
    statistic=mean,
) -> list[float]:
    if not values:
        raise AnalysisContractError("bootstrap requires values")
    rng = random.Random(seed)
    source = list(map(float, values))
    estimates = [
        float(statistic([
            source[rng.randrange(len(source))]
            for _ in source
        ]))
        for _ in range(iterations)
    ]
    alpha = (1.0 - confidence_level) / 2.0
    return [
        round(_percentile(estimates, alpha), 6),
        round(_percentile(estimates, 1.0 - alpha), 6),
    ]


def _bootstrap_icc(
    matrix: Sequence[Sequence[float]],
    *,
    iterations: int,
    confidence_level: float,
    seed: str,
) -> dict[str, list[float] | None]:
    rng = random.Random(seed)
    source = [list(row) for row in matrix]
    single: list[float] = []
    panel: list[float] = []
    for _ in range(iterations):
        sample = [
            source[rng.randrange(len(source))]
            for _ in source
        ]
        try:
            result = icc_absolute_agreement(sample)
        except AnalysisContractError:
            continue
        if math.isfinite(result["icc_a1"]):
            single.append(result["icc_a1"])
        if math.isfinite(result["icc_ak"]):
            panel.append(result["icc_ak"])
    if not single or not panel:
        return {"icc_a1_ci": None, "icc_ak_ci": None}
    alpha = (1.0 - confidence_level) / 2.0
    return {
        "icc_a1_ci": [
            round(_percentile(single, alpha), 6),
            round(_percentile(single, 1.0 - alpha), 6),
        ],
        "icc_ak_ci": [
            round(_percentile(panel, alpha), 6),
            round(_percentile(panel, 1.0 - alpha), 6),
        ],
    }


def _ranks(values: Sequence[float]) -> list[float]:
    indexed = sorted(enumerate(values), key=lambda item: item[1])
    ranks = [0.0] * len(values)
    cursor = 0
    while cursor < len(indexed):
        end = cursor + 1
        while end < len(indexed) and indexed[end][1] == indexed[cursor][1]:
            end += 1
        average_rank = ((cursor + 1) + end) / 2.0
        for original_index, _ in indexed[cursor:end]:
            ranks[original_index] = average_rank
        cursor = end
    return ranks


def _spearman(left: Sequence[float], right: Sequence[float]) -> float | None:
    if len(left) != len(right) or len(left) < 2:
        return None
    x = _ranks(left)
    y = _ranks(right)
    x_mean = mean(x)
    y_mean = mean(y)
    numerator = sum(
        (a - x_mean) * (b - y_mean)
        for a, b in zip(x, y)
    )
    denominator = math.sqrt(
        sum((a - x_mean) ** 2 for a in x)
        * sum((b - y_mean) ** 2 for b in y)
    )
    return numerator / denominator if denominator else None


def _tier_for_score(score: float, spec: Mapping[str, Any]) -> str:
    thresholds = sorted(
        spec.get("tier_thresholds") or [],
        key=lambda row: float(row["min"]),
        reverse=True,
    )
    for row in thresholds:
        if score >= float(row["min"]):
            return str(row["name"])
    raise AnalysisContractError("tier thresholds do not cover score")


def _score_metrics(
    engine: Sequence[float],
    consensus: Sequence[float],
    *,
    engine_tiers: Sequence[str],
    consensus_tiers: Sequence[str],
    tier_order: Sequence[str],
    bootstrap: Mapping[str, Any],
    seed_suffix: str,
) -> dict[str, Any]:
    errors = [
        engine_value - consensus_value
        for engine_value, consensus_value in zip(engine, consensus)
    ]
    absolute = [abs(value) for value in errors]
    tier_index = {tier: index for index, tier in enumerate(tier_order)}
    exact = [
        left == right
        for left, right in zip(engine_tiers, consensus_tiers)
    ]
    within_one = [
        abs(tier_index[left] - tier_index[right]) <= 1
        for left, right in zip(engine_tiers, consensus_tiers)
    ]
    iterations = int(bootstrap["iterations"])
    confidence = float(bootstrap["confidence_level"])
    seed = f"{bootstrap['seed']}:{seed_suffix}"
    return {
        "n": len(errors),
        "mean_signed_error": round(mean(errors), 6),
        "signed_bias_ci": _bootstrap_ci(
            errors,
            iterations=iterations,
            confidence_level=confidence,
            seed=seed,
        ),
        "mean_absolute_error": round(mean(absolute), 6),
        "spearman_rank_correlation": (
            None
            if (rho := _spearman(engine, consensus)) is None
            else round(rho, 6)
        ),
        "exact_tier_agreement": round(sum(exact) / len(exact), 6),
        "within_one_tier_agreement": round(
            sum(within_one) / len(within_one),
            6,
        ),
    }


def _consensus_records(
    baseline_rows: Sequence[Mapping[str, Any]],
    responses: Sequence[Mapping[str, Any]],
    spec: Mapping[str, Any],
) -> list[dict[str, Any]]:
    by_benchmark: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for response in responses:
        by_benchmark[str(response["benchmark_id"])].append(response)
    safety_order = {
        value: index
        for index, value in enumerate(
            spec.get("safety_severity_low_to_high") or []
        )
    }
    records: list[dict[str, Any]] = []
    for baseline in baseline_rows:
        benchmark_id = str(baseline["benchmark_id"])
        ratings = sorted(
            by_benchmark[benchmark_id],
            key=lambda row: int(row["reviewer_slot"]),
        )
        consensus = {
            field: float(median(
                float(row[field]) for row in ratings
            ))
            for field in (*PILLAR_REVIEW_FIELDS, "overall_0_100")
        }
        statuses = [
            str(row["product_safety_status"])
            for row in ratings
        ]
        counts = Counter(statuses)
        majority_status, majority_count = counts.most_common(1)[0]
        if majority_count < 2:
            majority_status = "no_consensus"
        engine_safety = str(baseline.get("product_safety_status") or "")
        reviewer_severities = [
            safety_order.get(status, -1) for status in statuses
        ]
        engine_severity = safety_order.get(engine_safety, -1)
        records.append({
            "baseline": dict(baseline),
            "ratings": ratings,
            "consensus": consensus,
            "safety_majority": majority_status,
            "potential_safety_undercall": (
                engine_severity >= 0
                and any(
                    severity > engine_severity
                    for severity in reviewer_severities
                )
            ),
            "potential_safety_overcall": (
                engine_severity >= 0
                and reviewer_severities
                and all(
                    severity >= 0 and severity < engine_severity
                    for severity in reviewer_severities
                )
            ),
        })
    return records


def _agreement_payload(
    records: Sequence[Mapping[str, Any]],
    *,
    field: str,
    bootstrap: Mapping[str, Any],
) -> dict[str, Any]:
    matrix = [
        [float(row[field]) for row in record["ratings"]]
        for record in records
    ]
    try:
        point = icc_absolute_agreement(matrix)
    except AnalysisContractError as exc:
        unavailable_reasons = {
            "ICC is undefined for constant ratings": "constant_ratings",
            "ICC requires at least two products": "fewer_than_two_products",
        }
        reason = unavailable_reasons.get(str(exc))
        if reason is None:
            raise
        return {
            "status": "not_estimable",
            "reason": reason,
            "icc_a1": None,
            "icc_a3": None,
            "icc_a1_ci": None,
            "icc_a3_ci": None,
        }
    intervals = _bootstrap_icc(
        matrix,
        iterations=int(bootstrap["iterations"]),
        confidence_level=float(bootstrap["confidence_level"]),
        seed=f"{bootstrap['seed']}:icc:{field}",
    )
    return {
        "status": "estimated",
        "icc_a1": round(point["icc_a1"], 6),
        "icc_a3": round(point["icc_ak"], 6),
        "icc_a1_ci": intervals["icc_a1_ci"],
        "icc_a3_ci": intervals["icc_ak_ci"],
    }


def analyze_benchmark(
    baseline_rows: Iterable[Mapping[str, Any]],
    response_rows: Iterable[Mapping[str, Any]],
    registry_rows: Iterable[Mapping[str, Any]],
    spec: Mapping[str, Any],
    *,
    stage: str,
    reviewer_packet_rows: Iterable[Mapping[str, Any]],
    reviewer_template_rows: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Run the pre-specified descriptive benchmark analysis."""
    baselines = [dict(row) for row in baseline_rows]
    if stage not in {"development", "holdout"}:
        raise AnalysisContractError("stage must be development or holdout")
    if not baselines:
        raise AnalysisContractError("baseline key is empty")
    if any(str(row.get("analysis_split")) != stage for row in baselines):
        raise AnalysisContractError(
            f"{stage} analysis received a different analysis_split"
        )
    benchmark_sequences: dict[str, int] = {}
    for row in baselines:
        benchmark_id = _nonempty(
            row.get("benchmark_id"),
            field="baseline benchmark_id",
        )
        if benchmark_id in benchmark_sequences:
            raise AnalysisContractError("duplicate baseline benchmark_id")
        benchmark_sequences[benchmark_id] = _as_int(
            row.get("review_sequence"),
            field=f"{benchmark_id}.review_sequence",
        )

    # Validate the complete frozen permutation BEFORE selecting a stage.
    # Original randomized orders remain sparse in development/holdout subsets.
    full_sequences = validate_packet_sequences(reviewer_packet_rows)
    orders = validate_template_orders(reviewer_template_rows, full_sequences, spec)
    if any(full_sequences.get(bid) != sequence for bid, sequence in benchmark_sequences.items()):
        raise AnalysisContractError("baseline review_sequence does not match frozen packet")
    panel = validate_reviewer_registry(registry_rows, spec)
    full_selected = validate_and_select_responses(
        response_rows,
        panel,
        full_sequences,
        spec,
        reviewer_orders=orders,
    )
    selected = [row for row in full_selected if row["benchmark_id"] in benchmark_sequences]
    all_records = _consensus_records(baselines, selected, spec)
    excluded_benchmark_ids = sorted({
        str(row["benchmark_id"])
        for row in selected
        if row["primary_exclusion_reasons"]
    })
    records = [
        record for record in all_records
        if str(record["baseline"]["benchmark_id"])
        not in excluded_benchmark_ids
    ]
    bootstrap = dict(spec.get("bootstrap") or {})
    tier_order = list(spec.get("tier_order_low_to_high") or [])
    sensitivity_scores = [float(record["consensus"]["overall_0_100"]) for record in all_records]
    sensitivity_overall = _score_metrics(
        [_as_float(record["baseline"].get("quality_score_v4_100"), field="quality_score_v4_100") for record in all_records],
        sensitivity_scores,
        engine_tiers=[str(record["baseline"].get("quality_tier")) for record in all_records],
        consensus_tiers=[_tier_for_score(score, spec) for score in sensitivity_scores],
        tier_order=tier_order, bootstrap=bootstrap,
        seed_suffix=f"{stage}:sensitivity_all_locked",
    )
    common = {
        "schema_version": "2.0.0",
        "analysis_version": spec.get("analysis_version"),
        "freeze_id": spec.get("freeze_id"),
        "stage": stage,
        "sample": {
            "analyzed_products": len(records),
            "selected_ratings": len(selected),
            "primary_ratings": len(records) * len(panel),
            "reviewer_panel_size": len(panel),
            "full_packet_products": len(full_sequences),
            "excluded_products": len(excluded_benchmark_ids),
            "excluded_benchmark_ids": excluded_benchmark_ids,
        },
        "primary_exclusions": [
            {"benchmark_id": row["benchmark_id"], "reviewer_id": row["reviewer_id"],
             "reasons": row["primary_exclusion_reasons"]}
            for row in selected if row["primary_exclusion_reasons"]
        ],
        "sensitivity_all_locked_responses": {
            "status": "exploratory_only",
            "independent_primary": False,
            "products": len(all_records),
            "overall": sensitivity_overall,
            "potential_safety_undercalls": sum(bool(record["potential_safety_undercall"]) for record in all_records),
            "potential_safety_overcalls": sum(bool(record["potential_safety_overcall"]) for record in all_records),
        },
    }
    if not records:
        return {
            **common,
            "status": "blocked_independent_primary_analysis",
            "primary_assessment": {
                "status": "blocked",
                "reason": "no_independent_complete_panel_products",
                "note": "Exposed/unknown responses remain exploratory; the fixed three-rater panel was not reduced.",
            },
            "overall": None, "pillars": {}, "agreement": {}, "strata": {}, "safety": {},
            "calibration": {"eligible": False, "decision_thresholds_status": (spec.get("decision_thresholds") or {}).get("status")},
        }

    engine_scores = [
        _as_float(
            record["baseline"].get("quality_score_v4_100"),
            field="quality_score_v4_100",
        )
        for record in records
    ]
    consensus_scores = [
        float(record["consensus"]["overall_0_100"])
        for record in records
    ]
    engine_tiers = [
        str(record["baseline"].get("quality_tier"))
        for record in records
    ]
    consensus_tiers = [
        _tier_for_score(score, spec)
        for score in consensus_scores
    ]
    overall = _score_metrics(
        engine_scores,
        consensus_scores,
        engine_tiers=engine_tiers,
        consensus_tiers=consensus_tiers,
        tier_order=tier_order,
        bootstrap=bootstrap,
        seed_suffix=f"{stage}:overall",
    )
    overall["signed_error_direction"] = (
        spec.get("metric_direction") or {}
    ).get("signed_error")

    agreement = {
        "overall_0_100": _agreement_payload(
            records,
            field="overall_0_100",
            bootstrap=bootstrap,
        )
    }
    pillars: dict[str, Any] = {}
    for review_field, engine_field in zip(
        PILLAR_REVIEW_FIELDS,
        PILLAR_ENGINE_FIELDS,
    ):
        engine_values = [
            _as_float(
                record["baseline"].get(engine_field),
                field=engine_field,
            )
            for record in records
        ]
        consensus_values = [
            float(record["consensus"][review_field])
            for record in records
        ]
        errors = [
            left - right
            for left, right in zip(engine_values, consensus_values)
        ]
        pillars[review_field] = {
            "n": len(errors),
            "mean_signed_error": round(mean(errors), 6),
            "signed_bias_ci": _bootstrap_ci(
                errors,
                iterations=int(bootstrap["iterations"]),
                confidence_level=float(bootstrap["confidence_level"]),
                seed=f"{bootstrap['seed']}:{stage}:pillar:{review_field}",
            ),
            "mean_absolute_error": round(
                mean(abs(value) for value in errors),
                6,
            ),
        }
        agreement[review_field] = _agreement_payload(
            records,
            field=review_field,
            bootstrap=bootstrap,
        )

    strata: dict[str, dict[str, Any]] = {}
    for stratum_field in ("archetype", "sample_cohort"):
        strata[stratum_field] = {}
        values = sorted({
            str(record["baseline"].get(stratum_field))
            for record in records
        })
        for value in values:
            subset = [
                record for record in records
                if str(record["baseline"].get(stratum_field)) == value
            ]
            subset_engine = [
                _as_float(
                    record["baseline"].get("quality_score_v4_100"),
                    field="quality_score_v4_100",
                )
                for record in subset
            ]
            subset_consensus = [
                float(record["consensus"]["overall_0_100"])
                for record in subset
            ]
            subset_engine_tiers = [
                str(record["baseline"].get("quality_tier"))
                for record in subset
            ]
            subset_consensus_tiers = [
                _tier_for_score(score, spec)
                for score in subset_consensus
            ]
            strata[stratum_field][value] = _score_metrics(
                subset_engine,
                subset_consensus,
                engine_tiers=subset_engine_tiers,
                consensus_tiers=subset_consensus_tiers,
                tier_order=tier_order,
                bootstrap=bootstrap,
                seed_suffix=f"{stage}:{stratum_field}:{value}",
            )

    undercalls = sum(
        bool(record["potential_safety_undercall"])
        for record in records
    )
    overcalls = sum(
        bool(record["potential_safety_overcall"])
        for record in records
    )
    undercall_queue = [
        {
            "benchmark_id": record["baseline"]["benchmark_id"],
            "engine_status": record["baseline"]["product_safety_status"],
            "reviewer_statuses": [
                row["product_safety_status"]
                for row in record["ratings"]
            ],
        }
        for record in records
        if record["potential_safety_undercall"]
    ]
    overcall_queue = [
        {
            "benchmark_id": record["baseline"]["benchmark_id"],
            "engine_status": record["baseline"]["product_safety_status"],
            "reviewer_statuses": [
                row["product_safety_status"]
                for row in record["ratings"]
            ],
        }
        for record in records
        if record["potential_safety_overcall"]
    ]
    thresholds = dict(spec.get("decision_thresholds") or {})
    return {
        **common,
        "status": "descriptive_only_calibration_frozen",
        "primary_assessment": {"status": "descriptive_only", "independent_complete_panel": True},
        "overall": overall,
        "pillars": pillars,
        "agreement": agreement,
        "strata": strata,
        "safety": {
            "potential_undercalls": undercalls,
            "potential_overcalls": overcalls,
            "requires_blinded_adjudication": undercalls > 0,
            "undercall_queue": undercall_queue,
            "overcall_queue": overcall_queue,
        },
        "calibration": {
            "eligible": bool(
                thresholds.get("calibration_eligibility", False)
            ),
            "decision_thresholds_status": thresholds.get("status"),
        },
    }


def assert_baseline_access(
    baseline_path: Path,
    *,
    stage: str,
    candidate_lock_path: Path | None = None,
) -> None:
    """Reject unauthorized baseline paths before opening them."""
    normalized_name = baseline_path.name.lower()
    if stage == "development":
        if "sealed" in normalized_name or "holdout" in normalized_name:
            raise AnalysisContractError(
                "development analyzer refuses sealed holdout before file read"
            )
        return
    if stage != "holdout":
        raise AnalysisContractError("unknown analysis stage")
    if candidate_lock_path is None or not candidate_lock_path.is_file():
        raise AnalysisContractError(
            "holdout analysis requires an existing candidate lock"
        )


def build_response_lock(
    *,
    manifest_path: Path,
    analysis_spec_path: Path,
    analysis_script_path: Path,
    reviewer_packet_path: Path,
    reviewer_template_path: Path,
    reviewer_registry_path: Path,
    responses_path: Path,
    locked_on: str,
) -> dict[str, Any]:
    """Validate complete blinded inputs and return their content lock."""
    frozen = load_frozen_response_inputs(
        manifest_path=manifest_path, analysis_spec_path=analysis_spec_path,
        analysis_script_path=analysis_script_path, reviewer_packet_path=reviewer_packet_path,
        reviewer_template_path=reviewer_template_path,
    )
    manifest, spec, benchmark_sequences = frozen["manifest"], frozen["spec"], frozen["sequences"]
    panel = validate_reviewer_registry(
        _load_csv(reviewer_registry_path),
        spec,
    )
    selected = validate_and_select_responses(
        _load_csv(responses_path),
        panel,
        benchmark_sequences,
        spec,
        reviewer_orders=frozen["orders"],
    )
    expected_ratings = _as_int(
        (spec.get("primary_design") or {}).get("required_ratings"),
        field="primary_design.required_ratings",
    )
    if len(selected) != expected_ratings:
        raise AnalysisContractError(
            "full response lock rating count does not match analysis spec"
        )
    return {
        "schema_version": "2.0.0",
        "response_contract_version": RESPONSE_CONTRACT_VERSION,
        "status": "locked",
        "freeze_id": manifest.get("freeze_id"),
        "locked_on": _nonempty(locked_on, field="locked_on"),
        **frozen["hashes"],
        "reviewer_registry_sha256": _sha256(reviewer_registry_path),
        "responses_sha256": _sha256(responses_path),
        "selected_rating_count": len(selected),
        "benchmark_product_count": len(benchmark_sequences),
        "exploratory_only_rating_count": sum(bool(row["primary_exclusion_reasons"]) for row in selected),
        "independent_complete_panel_products": len(set(benchmark_sequences) - {
            row["benchmark_id"] for row in selected if row["primary_exclusion_reasons"]
        }),
    }


def verify_response_lock(
    lock: Mapping[str, Any],
    *,
    manifest_path: Path,
    analysis_spec_path: Path,
    analysis_script_path: Path,
    reviewer_packet_path: Path,
    reviewer_template_path: Path,
    reviewer_registry_path: Path,
    responses_path: Path,
) -> None:
    """Fail when any locked response input or analysis artifact changed."""
    if lock.get("status") != "locked":
        raise AnalysisContractError("response lock status is not locked")
    if lock.get("response_contract_version") != RESPONSE_CONTRACT_VERSION:
        raise AnalysisContractError("legacy response lock; a new versioned freeze is required")
    expected = {
        "manifest_sha256": _sha256(manifest_path),
        "analysis_spec_sha256": _sha256(analysis_spec_path),
        "analysis_script_sha256": _sha256(analysis_script_path),
        "reviewer_packet_sha256": _sha256(reviewer_packet_path),
        "reviewer_template_sha256": _sha256(reviewer_template_path),
        "reviewer_registry_sha256": _sha256(reviewer_registry_path),
        "responses_sha256": _sha256(responses_path),
    }
    for field, actual in expected.items():
        if lock.get(field) != actual:
            raise AnalysisContractError(
                f"response lock {field} does not match current file"
            )
    frozen = load_frozen_response_inputs(
        manifest_path=manifest_path, analysis_spec_path=analysis_spec_path,
        analysis_script_path=analysis_script_path, reviewer_packet_path=reviewer_packet_path,
        reviewer_template_path=reviewer_template_path,
    )
    if lock.get("freeze_id") != frozen["manifest"].get("freeze_id"):
        raise AnalysisContractError("response lock freeze_id does not match manifest")


def validate_candidate_lock(
    candidate_lock: Mapping[str, Any],
    *,
    response_lock: Mapping[str, Any],
    response_lock_sha256: str,
    spec: Mapping[str, Any],
) -> None:
    """Validate the approved change record before any holdout key is read."""
    if candidate_lock.get("status") != "locked":
        raise AnalysisContractError("candidate lock is not locked")
    for field in (
        "freeze_id",
        "analysis_spec_sha256",
        "analysis_script_sha256",
    ):
        if candidate_lock.get(field) != response_lock.get(field):
            raise AnalysisContractError(
                f"candidate lock {field} does not match response lock"
            )
    if candidate_lock.get("response_lock_sha256") != response_lock_sha256:
        raise AnalysisContractError(
            "candidate lock response_lock_sha256 does not match"
        )
    for field in (
        "approved_by_statistician",
        "approved_by_clinical_owner",
    ):
        _nonempty(candidate_lock.get(field), field=f"candidate_lock.{field}")

    contract = dict(spec.get("candidate_lock_contract") or {})
    allowed_directions = {
        str(value)
        for value in contract.get("allowed_expected_directions") or (
            "increase_engine_score",
            "decrease_engine_score",
            "mixed_parameter_specific",
            "no_score_change_safety_only",
        )
    }
    candidates = candidate_lock.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise AnalysisContractError("candidate lock has no candidates")
    candidate_ids: set[str] = set()
    for index, candidate in enumerate(candidates, start=1):
        if not isinstance(candidate, dict):
            raise AnalysisContractError(
                f"candidate {index} must be a JSON object"
            )
        candidate_id = _nonempty(
            candidate.get("candidate_id"),
            field=f"candidate {index}.candidate_id",
        )
        if candidate_id in candidate_ids:
            raise AnalysisContractError("candidate IDs must be unique")
        candidate_ids.add(candidate_id)
        for field in (
            "implementation_commit",
            "mechanistic_link",
        ):
            _nonempty(
                candidate.get(field),
                field=f"{candidate_id}.{field}",
            )
        direction = _nonempty(
            candidate.get("expected_direction"),
            field=f"{candidate_id}.expected_direction",
        )
        if direction not in allowed_directions:
            raise AnalysisContractError(
                f"{candidate_id}.expected_direction is not allowed"
            )
        parameters = candidate.get("changed_parameters")
        if (
            not isinstance(parameters, list)
            or not parameters
            or any(not str(value).strip() for value in parameters)
        ):
            raise AnalysisContractError(
                f"{candidate_id}.changed_parameters must be nonempty"
            )
        if candidate.get("safety_regression_gate") != "must_not_worsen":
            raise AnalysisContractError(
                f"{candidate_id}.safety_regression_gate must_not_worsen"
            )


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Lock and analyze the V4 reviewer benchmark"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    lock_parser = subparsers.add_parser("lock-responses")
    for name in (
        "manifest",
        "analysis-spec",
        "reviewer-packet",
        "reviewer-template",
        "reviewer-registry",
        "responses",
        "output",
    ):
        lock_parser.add_argument(f"--{name}", required=True, type=Path)
    lock_parser.add_argument("--locked-on", required=True)

    for command in ("analyze-development", "analyze-holdout"):
        analysis_parser = subparsers.add_parser(command)
        for name in (
            "manifest",
            "analysis-spec",
            "response-lock",
            "reviewer-packet",
            "reviewer-template",
            "reviewer-registry",
            "responses",
            "baseline-key",
            "output",
        ):
            analysis_parser.add_argument(
                f"--{name}",
                required=True,
                type=Path,
            )
        if command == "analyze-holdout":
            analysis_parser.add_argument(
                "--candidate-lock",
                required=True,
                type=Path,
            )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.output.exists():
        raise FileExistsError(f"output is immutable; already exists: {args.output}")
    script_path = Path(__file__).resolve()
    if args.command == "lock-responses":
        lock = build_response_lock(
            manifest_path=args.manifest,
            analysis_spec_path=args.analysis_spec,
            analysis_script_path=script_path,
            reviewer_packet_path=args.reviewer_packet,
            reviewer_template_path=args.reviewer_template,
            reviewer_registry_path=args.reviewer_registry,
            responses_path=args.responses,
            locked_on=args.locked_on,
        )
        with args.output.open("x", encoding="utf-8") as handle:
            handle.write(json.dumps(lock, indent=2, sort_keys=True) + "\n")
        print(json.dumps({
            "status": lock["status"],
            "selected_rating_count": lock["selected_rating_count"],
        }, sort_keys=True))
        return 0

    stage = (
        "development"
        if args.command == "analyze-development"
        else "holdout"
    )
    candidate_lock_path = getattr(args, "candidate_lock", None)
    assert_baseline_access(
        args.baseline_key,
        stage=stage,
        candidate_lock_path=candidate_lock_path,
    )
    lock = _load_json(args.response_lock)
    spec = _load_json(args.analysis_spec)
    verify_response_lock(
        lock,
        manifest_path=args.manifest,
        analysis_spec_path=args.analysis_spec,
        analysis_script_path=script_path,
        reviewer_packet_path=args.reviewer_packet,
        reviewer_template_path=args.reviewer_template,
        reviewer_registry_path=args.reviewer_registry,
        responses_path=args.responses,
    )
    if stage == "holdout":
        candidate_lock = _load_json(candidate_lock_path)
        validate_candidate_lock(
            candidate_lock,
            response_lock=lock,
            response_lock_sha256=_sha256(args.response_lock),
            spec=spec,
        )

    result = analyze_benchmark(
        _load_csv(args.baseline_key),
        _load_csv(args.responses),
        _load_csv(args.reviewer_registry),
        spec,
        stage=stage,
        reviewer_packet_rows=_load_csv(args.reviewer_packet),
        reviewer_template_rows=_load_csv(args.reviewer_template),
    )
    with args.output.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "status": result["status"],
        "analyzed_products": result["sample"]["analyzed_products"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
