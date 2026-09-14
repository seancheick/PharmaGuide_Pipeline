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


def test_applied_batch1_disposition_survives_later_registry_edits(tmp_path) -> None:
    """Once applied, an unrelated registry change (the next status decision or
    curation wave) must not turn the disposition back into a snapshot mismatch."""
    module = _module()
    registry = json.loads(
        (ROOT / "scripts/data/clinically_relevant_strains.json").read_text()
    )
    disposition = json.loads(module.DISPOSITION.read_text())
    assert module._already_applied(registry, disposition)

    later = copy.deepcopy(registry)
    lgg = next(e for e in later["clinically_relevant_strains"] if e["id"] == "STRAIN_LGG")
    lgg["study_contexts"][0]["review_status"] = "adjudication_required"
    later_path = tmp_path / "clinically_relevant_strains.json"
    later_path.write_text(json.dumps(later, indent=2, ensure_ascii=False) + "\n")
    module.REGISTRY = later_path

    _, prospective = module.validate(later, disposition)
    assert module._contexts(prospective) == module._contexts(later)
    assert module._already_applied(later, disposition)

    # A partially reverted patch is no longer "applied": the snapshot rule returns.
    reverted = copy.deepcopy(later)
    patch = disposition["patches"][0]
    target = module._contexts(reverted)[patch["record_id"]]
    module._write_path(target, patch["field_path"], patch["old_value"])
    assert not module._already_applied(reverted, disposition)


def _pre_apply_state(module, tmp_path):
    """Registry with every declared patch reverted, and a disposition bound to it."""
    registry = json.loads((ROOT / "scripts/data/clinically_relevant_strains.json").read_text())
    disposition = json.loads(module.DISPOSITION.read_text())
    contexts = module._contexts(registry)
    for patch in disposition["patches"]:
        module._write_path(contexts[patch["record_id"]], patch["field_path"], patch["old_value"])
    path = tmp_path / "clinically_relevant_strains.json"
    path.write_text(json.dumps(registry, indent=2, ensure_ascii=False) + "\n")
    module.REGISTRY = path
    disposition["_metadata"]["dataset_sha256"] = module._sha256(path)
    assert not module._already_applied(registry, disposition)
    return registry, disposition


def _patch(record_id, field_path, old_value, new_value, pmid):
    return {"record_id": record_id, "field_path": field_path, "old_value": old_value,
            "new_value": new_value, "source_pmid": pmid,
            "source_url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            "source_location": "abstract", "reviewer_reason": "regression test"}


def test_write_path_never_drops_a_list_index_onto_a_missing_key() -> None:
    module = _module()
    payload = {"dose": {}}
    try:
        module._write_path(payload, "dose.newlist[0]", 5)
    except ValueError as exc:
        assert "missing list" in str(exc)
    else:
        raise AssertionError("a list index on a missing key must not become a scalar")
    assert payload == {"dose": {}}


def test_patches_are_confined_to_records_with_an_approve_decision(tmp_path) -> None:
    module = _module()
    registry, disposition = _pre_apply_state(module, tmp_path)
    outsider = "lgg_pediatric_aad_guideline_26756877"
    assert outsider not in disposition["decisions"]
    current = module._contexts(registry)[outsider]["condition"]
    disposition["patches"].append(_patch(outsider, "condition", current, "something_else", "26756877"))
    try:
        module.validate(registry, disposition)
    except ValueError as exc:
        assert "without an approve decision" in str(exc)
    else:
        raise AssertionError("a patch outside the decided records must be refused")


def test_patched_record_must_also_pass_the_runtime_validator(tmp_path) -> None:
    module = _module()
    registry, disposition = _pre_apply_state(module, tmp_path)
    record = "dds1_ibs_three_arm_32019158"
    # Passes the frozen vocabulary (two registered components) but not the runtime
    # rule that an exact-strain context names exactly one component.
    disposition["patches"].append(_patch(
        record, "components", ["STRAIN_ACIDOPHILUS_DDS1"],
        ["STRAIN_ACIDOPHILUS_DDS1", "STRAIN_LGG"], "32019158"))
    try:
        module.validate(registry, disposition)
    except ValueError as exc:
        assert "runtime validation" in str(exc)
    else:
        raise AssertionError("a patch the runtime validator rejects must not be applied")
