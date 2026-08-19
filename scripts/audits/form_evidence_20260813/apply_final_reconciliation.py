#!/usr/bin/env python3
"""Apply the reviewed 2026-08-18 form-evidence reconciliation atomically."""

from __future__ import annotations

import copy
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


SCRIPTS_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SCRIPTS_DIR))

from iqm_form_evidence import (  # noqa: E402
    apply_manifest_file,
    form_digest,
    validate_form_evidence,
)


AUDIT_DIR = Path(__file__).resolve().parent
IQM_PATH = SCRIPTS_DIR / "data" / "ingredient_quality_map.json"
BACKLOG_PATH = SCRIPTS_DIR / "data" / "iqm_excellent_evidence_backlog.json"
LEDGER_PATH = AUDIT_DIR / "reference_level_reconciliation_20260818.json"
MANIFEST_PATH = AUDIT_DIR / "final_reconciliation_manifest_20260818.json"
REVIEW_DATE = "2026-08-18"
KEEP = "KEEP_FORM_SOURCE"


def _pubmed_reference(
    *,
    pmid: str,
    doi: str,
    title: str,
    published_date: str,
    publication_types: list[str],
    evidence_grade: str,
    supports_claims: list[str],
) -> dict[str, Any]:
    return {
        "type": "pubmed",
        "authority": "NCBI PubMed",
        "pmid": pmid,
        "doi": doi,
        "title": title,
        "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        "published_date": published_date,
        "publication_types": publication_types,
        "evidence_grade": evidence_grade,
        "retracted": False,
        "supports_claims": supports_claims,
        "verification_source": "pubmed_eutils",
        "verified_on": REVIEW_DATE,
    }


HMB_REFERENCE = _pubmed_reference(
    pmid="21134325",
    doi="10.1017/S0007114510003582",
    title=(
        "Free acid gel form of β-hydroxy-β-methylbutyrate (HMB) improves "
        "HMB clearance from plasma in human subjects compared with the "
        "calcium HMB salt."
    ),
    published_date="2011-02-01",
    publication_types=[
        "Comparative Study",
        "Journal Article",
        "Randomized Controlled Trial",
        "Research Support, Non-U.S. Gov't",
    ],
    evidence_grade="rct",
    supports_claims=["comparative_oral_bioavailability"],
)

COLLAGEN_REFERENCE = _pubmed_reference(
    pmid="26934933",
    doi="10.1248/bpb.b15-00624",
    title=(
        "Absorption and Urinary Excretion of Peptides after Collagen "
        "Tripeptide Ingestion in Humans."
    ),
    published_date="2016-01-01",
    publication_types=[
        "Clinical Trial",
        "Journal Article",
        "Research Support, Non-U.S. Gov't",
    ],
    evidence_grade="human_comparative",
    supports_claims=["collagen_tripeptide_absorption"],
)

REPLACEMENT_EVIDENCE: dict[tuple[str, str], dict[str, Any]] = {
    ("hmb", "hmb calcium salt (hmb-ca)"): {
        "schema_version": "1.0.0",
        "axis": "systemic_bioavailability",
        "evidence_level": "moderate",
        "score_supported": True,
        "rationale": (
            "A randomized human crossover directly compared calcium HMB with "
            "HMB free acid, establishing calcium HMB as the reference form "
            "while showing higher exposure for the free-acid form."
        ),
        "review": {
            "status": "source_verified",
            "by": "PharmaGuide evidence audit",
            "date": REVIEW_DATE,
        },
        "references_structured": [HMB_REFERENCE],
    },
    ("hmb", "hmb free acid (hmb-fa)"): {
        "schema_version": "1.0.0",
        "axis": "systemic_bioavailability",
        "evidence_level": "moderate",
        "score_supported": True,
        "rationale": (
            "A randomized human crossover found a faster peak and nearly "
            "double the exposure for HMB free acid versus calcium HMB, "
            "supporting the higher form-quality score."
        ),
        "review": {
            "status": "source_verified",
            "by": "PharmaGuide evidence audit",
            "date": REVIEW_DATE,
        },
        "references_structured": [HMB_REFERENCE],
    },
    ("collagen", "collagen tripeptides"): {
        "schema_version": "1.0.0",
        "axis": "systemic_bioavailability",
        "evidence_level": "moderate",
        "score_supported": True,
        "rationale": (
            "A human comparison measured higher post-dose collagen-derived "
            "di- and tripeptides after tripeptide-rich preparations than after "
            "a collagen peptide without tripeptides."
        ),
        "review": {
            "status": "source_verified",
            "by": "PharmaGuide evidence audit",
            "date": REVIEW_DATE,
        },
        "references_structured": [COLLAGEN_REFERENCE],
    },
}

SCORE_CORRECTIONS = {
    ("vitamin_c", "calcium ascorbate"): {"bio_score": 13, "score": 13},
    ("magnesium", "magnesium aspartate"): {"bio_score": 13, "score": 13},
    ("hmb", "hmb free acid (hmb-fa)"): {"bio_score": 14, "score": 14},
    ("dha", "DHA fish oil rTG"): {"bio_score": 14, "score": 17},
    ("epa", "EPA fish oil rTG"): {"bio_score": 14, "score": 17},
}

RATIONALE_CORRECTIONS = {
    ("vitamin_c", "calcium ascorbate"): (
        "NIH ODS reports no consistent bioavailability advantage among common "
        "vitamin C forms. Calcium ascorbate therefore aligns with the "
        "well-absorbed ascorbic-acid tier without a superiority bonus."
    ),
    ("magnesium", "magnesium aspartate"): (
        "A direct human comparison found magnesium aspartate comparable with "
        "other well-absorbed salts rather than superior, supporting alignment "
        "with the magnesium chloride and lactate tier."
    ),
}


def _reference_id(reference: dict[str, Any]) -> str:
    return str(reference.get("pmid") or "ODS")


def _load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"Expected object in {path}")
    return value


def _load_rows(path: Path) -> list[dict[str, Any]]:
    value = json.loads(path.read_text())
    if not isinstance(value, list) or not all(isinstance(row, dict) for row in value):
        raise ValueError(f"Expected object rows in {path}")
    return value


def _form(iqm: dict[str, Any], ingredient_key: str, form_key: str) -> dict[str, Any]:
    try:
        value = iqm[ingredient_key]["forms"][form_key]
    except KeyError as exc:
        raise ValueError(f"Missing IQM form {ingredient_key}::{form_key}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"Invalid IQM form {ingredient_key}::{form_key}")
    return value


def build_manifest(iqm: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(str(row["ingredient"]), str(row["form"]))].append(row)
    if len(rows) != 120 or len(grouped) != 89:
        raise ValueError("Reference ledger must contain 120 rows across 89 forms")

    changes: list[dict[str, Any]] = []
    verified_count = 0
    backlog_count = 0
    for ingredient_key, form_key in sorted(grouped):
        key = (ingredient_key, form_key)
        form = _form(iqm, ingredient_key, form_key)
        evidence = form.get("form_evidence")
        current_references = (
            evidence.get("references_structured")
            if isinstance(evidence, dict)
            else []
        )
        references_by_id = {
            _reference_id(reference): reference
            for reference in current_references or []
            if isinstance(reference, dict)
        }
        keep_ids = {
            str(row["ref"])
            for row in grouped[key]
            if row.get("verdict") == KEEP
        }

        set_values: dict[str, Any] = {}
        unset_values: list[str] = []
        if key in REPLACEMENT_EVIDENCE:
            desired_evidence = copy.deepcopy(REPLACEMENT_EVIDENCE[key])
            verified_count += 1
        elif keep_ids:
            missing = sorted(keep_ids - set(references_by_id))
            if missing:
                raise ValueError(
                    f"{ingredient_key}::{form_key} lacks retained source {missing[0]}"
                )
            if not isinstance(evidence, dict):
                raise ValueError(f"{ingredient_key}::{form_key} lacks form_evidence")
            desired_evidence = copy.deepcopy(evidence)
            desired_evidence["references_structured"] = [
                copy.deepcopy(reference)
                for reference in current_references
                if _reference_id(reference) in keep_ids
            ]
            desired_evidence["review"]["date"] = REVIEW_DATE
            if key in RATIONALE_CORRECTIONS:
                desired_evidence["rationale"] = RATIONALE_CORRECTIONS[key]
            verified_count += 1
        else:
            desired_evidence = None
            unset_values.append("form_evidence")
            backlog_count += 1

        if desired_evidence is not None:
            prospective = copy.deepcopy(form)
            prospective.update(SCORE_CORRECTIONS.get(key, {}))
            excellent = float(prospective.get("bio_score") or 0) >= 12
            problems = validate_form_evidence(
                desired_evidence,
                label=f"{ingredient_key}::{form_key}",
                excellent=excellent,
            )
            if problems:
                raise ValueError("\n".join(problems))
            set_values["form_evidence"] = desired_evidence

        set_values.update(SCORE_CORRECTIONS.get(key, {}))
        change: dict[str, Any] = {
            "ingredient_key": ingredient_key,
            "form_key": form_key,
            "expected_form_sha256": form_digest(form),
        }
        if set_values:
            change["set"] = set_values
        if unset_values:
            change["unset"] = unset_values
        changes.append(change)

    if verified_count != 49 or backlog_count != 40:
        raise ValueError(
            f"Unexpected evidence split: verified={verified_count}, backlog={backlog_count}"
        )
    return {
        "schema_version": "1.0.0",
        "review_date": REVIEW_DATE,
        "policy": (
            "Keep only reference-level sources adjudicated as form-quality "
            "evidence. Clinical-only and off-axis sources leave IQM; unresolved "
            "legacy Excellent scores return to the frozen backlog."
        ),
        "summary": {
            "audited_forms": 89,
            "forms_with_verified_evidence": verified_count,
            "forms_returned_to_legacy_backlog": backlog_count,
            "score_corrections": len(SCORE_CORRECTIONS),
        },
        "changes": changes,
    }


def update_backlog(iqm: dict[str, Any]) -> None:
    backlog = _load_object(BACKLOG_PATH)
    initial = set(backlog["initial_forms"])
    remaining: list[str] = []
    for key in sorted(initial):
        ingredient_key, form_key = key.split("::", 1)
        form = _form(iqm, ingredient_key, form_key)
        bio_score = form.get("bio_score")
        if not isinstance(bio_score, (int, float)) or bio_score < 12:
            continue
        evidence = form.get("form_evidence")
        if evidence is None or validate_form_evidence(
            evidence,
            label=key,
            excellent=True,
        ):
            remaining.append(key)
    backlog["remaining_forms"] = remaining
    backlog["_metadata"]["last_updated"] = REVIEW_DATE
    BACKLOG_PATH.write_text(json.dumps(backlog, indent=2, ensure_ascii=False) + "\n")


def main() -> int:
    iqm = _load_object(IQM_PATH)
    rows = _load_rows(LEDGER_PATH)
    manifest = build_manifest(iqm, rows)
    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    )
    result = apply_manifest_file(IQM_PATH, MANIFEST_PATH)
    update_backlog(_load_object(IQM_PATH))
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
