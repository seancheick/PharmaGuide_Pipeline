"""The batch-1 patch is snapshot-bound, explicit, and status-preserving."""

from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    ROOT
    / "scripts/audits/probiotic_curation_queue_2026_09_13/apply_batch1_disposition.py"
)


def _module():
    spec = importlib.util.spec_from_file_location("batch1_disposition", MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_batch1_disposition_validates_without_mutating_registry() -> None:
    module = _module()
    registry = json.loads(
        (ROOT / "scripts/data/clinically_relevant_strains.json").read_text()
    )
    original = copy.deepcopy(registry)
    disposition = json.loads(module.DISPOSITION.read_text())
    _, prospective = module.validate(registry, disposition)

    assert registry == original
    assert len(disposition["patches"]) == 61
    assert all(
        context.get("review_status") == "source_verified_pending_clinical_review"
        for context in module._contexts(prospective).values()
        if context.get("context_schema_version") == "1.1.0"
    )


def test_batch1_disposition_binds_every_patch_to_the_named_snapshot() -> None:
    module = _module()
    disposition = json.loads(module.DISPOSITION.read_text())
    metadata = disposition["_metadata"]
    assert metadata["review_snapshot_id"].startswith("batch_1_2026-09-14_")
    assert len(metadata["dataset_sha256"]) == 64
    assert all(
        patch["source_pmid"]
        and patch["source_url"]
        and patch["source_location"]
        and patch["reviewer_reason"]
        for patch in disposition["patches"]
    )


def test_evidence_review_packet_uses_frozen_fields_without_personal_metadata() -> None:
    builder = ROOT / (
        "scripts/audits/probiotic_curation_queue_2026_09_13/"
        "build_evidence_review_packet.py"
    )
    subprocess.run(["python", str(builder)], cwd=ROOT, check=True, capture_output=True)
    packet = (ROOT / "docs/plans/PROBIOTIC_EVIDENCE_REVIEW_PACKET_2026-09-14.md").read_text()
    assert "engineering owner verifies" in packet
    assert "Reviewers do not edit statuses" in packet
    assert "review team records the decision" not in packet
    assert "duration_as_printed" in packet
    assert "component_registration_status" in packet
    assert "clinician" not in packet.lower()
    assert "studied_dose." in packet
    assert "network_node_estimate" in packet
    assert "reviewer name/credentials" not in packet
    assert "decision date" not in packet.lower()
