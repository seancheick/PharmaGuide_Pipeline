"""The 2026-09-14 strain identity batch: exact designations map, uncertain labels stay unresolved."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from studied_formulas import clinical_strain_identity_matches

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "scripts/data/clinically_relevant_strains.json"
SPEC = ROOT / "scripts/audits/probiotic_registry_expansion_2026_09_14/identity_batch_2026_09_14.json"


def _entries():
    return json.loads(REGISTRY.read_text())["clinically_relevant_strains"]


def _spec():
    return json.loads(SPEC.read_text())


def _hits(entries, label):
    return sorted(e["id"] for e in entries if clinical_strain_identity_matches(label, e))


def _key(value):
    return re.sub(r"[^a-z0-9]+", "", str(value).lower())


def _applied_ops():
    return [op for op in _spec()["operations"] if not op.get("pending_authoritative_check")]


@pytest.mark.parametrize("op", _applied_ops(), ids=lambda op: op["key"])
def test_every_expected_label_resolves_to_exactly_its_identity(op):
    entries = _entries()
    if op["op"] == "correct_deposit":
        pairs = [(fix["target"], label) for fix in op["corrections"] for label in fix["expect_labels"]]
    else:
        target = op.get("id") or op["target"]
        pairs = [(target, label) for label in op["expect_labels"]]
    for target, label in pairs:
        assert _hits(entries, label) == [target], label


def test_merged_sd_stubs_are_gone_and_their_deposits_live_on_the_named_strain():
    entries = {e["id"]: e for e in _entries()}
    for op in _applied_ops():
        if op["op"] != "merge_duplicate":
            continue
        assert op["source"] not in entries
        assert _hits(list(entries.values()), op["expect_labels"][0]) == [op["target"]]


def test_new_identities_are_unreviewed_evidence_free_and_cited():
    entries = {e["id"]: e for e in _entries()}
    for op in _applied_ops():
        if op["op"] != "add_identity":
            continue
        entry = entries[op["id"]]
        assert entry["cfu_thresholds"]["dr_pham_signoff"] is False
        assert entry["cfu_thresholds"]["evidence"] is None
        # The batch itself added no evidence. Contexts may only come from a
        # later, separately attributed literature review (closure D1).
        assert all(c["authored_on"] > "2026-09-14" for c in entry["study_contexts"])
        assert not entry["study_contexts"] or entry["literature_review"]["reviewed_on"] > "2026-09-14"
        block = entry["identity_verification"]
        assert block["status"] in {"designation_verified", "designation_found_species_unconfirmed"}
        assert block["source_pmids"] and all(p.isdigit() for p in block["source_pmids"])
        assert block["verified_on"] == "2026-09-14"


def test_species_conflicts_are_not_accepted_for_research_presentation():
    import probiotic_measurements as pm
    entries = {e["id"]: e for e in _entries()}
    for ident in ("STRAIN_ACIDOPHILUS_HA122", "STRAIN_CASEI_HA108", "STRAIN_ACIDOPHILUS_LAFTI_L10"):
        assert pm.identity_confidence(entries[ident]) not in pm.IDENTITY_CONFIDENCE_ACCEPTED


@pytest.mark.parametrize("label", [
    "Bifidobacterium breve BB-3",
    "Bifidobacterium bifidum BB-6",
    "Bifidobacterium longum BL-5",
    "Bifidobacterium bifidum/lactis Bb-02",
    "Bifidobacterium animalis lactis Bb-02",
    "Bifidobacterium bifidum (SD-6575)",
    "Lactobacillus rhamnosus-111",
    "Bifidobacterium lactis Bi-04",
    "Lactobacillus plantarum Lp299",
    "Bifidobacterium breve Bb-18",
    "Bifidobacterium breve UABbr-11",
    "Lactobacillus reuteri (JBD 301)",
    "B. bifidum BB-12",
    "Lactobacillus rhamnosus SD-5839",
    "LR05",
])
def test_uncertain_or_non_exact_designations_stay_unresolved(label):
    assert _hits(_entries(), label) == []


def test_no_alias_key_is_owned_by_two_identities():
    owners = {}
    for entry in _entries():
        for name in [entry["standard_name"], *entry.get("aliases", [])]:
            owners.setdefault(_key(name), set()).add(entry["id"])
    assert {k: v for k, v in owners.items() if len(v) > 1} == {}


def test_metadata_total_entries_matches_registry():
    payload = json.loads(REGISTRY.read_text())
    assert payload["_metadata"]["total_entries"] == len(payload["clinically_relevant_strains"])


def test_signoff_count_unchanged_by_the_batch():
    assert sum(e["cfu_thresholds"].get("dr_pham_signoff") is True for e in _entries()) == 40
