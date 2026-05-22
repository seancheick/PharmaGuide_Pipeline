from __future__ import annotations

import json
import re
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parents[1] / "data"

IDENTITY_FILES = {
    "harmful_additives": ("harmful_additives.json", "harmful_additives"),
    "banned_recalled_ingredients": (
        "banned_recalled_ingredients.json",
        "ingredients",
    ),
    "other_ingredients": ("other_ingredients.json", "other_ingredients"),
    "botanical_ingredients": ("botanical_ingredients.json", "botanical_ingredients"),
}

RED40_IDENTITY_LABELS = {
    "red 40",
    "red #40",
    "allura red",
    "allura red ac",
    "fd&c red #40",
    "fd&c red # 40",
    "fd&c red no. 40",
    "red dye 40",
    "red 40 lake",
    "red #40 lake",
    "allura red aluminum lake",
    "e129",
    "fd&c red #40 lake",
    "fd&c red # 40 lake",
    "fd&c red 40 lake",
    "fd and c red 40 lake",
    "red 40 aluminum lake",
    "allura red lake",
    "fd&c red #40 aluminum lake",
    "fd&c red no. 40 aluminum lake",
    "fd&c red no 40 aluminum lake",
}


def _norm(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _load_entries(db_name: str) -> list[dict]:
    file_name, root_key = IDENTITY_FILES[db_name]
    data = json.loads((DATA_DIR / file_name).read_text())
    return data[root_key]


def _label_owners() -> list[tuple[str, str, str, str]]:
    owners = []
    for db_name in IDENTITY_FILES:
        for entry in _load_entries(db_name):
            entry_id = entry.get("id")
            standard_name = entry.get("standard_name")
            if isinstance(standard_name, str) and standard_name.strip():
                owners.append((standard_name, db_name, entry_id, "standard_name"))
            for alias in entry.get("aliases") or []:
                if isinstance(alias, str) and alias.strip():
                    owners.append((alias, db_name, entry_id, "alias"))
    return owners


def test_red40_specific_labels_have_one_active_canonical_owner() -> None:
    red40_owners = [
        (label, db_name, entry_id, field)
        for label, db_name, entry_id, field in _label_owners()
        if _norm(label) in RED40_IDENTITY_LABELS
    ]

    canonical_owners = {(db_name, entry_id) for _, db_name, entry_id, _ in red40_owners}
    assert canonical_owners == {("harmful_additives", "ADD_RED40")}

    labels = {_norm(label) for label, _, _, _ in red40_owners}
    # Verify at least one Lake variant is covered (case+spacing normalized)
    assert "fd&c red #40 lake" in labels or "fd&c red 40 lake" in labels, (
        f"At least one FD&C Red #40 Lake variant must be in ADD_RED40 aliases. "
        f"Got: {sorted(labels)}"
    )


def test_red40_is_not_duplicated_into_banned_other_or_botanical_data() -> None:
    non_harmful_red40 = [
        (label, db_name, entry_id, field)
        for label, db_name, entry_id, field in _label_owners()
        if db_name != "harmful_additives"
        and _norm(label) in RED40_IDENTITY_LABELS
    ]

    assert non_harmful_red40 == []


def test_generic_fdc_red_descriptor_stays_generic() -> None:
    other_entries = {entry["id"]: entry for entry in _load_entries("other_ingredients")}
    descriptor = other_entries["OI_FDC_RED_DESCRIPTOR"]
    labels = {
        _norm(label)
        for label in [descriptor.get("standard_name"), *descriptor.get("aliases", [])]
        if isinstance(label, str) and label.strip()
    }

    assert "fd&c red" in labels
    assert labels.isdisjoint(RED40_IDENTITY_LABELS)
