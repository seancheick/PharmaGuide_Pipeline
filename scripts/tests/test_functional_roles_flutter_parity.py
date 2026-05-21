"""SP-5 C5 — Flutter parity for functional_roles_vocab.

The functional_roles vocab existed in the pipeline (and Flutter assets)
prior to SP-5, but no Dart loader was wired up. This commit adds the
loader + VocabRegistry entry. The test below verifies parity between
pipeline source, Flutter asset, and Dart loader.

Pipeline-side integrity is locked separately by
`test_functional_roles_vocab_contract.py` (22 cases) plus the per-data-file
integrity tests (test_b01/b02/b05_functional_roles_integrity.py).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


REPO_ROOT = Path(__file__).resolve().parents[2]
VOCAB_PATH = REPO_ROOT / "scripts" / "data" / "functional_roles_vocab.json"
FLUTTER_ROOT = Path("/Users/seancheick/PharmaGuide ai")


def test_flutter_asset_matches_pipeline_source():
    if not FLUTTER_ROOT.exists():
        pytest.skip("Flutter repo not co-located")
    asset = FLUTTER_ROOT / "assets" / "data" / "functional_roles_vocab.json"
    if not asset.is_file():
        pytest.skip("Flutter functional_roles_vocab.json asset missing")
    with open(VOCAB_PATH) as fh:
        pipeline = json.load(fh)
    with open(asset) as fh:
        flutter = json.load(fh)
    assert pipeline == flutter, (
        "Flutter assets/data/functional_roles_vocab.json drifted from pipeline "
        "scripts/data/functional_roles_vocab.json. Re-copy the pipeline file."
    )


def test_flutter_dart_loader_present_and_well_formed():
    if not FLUTTER_ROOT.exists():
        pytest.skip("Flutter repo not co-located")
    dart_path = FLUTTER_ROOT / "lib" / "core" / "data" / "functional_roles_vocab.dart"
    if not dart_path.is_file():
        pytest.skip("functional_roles_vocab.dart not yet generated")
    dart_src = dart_path.read_text()
    assert "class FunctionalRoleEntry" in dart_src, "Dart entry class missing"
    assert "loadFunctionalRolesVocab" in dart_src, "Dart loader fn missing"
    assert "functional_roles_vocab.json" in dart_src, "Dart loader doesn't load the asset"
    assert "class RegulatoryReference" in dart_src, (
        "Dart loader must surface the regulatory_references field as a class — "
        "users need tap-through links to FDA CFR / EU E-number text."
    )


def test_vocab_registry_wires_functional_roles():
    if not FLUTTER_ROOT.exists():
        pytest.skip("Flutter repo not co-located")
    registry = FLUTTER_ROOT / "lib" / "core" / "data" / "vocab_registry.dart"
    if not registry.is_file():
        pytest.skip("VocabRegistry not present")
    src = registry.read_text()
    assert "FunctionalRoleEntry" in src, "VocabRegistry missing FunctionalRoleEntry import / field"
    assert "loadFunctionalRolesVocab" in src, "VocabRegistry doesn't load functional_roles"
    assert "functionalRole(" in src, "VocabRegistry missing functionalRole() getter"


def test_data_files_reference_only_canonical_role_ids():
    """Every functional_roles[] array across the three data files must use
    only IDs from the vocab. This locks the source-of-truth contract:
    enrichers / scorers shouldn't invent new roles outside the vocab."""
    with open(VOCAB_PATH) as fh:
        vocab = json.load(fh)
    canonical_ids = {r["id"] for r in vocab["functional_roles"]}

    data_files = (
        REPO_ROOT / "scripts" / "data" / "harmful_additives.json",
        REPO_ROOT / "scripts" / "data" / "other_ingredients.json",
        REPO_ROOT / "scripts" / "data" / "botanical_ingredients.json",
    )

    used_ids = set()
    for path in data_files:
        if not path.is_file():
            continue
        with open(path) as fh:
            data = json.load(fh)
        # Each file has a different top-level structure; iterate all dict
        # values recursively looking for `functional_roles` arrays.
        def _walk(node):
            if isinstance(node, dict):
                roles = node.get("functional_roles")
                if isinstance(roles, list):
                    for r in roles:
                        if isinstance(r, str):
                            used_ids.add(r)
                for v in node.values():
                    _walk(v)
            elif isinstance(node, list):
                for v in node:
                    _walk(v)
        _walk(data)

    unknown = used_ids - canonical_ids
    assert not unknown, (
        f"Data files use functional_role IDs not in the vocab: {unknown}. "
        f"Either add them to functional_roles_vocab.json (clinician review) "
        f"or fix the data file."
    )
