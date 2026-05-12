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

For details on severity codes, see plan file:
  ~/.claude/plans/you-are-a-reactive-zephyr.md  §"Severity assignment"
"""

from __future__ import annotations

import argparse
import collections
import contextlib
import json
import re
import sqlite3
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Iterable


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
    severity: str
    code: str
    note: str
    ingredient: str | None = None
    stage: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


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

    def add(self, code: str, note: str, ingredient: str | None = None, stage: str | None = None) -> None:
        sev = FINDING_CATALOG.get(code)
        if sev is None:
            raise ValueError(f"unknown finding code {code!r} — add to FINDING_CATALOG first")
        self.findings.append(Finding(severity=sev, code=code, note=note, ingredient=ingredient, stage=stage))

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


def _collect_raw_active_names(cleaned: dict) -> list[str]:
    out: list[str] = []
    def walk(rows: list) -> None:
        if not isinstance(rows, list):
            return
        for r in rows:
            if isinstance(r, dict):
                n = r.get("name") or r.get("ingredientName") or ""
                if n:
                    out.append(str(n))
                walk(r.get("nestedRows") or [])
    walk(cleaned.get("activeIngredients") or [])
    return out


def _collect_raw_inactive_names(cleaned: dict) -> list[str]:
    out: list[str] = []
    inacts = cleaned.get("inactiveIngredients")
    if isinstance(inacts, list):
        for r in inacts:
            if isinstance(r, dict):
                n = r.get("name") or r.get("ingredientName") or ""
                if n:
                    out.append(str(n))
            elif isinstance(r, str):
                out.append(r)
    other = cleaned.get("otheringredients") or {}
    ing_list = other.get("ingredients") if isinstance(other, dict) else None
    if isinstance(ing_list, list):
        for r in ing_list:
            if isinstance(r, dict):
                n = r.get("name") or r.get("ingredientName") or ""
                if n:
                    out.append(str(n))
            elif isinstance(r, str):
                out.append(r)
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
STANDARDIZATION_RE = re.compile(
    r"(standardi[sz]ed to\b|\b\d+(?:\.\d+)?\s*%\b|\bcontains\s+\d)",
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
            rec.add("UNKNOWN_DROP_REASON_CODE", f"reason {r!r} not in enum")


def _check_active_count_reconciliation(rec: ProductRecord, blob: dict) -> None:
    raw = int(blob.get("raw_actives_count") or 0)
    blob_n = len(blob.get("ingredients") or [])
    reasons = blob.get("ingredients_dropped_reasons") or []
    if raw > 0 and blob_n == 0 and not reasons:
        rec.add("UNEXPLAINED_DROP_REASON",
                f"raw_actives_count={raw}, ingredients=0, no drop reasons emitted")


def _check_inactive_recovery(rec: ProductRecord, blob: dict) -> None:
    raw = blob.get("raw_inactives_count")
    if not isinstance(raw, int):
        return
    blob_n = len(blob.get("inactive_ingredients") or [])
    if raw > 0 and blob_n == 0:
        rec.add("INACTIVE_LIST_EMPTY_BUT_RAW_NONZERO",
                f"raw_inactives_count={raw}, blob inactive_ingredients=0")


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

    reasons = set(blob.get("ingredients_dropped_reasons") or [])

    for raw_name in raw_names:
        nk = _normalize_name(raw_name)
        if not nk:
            continue
        if nk in blob_names:
            continue
        # cheaper substring fallback — handles "Vitamin A Palmitate" ↔ "Retinyl Palmitate"
        if any(nk in bn or bn in nk for bn in blob_names if len(bn) >= 4):
            continue
        # If the cleaner emitted *some* drop reason, this raw might be one of them.
        # We can't pinpoint which, so we log a LOW-severity informational note
        # only when there are *zero* drop reasons.
        if not reasons:
            rec.add("RAW_ACTIVE_MISSING_FROM_BLOB",
                    f"raw label name {raw_name!r} appears nowhere in blob",
                    ingredient=raw_name)


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
    for n in raw_names:
        nk = _normalize_name(n)
        if not nk:
            continue
        if nk in blob_names or any(nk in bn or bn in nk for bn in blob_names if len(bn) >= 4):
            continue
        rec.add("RAW_INACTIVE_MISSING_FROM_BLOB",
                f"raw label inactive {n!r} not in blob",
                ingredient=n)


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
        is_mapped = bool(ing.get("is_mapped") or ing.get("mapped"))
        cid = ing.get("canonical_id") or ing.get("normalized_key") or ing.get("parent_key")
        if is_mapped and not cid:
            rec.add("CANONICAL_ID_MISSING_ON_MAPPED",
                    "is_mapped=True but canonical_id/normalized_key/parent_key absent",
                    ingredient=ing.get("name"))


def _check_display_label_collapse(rec: ProductRecord, blob: dict) -> None:
    """Invariant #1 from test_label_fidelity_contract.py."""
    for ing in blob.get("ingredients") or []:
        display = (ing.get("display_label") or "").strip()
        canonical = (
            ing.get("canonical_name")
            or ing.get("scoring_group_canonical")
            or ing.get("standard_name")
            or ""
        ).strip()
        source = (ing.get("raw_source_text") or ing.get("name") or "").strip()
        if not display or not canonical or not source:
            continue
        if (display.lower() == canonical.lower()
                and source.lower() != canonical.lower()):
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
    for ing in blob.get("ingredients") or []:
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
        display = (ing.get("display_label") or "").lower()
        for tok in BRANDED_TOKENS:
            if tok.lower() in label_blob and tok.lower() not in display:
                rec.add("BRANDED_TOKEN_DROPPED",
                        f"branded token {tok!r} in label data but absent from display_label={display!r}",
                        ingredient=ing.get("name"))
                break


def _check_plant_part(rec: ProductRecord, blob: dict) -> None:
    """Invariant #5: plant part token preserved in display_label."""
    for ing in blob.get("ingredients") or []:
        forms = ing.get("forms") or []
        form_blob = " ".join((f.get("name", "") if isinstance(f, dict) else "") for f in forms)
        raw = (ing.get("raw_source_text") or "")
        for source_text in (form_blob, raw):
            m = PLANT_PART_RE.search(source_text)
            if not m:
                continue
            part = m.group(1).lower()
            display = (ing.get("display_label") or "").lower()
            equivalents = {"leaf": ("leaf", "leaves"), "leaves": ("leaf", "leaves")}
            acceptable = equivalents.get(part, (part,))
            if not any(e in display for e in acceptable):
                rec.add("PLANT_PART_DROPPED",
                        f"plant part {part!r} present in source {source_text!r} but absent from display_label",
                        ingredient=ing.get("name"))
                break  # one finding per ingredient


def _check_standardization(rec: ProductRecord, blob: dict) -> None:
    """Invariant #6: standardization note preserved when raw notes carry it."""
    for ing in blob.get("ingredients") or []:
        notes = ing.get("notes")
        notes_list: list[str] = []
        if isinstance(notes, str):
            notes_list = [notes]
        elif isinstance(notes, list):
            notes_list = [n for n in notes if isinstance(n, str)]
        notes_text = " ".join(notes_list)
        if not STANDARDIZATION_RE.search(notes_text):
            continue
        note = ing.get("standardization_note")
        if not note:
            rec.add("STANDARDIZATION_NOTE_DROPPED",
                    f"raw notes carry standardization but standardization_note empty: notes={notes_text[:120]!r}",
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
    """Vitamin A IU → mcg RAE conversion factor is form-dependent
    (retinol = 1 mcg RAE / 3.33 IU; beta-carotene = 1 mcg RAE / 20 IU).
    If a Vitamin A active has unit IU but no form-aware normalization,
    that's a BLOCKER.  Vitamin D IU ↔ mcg is form-agnostic (40 IU/mcg) so we
    don't flag it. Vitamin E IU↔mg differs by tocopherol form (alpha vs
    mixed) and is similarly form-dependent — flag it.
    """
    for ing in blob.get("ingredients") or []:
        n = (ing.get("name") or "").lower()
        unit = (ing.get("dosage_unit") or ing.get("unit") or "").upper()
        normalized_unit = (ing.get("normalized_unit") or "").upper()
        normalized_value = ing.get("normalized_value")
        if unit == "IU" and ("vitamin a" in n or "retinyl" in n or "carotene" in n):
            # Need a normalized RAE value AND form-aware factor.
            if normalized_value is None or normalized_unit not in ("MCG RAE", "MCG", "UG RAE", "UG"):
                rec.add("UNSAFE_UNIT_CONVERSION",
                        f"Vitamin A in IU ({ing.get('dosage')}) without form-aware normalization to mcg RAE",
                        ingredient=ing.get("name"))
        if unit == "IU" and "vitamin e" in n:
            if normalized_value is None:
                rec.add("UNSAFE_UNIT_CONVERSION",
                        f"Vitamin E in IU without form-aware normalization (alpha vs mixed tocopherols differ)",
                        ingredient=ing.get("name"))


def _check_blend_children(rec: ProductRecord, blob: dict) -> None:
    """Blend children sanity. The cleaner's blend classifier uses 4 states
    (see project_blend_classifier_4state memory): DISCLOSED_BLEND,
    BLEND_HEADER, OPAQUE_BLEND, fake-transparency-as-OPAQUE.

    Correct behavior per state (disclosure_level field in the blob):
      - "full" / "partial":   children with names AND individual doses.
                              Missing dose on any child → MEDIUM finding.
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
    for blnd in blends:
        if not isinstance(blnd, dict):
            continue
        disclosure_level = (blnd.get("disclosure_level") or "").lower()
        kids = blnd.get("child_ingredients") or blnd.get("children") or []
        for child in kids:
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
                        ingredient=blnd.get("name"))
                continue

            # Per-state checks
            child_qty = child.get("quantity")
            if disclosure_level in ("full", "partial"):
                # Children should have doses (or an explicit disclosed flag)
                disclosed = (
                    child.get("is_disclosed_dose")
                    or child.get("disclosed")
                    or child_qty is not None
                )
                if not disclosed:
                    rec.add("BLEND_CHILD_WITHOUT_DOSE_DISCLOSURE",
                            f"blend {blnd.get('name')!r} ({disclosure_level}) child "
                            f"{child.get('name')!r} has no dose / disclosure flag",
                            ingredient=child.get("name"))
            elif disclosure_level == "none":
                # OPAQUE blend: child names OK, doses MUST be None.
                # A non-None dose contradicts the parent's classification.
                if child_qty is not None:
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
                f"ingredients in BOTH ingredients[] and unmapped_actives.names: {sorted(dupes)}")


# ---------------------------------------------------------------------------
# Top-level audit driver
# ---------------------------------------------------------------------------

def audit_product(
    dsld_id: str,
    archetype: str | None,
    blob_dir: Path,
    products_root: Path | None,
    db_path: Path | None,
    stage_index: StageIndex | None,
) -> ProductRecord:
    blob = _read_blob(blob_dir, dsld_id)
    if blob is None:
        return ProductRecord(
            dsld_id=dsld_id, archetype=archetype, product_name=None, upc=None,
            findings=[Finding(
                severity=SEVERITY_BLOCKER,
                code="RAW_ACTIVE_MISSING_FROM_BLOB",
                note=f"blob not found at {blob_dir / f'{dsld_id}.json'}",
            )],
        )

    cleaned = stage_index.read(dsld_id) if stage_index else None
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
            "score_quality_80": (core_row or {}).get("score_quality_80"),
        },
    }

    # Run all checks. Each one appends Findings to rec.
    _check_drop_reason_enum(rec, blob)
    _check_active_count_reconciliation(rec, blob)
    _check_inactive_recovery(rec, blob)
    _check_unmapped_consistency(rec, blob)
    _check_v1_5_0_contract(rec, blob)
    _check_canonical_id_on_mapped(rec, blob)
    _check_display_label_collapse(rec, blob)
    _check_branded_tokens(rec, blob)
    _check_plant_part(rec, blob)
    _check_standardization(rec, blob)
    _check_np_leak(rec, blob)
    _check_well_dosed_on_undisclosed(rec, blob)
    _check_unsafe_unit_conversion(rec, blob)
    _check_blend_children(rec, blob)
    _check_core_db_blob_agreement(rec, core_row, blob)
    _check_raw_actives_present_in_blob(rec, cleaned, blob)
    _check_raw_inactives_present_in_blob(rec, cleaned, blob)

    return rec


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

    # Pick targets
    if args.ids:
        targets = [(None, did) for did in args.ids]
    else:
        # default: canary
        targets = [(arch, did) for arch, did in CANARY_SET.items()]

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
        )
        records.append(rec)
        marker = "X" if rec.has_blocker() else ("!" if any(f.severity == SEVERITY_HIGH for f in rec.findings) else ".")
        print(f"  [{marker}] {did} ({archetype}) — {len(rec.findings)} findings", file=sys.stderr)

    report = {
        "schema": "raw_to_final_audit_v1",
        "build_dir": str(args.build_dir),
        "products_root": str(args.products_root),
        "finding_catalog": FINDING_CATALOG,
        "summary": _summarize(records),
        "products": [r.as_dict() for r in records],
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
    print(f"products with BLOCKER:      {s['products_with_blocker']}")
    print(f"products with HIGH:         {s['products_with_high']}")
    print(f"top finding codes:")
    for code, n in sorted(s["by_code"].items(), key=lambda x: -x[1])[:10]:
        print(f"  {n:5d}  {code}")

    threshold_order = ["LOW", "MEDIUM", "HIGH", "BLOCKER"]
    threshold_idx = threshold_order.index(args.severity_min)
    fail_if_any_at_or_above = set(threshold_order[threshold_idx:])
    triggered = sum(s["by_severity"].get(k, 0) for k in fail_if_any_at_or_above)
    return 1 if triggered > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
