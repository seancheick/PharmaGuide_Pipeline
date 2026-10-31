"""
Phase 1 of the raw → Flutter data-integrity audit.

For each product in the canary set (or --all), walks the full lineage:

  raw DSLD JSON     (cleaned_batch.{activeIngredients, inactiveIngredients})
        ↓
  cleaned           (cleaned_batch.display_ingredients[])
        ↓
  enriched          (output_<brand>_enriched/*.json)        — optional, not in canary set today
        ↓
  scored            (output_<brand>_scored/scored/*.json)   — optional
        ↓
  detail_blob       (final_db_output/detail_blobs/<id>.json)
        ↓
  products_core row (final_db_output/pharmaguide_core.db)

and emits the per-product reconciliation record specified in the plan, with
finding severity = BLOCKER / HIGH / MEDIUM / LOW.

  BLOCKER → script exits non-zero. CI gate.

Run:
  python3 scripts/audit_raw_to_final.py \
      --build-dir scripts/final_db_output \
      --products-root scripts/products \
      --out reports/raw_to_final_audit.json \
      --canary

Every exported product, with the raw-row line checks (the snapshot/release gate):
  python3 scripts/audit_raw_to_final.py \
      --build-dir <final_db_output candidate> --products-root scripts/products \
      --out <candidate>/raw_to_final_audit.json --all [--raw-root <raw DSLD labels>]

For details on severity codes, see plan file:
  ~/.claude/plans/you-are-a-reactive-zephyr.md  §"Severity assignment"
"""

from __future__ import annotations

import argparse
import collections
from copy import deepcopy
from functools import lru_cache
import contextlib
import json
import re
import sqlite3
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Mapping

from dataset_paths import brand_dataset_root


# ---------------------------------------------------------------------------
# CANARY SET — one DSLD ID per archetype (sourced from blob property scan).
# Keep this list short; canaries should be representative, not exhaustive.
# ---------------------------------------------------------------------------

CANARY_SET: dict[str, str] = {
    "simple_single":   "1004",   # L-Arginine 1000 — 1 active, 2 inactives
    "multivit":        "1007",   # Mega Teen — 26 actives, 5 inactives
    "vitamin_a_iu":    "1007",   # Same blob; exercises Vitamin A 5000 IU unit-conversion safety
    "botanical":       "1181",   # Be-Energized Calorie Burning Formula — branded+plant-part
    "blend":           "43994",  # Perfect Food Raw Apple — disclosed prop-blend with 49 children
    "probiotic":       "1044",   # Ultra Probiotic Complex 25
    "omega3":          "178667", # Enteric-Coated Fish Oil 1200 mg
    "magnesium_form":  "193349", # Basic Nutrients IV Multi With Copper And Iron — Magnesium Citrate
                                 # (183043 excluded from v1.6.0 builds: NOT_SCORED verdict)
    "many_others":     "1031",   # Ultra Iron 65 — 12 inactives
    "allergen_cert":   "1003",   # L-Arginine 5000 mg Natural Orange — 3 certs + allergen warning
    # "unmapped" archetype intentionally unreachable in v1.6.0:
    # the Batch 3 data integrity gate excludes every product with
    # unmapped_actives_total > 0 (NOT_SCORED verdict). v1 had 16 such
    # products; v2 has 0. If/when the gate softens to a "partial coverage"
    # representation, restore this canary with the matching DSLD ID.
}

CANARY_PRODUCTS_PATH = Path(__file__).resolve().parent / "data" / "canary_products.json"


def _load_current_canary_set() -> dict[str, str]:
    """Load the maintained v4 canary catalog.

    ``CANARY_SET`` above is retained as a legacy fallback for older
    worktrees, but the shipped catalog canary source of truth is
    ``scripts/data/canary_products.json``. Keeping this audit on the same
    canary file prevents raw→final coverage from silently drifting to
    retired DSLD IDs.
    """
    try:
        doc = json.loads(CANARY_PRODUCTS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return dict(CANARY_SET)

    canaries = doc.get("canaries")
    if not isinstance(canaries, list):
        return dict(CANARY_SET)

    loaded: dict[str, str] = {}
    seen: collections.Counter[str] = collections.Counter()
    for idx, item in enumerate(canaries, start=1):
        if not isinstance(item, dict):
            continue
        dsld_id = str(item.get("dsld_id") or "").strip()
        if not dsld_id:
            continue
        primary = str(item.get("primary_class") or "canary").strip() or "canary"
        subclass = str(item.get("subclass") or idx).strip() or str(idx)
        base = f"{primary}:{subclass}"
        seen[base] += 1
        archetype = base if seen[base] == 1 else f"{base}:{seen[base]}"
        loaded[archetype] = dsld_id

    return loaded or dict(CANARY_SET)


# ---------------------------------------------------------------------------
# Findings model
# ---------------------------------------------------------------------------

# Severity → exit-code gate. Anything BLOCKER fails the script.
SEVERITY_BLOCKER = "BLOCKER"
SEVERITY_HIGH    = "HIGH"
SEVERITY_MEDIUM  = "MEDIUM"
SEVERITY_LOW     = "LOW"

# Code catalog — per plan §"Severity assignment". One entry per finding code.
FINDING_CATALOG: dict[str, str] = {
    # BLOCKER — silent loss / clinical-data corruption
    "RAW_ACTIVE_MISSING_FROM_BLOB":           SEVERITY_BLOCKER,
    "RAW_INACTIVE_MISSING_FROM_BLOB":         SEVERITY_BLOCKER,
    "BLEND_CHILD_FLATTENED_NO_PARENT":        SEVERITY_BLOCKER,
    "INACTIVE_LIST_EMPTY_BUT_RAW_NONZERO":    SEVERITY_BLOCKER,
    "UNSAFE_UNIT_CONVERSION":                 SEVERITY_BLOCKER,
    "FLUTTER_DISPLAY_FALLBACK_MISMATCH":      SEVERITY_BLOCKER,
    "UNEXPLAINED_DROP_REASON":                SEVERITY_BLOCKER,
    "UNKNOWN_DROP_REASON_CODE":               SEVERITY_BLOCKER,
    # BLOCKER — the straight line raw DSLD row → exported row (--raw-root)
    "RAW_LABEL_NOT_FOUND":                    SEVERITY_BLOCKER,
    "RAW_LABEL_UNREADABLE":                   SEVERITY_BLOCKER,
    "RAW_ROW_MISSING_FROM_LEDGER":            SEVERITY_BLOCKER,
    "LEDGER_ROW_NOT_IN_RAW":                  SEVERITY_BLOCKER,
    "LEDGER_NAME_DIFFERS_FROM_RAW":           SEVERITY_BLOCKER,
    "EXPORT_IDENTITY_NOT_FROM_ENRICHER":      SEVERITY_BLOCKER,
    "AMOUNT_CHANGE_WITHOUT_EVIDENCE":         SEVERITY_BLOCKER,
    "NORMALIZED_DOSE_NOT_FROM_OWN_ROW":       SEVERITY_BLOCKER,
    "BLOB_WITHOUT_ENRICHED_RECORD":           SEVERITY_BLOCKER,
    # HIGH — contract violation that breaks routing / interaction matching
    "CANONICAL_ID_MISSING_ON_MAPPED":         SEVERITY_HIGH,
    "DISPLAY_LABEL_COLLAPSES_TO_CANONICAL":   SEVERITY_HIGH,
    "BRANDED_TOKEN_DROPPED":                  SEVERITY_HIGH,
    "PLANT_PART_DROPPED":                     SEVERITY_HIGH,
    "STANDARDIZATION_NOTE_DROPPED":           SEVERITY_HIGH,
    "WELL_DOSED_ON_UNDISCLOSED_BLEND":        SEVERITY_HIGH,
    "CORE_DB_BLOB_COUNT_MISMATCH":            SEVERITY_HIGH,
    # MEDIUM — degraded clinical-evidence routing or transparency
    "DELIVERS_MARKERS_MISSING_FOR_BOTANICAL": SEVERITY_MEDIUM,
    "EVIDENCE_BULLET_USES_RAW_ID":            SEVERITY_MEDIUM,
    "DISPLAY_DOSE_LABEL_NP_LEAK":             SEVERITY_MEDIUM,
    "BLEND_CHILD_WITHOUT_DOSE_DISCLOSURE":    SEVERITY_MEDIUM,
    # LOW — contract debt, informational
    "FORM_STATUS_ABSENT":                     SEVERITY_LOW,
    "FORM_MATCH_STATUS_ABSENT":               SEVERITY_LOW,
    "DOSE_STATUS_ABSENT":                     SEVERITY_LOW,
    "IS_SAFETY_CONCERN_ABSENT":               SEVERITY_LOW,
    "INACTIVE_V1_5_0_CONTRACT_ABSENT":        SEVERITY_LOW,
}


@dataclass
class Finding:
    """One discrepancy. A BLOCKER names where and what: the location, the field,
    the source-of-truth value (raw label, or the enricher's identity decision)
    and the exported value. The location is the raw row path (``ingredientRows[..]``
    / ``otheringredients.ingredients[..]``); ``label`` for a whole-label finding;
    or, when the row carries no raw_source_path, a ``cleaned:`` or ``blob:``
    location in that layer, never presented as a raw row."""
    severity: str
    code: str
    note: str
    ingredient: str | None = None
    stage: str | None = None
    row_path: str | None = None
    field: str | None = None
    source_value: Any = None
    exported_value: Any = None

    def as_dict(self) -> dict[str, Any]:
        out = {k: v for k, v in asdict(self).items() if v is not None}
        if self.field is not None:  # an absent value is evidence, not noise
            out.setdefault("source_value", None)
            out.setdefault("exported_value", None)
        return out


@dataclass
class ProductRecord:
    dsld_id: str
    archetype: str | None
    product_name: str | None
    upc: str | None
    stages: dict[str, Any] = field(default_factory=dict)
    findings: list[Finding] = field(default_factory=list)
    raw_source_found: bool = False
    notes: list[str] = field(default_factory=list)

    def add(self, code: str, note: str, ingredient: str | None = None, stage: str | None = None, *,
            row_path: str | None = None, field: str | None = None,
            source: Any = None, exported: Any = None) -> None:
        sev = FINDING_CATALOG.get(code)
        if sev is None:
            raise ValueError(f"unknown finding code {code!r} — add to FINDING_CATALOG first")
        if sev == SEVERITY_BLOCKER and not (row_path and field):
            raise ValueError(f"BLOCKER {code} must name its row_path and field")
        self.findings.append(Finding(severity=sev, code=code, note=note, ingredient=ingredient, stage=stage,
                                     row_path=row_path, field=field,
                                     source_value=source, exported_value=exported))

    def has_blocker(self) -> bool:
        return any(f.severity == SEVERITY_BLOCKER for f in self.findings)

    def as_dict(self) -> dict[str, Any]:
        return {
            "dsld_id": self.dsld_id,
            "archetype": self.archetype,
            "product_name": self.product_name,
            "upc": self.upc,
            "raw_source_found": self.raw_source_found,
            "stages": self.stages,
            "findings": [f.as_dict() for f in self.findings],
            "notes": self.notes,
        }


# ---------------------------------------------------------------------------
# Stage readers
# ---------------------------------------------------------------------------

class StageIndex:
    """Lazy DSLD-ID → cleaned-batch lookup across all `output_*/cleaned/` folders.

    Cleaned-batch files keep raw DSLD fields (`activeIngredients`,
    `inactiveIngredients`, `servingSizes`, `nutritionalInfo`, `otheringredients`)
    alongside the cleaner's classification (`display_ingredients`,
    `raw_actives_count`, `raw_inactives_count`). For the audit's "raw" view
    we use the raw DSLD fields from this same file."""

    def __init__(self, products_root: Path) -> None:
        self.products_root = products_root
        # dsld_id -> (cleaned_batch_path, index_into_list)
        self._index: dict[str, tuple[Path, int]] = {}
        self._loaded = False

    def build(self, only_ids: set[str] | None = None) -> None:
        """Walk output_*/cleaned/*.json and record where each DSLD ID lives.
        If `only_ids` is supplied, scan can short-circuit once all are found."""
        wanted: set[str] | None = set(only_ids) if only_ids else None
        for cleaned_dir in sorted(self.products_root.glob("output_*/cleaned")):
            for batch_path in sorted(cleaned_dir.glob("cleaned_batch_*.json")):
                try:
                    data = json.loads(batch_path.read_text())
                except Exception:
                    continue
                if not isinstance(data, list):
                    continue
                for i, product in enumerate(data):
                    did = str(product.get("id") or product.get("dsld_id") or "").strip()
                    if not did:
                        continue
                    # First occurrence wins. Brand folders may overlap on re-cleans.
                    if did not in self._index:
                        self._index[did] = (batch_path, i)
                if wanted and wanted.issubset(self._index.keys()):
                    self._loaded = True
                    return
        self._loaded = True

    def read(self, dsld_id: str) -> dict | None:
        if not self._loaded:
            self.build({dsld_id})
        entry = self._index.get(str(dsld_id))
        if not entry:
            return None
        path, idx = entry
        try:
            data = json.loads(path.read_text())
            return data[idx] if isinstance(data, list) and idx < len(data) else None
        except Exception:
            return None


def _read_blob(blob_dir: Path, dsld_id: str) -> dict | None:
    p = blob_dir / f"{dsld_id}.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def _load_excluded_by_gate(build_dir: Path) -> dict[str, list[str]]:
    """Return exact product quarantine destinations from the candidate.

    A missing live blob is reconciled only when ``export_manifest.json`` names
    that same product in ``excluded_by_gate``. Aggregate ingredient drop
    telemetry is deliberately ignored and cannot self-amnesty a source row.
    """
    manifest_path = build_dir / "export_manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    exclusions: dict[str, list[str]] = {}
    for row in manifest.get("excluded_by_gate") or []:
        if not isinstance(row, dict):
            continue
        dsld_id = str(row.get("dsld_id") or "").strip()
        reason = str(row.get("error") or "").strip()
        if not dsld_id or not reason:
            continue
        reasons = exclusions.setdefault(dsld_id, [])
        if reason not in reasons:
            reasons.append(reason)
    return exclusions


def _read_core_row(db_path: Path, dsld_id: str) -> dict | None:
    if not db_path.exists():
        return None
    with contextlib.closing(sqlite3.connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.execute("SELECT * FROM products_core WHERE dsld_id = ?", (dsld_id,))
            row = cur.fetchone()
            return dict(row) if row else None
        except sqlite3.DatabaseError:
            return None


# ---------------------------------------------------------------------------
# Per-stage counters
# ---------------------------------------------------------------------------

def _count_raw_actives_from_cleaned(cleaned: dict) -> int:
    """Count raw DSLD activeIngredients entries — this is what the user saw
    on the bottle. Includes nested blend members."""
    actives = cleaned.get("activeIngredients") or []
    # Each entry is one label row. Nested rows count separately.
    n = 0
    def walk(rows: list) -> None:
        nonlocal n
        if not isinstance(rows, list):
            return
        for r in rows:
            if isinstance(r, dict):
                n += 1
                walk(r.get("nestedRows") or [])
    walk(actives)
    return n


def _count_raw_inactives_from_cleaned(cleaned: dict) -> int:
    """Count raw DSLD inactive ingredients — `inactiveIngredients` OR
    `otheringredients.ingredients` depending on DSLD source variant."""
    inacts = cleaned.get("inactiveIngredients")
    if isinstance(inacts, list) and inacts:
        return len(inacts)
    other = cleaned.get("otheringredients") or {}
    ingredients = other.get("ingredients") if isinstance(other, dict) else None
    if isinstance(ingredients, list):
        return len(ingredients)
    return 0


def _collect_raw_active_names(cleaned: dict) -> list[tuple[str, str]]:
    """(name, location) per cleaned active: its raw_source_path, else a ``cleaned:`` location."""
    out: list[tuple[str, str]] = []
    def walk(rows: list, prefix: str) -> None:
        if not isinstance(rows, list):
            return
        for index, r in enumerate(rows):
            if isinstance(r, dict):
                path = r.get("raw_source_path") or f"{prefix}[{index}]"
                n = r.get("name") or r.get("ingredientName") or ""
                if n:
                    out.append((str(n), str(path)))
                walk(r.get("nestedRows") or [], f"{prefix}[{index}].nestedRows")
    walk(cleaned.get("activeIngredients") or [], "cleaned:activeIngredients")
    return out


def _collect_raw_inactive_names(cleaned: dict) -> list[tuple[str, str]]:
    """(name, location) per cleaned inactive: its raw_source_path, else a ``cleaned:`` location."""
    out: list[tuple[str, str]] = []
    other = cleaned.get("otheringredients") or {}
    for prefix, rows in (
        ("cleaned:inactiveIngredients", cleaned.get("inactiveIngredients")),
        ("cleaned:otheringredients.ingredients", other.get("ingredients") if isinstance(other, dict) else None),
    ):
        for index, r in enumerate(rows if isinstance(rows, list) else []):
            path = f"{prefix}[{index}]"
            if isinstance(r, dict):
                n = r.get("name") or r.get("ingredientName") or ""
                if n:
                    out.append((str(n), str(r.get("raw_source_path") or path)))
            elif isinstance(r, str):
                out.append((r, path))
    return out


# ---------------------------------------------------------------------------
# Checks (each takes a record and the loaded stages, appends findings)
# ---------------------------------------------------------------------------

BRANDED_TOKENS = (
    "KSM-66","Meriva","BioPerine","Ferrochel","Sensoril","Phytosome",
    "Pycnogenol","Setria","Albion","TRAACS","Chromax","Curcumin C3",
    "Longvida","Wellmune","CurcuWIN","LJ100","enXtra","AstraGin","Venetron",
)
PLANT_PART_RE = re.compile(
    r"\b(root|leaf|leaves|seed|bark|rhizome|flower|fruit|stem|aerial)\b",
    re.IGNORECASE,
)
NP_RE = re.compile(r"\bNP\b")

# v1.5.0 fields the audit reports on every active that's missing them.
# Per Phase 0 we know these are 0% emitted across all 8169 blobs — so each
# canary will surface N findings here. The summary aggregates them.
V1_5_0_ACTIVE_FIELDS = (
    ("form_status",       "FORM_STATUS_ABSENT"),
    ("form_match_status", "FORM_MATCH_STATUS_ABSENT"),
    ("dose_status",       "DOSE_STATUS_ABSENT"),
    ("is_safety_concern", "IS_SAFETY_CONCERN_ABSENT"),
)


def _normalize_name(s: str) -> str:
    """Cheap normalization for label-name matching across stages."""
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def _check_drop_reason_enum(rec: ProductRecord, blob: dict) -> None:
    # E1.2.5 enum already exists; assert any reasons used are in the allowed set.
    try:
        from build_final_db import _ALLOWED_DROP_REASONS  # type: ignore
        allowed = set(_ALLOWED_DROP_REASONS)
    except Exception:
        # Hard-code the canonical set (kept in sync with build_final_db).
        allowed = {
            "DROPPED_STRUCTURAL_HEADER",
            "DROPPED_NUTRITION_FACT",
            "DROPPED_AS_INACTIVE",
            "DROPPED_SUMMARY_WRAPPER",
            "DROPPED_UNMAPPED_ACTIVE",
            "DROPPED_PARSE_ERROR",
        }
    reasons = blob.get("ingredients_dropped_reasons") or []
    for r in reasons:
        if r not in allowed:
            rec.add("UNKNOWN_DROP_REASON_CODE", f"reason {r!r} not in enum",
                    row_path="label", field="ingredients_dropped_reasons", exported=r)


def _check_active_count_reconciliation(rec: ProductRecord, blob: dict) -> None:
    raw = int(blob.get("raw_actives_count") or 0)
    blob_n = len(blob.get("ingredients") or [])
    reasons = blob.get("ingredients_dropped_reasons") or []
    if raw > 0 and blob_n == 0 and not reasons:
        rec.add("UNEXPLAINED_DROP_REASON",
                f"raw_actives_count={raw}, ingredients=0, no drop reasons emitted",
                row_path="label", field="ingredients", source=raw, exported=blob_n)


def _check_inactive_recovery(rec: ProductRecord, blob: dict) -> None:
    raw = blob.get("raw_inactives_count")
    if not isinstance(raw, int):
        return
    blob_n = len(blob.get("inactive_ingredients") or [])
    if raw > 0 and blob_n == 0:
        rec.add("INACTIVE_LIST_EMPTY_BUT_RAW_NONZERO",
                f"raw_inactives_count={raw}, blob inactive_ingredients=0",
                row_path="label", field="inactive_ingredients", source=raw, exported=blob_n)


def _check_raw_actives_present_in_blob(
    rec: ProductRecord, cleaned: dict | None, blob: dict
) -> None:
    if cleaned is None:
        return
    raw_names = _collect_raw_active_names(cleaned)
    # All places a raw name might legitimately land in the blob:
    blob_names: set[str] = set()
    for ing in blob.get("ingredients") or []:
        for k in ("raw_source_text", "name", "standard_name", "display_label"):
            v = ing.get(k)
            if v:
                blob_names.add(_normalize_name(str(v)))
    for ing in blob.get("inactive_ingredients") or []:
        for k in ("raw_source_text", "name", "standard_name", "display_label"):
            v = ing.get(k)
            if v:
                blob_names.add(_normalize_name(str(v)))
    # Non-scoring label rows remain valid destinations. Count both displayed
    # rows and explicit ledger omissions; neither should have to masquerade as
    # a scored or inactive ingredient merely to reconcile its source line.
    for collection in (
        "display_ingredients",
        "label_ledger_omissions",
        "row_ledger",
    ):
        for row in blob.get(collection) or []:
            if not isinstance(row, dict):
                continue
            for key in (
                "raw_source_text",
                "source_label",
                "label_display_name",
                "display_name",
            ):
                value = row.get(key)
                if value:
                    blob_names.add(_normalize_name(str(value)))
    pbd = blob.get("proprietary_blend_detail") or {}
    for blnd in pbd.get("blends") or []:
        if isinstance(blnd, dict):
            blend_name = blnd.get("name") or ""
            if blend_name:
                blob_names.add(_normalize_name(blend_name))
            for ck in ("child_ingredients", "children", "ingredients"):
                for c in blnd.get(ck) or []:
                    if isinstance(c, dict):
                        for k in ("name", "raw_source_text", "standard_name"):
                            v = c.get(k)
                            if v:
                                blob_names.add(_normalize_name(str(v)))
                    elif isinstance(c, str):
                        blob_names.add(_normalize_name(c))
    for n in (blob.get("unmapped_actives") or {}).get("names") or []:
        blob_names.add(_normalize_name(n))

    for raw_name, raw_path in raw_names:
        nk = _normalize_name(raw_name)
        if not nk:
            continue
        if nk in blob_names:
            continue
        # cheaper substring fallback — handles "Vitamin A Palmitate" ↔ "Retinyl Palmitate"
        if any(nk in bn or bn in nk for bn in blob_names if len(bn) >= 4):
            continue
        rec.add("RAW_ACTIVE_MISSING_FROM_BLOB",
                f"raw label name {raw_name!r} appears nowhere in blob or row ledger",
                ingredient=raw_name, row_path=raw_path, field="name", source=raw_name)


def _check_raw_inactives_present_in_blob(
    rec: ProductRecord, cleaned: dict | None, blob: dict
) -> None:
    if cleaned is None:
        return
    raw_names = _collect_raw_inactive_names(cleaned)
    blob_names: set[str] = set()
    for ing in blob.get("inactive_ingredients") or []:
        for k in ("raw_source_text", "name", "standard_name"):
            v = ing.get(k)
            if v:
                blob_names.add(_normalize_name(str(v)))
    # Some inactives may legitimately have been reclassified as actives,
    # so also accept ingredients[] matches.
    for ing in blob.get("ingredients") or []:
        for k in ("raw_source_text", "name", "standard_name"):
            v = ing.get(k)
            if v:
                blob_names.add(_normalize_name(str(v)))
    for n, raw_path in raw_names:
        nk = _normalize_name(n)
        if not nk:
            continue
        if nk in blob_names or any(nk in bn or bn in nk for bn in blob_names if len(bn) >= 4):
            continue
        rec.add("RAW_INACTIVE_MISSING_FROM_BLOB",
                f"raw label inactive {n!r} not in blob",
                ingredient=n, row_path=raw_path, field="name", source=n)


def _check_v1_5_0_contract(rec: ProductRecord, blob: dict) -> None:
    """For each active, flag missing v1.5.0 fields. Aggregate at LOW severity
    because they're documented in the contract spec but the implementation
    has not landed (Phase 0 showed 0% emit across all 8169 blobs)."""
    for ing in blob.get("ingredients") or []:
        for field_name, code in V1_5_0_ACTIVE_FIELDS:
            if ing.get(field_name) is None:
                rec.add(code,
                        f"v1.5.0 promises {field_name!r}, missing on this active",
                        ingredient=ing.get("name") or ing.get("raw_source_text"))
    # Inactive contract: aggregate one finding per missing field across all inactives
    inacts = blob.get("inactive_ingredients") or []
    if inacts:
        for field_name in ("display_label", "display_role_label", "severity_status", "is_safety_concern"):
            n_missing = sum(1 for x in inacts if x.get(field_name) is None)
            if n_missing > 0:
                rec.add("INACTIVE_V1_5_0_CONTRACT_ABSENT",
                        f"{n_missing}/{len(inacts)} inactives missing {field_name!r}")


def _check_canonical_id_on_mapped(rec: ProductRecord, blob: dict) -> None:
    for ing in blob.get("ingredients") or []:
        is_mapped = bool(ing.get("is_mapped"))
        cid = ing.get("canonical_id") or ing.get("normalized_key") or ing.get("parent_key")
        if is_mapped and not cid:
            rec.add("CANONICAL_ID_MISSING_ON_MAPPED",
                    "is_mapped=True but canonical_id/normalized_key/parent_key absent",
                    ingredient=ing.get("name"))


def _app_active_rows(blob: dict) -> list[dict[str, Any]]:
    """Return the rows Flutter actually uses for the active label surface.

    Schema 2.4 renders ``display_ingredients`` whenever that canonical ledger
    is present. ``ingredients`` is then analysis compatibility data, not the
    title source of truth. Older blobs without the ledger retain the legacy
    fallback.
    """
    if isinstance(blob.get("display_ingredients"), list):
        excluded_types = {
            "inactive_ingredient",
            "nutrition_fact",
            "structural_container",
            "summary_wrapper",
        }
        return [
            row
            for row in blob["display_ingredients"]
            if isinstance(row, dict)
            and str(row.get("display_type") or "").strip() not in excluded_types
            and str(row.get("source_section") or "").strip().lower()
            not in {"inactive", "inactiveingredients"}
        ]
    return [
        row for row in (blob.get("ingredients") or []) if isinstance(row, dict)
    ]


def _row_analysis_value(row: Mapping[str, Any], key: str) -> Any:
    if key in row:
        return row.get(key)
    analysis = row.get("analysis")
    return analysis.get(key) if isinstance(analysis, Mapping) else None


def _app_display_label(row: Mapping[str, Any]) -> str:
    for key in (
        "label_display_name",
        "display_label",
        "standard_name",
        "name",
        "raw_source_text",
    ):
        value = _row_analysis_value(row, key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _app_visible_surface(row: Mapping[str, Any]) -> str:
    """Combine title and separately rendered form detail for fidelity checks."""
    values: list[str] = [_app_display_label(row)]
    for key in (
        "label_display_form",
        "display_form_label",
        "form_note_preview",
        "form_note",
    ):
        value = _row_analysis_value(row, key)
        if value is not None and str(value).strip():
            values.append(str(value).strip())
    return " ".join(values).lower()


def _is_reciprocal_display_remap(
    row: Mapping[str, Any], rows: list[dict[str, Any]]
) -> bool:
    """Recognize an explicit two-row source correction without self-amnesty.

    A reviewed hierarchy correction can swap two DSLD source identities while
    preserving both original source paths in the display ledger.  Treat that
    as intentional only when the peer points back, both rows retain the same
    canonical identity, and their source/display labels are exact reciprocals.
    A one-way or merely canonical remap must still fail the fidelity check.
    """
    own_path = str(row.get("raw_source_path") or "").strip()
    mapped = row.get("mapped_to")
    mapped_path = str(
        mapped.get("raw_source_path") if isinstance(mapped, Mapping) else ""
    ).strip()
    if not own_path or not mapped_path or own_path == mapped_path:
        return False

    source = _normalize_name(
        str(row.get("raw_source_text") or row.get("name") or "")
    )
    display = _normalize_name(_app_display_label(row))
    canonical_id = str(
        _row_analysis_value(row, "canonical_id")
        or row.get("canonical_id")
        or ""
    ).strip()
    if not source or not display or not canonical_id:
        return False

    for peer in rows:
        if peer is row:
            continue
        if str(peer.get("raw_source_path") or "").strip() != mapped_path:
            continue
        peer_mapped = peer.get("mapped_to")
        peer_mapped_path = str(
            peer_mapped.get("raw_source_path")
            if isinstance(peer_mapped, Mapping)
            else ""
        ).strip()
        if peer_mapped_path != own_path:
            continue
        peer_canonical_id = str(
            _row_analysis_value(peer, "canonical_id")
            or peer.get("canonical_id")
            or ""
        ).strip()
        if peer_canonical_id != canonical_id:
            continue
        peer_source = _normalize_name(
            str(peer.get("raw_source_text") or peer.get("name") or "")
        )
        peer_display = _normalize_name(_app_display_label(peer))
        if source == peer_display and display == peer_source:
            return True
    return False


def _check_display_label_collapse(rec: ProductRecord, blob: dict, raw: Mapping[str, Any] | None = None) -> None:
    """Invariant #1 from test_label_fidelity_contract.py."""
    corrected = _corrected_source_paths(raw, rec.dsld_id) if raw else {}
    rows = _app_active_rows(blob)
    for ing in rows:
        display = _app_display_label(ing)
        canonical = (
            _row_analysis_value(ing, "canonical_name")
            or _row_analysis_value(ing, "scoring_group_canonical")
            or _row_analysis_value(ing, "standard_name")
            or _row_analysis_value(ing, "display_label")
            or ""
        )
        canonical = str(canonical).strip()
        source = (ing.get("raw_source_text") or ing.get("name") or "").strip()
        if not display or not canonical or not source:
            continue
        correction = corrected.get(ing.get("raw_source_path")) or {}
        if (correction.get("_label_correction_applied")
                and source == correction.get("_pre_correction_name")
                and display == correction.get("name")):
            continue
        if (display.lower() == canonical.lower()
                and source.lower() != canonical.lower()
                and _normalize_name(source) not in _normalize_name(
                    _app_visible_surface(ing)
                )
                and not _is_reciprocal_display_remap(ing, rows)):
            rec.add("DISPLAY_LABEL_COLLAPSES_TO_CANONICAL",
                    f"display={display!r} canonical={canonical!r} source={source!r}",
                    ingredient=source)


def _check_branded_tokens(rec: ProductRecord, blob: dict) -> None:
    """Invariant #4: branded tokens (KSM-66, Meriva...) preserved in display_label.

    IMPORTANT: only scan **label-derived** fields (raw_source_text, name, forms[].name).
    Earlier versions scanned ``notes`` as well, which produced large numbers of
    false positives: IQM ``notes`` is reference text that often mentions multiple
    branded forms applicable to the nutrient class (e.g. the manganese IQM note
    discusses Ferrochel as a related chelate). That text is editorial context,
    not label content — flagging it as a "dropped branded token" is wrong.
    """
    for ing in _app_active_rows(blob):
        # Only scan LABEL-derived fields.
        label_sources = [
            ing.get("name") or "",
            ing.get("raw_source_text") or "",
            " ".join(
                (f.get("name", "") if isinstance(f, dict) else "")
                for f in (ing.get("forms") or [])
            ),
        ]
        label_blob = " ".join(label_sources).lower()
        display = _app_visible_surface(ing)
        for tok in BRANDED_TOKENS:
            if tok.lower() in label_blob and tok.lower() not in display:
                rec.add("BRANDED_TOKEN_DROPPED",
                        f"branded token {tok!r} in label data but absent from app display surface={display!r}",
                        ingredient=ing.get("name"))
                break


def _check_plant_part(rec: ProductRecord, blob: dict) -> None:
    """Invariant #5: plant part token preserved in display_label."""
    for ing in _app_active_rows(blob):
        forms = ing.get("forms") or []
        form_blob = " ".join((f.get("name", "") if isinstance(f, dict) else "") for f in forms)
        raw = (ing.get("raw_source_text") or "")
        for source_text in (form_blob, raw):
            m = PLANT_PART_RE.search(source_text)
            if not m:
                continue
            part = m.group(1).lower()
            display = _app_visible_surface(ing)
            equivalents = {"leaf": ("leaf", "leaves"), "leaves": ("leaf", "leaves")}
            acceptable = equivalents.get(part, (part,))
            if not any(e in display for e in acceptable):
                rec.add("PLANT_PART_DROPPED",
                        f"plant part {part!r} present in source {source_text!r} but absent from app display surface",
                        ingredient=ing.get("name"))
                break  # one finding per ingredient


def _check_standardization(rec: ProductRecord, blob: dict, cleaned: dict | None = None) -> None:
    """Invariant #6: exporter-recognized standardization claims survive.

    The producer deliberately recognizes only reviewed compounds and rejects
    ranges, generic editorial prose, and unsupported marker names. The audit
    must recompute that exact contract; a broad ``%``/``standardized`` cue
    creates false release failures for claims the exporter correctly refused
    to turn into consumer copy. The claim source is the label row (the cleaned
    row's notes, matched by raw_source_path), never the blob's IQM notes.
    """
    from build_final_db import _compute_standardization_note  # type: ignore

    label_rows = {row.get("raw_source_path"): row
                  for row in ((cleaned or {}).get("activeIngredients") or [])
                  if isinstance(row, dict) and row.get("raw_source_path")}
    for ing in blob.get("ingredients") or []:
        label = label_rows.get(ing.get("raw_source_path")) or {}
        expected = _compute_standardization_note({
            "notes": label.get("notes"),
            "raw_source_text": ing.get("raw_source_text"),
            **{key: label.get(key) for key in ("quantity", "unit", "parentBlendMass", "parentBlendUnit")},
        })
        if not expected:
            continue
        actual = ing.get("standardization_note")
        if actual != expected:
            rec.add("STANDARDIZATION_NOTE_DROPPED",
                    f"expected standardization_note={expected!r}, got {actual!r}",
                    ingredient=ing.get("name"))


def _check_np_leak(rec: ProductRecord, blob: dict) -> None:
    """Invariant #3: NP sentinel never in display_dose_label."""
    for ing in blob.get("ingredients") or []:
        label = ing.get("display_dose_label") or ""
        if NP_RE.search(label):
            rec.add("DISPLAY_DOSE_LABEL_NP_LEAK",
                    f"display_dose_label leaks 'NP': {label!r}",
                    ingredient=ing.get("name"))


def _check_well_dosed_on_undisclosed(rec: ProductRecord, blob: dict) -> None:
    """Invariant #2."""
    for ing in blob.get("ingredients") or []:
        in_blend = bool(ing.get("is_in_proprietary_blend"))
        disclosed = bool(ing.get("individually_disclosed"))
        badge = (ing.get("display_badge") or "").strip().lower()
        if in_blend and not disclosed and badge == "well_dosed":
            rec.add("WELL_DOSED_ON_UNDISCLOSED_BLEND",
                    f"prop-blend member with undisclosed dose badged 'well_dosed'",
                    ingredient=ing.get("name"))


def _check_unsafe_unit_conversion(rec: ProductRecord, blob: dict) -> None:
    """Vitamin A IU normalization requires explicit form lineage.

    NIH ODS uses 0.3 mcg RAE/IU for both preformed retinol and supplemental
    beta-carotene, but only preformed retinol participates in the Vitamin A UL.
    If a Vitamin A active has unit IU but no form-aware normalization, that's a
    BLOCKER. Vitamin D IU ↔ mcg is form-agnostic (40 IU/mcg) so we don't flag
    it. Vitamin E IU↔mg differs by tocopherol form (alpha vs mixed) and is
    similarly form-dependent — flag it.
    """
    def has_explicit_unknown_vitamin_a_evidence(ing: dict) -> bool:
        ev = ing.get("conversion_evidence")
        if not isinstance(ev, dict):
            return False
        warnings = " ".join(str(w) for w in (ev.get("warnings") or []))
        return (
            ev.get("conversion_rule_id") == "vitamin_a_unknown"
            and ev.get("form_detection_source") == "no_conversion_possible"
            and str(ev.get("confidence") or "").lower() == "low"
            and (
                "retinol vs beta-carotene" in warnings.lower()
                or ("form" in warnings.lower() and "unknown" in warnings.lower())
            )
        )

    for index, ing in enumerate(blob.get("ingredients") or []):
        location = dict(row_path=ing.get("raw_source_path") or f"blob:ingredients[{index}]", field="normalized_amount",
                        source=f"{ing.get('quantity')} {ing.get('unit')}",
                        exported=None if ing.get("normalized_amount") is None
                        else f"{ing.get('normalized_amount')} {ing.get('normalized_unit')}")
        n = (ing.get("name") or "").lower()
        unit = (ing.get("unit") or "").upper()
        normalized_unit = (ing.get("normalized_unit") or "").upper()
        normalized_value = ing.get("normalized_amount")
        if unit == "IU" and ("vitamin a" in n or "retinyl" in n or "carotene" in n):
            # Need a normalized RAE value AND form-aware factor.
            if normalized_value is None or normalized_unit not in ("MCG RAE", "MCG", "UG RAE", "UG"):
                if has_explicit_unknown_vitamin_a_evidence(ing):
                    continue
                rec.add("UNSAFE_UNIT_CONVERSION",
                        f"Vitamin A in IU ({ing.get('quantity')}) without form-aware normalization to mcg RAE",
                        ingredient=ing.get("name"), **location)
        if unit == "IU" and "vitamin e" in n:
            if normalized_value is None:
                rec.add("UNSAFE_UNIT_CONVERSION",
                        f"Vitamin E in IU without form-aware normalization (alpha vs mixed tocopherols differ)",
                        ingredient=ing.get("name"), **location)


def _check_blend_children(rec: ProductRecord, blob: dict) -> None:
    """Blend children sanity. The cleaner's blend classifier uses 4 states
    (see project_blend_classifier_4state memory): DISCLOSED_BLEND,
    BLEND_HEADER, OPAQUE_BLEND, fake-transparency-as-OPAQUE.

    Correct behavior per state (disclosure_level field in the blob):
      - "full":               every named child has an individual dose.
      - "partial":            blend total and child names are disclosed;
                              individual child doses may be withheld.
      - "none" (OPAQUE):      children MAY be listed by name without doses
                              (the label says "Antioxidant Blend (2.4 g)
                              consisting of: A, B, C..."). What makes the
                              blend opaque is the LACK of individual doses,
                              not the absence of names. Only a BLOCKER
                              if a child has a non-None quantity that
                              contradicts the parent's "none" classification.

    Flatten = a child appears with no name at all → BLOCKER (silent loss).
    """
    pbd = blob.get("proprietary_blend_detail") or {}
    blends = pbd.get("blends") or []
    for blend_index, blnd in enumerate(blends):
        if not isinstance(blnd, dict):
            continue
        disclosure_level = (blnd.get("disclosure_level") or "").lower()
        kids_key = "child_ingredients" if blnd.get("child_ingredients") else "children"
        kids = blnd.get("child_ingredients") or blnd.get("children") or []
        for child_index, child in enumerate(kids):
            if not isinstance(child, dict):
                continue
            has_name = bool(
                child.get("name")
                or child.get("standard_name")
                or child.get("raw_source_text")
            )
            if not has_name:
                # A child without ANY name is a silent loss.
                rec.add("BLEND_CHILD_FLATTENED_NO_PARENT",
                        f"blend {blnd.get('name')!r} has a child entry with no name",
                        ingredient=blnd.get("name"),
                        row_path=child.get("raw_source_path")
                        or f"blob:proprietary_blend_detail.blends[{blend_index}].{kids_key}[{child_index}]",
                        field="name", exported=child)
                continue

            # Per-state checks
            child_qty = (
                child.get("amount")
                if "amount" in child
                else child.get("quantity")
            )
            has_child_amount = (
                child_qty is not None
                and child_qty != ""
                and not isinstance(child_qty, bool)
            )
            if disclosure_level == "full":
                # Full means every child amount is individually disclosed.
                disclosed = (
                    child.get("is_disclosed_dose")
                    or child.get("disclosed")
                    or has_child_amount
                )
                if not disclosed:
                    rec.add("BLEND_CHILD_WITHOUT_DOSE_DISCLOSURE",
                            f"blend {blnd.get('name')!r} (full) child "
                            f"{child.get('name')!r} has no dose / disclosure flag",
                            ingredient=child.get("name"))
            elif disclosure_level == "partial":
                # Partial is a parent-total contract, not a promise that any
                # one child's dose is known.
                blend_total = blnd.get("total_weight")
                if blend_total is None:
                    blend_total = blnd.get("blend_total_mg")
                if not isinstance(blend_total, (int, float)) or blend_total <= 0:
                    rec.add(
                        "BLEND_CHILD_WITHOUT_DOSE_DISCLOSURE",
                        f"blend {blnd.get('name')!r} marked partial but has no "
                        "positive disclosed blend total",
                        ingredient=blnd.get("name"),
                    )
                    break
            elif disclosure_level == "none":
                # OPAQUE blend: child names OK, doses MUST be None.
                # A non-None dose contradicts the parent's classification.
                if has_child_amount:
                    rec.add("BLEND_CHILD_WITHOUT_DOSE_DISCLOSURE",
                            f"blend {blnd.get('name')!r} marked opaque (disclosure='none') "
                            f"but child {child.get('name')!r} has quantity={child_qty!r} — "
                            "classifier and child data disagree",
                            ingredient=child.get("name"))


def _check_core_db_blob_agreement(rec: ProductRecord, core_row: dict | None, blob: dict) -> None:
    """The plan calls for core_db.active_ingredient_count to match
    len(blob.ingredients). v1.5.0 schema does NOT declare these columns —
    so if they're missing, we record that as a contract-doc-vs-implementation
    drift note rather than a row-mismatch."""
    if core_row is None:
        rec.notes.append("core_db row not found for dsld_id — skipping core_db agreement check")
        return
    # Columns called out in the user's prompt — but they may not exist in current schema.
    blob_active_n = len(blob.get("ingredients") or [])
    blob_inactive_n = len(blob.get("inactive_ingredients") or [])
    if "active_ingredient_count" in core_row:
        c = core_row.get("active_ingredient_count")
        if c is not None and c != blob_active_n:
            rec.add("CORE_DB_BLOB_COUNT_MISMATCH",
                    f"core_db.active_ingredient_count={c} vs len(blob.ingredients)={blob_active_n}")
    else:
        rec.notes.append("core_db has no `active_ingredient_count` column — v1.5.0 doc lists fields that aren't in the schema")
    if "inactive_ingredient_count" in core_row:
        c = core_row.get("inactive_ingredient_count")
        if c is not None and c != blob_inactive_n:
            rec.add("CORE_DB_BLOB_COUNT_MISMATCH",
                    f"core_db.inactive_ingredient_count={c} vs len(blob.inactive_ingredients)={blob_inactive_n}")


def _check_unmapped_consistency(rec: ProductRecord, blob: dict) -> None:
    """An ingredient listed in unmapped_actives.names must NOT also appear
    in ingredients[] — otherwise we're double-rendering."""
    unmapped_names = {(_normalize_name(n)) for n in (blob.get("unmapped_actives") or {}).get("names") or []}
    if not unmapped_names:
        return
    in_actives = {_normalize_name((i.get("name") or i.get("raw_source_text") or "")) for i in blob.get("ingredients") or []}
    dupes = unmapped_names & in_actives
    if dupes:
        rec.add("RAW_ACTIVE_MISSING_FROM_BLOB",  # closest catalog match
                f"ingredients in BOTH ingredients[] and unmapped_actives.names: {sorted(dupes)}",
                row_path="label", field="unmapped_actives.names", exported=sorted(dupes))


# ---------------------------------------------------------------------------
# Top-level audit driver
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Line integrity — every raw DSLD row reaches the export unchanged or with a
# recorded reason (line integrity audit 2026-10-19; ADR-0005)
# ---------------------------------------------------------------------------

def _raw_paths(raw: Mapping[str, Any]) -> dict[str, dict]:
    """Every raw row path, enumerated from the label itself (not from the ledger)."""
    paths: dict[str, dict] = {}

    def walk(rows: Any, prefix: str) -> None:
        for index, row in enumerate(rows if isinstance(rows, list) else []):
            if not isinstance(row, dict):
                continue
            path = f"{prefix}[{index}]"
            paths[path] = row
            walk(row.get("nestedRows"), f"{path}.nestedRows")
            for form_index, form in enumerate(row.get("forms") or []):
                if isinstance(form, dict):
                    paths[f"{path}.forms[{form_index}]"] = form

    walk(raw.get("ingredientRows"), "ingredientRows")
    other = raw.get("otheringredients")
    walk(other.get("ingredients") if isinstance(other, dict) else None, "otheringredients.ingredients")
    return paths


@lru_cache(maxsize=1)
def _label_correction_owner():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    return EnhancedDSLDNormalizer()


def _verified_corrected_form_paths(raw: Mapping[str, Any], product_id: str) -> dict[str, dict]:
    """Read reviewed form replacements through the cleaner's guarded applier.

    Original ingredient rows and amounts remain the independent audit source.
    Only form inventories explicitly replaced by an applied correction differ.
    """
    paths = _corrected_source_paths(raw, product_id)
    out = {}
    for path, row in paths.items():
        if row.get("_label_correction_applied") and "_pre_correction_forms" in row:
            prefix = f"{path}.forms["
            out.update({ref: form for ref, form in paths.items() if ref.startswith(prefix)})
    return out


def _corrected_source_paths(raw: Mapping[str, Any], product_id: str) -> dict[str, dict]:
    owner = _label_correction_owner()
    if str(product_id) not in owner._label_corrections_by_dsld_id:
        return {}
    corrected = dict(raw)
    rows = deepcopy(raw.get("ingredientRows") or [])
    # Clean stamps immutable source paths before applying reviewed corrections.
    # Audit the same guarded correction against a copy of those source rows.
    owner._stamp_raw_source_paths(rows, "ingredientRows")
    corrected["ingredientRows"] = owner._apply_label_corrections(
        rows, str(product_id))
    return _raw_paths(corrected)


def _line_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().casefold()


def _same_amount(a: Any, b: Any) -> bool:
    return (
        isinstance(a, (int, float)) and isinstance(b, (int, float))
        and abs(float(a) - float(b)) <= 1e-9 * max(1.0, abs(float(a)))
    )


def _recorded_amounts(cleaned_row: Mapping[str, Any]) -> list[tuple[Any, str]]:
    """(amount, unit) values the cleaner recorded a reason to export.

    A selected printed serving column (quantityVariants), a reviewer-signed
    source correction, or a %DV-equation dose correction (dose_data_quality).
    """
    out: list[tuple[Any, str]] = []
    for variant in cleaned_row.get("quantityVariants") or []:
        if isinstance(variant, dict) and variant.get("selected_for_analysis"):
            out.append((variant.get("quantity"), _line_text(variant.get("unit"))))
    correction = cleaned_row.get("source_correction")
    if isinstance(correction, dict):
        unit = correction.get("corrected_quantity_unit") or cleaned_row.get("unit")
        amount = correction.get("corrected_quantity", cleaned_row.get("quantity"))
        out.append((amount, _line_text(unit)))
    quality = cleaned_row.get("dose_data_quality")
    if isinstance(quality, dict) and quality.get("corrected_unit"):
        out.append((quality.get("corrected_amount"), _line_text(quality.get("corrected_unit"))))
    return out


def _check_line_integrity(
    rec: ProductRecord,
    raw: Mapping[str, Any],
    cleaned: Mapping[str, Any] | None,
    enriched: Mapping[str, Any] | None,
    blob: Mapping[str, Any],
) -> None:
    raws = _raw_paths(raw)
    for path, form in _verified_corrected_form_paths(raw, rec.dsld_id).items():
        raws.setdefault(path, form)
    rows = {path for path in raws if ".forms[" not in path}
    ledger = [entry for entry in blob.get("row_ledger") or [] if isinstance(entry, dict)]
    refs = {entry.get("row_ref") for entry in ledger}
    for path in sorted(rows - refs):
        rec.add("RAW_ROW_MISSING_FROM_LEDGER", f"raw row {path} has no row_ledger entry",
                ingredient=raws[path].get("name"), stage="blob",
                row_path=path, field="row_ledger.row_ref", source=raws[path].get("name"))
    labels = {str(entry.get("row_ref")): entry.get("source_label") for entry in ledger}
    for ref in sorted(str(r) for r in refs if r and r not in raws):
        rec.add("LEDGER_ROW_NOT_IN_RAW", f"row_ledger names {ref}, which the raw label does not have",
                ingredient=labels.get(ref), stage="blob", row_path=ref, field="row_ledger.row_ref", exported=ref)
    for row in blob.get("ingredients") or []:
        path = row.get("raw_source_path") if isinstance(row, dict) else None
        if path and path not in raws:
            rec.add("LEDGER_ROW_NOT_IN_RAW", f"exported row points at {path}, which the raw label does not have",
                    ingredient=row.get("name"), stage="blob",
                    row_path=path, field="ingredients.raw_source_path", exported=path)
    for entry in ledger:
        ref = entry.get("row_ref")
        if ref in raws and entry.get("source_label") is not None:
            if _line_text(entry.get("source_label")) != _line_text(raws[ref].get("name")):
                rec.add("LEDGER_NAME_DIFFERS_FROM_RAW",
                        f"{ref}: ledger {entry.get('source_label')!r} vs raw {raws[ref].get('name')!r}", stage="blob",
                        row_path=ref, field="row_ledger.source_label",
                        source=raws[ref].get("name"), exported=entry.get("source_label"))

    _check_export_identity(rec, enriched, blob)

    # Amounts: a changed printed amount or unit carries the cleaner's recorded reason.
    cleaned_rows = {
        row.get("raw_source_path"): row
        for row in (cleaned or {}).get("activeIngredients") or []
        if isinstance(row, dict) and row.get("raw_source_path")
    }
    for row in blob.get("ingredients") or []:
        path = row.get("raw_source_path") if isinstance(row, dict) else None
        if path not in raws:
            continue
        printed = [q for q in raws[path].get("quantity") or [] if isinstance(q, dict)]
        first = printed[0] if printed else {}
        amount, unit = row.get("quantity"), _line_text(row.get("unit"))
        if not (isinstance(first.get("quantity"), (int, float)) and first["quantity"] > 0):
            continue
        if _same_amount(first["quantity"], amount) and _line_text(first.get("unit")) == unit:
            continue
        recorded = _recorded_amounts(cleaned_rows.get(path) or {})
        if not any(_same_amount(a, amount) and u == unit for a, u in recorded):
            changed = [name for name, same in (
                ("quantity", _same_amount(first["quantity"], amount)),
                ("unit", _line_text(first.get("unit")) == unit)) if not same]
            rec.add("AMOUNT_CHANGE_WITHOUT_EVIDENCE",
                    f"{path}: printed {first.get('quantity')} {first.get('unit')}, exported {amount} "
                    f"{row.get('unit')} with no recorded serving column, correction or %DV evidence",
                    ingredient=row.get("name"), stage="blob", row_path=path, field=",".join(changed),
                    source=f"{first.get('quantity')} {first.get('unit')}", exported=f"{amount} {row.get('unit')}")

    # Reuse the exporter's display owner, including legitimate folate and
    # alternate-serving folds. Flutter renders these doses before analysis.
    display_sources = (cleaned or {}).get("display_ingredients") or []
    if display_sources:
        from copy import deepcopy
        from build_final_db import (
            _build_canonical_label_ledger, _reconcile_display_source_rows,
            _fold_probiotic_serving_headers, _fold_general_serving_variants,
        )
        expected_rows = _build_canonical_label_ledger(
            _reconcile_display_source_rows(deepcopy(display_sources)),
            blob.get("ingredients") or [], blob.get("inactive_ingredients") or [],
        )
        expected_rows = _fold_probiotic_serving_headers(enriched or {}, expected_rows)
        expected_rows = _fold_general_serving_variants(enriched or {}, expected_rows)
        actual_by_path = {
            row.get("raw_source_path"): row
            for row in blob.get("display_ingredients") or []
            if isinstance(row, dict) and row.get("raw_source_path")
        }
        for expected in expected_rows:
            path = expected.get("raw_source_path")
            if not path:
                continue
            actual = actual_by_path.get(path)
            if actual is None:
                rec.add("RAW_ACTIVE_MISSING_FROM_BLOB",
                        f"{path}: canonical app label row is missing",
                        ingredient=expected.get("label_display_name"), stage="blob", row_path=path,
                        field="display_ingredients.raw_source_path", source=path)
                continue
            for key in ("exact_dose_text", "parenthetical_dose_text", "display_dose_label",
                        "quantity", "unit", "serving_variants", "folded_label_components"):
                value = expected.get(key)
                equal = (_line_text(value) == _line_text(actual.get(key))
                         if key in ("exact_dose_text", "parenthetical_dose_text", "display_dose_label", "unit")
                         else value == actual.get(key))
                if (value or actual.get(key)) and not equal:
                    rec.add("AMOUNT_CHANGE_WITHOUT_EVIDENCE",
                            f"{path}: app dose differs from the canonical label ledger",
                            ingredient=expected.get("label_display_name"), stage="blob", row_path=path,
                            field=f"display_ingredients.{key}", source=value, exported=actual.get(key))


def _check_export_identity(rec: ProductRecord, enriched: Mapping[str, Any] | None, blob: Mapping[str, Any]) -> None:
    """The enricher's decision for a path is what ships (ADR-0005); needs no raw label."""
    decided: dict[str, set[str]] = collections.defaultdict(set)
    iqd = (enriched or {}).get("ingredient_quality_data") or {}
    for rows in iqd.values():
        for row in rows if isinstance(rows, list) else []:
            if isinstance(row, dict) and row.get("raw_source_path"):
                decided[row["raw_source_path"]].add(str(row.get("canonical_id") or ""))
    # The display ledger row keeps the printed label's identity for the app's
    # ingredient-id union; the enricher's identity is its namespaced analysis.
    exported = [("ingredients", row, row) for row in blob.get("ingredients") or [] if isinstance(row, dict)]
    exported += [
        ("display_ingredients.analysis", row, row["analysis"])
        for row in blob.get("display_ingredients") or []
        if isinstance(row, dict) and isinstance(row.get("analysis"), dict)
    ]
    for key, row, identity in exported:
        path = row.get("raw_source_path")
        if path in decided and str(identity.get("canonical_id") or "") not in decided[path]:
            rec.add("EXPORT_IDENTITY_NOT_FROM_ENRICHER",
                    f"{key} {path}: exported {identity.get('canonical_id')!r}, enricher decided "
                    f"{sorted(decided[path])!r}", ingredient=row.get("name"), stage="blob",
                    row_path=path, field=f"{key}.canonical_id",
                    source=sorted(decided[path]), exported=identity.get("canonical_id"))
    _check_export_normalized_dose(rec, enriched, blob)


def _check_export_normalized_dose(rec: ProductRecord, enriched: Mapping[str, Any] | None,
                                  blob: Mapping[str, Any]) -> None:
    """The enricher's normalized dose for a row is what ships, never a same-name sibling's.

    A row's dose is the entry whose source_field is that row, else the one entry
    with no position under its name; with neither, the dose ships as unknown.
    """
    from build_final_db import safe_float, safe_str

    entries = ((enriched or {}).get("dosage_normalization") or {}).get("normalized_ingredients")
    if not isinstance(entries, list):
        return  # legacy name-keyed artifacts carry no row identity to judge
    entries = [entry for entry in entries if isinstance(entry, dict)]
    own: dict[str, dict] = {}
    for entry in entries:
        if entry.get("source_field"):
            own.setdefault(entry["source_field"], entry)
    actives = (enriched or {}).get("activeIngredients") or []
    index_by_path: dict[str, int] = {}
    for index, row in enumerate(actives):
        if isinstance(row, dict) and row.get("raw_source_path"):
            index_by_path.setdefault(row["raw_source_path"], index)
    for row in blob.get("ingredients") or []:
        path = row.get("raw_source_path") if isinstance(row, dict) else None
        if path not in index_by_path:
            continue
        entry = own.get(f"activeIngredients[{index_by_path[path]}]")
        if entry is None:
            source = actives[index_by_path[path]]
            raw = safe_str(source.get("raw_source_text"))
            entry = {}
            for name in dict.fromkeys((raw, safe_str(source.get("name"), raw))):
                unpositioned = [e for e in entries if name and not e.get("source_field")
                                and e.get("original_name") == name]
                if unpositioned:
                    matching_rows = sum(
                        name in {safe_str(active.get("raw_source_text")), safe_str(active.get("name"))}
                        for active in actives if isinstance(active, dict)
                    )
                    entry = unpositioned[0] if len(unpositioned) == 1 and matching_rows == 1 else {}
                    break
        expected = (safe_float(entry.get("normalized_amount")), safe_str(entry.get("normalized_unit")))
        exported = (row.get("normalized_amount"), row.get("normalized_unit") or "")
        if expected[1] != exported[1] or not (
            expected[0] == exported[0]
            or (expected[0] is not None and exported[0] is not None and _same_amount(expected[0], exported[0]))
        ):
            rec.add("NORMALIZED_DOSE_NOT_FROM_OWN_ROW",
                    f"ingredients {path}: exported {exported[0]} {exported[1]}, its own normalization "
                    f"entry says {expected[0]} {expected[1]}", ingredient=row.get("name"), stage="blob",
                    row_path=path, field="ingredients.normalized_amount",
                    source=f"{expected[0]} {expected[1]}", exported=f"{exported[0]} {exported[1]}")


def audit_product(
    dsld_id: str,
    archetype: str | None,
    blob_dir: Path,
    products_root: Path | None,
    db_path: Path | None,
    stage_index: StageIndex | None,
    excluded_by_gate: Mapping[str, list[str]] | None = None,
    *,
    cleaned_record: dict | None = None,
    raw_record: dict | None = None,
) -> ProductRecord:
    blob = _read_blob(blob_dir, dsld_id)
    if blob is None:
        quarantine_reasons = list((excluded_by_gate or {}).get(dsld_id) or [])
        if quarantine_reasons:
            return ProductRecord(
                dsld_id=dsld_id,
                archetype=archetype,
                product_name=None,
                upc=None,
                stages={
                    "final_destination": {
                        "kind": "quarantined",
                        "reasons": quarantine_reasons,
                    }
                },
                notes=[
                    "No live blob expected: export_manifest records an exact "
                    "excluded_by_gate destination for this product."
                ],
            )
        return ProductRecord(
            dsld_id=dsld_id, archetype=archetype, product_name=None, upc=None,
            findings=[Finding(
                severity=SEVERITY_BLOCKER,
                code="RAW_ACTIVE_MISSING_FROM_BLOB",
                note=f"blob not found at {blob_dir / f'{dsld_id}.json'}",
                row_path="label", field="detail_blob",
            )],
        )

    cleaned = cleaned_record if cleaned_record is not None else (
        stage_index.read(dsld_id) if stage_index else None
    )
    core_row = _read_core_row(db_path, dsld_id) if db_path else None

    rec = ProductRecord(
        dsld_id=dsld_id,
        archetype=archetype,
        product_name=blob.get("product_name"),
        upc=(core_row or {}).get("upc_sku"),
        raw_source_found=cleaned is not None,
    )

    raw_actives = _count_raw_actives_from_cleaned(cleaned) if cleaned else None
    raw_inactives = _count_raw_inactives_from_cleaned(cleaned) if cleaned else None

    rec.stages = {
        "raw": {
            "actives": raw_actives,
            "inactives": raw_inactives,
        } if cleaned else {"note": "cleaned_batch not found in products_root"},
        "blob": {
            "ingredients_count": len(blob.get("ingredients") or []),
            "inactive_ingredients_count": len(blob.get("inactive_ingredients") or []),
            "raw_actives_count": blob.get("raw_actives_count"),
            "raw_inactives_count": blob.get("raw_inactives_count"),
            "drop_reasons": blob.get("ingredients_dropped_reasons") or [],
            "unmapped_actives_total": (blob.get("unmapped_actives") or {}).get("total"),
            "has_proprietary_blends": bool(((blob.get("proprietary_blend_detail") or {}).get("has_proprietary_blends"))),
        },
        "core_db": {
            "row_present": core_row is not None,
            "verdict": (core_row or {}).get("verdict"),
            # v2.0.0: the headline is the v4 /100 score; the legacy /80 column was dropped.
            "quality_score_v4_100": (core_row or {}).get("quality_score_v4_100"),
            "quality_score_status": (core_row or {}).get("quality_score_status"),
            "score_model_version": (core_row or {}).get("score_model_version"),
        },
    }

    # Run all checks. Each one appends Findings to rec.
    _check_drop_reason_enum(rec, blob)
    _check_active_count_reconciliation(rec, blob)
    _check_inactive_recovery(rec, blob)
    _check_unmapped_consistency(rec, blob)
    _check_v1_5_0_contract(rec, blob)
    _check_canonical_id_on_mapped(rec, blob)
    _check_display_label_collapse(rec, blob, raw_record)
    _check_branded_tokens(rec, blob)
    _check_plant_part(rec, blob)
    _check_standardization(rec, blob, cleaned)
    _check_np_leak(rec, blob)
    _check_well_dosed_on_undisclosed(rec, blob)
    _check_unsafe_unit_conversion(rec, blob)
    _check_blend_children(rec, blob)
    _check_core_db_blob_agreement(rec, core_row, blob)
    _check_raw_actives_present_in_blob(rec, cleaned, blob)
    _check_raw_inactives_present_in_blob(rec, cleaned, blob)

    return rec


def _stage_batches(products_root: Path) -> list[tuple[Path, Path]]:
    """(enriched batch, cleaned batch) pairs; approved submissions last, as the build joins them."""
    pairs = []
    for enriched_dir in sorted(products_root.glob("output_*_enriched/enriched")):
        brand_dir = products_root / enriched_dir.parent.name.removesuffix("_enriched")
        for enriched_path in sorted(enriched_dir.glob("enriched_*.json")):
            pairs.append((enriched_path, brand_dir / "cleaned" / enriched_path.name.removeprefix("enriched_")))
    return sorted(pairs, key=lambda pair: "Product_Submissions" in str(pair[0]))


def audit_all_products(
    blob_dir: Path,
    products_root: Path,
    raw_root: Path,
    db_path: Path | None,
    excluded_by_gate: Mapping[str, list[str]],
) -> list[ProductRecord]:
    """Every product with a detail blob, raw label → cleaned → enriched → blob → core row.

    Streams one enriched batch (and its cleaned twin) at a time. A product built
    from an approved submission is audited from that submission, as the build
    joins it last; a submission has no DSLD raw label, so its line checks are
    recorded as not applicable instead of passing silently.
    """
    raw_index = {path.stem: path for path in raw_root.rglob("*.json")}
    batches = _stage_batches(products_root)
    submitted: set[str] = set()
    for enriched_path, _ in batches:
        if "Product_Submissions" in str(enriched_path):
            submitted.update(str(p.get("id") or p.get("dsld_id")) for p in json.loads(enriched_path.read_text()))
    records: list[ProductRecord] = []
    for enriched_path, cleaned_path in batches:
        from_submission = "Product_Submissions" in str(enriched_path)
        enriched_batch = json.loads(enriched_path.read_text())
        cleaned_batch = json.loads(cleaned_path.read_text()) if cleaned_path.exists() else []
        cleaned_by_id = {str(p.get("id") or p.get("dsld_id")): p for p in cleaned_batch if isinstance(p, dict)}
        for enriched in enriched_batch:
            if not isinstance(enriched, dict):
                continue
            dsld_id = str(enriched.get("id") or enriched.get("dsld_id") or "")
            if not dsld_id or (dsld_id in submitted and not from_submission):
                continue
            if not (blob_dir / f"{dsld_id}.json").exists() and dsld_id not in excluded_by_gate:
                continue  # never exported (e.g. the active-count gate); not a row-line question
            raw_record = None
            if not from_submission and dsld_id in raw_index:
                try:
                    raw_record = json.loads(raw_index[dsld_id].read_text())
                except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                    pass  # The independent raw-availability check below reports it.
            rec = audit_product(dsld_id, None, blob_dir, products_root, db_path, None,
                                excluded_by_gate, cleaned_record=cleaned_by_id.get(dsld_id),
                                raw_record=raw_record)
            blob = _read_blob(blob_dir, dsld_id)
            if blob is not None:
                if from_submission or enriched.get("manual_product_provenance"):
                    rec.notes.append("approved submission: no DSLD raw label; raw-row checks not applicable")
                    _check_export_identity(rec, enriched, blob)
                elif dsld_id not in raw_index:
                    rec.add("RAW_LABEL_NOT_FOUND", f"no raw DSLD label {dsld_id}.json under {raw_root}", stage="raw",
                            row_path="label", field="raw_label", exported=f"detail_blobs/{dsld_id}.json")
                else:
                    try:
                        raw = raw_record if raw_record is not None else json.loads(raw_index[dsld_id].read_text())
                    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                        rec.add("RAW_LABEL_UNREADABLE", f"raw DSLD label {raw_index[dsld_id]} under {raw_root} "
                                f"cannot be read: {exc}", stage="raw", row_path="label", field="raw_label",
                                source=str(raw_index[dsld_id]), exported=f"detail_blobs/{dsld_id}.json")
                    else:
                        _check_line_integrity(rec, raw, cleaned_by_id.get(dsld_id), enriched, blob)
            records.append(rec)
        del enriched_batch, cleaned_batch, cleaned_by_id
    audited = {rec.dsld_id for rec in records}
    for blob_path in sorted(blob_dir.glob("*.json")):
        if blob_path.stem not in audited:
            rec = ProductRecord(blob_path.stem, None, None, None)
            rec.add("BLOB_WITHOUT_ENRICHED_RECORD", "exported blob has no enriched record under products-root",
                    stage="blob", row_path="label", field="enriched_record",
                    exported=f"detail_blobs/{blob_path.name}")
            records.append(rec)
    return records


def _summarize(records: list[ProductRecord]) -> dict[str, Any]:
    by_severity: collections.Counter[str] = collections.Counter()
    by_code: collections.Counter[str] = collections.Counter()
    products_with_blocker: list[str] = []
    products_with_high: list[str] = []
    for r in records:
        for f in r.findings:
            by_severity[f.severity] += 1
            by_code[f.code] += 1
        if r.has_blocker():
            products_with_blocker.append(r.dsld_id)
        if any(f.severity == SEVERITY_HIGH for f in r.findings):
            products_with_high.append(r.dsld_id)
    return {
        "products_audited": len(records),
        "products_with_raw_source": sum(1 for r in records if r.raw_source_found),
        "by_severity": dict(by_severity),
        "by_code": dict(by_code),
        "products_with_blocker": sorted(set(products_with_blocker)),
        "products_with_high": sorted(set(products_with_high)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-dir", required=True, type=Path)
    parser.add_argument("--products-root", required=True, type=Path,
                        help="root containing output_*/cleaned/ folders")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--canary", action="store_true",
                        help="audit only the canary archetype set (default if no --ids)")
    parser.add_argument("--ids", nargs="*", default=[],
                        help="explicit DSLD IDs to audit")
    parser.add_argument("--all", action="store_true",
                        help="audit every exported product, with the raw-row line checks")
    parser.add_argument("--raw-root", type=Path, default=None,
                        help="raw DSLD label root for --all (default: dataset_paths.brand_dataset_root)")
    parser.add_argument("--severity-min", default="BLOCKER",
                        choices=["BLOCKER", "HIGH", "MEDIUM", "LOW"],
                        help="exit non-zero if any finding at this severity or higher")
    args = parser.parse_args()

    blob_dir = args.build_dir / "detail_blobs"
    db_path = args.build_dir / "pharmaguide_core.db"
    if not blob_dir.is_dir():
        print(f"ERROR: {blob_dir} missing", file=sys.stderr)
        return 2
    if not args.products_root.is_dir():
        print(f"ERROR: {args.products_root} missing", file=sys.stderr)
        return 2

    excluded_by_gate = _load_excluded_by_gate(args.build_dir)
    if args.all:
        raw_root = args.raw_root or brand_dataset_root()
        if not raw_root.is_dir():
            print(f"ERROR: raw DSLD root {raw_root} missing; the line checks cannot run", file=sys.stderr)
            return 2
        print(f"[raw_to_final] auditing every exported product against {raw_root}", file=sys.stderr)
        records = audit_all_products(blob_dir, args.products_root, raw_root, db_path, excluded_by_gate)
        if not records:
            print("ERROR: no exported products found to audit", file=sys.stderr)
            return 2
        return _report(args, records, products=[r for r in records if _at_or_above(r, args.severity_min)])

    # Pick targets
    if args.ids:
        targets = [(None, did) for did in args.ids]
    else:
        # default: canary
        targets = [(arch, did) for arch, did in _load_current_canary_set().items()]

    print(f"[raw_to_final] auditing {len(targets)} products", file=sys.stderr)

    # Index the products_root so we can find cleaned batches quickly
    stage_index = StageIndex(args.products_root)
    stage_index.build(only_ids={did for _, did in targets})

    records: list[ProductRecord] = []
    for archetype, did in targets:
        rec = audit_product(
            dsld_id=did,
            archetype=archetype,
            blob_dir=blob_dir,
            products_root=args.products_root,
            db_path=db_path,
            stage_index=stage_index,
            excluded_by_gate=excluded_by_gate,
        )
        records.append(rec)
        marker = "X" if rec.has_blocker() else ("!" if any(f.severity == SEVERITY_HIGH for f in rec.findings) else ".")
        print(f"  [{marker}] {did} ({archetype}) — {len(rec.findings)} findings", file=sys.stderr)
    return _report(args, records, products=records)


_THRESHOLD_ORDER = ["LOW", "MEDIUM", "HIGH", "BLOCKER"]


def _at_or_above(rec: ProductRecord, severity_min: str) -> bool:
    floor = _THRESHOLD_ORDER.index(severity_min)
    return any(_THRESHOLD_ORDER.index(f.severity) >= floor for f in rec.findings)


def _report(args: argparse.Namespace, records: list[ProductRecord], products: list[ProductRecord]) -> int:
    report = {
        "schema": "raw_to_final_audit_v1",
        "build_dir": str(args.build_dir),
        "products_root": str(args.products_root),
        "finding_catalog": FINDING_CATALOG,
        "summary": _summarize(records),
        "products": [r.as_dict() for r in products],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2))
    print(f"[raw_to_final] wrote {args.out}", file=sys.stderr)

    # Loud verdict
    s = report["summary"]
    print("\n--- RAW→FINAL AUDIT VERDICT ---")
    print(f"products audited:           {s['products_audited']}")
    print(f"raw source available for:   {s['products_with_raw_source']}/{s['products_audited']}")
    print(f"findings by severity:       {s['by_severity']}")
    print(f"products with BLOCKER:      {s['products_with_blocker'][:50]}")
    print(f"products with HIGH:         {len(s['products_with_high'])}")
    print(f"top finding codes:")
    for code, n in sorted(s["by_code"].items(), key=lambda x: -x[1])[:10]:
        print(f"  {n:5d}  {code}")
    # The candidate holding the JSON report is removed when this gate fails, so
    # the gate log carries every blocking product, row, field and both values.
    for rec in records:
        for f in rec.findings:
            if f.severity == SEVERITY_BLOCKER:
                print(f"BLOCKER {f.code} product={rec.dsld_id} row={f.row_path} field={f.field} "
                      f"source={f.source_value!r} exported={f.exported_value!r}")

    fail_if_any_at_or_above = set(_THRESHOLD_ORDER[_THRESHOLD_ORDER.index(args.severity_min):])
    triggered = sum(s["by_severity"].get(k, 0) for k in fail_if_any_at_or_above)
    return 1 if triggered > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
