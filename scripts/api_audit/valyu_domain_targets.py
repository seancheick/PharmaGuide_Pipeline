from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
SCRIPTS_ROOT = SCRIPT_DIR.parent
PROJECT_ROOT = SCRIPTS_ROOT.parent

IQM_PATH = PROJECT_ROOT / "scripts" / "data" / "ingredient_quality_map.json"
CLINICAL_PATH = PROJECT_ROOT / "scripts" / "data" / "backed_clinical_studies.json"
HARMFUL_PATH = PROJECT_ROOT / "scripts" / "data" / "harmful_additives.json"
RECALL_PATH = PROJECT_ROOT / "scripts" / "data" / "banned_recalled_ingredients.json"

INACTIVE_CATEGORIES = {
    "flow_agent_anticaking",
    "capsule_shell",
    "capsule_coating",
    "coating",
    "color",
    "colorant",
    "sweetener",
    "flavor",
    "preservative",
}

INACTIVE_TOKENS = (
    "silicon dioxide",
    "hypromellose",
    "titanium dioxide",
    "magnesium stearate",
    "vegetable capsule",
    "gelatin",
)


def _iter_iqm_entries(iqm: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(iqm.get("ingredients"), list):
        return [item for item in iqm["ingredients"] if isinstance(item, dict)]
    return [item for item in iqm.values() if isinstance(item, dict) and item.get("standard_name")]


def _clinical_names(clinical: dict[str, Any]) -> set[str]:
    rows = clinical.get("backed_clinical_studies", [])
    names = set()
    for row in rows:
        if isinstance(row, dict):
            name = str(row.get("standard_name") or "").strip().lower()
            if name:
                names.add(name)
    return names


def _is_active_candidate(entry: dict[str, Any]) -> bool:
    category = str(entry.get("category") or "").strip().lower()
    name = str(entry.get("standard_name") or entry.get("name") or "").strip().lower()
    if category in INACTIVE_CATEGORIES:
        return False
    return not any(token in name for token in INACTIVE_TOKENS)


def load_iqm_gap_targets(iqm: dict[str, Any], clinical: dict[str, Any]) -> list[dict[str, Any]]:
    existing = _clinical_names(clinical)
    targets: list[dict[str, Any]] = []

    for entry in _iter_iqm_entries(iqm):
        if not _is_active_candidate(entry):
            continue
        name = str(entry.get("standard_name") or entry.get("name") or "").strip()
        if not name or name.lower() in existing:
            continue
        targets.append(
            {
                "domain": "iqm_gap_scan",
                "target_file": str(IQM_PATH),
                "entity_type": "ingredient",
                "entity_id": str(entry.get("id") or entry.get("slug") or name.lower().replace(" ", "_")),
                "entity_name": name,
                "category": str(entry.get("category") or ""),
            }
        )

    return targets


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_clinical_refresh_targets(clinical: dict[str, Any], limit: int | None = None) -> list[dict[str, Any]]:
    rows = clinical.get("backed_clinical_studies", [])
    targets: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = str(row.get("standard_name") or "").strip()
        if not name:
            continue
        targets.append(
            {
                "domain": "clinical_refresh",
                "target_file": str(CLINICAL_PATH),
                "entity_type": "clinical_entry",
                "entity_id": str(row.get("id") or name.lower().replace(" ", "_")),
                "entity_name": name,
                "priority_hint": str(row.get("score_contribution") or ""),
            }
        )
    return targets[:limit] if limit else targets


def load_harmful_refresh_targets(harmful: dict[str, Any], limit: int | None = None) -> list[dict[str, Any]]:
    rows = harmful.get("harmful_additives", [])
    targets: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = str(row.get("standard_name") or "").strip()
        if not name:
            continue
        targets.append(
            {
                "domain": "harmful_refresh",
                "target_file": str(HARMFUL_PATH),
                "entity_type": "harmful_additive",
                "entity_id": str(row.get("id") or name.lower().replace(" ", "_")),
                "entity_name": name,
                "priority_hint": str(row.get("severity_level") or ""),
            }
        )
    return targets[:limit] if limit else targets


def load_recall_refresh_targets(recalled: dict[str, Any], limit: int | None = None) -> list[dict[str, Any]]:
    rows = recalled.get("ingredients", [])
    targets: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = str(row.get("standard_name") or "").strip()
        if not name:
            continue
        targets.append(
            {
                "domain": "recall_refresh",
                "target_file": str(RECALL_PATH),
                "entity_type": str(row.get("entity_type") or "regulatory_entry"),
                "entity_id": str(row.get("id") or name.lower().replace(" ", "_")),
                "entity_name": name,
                "priority_hint": str(row.get("status") or ""),
            }
        )
    return targets[:limit] if limit else targets


def load_targets(domain: str, *, limit: int | None = None) -> list[dict[str, Any]]:
    if domain == "clinical-refresh":
        return load_clinical_refresh_targets(load_json(CLINICAL_PATH), limit=limit)
    if domain == "iqm-gap-scan":
        return load_iqm_gap_targets(load_json(IQM_PATH), load_json(CLINICAL_PATH))[:limit] if limit else load_iqm_gap_targets(load_json(IQM_PATH), load_json(CLINICAL_PATH))
    if domain == "harmful-refresh":
        return load_harmful_refresh_targets(load_json(HARMFUL_PATH), limit=limit)
    if domain == "recall-refresh":
        return load_recall_refresh_targets(load_json(RECALL_PATH), limit=limit)
    raise ValueError(f"Unsupported domain: {domain}")
