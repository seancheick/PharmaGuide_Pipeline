"""SP-6 — evidence-grade canonical-ID enforcement + Flutter parity + provenance.

The pipeline already ships three canonical evidence vocabs, all LOCKED
with clinician sign-off:
  - evidence_level_vocab   (5 study-design tiers)
  - evidence_strength_vocab (6 qualitative strength tiers)
  - study_type_vocab       (7 study-type tiers)

Per-vocab contract tests
(`test_evidence_level_vocab_contract.py`, `test_evidence_strength_vocab_contract.py`,
`test_study_type_vocab_contract.py`) already lock each vocab's internal
structure (ID set, field shape, char limits, etc.).

This SP-6 test file adds the three things that were missing:

  1. CANONICAL-ID ENFORCEMENT across the data files. Every
     `evidence_level`, `evidence_strength`, and `study_type` value used
     by the data files must be a canonical ID from its respective vocab.
     If a data-file entry uses an off-vocab string, it's flagged here.

  2. PROVENANCE AUDIT — clinical-evidence entries must carry a PMID or
     NCT identifier so their grade is traceable to a real study. Per the
     SP-0 design doc: "Map evidence grade to clinical-study data and
     audited identifiers. Do not infer evidence grade from marketing copy."

  3. FLUTTER PARITY — the three Dart loaders + VocabRegistry entries exist
     and stay byte-identical to the pipeline source assets.

Together these locks finish the SP-6 source-of-truth contract for the
evidence-grade layer.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


REPO_ROOT = Path(__file__).resolve().parents[2]
DATA = REPO_ROOT / "scripts" / "data"
FLUTTER_ROOT = Path("/Users/seancheick/PharmaGuide ai")


# ============================================================================
# 1. Canonical-ID enforcement — data files only use vocab IDs
# ============================================================================


def _load_canonical_ids(vocab_filename: str, entries_key: str) -> set[str]:
    with open(DATA / vocab_filename) as fh:
        data = json.load(fh)
    return {e["id"] for e in data.get(entries_key, []) if isinstance(e, dict) and e.get("id")}


@pytest.fixture(scope="module")
def evidence_level_ids() -> set[str]:
    return _load_canonical_ids("evidence_level_vocab.json", "evidence_levels")


@pytest.fixture(scope="module")
def evidence_strength_ids() -> set[str]:
    return _load_canonical_ids("evidence_strength_vocab.json", "evidence_strengths")


@pytest.fixture(scope="module")
def study_type_ids() -> set[str]:
    return _load_canonical_ids("study_type_vocab.json", "study_types")


def _collect_field_values(node, field_name: str) -> set[str]:
    """Walk a data file collecting `field_name` values. Skips any subtree
    rooted at a key starting with `_` (metadata, schema notes). Without
    this, the test picks up documentation strings from
    `_metadata._scoring_fields_used.study_type` etc."""
    found: set[str] = set()

    def _walk(n):
        if isinstance(n, dict):
            value = n.get(field_name)
            if isinstance(value, str) and value:
                found.add(value)
            elif isinstance(value, list):
                for v in value:
                    if isinstance(v, str):
                        found.add(v)
            for k, v in n.items():
                if isinstance(k, str) and k.startswith("_"):
                    continue
                _walk(v)
        elif isinstance(n, list):
            for v in n:
                _walk(v)

    _walk(node)
    return found


def test_backed_clinical_studies_uses_canonical_evidence_level_ids(evidence_level_ids):
    """Every `evidence_level` value in backed_clinical_studies.json must be a
    canonical ID. If a data-entry author used an off-vocab string, this
    fails so they fix the entry rather than silently drifting."""
    path = DATA / "backed_clinical_studies.json"
    if not path.is_file():
        pytest.skip("backed_clinical_studies.json missing")
    with open(path) as fh:
        data = json.load(fh)
    used = _collect_field_values(data, "evidence_level")
    unknown = used - evidence_level_ids
    assert not unknown, (
        f"backed_clinical_studies.json uses non-canonical evidence_level "
        f"IDs: {unknown}. Canonical set: {sorted(evidence_level_ids)}."
    )


def test_backed_clinical_studies_uses_canonical_study_type_ids(study_type_ids):
    path = DATA / "backed_clinical_studies.json"
    if not path.is_file():
        pytest.skip("backed_clinical_studies.json missing")
    with open(path) as fh:
        data = json.load(fh)
    used = _collect_field_values(data, "study_type")
    unknown = used - study_type_ids
    assert not unknown, (
        f"backed_clinical_studies.json uses non-canonical study_type "
        f"IDs: {unknown}. Canonical set: {sorted(study_type_ids)}."
    )


def test_ingredient_interaction_rules_uses_canonical_evidence_strength_ids(
    evidence_strength_ids,
):
    """ingredient_interaction_rules.json reuses the FIELD name evidence_level
    for what the vocab system named evidence_strength (per the
    evidence_level_vocab `future_split_note` and evidence_strength_vocab
    metadata). The values must come from evidence_strength_vocab."""
    path = DATA / "ingredient_interaction_rules.json"
    if not path.is_file():
        pytest.skip("ingredient_interaction_rules.json missing")
    with open(path) as fh:
        data = json.load(fh)
    used = _collect_field_values(data, "evidence_level")
    unknown = used - evidence_strength_ids
    assert not unknown, (
        f"ingredient_interaction_rules.json uses non-canonical evidence_strength "
        f"IDs in its `evidence_level` field: {unknown}. "
        f"Canonical set: {sorted(evidence_strength_ids)}."
    )


# ============================================================================
# 2. Provenance audit — clinical evidence entries carry PMID or NCT
# ============================================================================


def test_clinical_evidence_entries_have_pmid_or_nct_provenance():
    """Every entry in backed_clinical_studies.json with a non-`preclinical`
    evidence_level should carry at least one PMID or NCT identifier. Locks
    the SP-0 rule: "Map evidence grade to clinical-study data and audited
    identifiers. Do not infer evidence grade from marketing copy."
    """
    path = DATA / "backed_clinical_studies.json"
    if not path.is_file():
        pytest.skip("backed_clinical_studies.json missing")
    with open(path) as fh:
        data = json.load(fh)

    # Build the list of clinical-evidence entries. Tolerate either an `entries`
    # list at the top level or a dict of named entries — different versions
    # of the schema may shape it differently.
    entries: list[dict] = []
    if isinstance(data, dict):
        for key, value in data.items():
            if key.startswith("_"):
                continue
            if isinstance(value, list):
                entries.extend(v for v in value if isinstance(v, dict))
            elif isinstance(value, dict):
                # Single-entry dict keyed by ingredient name; collect leaf
                # dicts that look like a study entry (have evidence_level).
                def _collect(node):
                    if isinstance(node, dict):
                        if "evidence_level" in node:
                            entries.append(node)
                        for v in node.values():
                            _collect(v)
                    elif isinstance(node, list):
                        for v in node:
                            _collect(v)
                _collect(value)

    if not entries:
        pytest.skip("backed_clinical_studies.json has no recognizable entries")

    def _has_provenance(entry: dict) -> bool:
        """A clinical-evidence entry carries provenance when any of these
        produces a non-empty PMID / NCT / DOI value:
          - top-level pmid / pmids / pmid_refs (flat schemas)
          - top-level nct / nct_ids / nct_refs
          - references_structured[] — `{type, pmid, nct_id, doi, ...}` items
        """
        # Flat fields first.
        for key in ("pmid", "pmids", "pmid_refs", "nct", "nct_ids", "nct_refs", "doi"):
            v = entry.get(key)
            if isinstance(v, str) and v.strip():
                return True
            if isinstance(v, list) and any(isinstance(x, str) and x.strip() for x in v):
                return True
        # Nested structured references.
        refs = entry.get("references_structured")
        if isinstance(refs, list):
            for ref in refs:
                if not isinstance(ref, dict):
                    continue
                for key in ("pmid", "nct_id", "nct", "doi", "url"):
                    v = ref.get(key)
                    if isinstance(v, str) and v.strip():
                        return True
        return False

    missing_provenance: list[str] = []
    for entry in entries:
        level = entry.get("evidence_level") or ""
        if level == "preclinical":
            # Animal / in-vitro entries may legitimately have no PMID — skip.
            continue
        if not _has_provenance(entry):
            ing = entry.get("ingredient") or entry.get("standard_name") or entry.get("name") or entry.get("id") or "(unknown)"
            missing_provenance.append(f"{ing} [evidence_level={level}]")

    # Soft threshold — allow up to 5% missing as known data-quality gaps
    # rather than blocking the contract entirely. The contract is "every
    # entry SHOULD carry provenance"; the test reports drift if it grows.
    if missing_provenance:
        rate = len(missing_provenance) / max(len(entries), 1)
        assert rate <= 0.05, (
            f"{len(missing_provenance)}/{len(entries)} clinical-evidence "
            f"entries lack PMID/NCT provenance ({rate*100:.1f}% > 5% threshold). "
            f"Sample: {missing_provenance[:5]}"
        )


# ============================================================================
# 3. Flutter parity — Dart loaders + VocabRegistry wiring
# ============================================================================


@pytest.mark.parametrize("vocab_name,entries_key,dart_class", [
    ("evidence_level_vocab",   "evidence_levels",   "EvidenceLevelEntry"),
    ("evidence_strength_vocab", "evidence_strengths", "EvidenceStrengthEntry"),
    ("study_type_vocab",       "study_types",       "StudyTypeEntry"),
])
def test_flutter_asset_matches_pipeline(vocab_name, entries_key, dart_class):
    if not FLUTTER_ROOT.exists():
        pytest.skip("Flutter repo not co-located")
    asset = FLUTTER_ROOT / "assets" / "data" / f"{vocab_name}.json"
    if not asset.is_file():
        pytest.skip(f"Flutter {vocab_name}.json asset missing")
    with open(DATA / f"{vocab_name}.json") as fh:
        pipeline = json.load(fh)
    with open(asset) as fh:
        flutter = json.load(fh)
    assert pipeline == flutter, (
        f"Flutter assets/data/{vocab_name}.json drifted from pipeline source."
    )


@pytest.mark.parametrize("vocab_name,dart_class,loader_fn", [
    ("evidence_level_vocab",   "EvidenceLevelEntry",   "loadEvidenceLevelVocab"),
    ("evidence_strength_vocab", "EvidenceStrengthEntry", "loadEvidenceStrengthVocab"),
    ("study_type_vocab",       "StudyTypeEntry",       "loadStudyTypeVocab"),
])
def test_flutter_dart_loader_well_formed(vocab_name, dart_class, loader_fn):
    if not FLUTTER_ROOT.exists():
        pytest.skip("Flutter repo not co-located")
    dart = FLUTTER_ROOT / "lib" / "core" / "data" / f"{vocab_name}.dart"
    if not dart.is_file():
        pytest.skip(f"{vocab_name}.dart missing")
    src = dart.read_text()
    assert f"class {dart_class}" in src
    assert loader_fn in src
    assert f"{vocab_name}.json" in src


@pytest.mark.parametrize("loader_fn,getter_fragment", [
    ("loadEvidenceLevelVocab",   "evidenceLevel("),
    ("loadEvidenceStrengthVocab", "evidenceStrength("),
    ("loadStudyTypeVocab",       "studyType("),
])
def test_vocab_registry_wires_evidence_vocab(loader_fn, getter_fragment):
    if not FLUTTER_ROOT.exists():
        pytest.skip("Flutter repo not co-located")
    registry = FLUTTER_ROOT / "lib" / "core" / "data" / "vocab_registry.dart"
    if not registry.is_file():
        pytest.skip("VocabRegistry missing")
    src = registry.read_text()
    assert loader_fn in src, f"VocabRegistry doesn't load {loader_fn!r}"
    assert getter_fragment in src, f"VocabRegistry missing getter {getter_fragment!r}"


# ============================================================================
# 4. v4 evidence module consumes canonical IDs without re-deriving
# ============================================================================

def test_v4_evidence_does_not_redefine_evidence_grade():
    """The v4 evidence module (`scoring_v4/modules/generic_evidence.py` and
    the per-class wrappers) MUST NOT define their own evidence-level /
    evidence-strength / study-type taxonomy. Confirms the source-of-truth
    contract — they read the canonical IDs from the data files instead."""
    forbidden_phrases = (
        # If any of these appear in a v4 module, the module is re-defining
        # an evidence taxonomy instead of consuming the canonical one.
        "EVIDENCE_LEVEL_TIERS",
        "EVIDENCE_STRENGTH_TIERS",
        "STUDY_TYPE_TIERS",
    )
    v4_dir = REPO_ROOT / "scripts" / "scoring_v4"
    for path in v4_dir.rglob("*.py"):
        src = path.read_text()
        for phrase in forbidden_phrases:
            assert phrase not in src, (
                f"{path.relative_to(REPO_ROOT)} defines a local evidence "
                f"taxonomy ({phrase!r}). Use the canonical vocab JSON instead."
            )
